import json
import re

import httpx
import pytest

from unitlab import (
    AuthenticationError,
    ProcessingTimeoutError,
    UnitlabClient,
    tiles_from_template,
)
from unitlab.resources.assets import Asset
from unitlab.resources.projects import BatchQueue, Project


def configured_client(handler):
    transport = httpx.MockTransport(handler)
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
