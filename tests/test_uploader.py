import json
import re

import httpx
import pytest

from unitlab import (
    AuthenticationError,
    PermissionDeniedError,
    ProcessingTimeoutError,
    UnitlabClient,
    _uploader,
    tiles_from_template,
)
from unitlab.resources.assets import Asset
from unitlab.resources.projects import BatchQueue, Project


@pytest.mark.parametrize(
    ("filename", "generic_type"),
    (("page.html", "html"), ("page.htm", "html"), ("series.csv", "timeseries")),
)
def test_html_and_timeseries_files_are_uploadable(tmp_path, filename, generic_type):
    path = tmp_path / filename
    path.write_bytes(b"content")

    assert _uploader.detect_generic_type(filename) == generic_type
    assert _uploader.collect_files(path) == [path]


def configured_client(handler, monkeypatch=None):
    """A client whose requests reach ``handler``; storage PUTs too with monkeypatch."""
    transport = httpx.MockTransport(handler)
    if monkeypatch is not None:
        native_async_client = httpx.AsyncClient

        def storage_client(*args, **kwargs):
            kwargs.setdefault("transport", transport)
            return native_async_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", storage_client)
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    client._api.client.close()
    client._api.client = httpx.Client(
        base_url="http://testserver",
        headers={"Authorization": "Api-Key key"},
        transport=transport,
    )

    def async_client(*, timeout=600.0):
        return httpx.AsyncClient(
            base_url="http://testserver",
            headers={"Authorization": "Api-Key key"},
            transport=transport,
            timeout=timeout,
        )

    client._api.async_client = async_client
    return client


def test_empty_httpx_errors_get_a_readable_message():
    from unitlab._http import error_text

    assert error_text(httpx.ReadTimeout("")) == (
        "ReadTimeout: no answer before the request timed out"
    )
    assert error_text(httpx.RemoteProtocolError("")).startswith(
        "RemoteProtocolError: the connection closed"
    )
    assert error_text(httpx.ConnectError("refused")) == "refused"


def test_upload_reports_dropped_connections_and_caps_files_in_flight(tmp_path):
    import asyncio

    for index in range(5):
        (tmp_path / f"img{index}.png").write_bytes(b"png")
    in_flight = peak = 0

    def info(request):
        return httpx.Response(
            200,
            json={
                "accepted_formats": ["png"],
                "max_file_sizes": {"img": 1_000_000},
                "max_file_size": 1_000_000,
                "generic_type": None,
            },
        )

    async def upload(request):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        if b'filename="img0.png"' in request.content:
            # What a restarting server does: httpx raises with no message.
            raise httpx.RemoteProtocolError("")
        return httpx.Response(201, json={"datasource_id": "ds", "generic_type": "img"})

    client = UnitlabClient(api_key="key", api_url="http://testserver")
    client._api.client.close()
    client._api.client = httpx.Client(
        base_url="http://testserver", transport=httpx.MockTransport(info)
    )
    client._api.async_client = lambda *, timeout=600.0: httpx.AsyncClient(
        base_url="http://testserver", transport=httpx.MockTransport(upload)
    )
    project = Project(id="project-id", name="Images", raw={}, _client=client)
    batch = project.upload(tmp_path, max_concurrent_uploads=2)
    assert peak == 2
    assert batch.uploaded == 4
    assert [failure.path.name for failure in batch.failed] == ["img0.png"]
    assert "connection closed" in batch.failed[0].error
    assert "missing datasource_id" not in batch.failed[0].error
    client.close()


def test_project_upload_uses_one_batch_queue_and_chunks(tmp_path):
    session_ids = []
    uploads = 0

    def handler(request):
        nonlocal uploads
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["png"],
                    "max_file_sizes": {"img": 1_000_000},
                    "max_file_size": 1_000_000,
                    "generic_type": None,
                },
            )
        uploads += 1
        body = request.content.decode("latin1")
        match = re.search(r'name="session_id"\r\n\r\n([^\r]+)', body)
        assert match
        session_ids.append(match.group(1))
        return httpx.Response(
            201,
            json={
                "datasource_id": f"ds-{uploads}",
                "upload_session_id": match.group(1),
                "generic_type": "img",
            },
        )

    for index in range(21):
        (tmp_path / f"{index:02}.png").write_bytes(b"png")
    client = configured_client(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)
    batch = project.upload(tmp_path)
    assert batch.total == 21
    assert batch.uploaded == 21
    assert len(batch.data_item_ids) == 21
    assert len(set(session_ids)) == 1
    assert batch.batch_queue_id == session_ids[0]
    client.close()


def test_project_upload_can_select_tabular_csv_row_mode(tmp_path):
    upload_body = ""

    def handler(request):
        nonlocal upload_body
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["csv"],
                    "max_file_sizes": {"timeseries": 1_000, "tabular": 1_000},
                    "generic_type": None,
                },
            )
        upload_body = request.content.decode("latin1")
        return httpx.Response(
            202,
            json={
                "datasource_id": "row-1",
                "upload_session_id": "queue-1",
                "generic_type": "tabular",
                "upload_status": "processing",
                "task_id": "tabular-task-1",
            },
        )

    path = tmp_path / "feedback.csv"
    path.write_text("id,comment\n1,Great product\n")
    client = configured_client(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)

    batch = project.upload(path, generic_type="tabular", primary_column="comment")

    assert batch.uploaded == 1
    assert batch.raw[0]["upload_status"] == "processing"
    assert batch.raw[0]["task_id"] == "tabular-task-1"
    assert 'name="generic_type"' in upload_body
    assert "tabular" in upload_body
    assert 'name="primary_column"' in upload_body
    assert "comment" in upload_body
    client.close()


def test_project_upload_reports_oversized_files(tmp_path):
    uploads = 0

    def handler(request):
        nonlocal uploads
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["png"],
                    "max_file_sizes": {"img": 2},
                    "generic_type": None,
                },
            )
        uploads += 1
        return httpx.Response(
            201,
            json={
                "datasource_id": "item-1",
                "upload_session_id": "queue-1",
                "generic_type": "img",
            },
        )

    (tmp_path / "small.png").write_bytes(b"ok")
    (tmp_path / "large.png").write_bytes(b"too large")
    client = configured_client(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)
    batch = project.upload(tmp_path)

    assert uploads == 1
    assert batch.total == 2
    assert batch.uploaded == 1
    assert [failure.path.name for failure in batch.failed] == ["large.png"]
    client.close()


def test_project_upload_does_not_retry_non_idempotent_file_post(tmp_path):
    attempts = {"good.png": 0, "bad.png": 0}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["png"],
                    "max_file_sizes": {"img": 1_000},
                    "generic_type": None,
                },
            )
        body = request.content.decode("latin1")
        name = "bad.png" if "bad.png" in body else "good.png"
        attempts[name] += 1
        if name == "bad.png":
            return httpx.Response(503, json={"detail": "Try again"})
        return httpx.Response(
            201,
            json={
                "datasource_id": "item-good",
                "upload_session_id": "queue-1",
                "generic_type": "img",
            },
        )

    (tmp_path / "good.png").write_bytes(b"ok")
    (tmp_path / "bad.png").write_bytes(b"bad")
    client = configured_client(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)
    batch = project.upload(tmp_path)

    assert batch.total == 2
    assert batch.uploaded == 1
    assert [failure.path.name for failure in batch.failed] == ["bad.png"]
    assert attempts == {"good.png": 1, "bad.png": 1}
    client.close()


def test_medical_finalize_retries_transient_failures(monkeypatch, tmp_path):
    finalize_attempts = 0

    async def no_sleep(_delay):
        return None

    def handler(request):
        nonlocal finalize_attempts
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["dcm"],
                    "max_file_sizes": {"medical": 1_000},
                    "generic_type": None,
                },
            )
        if request.url.path.endswith("/finalize/"):
            finalize_attempts += 1
            return httpx.Response(
                503 if finalize_attempts < 3 else 200,
                json={"detail": "Try again"} if finalize_attempts < 3 else {},
            )
        return httpx.Response(
            201,
            json={
                "datasource_id": "medical-source",
                "upload_session_id": "queue-1",
                "generic_type": "medical",
            },
        )

    monkeypatch.setattr("unitlab._uploader.asyncio.sleep", no_sleep)
    (tmp_path / "scan.dcm").write_bytes(b"dicom")
    client = configured_client(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)
    batch = project.upload(tmp_path)

    assert batch.uploaded == 1
    assert finalize_attempts == 3
    client.close()


def test_project_upload_treats_skipped_response_as_failure(tmp_path):
    finalize_calls = 0

    def handler(request):
        nonlocal finalize_calls
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["dcm"],
                    "max_file_sizes": {"medical": 1_000},
                    "generic_type": None,
                },
            )
        if request.url.path.endswith("/finalize/"):
            finalize_calls += 1
            return httpx.Response(200, json={})
        if b"skip.dcm" in request.content:
            return httpx.Response(
                200,
                json={
                    "skipped": True,
                    "message": "Unsupported non-image SOP class",
                },
            )
        return httpx.Response(
            201,
            json={
                "datasource_id": "medical-source",
                "upload_session_id": "queue-1",
                "generic_type": "medical",
            },
        )

    (tmp_path / "scan.dcm").write_bytes(b"dicom")
    (tmp_path / "skip.dcm").write_bytes(b"dicom")
    client = configured_client(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)

    batch = project.upload(tmp_path)

    assert batch.total == 2
    assert batch.uploaded == 1
    assert [failure.path.name for failure in batch.failed] == ["skip.dcm"]
    assert len(batch.raw) == 1
    assert finalize_calls == 1
    client.close()


def test_asset_upload_resolves_folder_once_then_reuses_id(tmp_path):
    bodies = []

    def handler(request):
        bodies.append(request.content.decode("latin1"))
        index = len(bodies)
        return httpx.Response(
            201,
            json={
                "folder_id": "folder-1",
                "folder_name": "Raw data",
                "asset": {
                    "pk": f"asset-{index}",
                    "file_name": f"{index}.png",
                    "generic_type": "img",
                    "folder_id": "folder-1",
                    "custom_metadata": {"region": "CA-BC"},
                },
            },
        )

    for index in range(3):
        (tmp_path / f"{index}.png").write_bytes(b"png")
    client = configured_client(handler)
    result = client.assets.upload(
        tmp_path,
        folder="Raw data",
        tags=["review"],
        custom_metadata={"region": "CA-BC"},
    )
    assert result.folder_id == "folder-1"
    assert result.uploaded == 3
    assert len(result.assets) == 3
    assert 'name="folder_name"' in bodies[0]
    assert 'name="folder_id"' not in bodies[0]
    assert all('name="folder_id"' in body for body in bodies[1:])
    assert all("folder-1" in body for body in bodies[1:])
    assert all('name="custom_metadata"' in body for body in bodies)
    assert all('{"region":"CA-BC"}' in body for body in bodies)
    assert result.assets[0].custom_metadata == {"region": "CA-BC"}
    client.close()


def test_asset_upload_can_select_tabular_csv_row_mode(tmp_path):
    upload_body = ""

    def handler(request):
        nonlocal upload_body
        upload_body = request.content.decode("latin1")
        return httpx.Response(
            201,
            json={
                "folder_id": "folder-1",
                "folder_name": "Feedback",
                "asset": {
                    "pk": "asset-1",
                    "file_name": "feedback.csv",
                    "generic_type": "tabular",
                    "folder_id": "folder-1",
                },
            },
        )

    path = tmp_path / "feedback.csv"
    path.write_text("id,comment\n1,Great product\n")
    client = configured_client(handler)

    result = client.assets.upload(
        path,
        folder="Feedback",
        generic_type="tabular",
        primary_column="comment",
    )

    assert result.uploaded == 1
    assert 'name="generic_type"' in upload_body
    assert "tabular" in upload_body
    assert 'name="primary_column"' in upload_body
    assert "comment" in upload_body
    client.close()


def test_deferred_timeseries_upload_can_be_completed(tmp_path):
    upload_body = ""

    def handler(request):
        nonlocal upload_body
        if request.url.path == "/api/sdk/data-assets/upload/":
            upload_body = request.content.decode("latin1")
            return httpx.Response(
                202,
                json={
                    "folder_id": "folder-1",
                    "folder_name": "Charts",
                    "timeseries_configuration_required": True,
                    "configuration": {
                        "columns": ["time", "value"],
                        "defaults": {"x_column": "time", "channels": ["value"]},
                    },
                    "asset": {
                        "pk": "asset-1",
                        "file_name": "chart.csv",
                        "generic_type": "timeseries",
                        "folder_id": "folder-1",
                        "upload_status": "processing",
                    },
                },
            )
        assert request.url.path == (
            "/api/sdk/data-assets/assets/asset-1/timeseries-configuration/"
        )
        assert json.loads(request.content) == {
            "x_column": "time",
            "channels": ["value"],
        }
        return httpx.Response(
            200,
            json={
                "asset_id": "asset-1",
                "upload_status": "completed",
                "timeseries_configuration_required": False,
                "configuration": None,
                "timeseries": {"x_column": "time", "channels": ["value"]},
            },
        )

    path = tmp_path / "chart.csv"
    path.write_text("time,value\n0,1\n1,2\n")
    client = configured_client(handler)

    result = client.assets.upload(
        path,
        folder="Charts",
        defer_timeseries_configuration=True,
    )
    assert 'name="defer_timeseries_configuration"' in upload_body
    assert "true" in upload_body
    assert result.raw[0]["configuration"]["defaults"]["x_column"] == "time"
    asset = result.assets[0]

    configuration = asset.configure_timeseries(
        x_column="time",
        channels=["value"],
    )

    assert configuration["timeseries_configuration_required"] is False
    assert asset.upload_status == "completed"
    client.close()


def test_asset_updates_custom_metadata():
    def handler(request):
        assert request.method == "PATCH"
        assert request.url.path == (
            "/api/sdk/data-assets/assets/asset-1/custom-metadata/"
        )
        assert json.loads(request.content) == {
            "custom_metadata": {"camera": {"settings": ["night"]}}
        }
        return httpx.Response(
            200,
            json={
                "asset": {
                    "pk": "asset-1",
                    "file_name": "image.png",
                    "generic_type": "img",
                    "custom_metadata": {"camera": {"settings": ["night"]}},
                }
            },
        )

    client = configured_client(handler)
    asset = Asset._from_raw(
        client,
        {
            "pk": "asset-1",
            "file_name": "image.png",
            "generic_type": "img",
        },
    )

    result = asset.update_custom_metadata({"camera": {"settings": ["night"]}})

    assert result is asset
    assert asset.custom_metadata == {"camera": {"settings": ["night"]}}
    client.close()


def test_asset_custom_metadata_can_be_null():
    def handler(request):
        assert json.loads(request.content) == {"custom_metadata": None}
        return httpx.Response(
            200,
            json={
                "asset": {
                    "pk": "asset-1",
                    "file_name": "image.png",
                    "generic_type": "img",
                    "custom_metadata": None,
                }
            },
        )

    client = configured_client(handler)
    asset = Asset._from_raw(
        client,
        {
            "pk": "asset-1",
            "file_name": "image.png",
            "generic_type": "img",
            "custom_metadata": None,
        },
    )

    result = asset.update_custom_metadata(None)

    assert result is asset
    assert asset.custom_metadata is None
    client.close()


def test_asset_upload_reports_missing_folder_id_instead_of_crashing(tmp_path):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(201, json={"asset": {"pk": "unusable"}})
        return httpx.Response(
            201,
            json={
                "folder_id": "folder-1",
                "folder_name": "Raw data",
                "asset": {
                    "pk": "asset-2",
                    "file_name": "2.png",
                    "generic_type": "img",
                    "folder_id": "folder-1",
                },
            },
        )

    (tmp_path / "1.png").write_bytes(b"png")
    (tmp_path / "2.png").write_bytes(b"png")
    client = configured_client(handler)
    result = client.assets.upload(
        tmp_path,
        folder="Raw data",
    )

    assert result.uploaded == 1
    assert result.folder_id == "folder-1"
    assert result.failed[0].error == "Unexpected response: missing folder_id"
    client.close()


def test_asset_upload_rejects_later_response_without_asset(tmp_path):
    def handler(request):
        if b"bad.png" in request.content:
            return httpx.Response(201, json={"folder_id": "folder-1"})
        return httpx.Response(
            201,
            json={
                "folder_id": "folder-1",
                "folder_name": "Raw data",
                "asset": {
                    "pk": "asset-1",
                    "file_name": "good.png",
                    "generic_type": "img",
                    "folder_id": "folder-1",
                },
            },
        )

    (tmp_path / "bad.png").write_bytes(b"bad")
    (tmp_path / "good.png").write_bytes(b"good")
    client = configured_client(handler)

    result = client.assets.upload(tmp_path, folder_id="folder-1")

    assert result.uploaded == 1
    assert [asset.file_name for asset in result.assets] == ["good.png"]
    assert [failure.error for failure in result.failed] == [
        "Unexpected response: missing asset"
    ]
    client.close()


def test_waiter_and_grouping_template(monkeypatch, capsys):
    polls = 0

    def handler(request):
        nonlocal polls
        polls += 1
        processing = 1 if polls == 1 else 0
        return httpx.Response(
            200,
            json={
                "status": "processing" if processing else "completed",
                "total": 1,
                "completed": 1 - processing,
                "processing": processing,
                "failed": 0,
            },
        )

    monkeypatch.setattr("unitlab._waiter.time.sleep", lambda _delay: None)
    client = configured_client(handler)
    queue = BatchQueue._from_raw(
        client,
        "p1",
        {
            "pk": "q1",
            "name": "Batch Queue",
            "created": "",
            "item_count": 1,
            "data_type_counts": {},
        },
    )
    status = queue.wait(show_progress=True)
    assert status.status == "completed"
    assert polls == 2
    assert capsys.readouterr().err == ""

    config = tiles_from_template(
        "{patient_id}_{view}",
        {"view": ["L_CC", "R_CC"]},
    )
    assert config["grouping_keys"] == ["patient_id"]
    assert [tile["tile_id"] for tile in config["tiles"]] == ["l_cc", "r_cc"]
    assert config["tiles"][0]["match_rule"] == (r"^(?P<patient_id>.+?)_L_CC(?:\..*)?$")
    assert config["minimum_matched_tiles"] == 1
    assert config["required_tiles"] == []
    client.close()


def test_waiter_bounds_status_requests_by_deadline():
    request_timeouts = []

    def handler(request):
        request_timeouts.append(request.extensions["timeout"])
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "total": 1,
                "completed": 1,
                "processing": 0,
                "failed": 0,
            },
        )

    client = configured_client(handler)
    queue = BatchQueue._from_raw(
        client,
        "p1",
        {
            "pk": "q1",
            "name": "Batch Queue",
            "created": "",
            "item_count": 1,
            "data_type_counts": {},
        },
    )

    queue.wait(timeout=0.5, show_progress=False)
    assert request_timeouts
    assert max(request_timeouts[0].values()) <= 0.5

    with pytest.raises(ProcessingTimeoutError):
        queue.wait(timeout=0, show_progress=False)
    assert len(request_timeouts) == 1
    client.close()


def test_batch_queue_uses_public_data_names():
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "datasource_id": "item-1",
                        "file_name": "scan.png",
                        "generic_type": "img",
                        "upload_status": "completed",
                    }
                ],
                "next": None,
            },
        )

    client = configured_client(handler)
    queue = BatchQueue._from_raw(
        client,
        "project-1",
        {
            "pk": "queue-1",
            "name": "Batch Queue 1",
            "created": "2026-07-12T00:00:00Z",
            "item_count": 2,
            "data_type_counts": {"img": 1, "video": 1},
            "status": "processing",
            "completed": 1,
            "processing": 1,
            "failed": 0,
        },
    )

    assert queue.data_type_counts == {"image": 1, "video": 1}
    assert queue.state == "processing"
    assert queue.completed == 1
    assert queue.data() == [
        {
            "id": "item-1",
            "file_name": "scan.png",
            "data_type": "image",
            "status": "completed",
        }
    ]
    client.close()


def test_asset_upload_preserves_authentication_error(tmp_path):
    (tmp_path / "scan.png").write_bytes(b"png")

    def handler(request):
        return httpx.Response(401, json={"detail": "Invalid API key"}, request=request)

    client = configured_client(handler)
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client.assets.upload(tmp_path)
    client.close()


# --- Direct form uploads (SDK 3.2.1) ---
#
# A server with STORAGE_DIRECT_UPLOADS says so in project `upload-info`
# (`direct_uploads`); the library has no upload-info, so asset uploads probe the
# initiate route once per run. Each form-path file is then PUT straight into
# storage and `complete` runs the server's form code on it.

PROJECT_INFO = {
    "accepted_formats": ["png"],
    "max_file_sizes": {"img": 1_000_000},
    "max_file_size": 1_000_000,
    "generic_type": None,
}


def _form_fields(request):
    """Multipart fields of a request as {name: [values]}; asserts no file part."""
    body = request.content.decode("latin1")
    assert "filename=" not in body
    fields = {}
    for name, value in re.findall(r'name="([^"]+)"\r\n\r\n(.*?)\r\n--', body, re.S):
        fields.setdefault(name, []).append(value)
    return fields


def _ticket(index, *, id_key="datasource_id"):
    return {
        "upload_token": f"token-{index}",
        id_key: f"id-{index}",
        "upload_id": f"upload-{index}",
        "part_size": 64 * 1024 * 1024,
        "part_urls": [{"part_number": 1, "url": f"https://storage.test/part-{index}"}],
        "expires_in": 3600,
    }


def _no_sleep(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(_uploader.asyncio, "sleep", no_sleep)


def test_direct_when_server_advertises(monkeypatch, tmp_path):
    for index in range(3):
        (tmp_path / f"{index}.png").write_bytes(b"png%d" % index)
    initiates, puts, completes, posts = [], {}, [], []

    def handler(request):
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if path == "/api/sdk/projects/p1/direct-uploads/initiate/":
            initiates.append(json.loads(request.content))
            return httpx.Response(200, json={"uploads": [_ticket(i) for i in range(3)]})
        if request.url.host == "storage.test":
            assert request.method == "PUT"
            assert "authorization" not in request.headers
            puts[path] = request.content
            return httpx.Response(200, headers={"ETag": f'"etag-{path[-1]}"'})
        if path == "/api/sdk/projects/p1/direct-uploads/complete/":
            assert request.headers["content-type"].startswith("multipart/form-data")
            fields = _form_fields(request)
            completes.append(fields)
            index = fields["upload_token"][0][-1]
            return httpx.Response(
                201,
                json={
                    "datasource_id": f"id-{index}",
                    "upload_session_id": fields["session_id"][0],
                    "generic_type": "img",
                },
            )
        posts.append(path)
        raise AssertionError(path)

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert initiates == [
        {
            "files": [{"file_name": f"{i}.png", "file_size": 4} for i in range(3)],
            "single_put": True,
        }
    ]
    assert puts == {f"/part-{i}": b"png%d" % i for i in range(3)}
    assert sorted(fields["upload_token"][0] for fields in completes) == [
        "token-0",
        "token-1",
        "token-2",
    ]
    for fields in completes:
        index = fields["upload_token"][0][-1]
        assert json.loads(fields["parts"][0]) == [
            {"part_number": 1, "etag": f"etag-{index}"}
        ]
        assert fields["session_id"] == [batch.batch_queue_id]
    assert posts == []
    assert batch.uploaded == 3
    assert sorted(batch.data_item_ids) == ["id-0", "id-1", "id-2"]
    client.close()


def test_direct_single_put_sends_the_signed_headers(monkeypatch, tmp_path):
    # A one-part file's URL signs the object's type and cache (server
    # tiled_upload_views._single_put_url): the PUT must carry them.
    (tmp_path / "a.png").write_bytes(b"png")
    headers = {
        "Content-Type": "image/png",
        "Cache-Control": "max-age=86400",
        "If-None-Match": "*",
    }
    ticket = _ticket(0)
    ticket["part_urls"][0]["headers"] = headers
    puts = []

    def handler(request):
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if path.endswith("/direct-uploads/initiate/"):
            assert json.loads(request.content)["single_put"] is True
            return httpx.Response(200, json={"uploads": [ticket]})
        if request.url.host == "storage.test":
            puts.append(request.headers)
            return httpx.Response(200, headers={"ETag": '"etag-0"'})
        assert path.endswith("/direct-uploads/complete/")
        return httpx.Response(
            201,
            json={
                "datasource_id": "id-0",
                "upload_session_id": "s",
                "generic_type": "img",
            },
        )

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert batch.uploaded == 1
    (sent,) = puts
    assert sent["content-type"] == "image/png"
    assert sent["cache-control"] == "max-age=86400"
    assert sent["if-none-match"] == "*"
    assert sent["content-length"] == "3"
    assert "authorization" not in sent
    client.close()


def test_post_when_not_advertised(tmp_path):
    (tmp_path / "a.png").write_bytes(b"png")
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": False})
        assert request.url.path == "/api/sdk/projects/p1/upload-data/"
        return httpx.Response(201, json={"datasource_id": "ds", "generic_type": "img"})

    client = configured_client(handler)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert batch.uploaded == 1
    assert paths == [
        "/api/sdk/projects/p1/upload-info/",
        "/api/sdk/projects/p1/upload-data/",
    ]
    client.close()


def test_falls_back_to_post_when_initiate_refused(tmp_path):
    (tmp_path / "a.png").write_bytes(b"png")
    (tmp_path / "b.png").write_bytes(b"png")
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if request.url.path.endswith("/direct-uploads/initiate/"):
            return httpx.Response(400, json={"detail": "direct_upload_unavailable"})
        assert request.url.path == "/api/sdk/projects/p1/upload-data/"
        return httpx.Response(201, json={"datasource_id": "ds", "generic_type": "img"})

    client = configured_client(handler)
    # One file per chunk: the refusal is remembered, the second chunk only POSTs.
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(
        tmp_path, max_concurrent_uploads=1
    )

    assert batch.uploaded == 2
    assert paths == [
        "/api/sdk/projects/p1/upload-info/",
        "/api/sdk/projects/p1/direct-uploads/initiate/",
        "/api/sdk/projects/p1/upload-data/",
        "/api/sdk/projects/p1/upload-data/",
    ]
    client.close()


@pytest.mark.parametrize("status", [412, 403])
def test_single_put_412_or_403_falls_back_to_post_at_once(
    monkeypatch, tmp_path, status
):
    # 412: If-None-Match: * says the object is already stored; 403: the one
    # URL (never renewed for a form-path file) is refused. Sending the bytes
    # again cannot pass either way: one PUT, then the form POST (the stored
    # object, if any, is never completed).
    (tmp_path / "a.png").write_bytes(b"png")
    _no_sleep(monkeypatch)
    ticket = _ticket(0)
    ticket["part_urls"][0]["headers"] = {"If-None-Match": "*"}
    calls = {"put": 0, "post": 0}

    def handler(request):
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if path.endswith("/direct-uploads/initiate/"):
            return httpx.Response(200, json={"uploads": [ticket]})
        if request.url.host == "storage.test":
            calls["put"] += 1
            return httpx.Response(status)
        assert path == "/api/sdk/projects/p1/upload-data/", path
        calls["post"] += 1
        return httpx.Response(201, json={"datasource_id": "ds", "generic_type": "img"})

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert batch.data_item_ids == ["ds"]
    assert calls == {"put": 1, "post": 1}
    client.close()


def test_falls_back_to_post_when_put_fails(monkeypatch, tmp_path):
    (tmp_path / "a.png").write_bytes(b"png")
    _no_sleep(monkeypatch)
    calls = {"put": 0, "complete": 0, "post": 0}

    def handler(request):
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if path.endswith("/direct-uploads/initiate/"):
            return httpx.Response(200, json={"uploads": [_ticket(0)]})
        if request.url.host == "storage.test":
            calls["put"] += 1
            return httpx.Response(500)
        if path.endswith("/direct-uploads/complete/"):
            calls["complete"] += 1
            raise AssertionError("complete after a failed PUT")
        assert path == "/api/sdk/projects/p1/upload-data/"
        assert b'filename="a.png"' in request.content
        calls["post"] += 1
        return httpx.Response(201, json={"datasource_id": "ds", "generic_type": "img"})

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert batch.uploaded == 1
    assert batch.data_item_ids == ["ds"]
    assert calls == {
        "put": _uploader.TILED_PART_MAX_ATTEMPTS,
        "complete": 0,
        "post": 1,
    }
    client.close()


def test_large_image_goes_tiled_when_direct_is_on(monkeypatch, tmp_path):
    (tmp_path / "big.png").write_bytes(b"0123456789")
    monkeypatch.setattr(_uploader, "DIRECT_UPLOAD_MIN_BYTES", 4)
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if request.url.host == "storage.test":
            return httpx.Response(200, headers={"ETag": '"etag"'})
        if request.url.path.endswith("/tiled-uploads/initiate/"):
            return httpx.Response(
                200, json={**_ticket(0), "part_size": 10, "datasource_id": "big"}
            )
        assert request.url.path.endswith("/tiled-uploads/complete/")
        return httpx.Response(202, json={"datasource_id": "big"})

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert batch.data_item_ids == ["big"]
    assert paths == [
        "/api/sdk/projects/p1/upload-info/",
        "/api/sdk/projects/p1/tiled-uploads/initiate/",
        "/part-0",
        "/api/sdk/projects/p1/tiled-uploads/complete/",
    ]
    client.close()


def _asset_answer(index):
    return {
        "folder_id": "folder-1",
        "folder_name": "Raw data",
        "asset": {
            "pk": f"asset-{index}",
            "file_name": f"{index}.png",
            "generic_type": "img",
            "folder_id": "folder-1",
        },
    }


TODAYS_ACCEPTS = {"X-Server-Accepts": "gzip-body, delta-object-authorship"}


def test_assets_post_as_before_when_not_advertised(tmp_path):
    for index in range(3):
        (tmp_path / f"{index}.png").write_bytes(b"png")
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(
            201, headers=TODAYS_ACCEPTS, json=_asset_answer(len(paths))
        )

    client = configured_client(handler)
    result = client.assets.upload(tmp_path, folder="Raw data")

    assert result.uploaded == 3
    assert paths == ["/api/sdk/data-assets/upload/"] * 3
    client.close()


def test_assets_go_direct_after_first_post_advertises(monkeypatch, tmp_path):
    for index in range(3):
        (tmp_path / f"{index}.png").write_bytes(b"png")
    posts, initiates, completes = [], [], []

    def handler(request):
        path = request.url.path
        accepts = {"X-Server-Accepts": "gzip-body, direct-uploads"}
        if path == "/api/sdk/data-assets/upload/":
            posts.append(request.content.decode("latin1"))
            return httpx.Response(201, headers=accepts, json=_asset_answer(0))
        if path == "/api/sdk/data-assets/direct-uploads/initiate/":
            files = json.loads(request.content)["files"]
            initiates.append([entry["file_name"] for entry in files])
            return httpx.Response(
                200,
                json={"uploads": [_ticket(i, id_key="asset_id") for i in (1, 2)]},
            )
        if request.url.host == "storage.test":
            return httpx.Response(200, headers={"ETag": '"etag"'})
        assert path == "/api/sdk/data-assets/direct-uploads/complete/"
        fields = _form_fields(request)
        completes.append(fields)
        return httpx.Response(
            201, headers=accepts, json=_asset_answer(fields["upload_token"][0][-1])
        )

    client = configured_client(handler, monkeypatch)
    # With folder_id the first file also goes alone: its answer says "direct".
    result = client.assets.upload(
        tmp_path,
        folder_id="folder-1",
        tags=["a", "b"],
        custom_metadata={"region": "CA-BC"},
    )

    assert result.uploaded == 3
    # 3.2.0 parity: a folder_id run answers folder_name "" (no folder given).
    assert result.folder_name == ""
    assert len(posts) == 1
    assert 'filename="0.png"' in posts[0]
    assert 'name="folder_id"' in posts[0]
    assert initiates == [["1.png", "2.png"]]
    assert sorted(fields["upload_token"][0] for fields in completes) == [
        "token-1",
        "token-2",
    ]
    for fields in completes:
        assert fields["folder_id"] == ["folder-1"]
        assert fields["tags"] == ["a", "b"]
        assert fields["custom_metadata"] == ['{"region":"CA-BC"}']
    client.close()


def test_initiate_refusal_by_permission_still_finalizes_medical(monkeypatch, tmp_path):
    (tmp_path / "a.dcm").write_bytes(b"dicom")
    (tmp_path / "b.dcm").write_bytes(b"dicom")
    initiates = finalizes = 0

    def handler(request):
        nonlocal initiates, finalizes
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["dcm"],
                    "max_file_sizes": {"medical": 1_000},
                    "generic_type": None,
                    "direct_uploads": True,
                },
            )
        if path.endswith("/direct-uploads/initiate/"):
            initiates += 1
            if initiates == 2:
                return httpx.Response(
                    403, json={"detail": "No access", "code": "permission_denied"}
                )
            return httpx.Response(200, json={"uploads": [_ticket(0)]})
        if request.url.host == "storage.test":
            return httpx.Response(200, headers={"ETag": '"etag"'})
        if path.endswith("/direct-uploads/complete/"):
            return httpx.Response(
                201, json={"datasource_id": "id-0", "generic_type": "medical"}
            )
        assert path.endswith("/finalize/")
        finalizes += 1
        return httpx.Response(200, json={})

    client = configured_client(handler, monkeypatch)
    project = Project("p1", "Project", {"pk": "p1"}, client)

    with pytest.raises(PermissionDeniedError):
        project.upload(tmp_path, max_concurrent_uploads=1)
    assert (initiates, finalizes) == (2, 1)
    client.close()


def test_more_than_fifty_files_take_two_initiates(monkeypatch, tmp_path):
    names = [f"{index:02}.png" for index in range(51)]
    for name in names:
        (tmp_path / name).write_bytes(b"png")
    initiates = []

    def handler(request):
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if path.endswith("/direct-uploads/initiate/"):
            files = [
                entry["file_name"] for entry in json.loads(request.content)["files"]
            ]
            initiates.append(files)
            return httpx.Response(200, json={"uploads": [_ticket(n) for n in files]})
        if request.url.host == "storage.test":
            return httpx.Response(200, headers={"ETag": '"etag"'})
        assert path.endswith("/direct-uploads/complete/")
        token = _form_fields(request)["upload_token"][0]
        return httpx.Response(201, json={"datasource_id": token})

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(
        tmp_path, max_concurrent_uploads=len(names)
    )

    assert batch.uploaded == 51
    assert initiates == [names[:50], names[50:]]
    client.close()


def test_lost_complete_answer_is_asked_again(monkeypatch, tmp_path):
    # The server's complete is idempotent per ticket (first item, one charge).
    (tmp_path / "a.png").write_bytes(b"png")
    _no_sleep(monkeypatch)
    completes = 0

    def handler(request):
        nonlocal completes
        path = request.url.path
        if path.endswith("/upload-info/"):
            return httpx.Response(200, json={**PROJECT_INFO, "direct_uploads": True})
        if path.endswith("/direct-uploads/initiate/"):
            return httpx.Response(200, json={"uploads": [_ticket(0)]})
        if request.url.host == "storage.test":
            return httpx.Response(200, headers={"ETag": '"etag"'})
        assert path.endswith("/direct-uploads/complete/")
        completes += 1
        if completes == 1:
            raise httpx.ReadTimeout("", request=request)
        if completes == 2:
            return httpx.Response(502, text="Bad gateway")
        return httpx.Response(201, json={"datasource_id": "id-0"})

    client = configured_client(handler, monkeypatch)
    batch = Project("p1", "Project", {"pk": "p1"}, client).upload(tmp_path)

    assert batch.data_item_ids == ["id-0"]
    assert completes == 3
    client.close()
