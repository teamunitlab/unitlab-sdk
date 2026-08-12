import inspect
import json

import httpx
import pytest

from unitlab import (
    AmbiguousUploadCompletionError,
    NetworkError,
    UnitlabClient,
    _uploader,
)
from unitlab.resources.assets import Asset, AssetsNamespace
from unitlab.resources.projects import Project


def configured_client(handler, monkeypatch=None):
    transport = httpx.MockTransport(handler)
    native_async_client = httpx.AsyncClient
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
    if monkeypatch is not None:

        def routed_async_client(*args, **kwargs):
            kwargs.setdefault("transport", transport)
            return native_async_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", routed_async_client)
    return client


def test_public_tiled_upload_contract():
    assert "data_type" not in inspect.signature(Project.upload).parameters
    assert "data_type" not in inspect.signature(AssetsNamespace.upload).parameters
    assert inspect.signature(Asset.wait).parameters["timeout"].default == 25200
    assert issubclass(AmbiguousUploadCompletionError, NetworkError)


@pytest.mark.parametrize(
    "extension",
    ["svs", "avs", "ndpi", "scn", "bif", "svslide", "tf2", "tf8", "btf"],
)
def test_pathology_extensions_are_inferred(extension):
    assert _uploader.detect_generic_type(f"slide.{extension}") == "pathology"


@pytest.mark.parametrize(
    "extension", ["jp2", "cog", "geotiff", "gtif", "gtiff", "img", "ntf", "nitf"]
)
def test_geospatial_extensions_are_inferred(extension):
    assert _uploader.detect_generic_type(f"area.{extension}") == "geospatial"


def test_file_part_stream_is_bounded_to_its_range(tmp_path):
    chunk_size = 1024 * 1024
    path = tmp_path / "large.svs"
    path.write_bytes(b"skip" + b"a" * chunk_size + b"tail" + b"ignored")

    async def read_stream():
        return [
            chunk
            async for chunk in _uploader._FilePartStream(
                path,
                start=4,
                size=chunk_size + 4,
            )
        ]

    chunks = _uploader.run_sync(read_stream())
    assert [len(chunk) for chunk in chunks] == [chunk_size, 4]
    assert chunks[0] == b"a" * chunk_size
    assert chunks[1] == b"tail"


def test_small_tiff_uses_simple_asset_upload(tmp_path):
    source = tmp_path / "small.tiff"
    source.write_bytes(b"small tiff")
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        assert request.url.path == "/api/sdk/data-assets/upload/"
        assert b'name="generic_type"' not in request.content
        return httpx.Response(
            201,
            json={
                "asset": {
                    "pk": "asset-1",
                    "file_name": "small.tiff",
                    "generic_type": "geospatial",
                    "upload_status": "processing",
                    "folder_id": "folder-1",
                },
                "folder_id": "folder-1",
                "folder_name": "Maps",
            },
        )

    client = configured_client(handler)
    result = client.assets.upload(source, folder="Maps")

    assert result.uploaded == 1
    assert result.assets[0].data_type == "geospatial"
    assert requests == [("POST", "/api/sdk/data-assets/upload/")]
    client.close()


def test_project_multipart_upload_retries_only_puts_and_uses_plain_storage_client(
    monkeypatch,
    tmp_path,
):
    source = tmp_path / "map.tif"
    source.write_bytes(b"abcdefghij")
    calls = {"initiate": 0, "complete": 0, "abort": 0, "simple": 0}
    put_attempts = {}
    put_bodies = {}
    initiated = {}

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(_uploader.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(_uploader, "TILED_MULTIPART_MIN_TIFF_BYTES", 0)

    def handler(request):
        if request.url.path.endswith("/upload-info/"):
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["png", "tif", "tiff"],
                    "max_file_sizes": {"geospatial": 1_000},
                    "generic_type": None,
                },
            )
        if request.url.host == "storage.test":
            part_number = int(request.url.path.rsplit("-", 1)[-1])
            put_attempts[part_number] = put_attempts.get(part_number, 0) + 1
            put_bodies[part_number] = request.content
            assert request.method == "PUT"
            assert "authorization" not in request.headers
            assert "content-type" not in request.headers
            if part_number == 1 and put_attempts[part_number] == 1:
                return httpx.Response(503)
            return httpx.Response(200, headers={"ETag": f'"etag-{part_number}"'})
        if request.url.path.endswith("/initiate/"):
            calls["initiate"] += 1
            assert request.url.path == (
                "/api/sdk/projects/project-1/tiled-uploads/initiate/"
            )
            initiated.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "upload_token": "token-1",
                    "datasource_id": "datasource-1",
                    "upload_id": "upload-1",
                    "part_size": 4,
                    "part_urls": [
                        {
                            "part_number": number,
                            "url": f"https://storage.test/part-{number}",
                        }
                        for number in range(1, 4)
                    ],
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/complete/"):
            calls["complete"] += 1
            assert request.url.path == (
                "/api/sdk/projects/project-1/tiled-uploads/complete/"
            )
            assert json.loads(request.content) == {
                "upload_token": "token-1",
                "parts": [
                    {"part_number": number, "etag": f"etag-{number}"}
                    for number in range(1, 4)
                ],
            }
            return httpx.Response(
                202,
                json={
                    "datasource_id": "datasource-1",
                    "upload_session_id": initiated["session_id"],
                    "upload_status": "processing",
                    "task_id": "task-1",
                },
            )
        if request.url.path.endswith("/abort/"):
            calls["abort"] += 1
            return httpx.Response(204)
        if request.url.path.endswith("/upload-data/"):
            calls["simple"] += 1
            raise AssertionError(
                f"unexpected simple fallback: {put_attempts=}, {put_bodies=}"
            )
        raise AssertionError(request.url)

    client = configured_client(handler, monkeypatch)
    project = Project("project-1", "Project", {"pk": "project-1"}, client)
    result = project.upload(source)

    assert result.uploaded == 1
    assert result.data_item_ids == ["datasource-1"]
    assert result.batch_queue_id == initiated["session_id"]
    assert initiated == {
        "file_name": "map.tif",
        "file_size": 10,
        "session_id": result.batch_queue_id,
    }
    assert put_attempts == {1: 2, 2: 1, 3: 1}
    assert put_bodies == {1: b"abcd", 2: b"efgh", 3: b"ij"}
    assert calls == {"initiate": 1, "complete": 1, "abort": 0, "simple": 0}
    client.close()


def test_initiate_transport_failure_is_reported_without_simple_fallback(tmp_path):
    source = tmp_path / "slide.svs"
    source.write_bytes(b"slide")
    calls = {"initiate": 0, "simple": 0}

    def handler(request):
        if request.url.path.endswith("/upload-info/"):
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["svs"],
                    "max_file_sizes": {"pathology": 1_000},
                    "generic_type": None,
                },
            )
        if request.url.path.endswith("/initiate/"):
            calls["initiate"] += 1
            raise httpx.ConnectError("control plane unavailable", request=request)
        if request.url.path.endswith("/upload-data/"):
            calls["simple"] += 1
            return httpx.Response(201, json={"datasource_id": "duplicate"})
        raise AssertionError(request.url)

    client = configured_client(handler)
    project = Project("project-1", "Project", {"pk": "project-1"}, client)

    with pytest.raises(NetworkError, match="control plane unavailable"):
        project.upload(source)
    assert calls == {"initiate": 1, "simple": 0}
    client.close()


def test_asset_multipart_upload_completes_with_destination_metadata(
    monkeypatch,
    tmp_path,
):
    source = tmp_path / "slide.ndpi"
    source.write_bytes(b"slide")
    completion = {}

    def handler(request):
        if request.url.host == "storage.test":
            assert request.method == "PUT"
            assert "authorization" not in request.headers
            assert request.content == b"slide"
            return httpx.Response(200, headers={"ETag": '"asset-etag"'})
        if request.url.path.endswith("/initiate/"):
            assert request.url.path == ("/api/sdk/data-assets/tiled-uploads/initiate/")
            assert json.loads(request.content) == {
                "file_name": "slide.ndpi",
                "file_size": 5,
            }
            return httpx.Response(
                200,
                json={
                    "upload_token": "asset-token",
                    "asset_id": "asset-1",
                    "upload_id": "upload-1",
                    "part_size": 5,
                    "part_urls": [
                        {"part_number": 1, "url": "https://storage.test/asset-1"}
                    ],
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/complete/"):
            assert request.url.path == ("/api/sdk/data-assets/tiled-uploads/complete/")
            completion.update(json.loads(request.content))
            return httpx.Response(
                202,
                json={
                    "asset": {
                        "pk": "asset-1",
                        "file_name": "slide.ndpi",
                        "generic_type": "pathology",
                        "upload_status": "processing",
                        "folder_id": "folder-1",
                    },
                    "folder_id": "folder-1",
                    "folder_name": "Raw slides",
                    "task_id": "task-1",
                },
            )
        raise AssertionError(request.url)

    client = configured_client(handler, monkeypatch)
    result = client.assets.upload(
        source,
        folder="Raw slides",
        path="case-1",
        tags=["review"],
        custom_metadata={"scanner": "A"},
    )

    assert result.uploaded == 1
    assert result.folder_id == "folder-1"
    assert len(result.assets) == 1
    assert result.assets[0].upload_status == "processing"
    assert completion == {
        "upload_token": "asset-token",
        "parts": [{"part_number": 1, "etag": "asset-etag"}],
        "folder_name": "Raw slides",
        "path": "case-1",
        "tags": ["review"],
        "custom_metadata": {"scanner": "A"},
    }
    client.close()


def test_precompletion_part_failure_aborts_without_simple_fallback(
    monkeypatch,
    tmp_path,
):
    source = tmp_path / "slide.svs"
    source.write_bytes(b"slide")
    calls = {"put": 0, "abort": 0, "complete": 0, "simple": 0}

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(_uploader.asyncio, "sleep", no_sleep)

    def handler(request):
        if request.url.path.endswith("/upload-info/"):
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["svs"],
                    "max_file_sizes": {"pathology": 1_000},
                    "generic_type": None,
                },
            )
        if request.url.host == "storage.test":
            calls["put"] += 1
            return httpx.Response(503)
        if request.url.path.endswith("/initiate/"):
            return httpx.Response(
                200,
                json={
                    "upload_token": "token-1",
                    "datasource_id": "datasource-1",
                    "upload_id": "upload-1",
                    "part_size": 5,
                    "part_urls": [
                        {"part_number": 1, "url": "https://storage.test/part-1"}
                    ],
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/abort/"):
            calls["abort"] += 1
            assert json.loads(request.content) == {"upload_token": "token-1"}
            return httpx.Response(204)
        if request.url.path.endswith("/complete/"):
            calls["complete"] += 1
            return httpx.Response(500)
        if request.url.path.endswith("/upload-data/"):
            calls["simple"] += 1
            assert b'name="generic_type"' not in request.content
            return httpx.Response(
                201,
                json={
                    "datasource_id": "fallback-source",
                    "upload_session_id": "queue-1",
                    "generic_type": "pathology",
                },
            )
        raise AssertionError(request.url)

    client = configured_client(handler, monkeypatch)
    project = Project("project-1", "Project", {"pk": "project-1"}, client)

    with pytest.raises(NetworkError, match="Multipart part upload failed"):
        project.upload(source)
    assert calls == {
        "put": _uploader.TILED_PART_MAX_ATTEMPTS,
        "abort": 1,
        "complete": 0,
        "simple": 0,
    }
    client.close()


def test_completion_failure_is_ambiguous_without_retry_abort_or_fallback(
    monkeypatch,
    tmp_path,
):
    source = tmp_path / "slide.scn"
    source.write_bytes(b"slide")
    calls = {"complete": 0, "abort": 0, "simple": 0}

    def handler(request):
        if request.url.path.endswith("/upload-info/"):
            return httpx.Response(
                200,
                json={
                    "accepted_formats": ["scn"],
                    "max_file_sizes": {"pathology": 1_000},
                    "generic_type": None,
                },
            )
        if request.url.host == "storage.test":
            return httpx.Response(200, headers={"ETag": '"etag-1"'})
        if request.url.path.endswith("/initiate/"):
            return httpx.Response(
                200,
                json={
                    "upload_token": "token-1",
                    "datasource_id": "datasource-1",
                    "upload_id": "upload-1",
                    "part_size": 5,
                    "part_urls": [
                        {"part_number": 1, "url": "https://storage.test/part-1"}
                    ],
                    "expires_in": 3600,
                },
            )
        if request.url.path.endswith("/complete/"):
            calls["complete"] += 1
            return httpx.Response(503, json={"detail": "confirmation lost"})
        if request.url.path.endswith("/abort/"):
            calls["abort"] += 1
            return httpx.Response(204)
        if request.url.path.endswith("/upload-data/"):
            calls["simple"] += 1
            return httpx.Response(201, json={"datasource_id": "duplicate"})
        raise AssertionError(request.url)

    client = configured_client(handler, monkeypatch)
    project = Project("project-1", "Project", {"pk": "project-1"}, client)

    with pytest.raises(AmbiguousUploadCompletionError):
        project.upload(source)
    assert calls == {"complete": 1, "abort": 0, "simple": 0}
    client.close()


def test_asset_status_wait_and_retry_use_sdk_endpoints():
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "upload_status": "completed",
                    "total": 1,
                    "completed": 1,
                    "processing": 0,
                    "failed": 0,
                },
            )
        return httpx.Response(202, json={"task_id": "task-2", "status": "processing"})

    client = configured_client(handler)
    asset = Asset._from_raw(
        client,
        {
            "pk": "asset-1",
            "file_name": "slide.svs",
            "generic_type": "pathology",
            "upload_status": "processing",
        },
    )

    assert asset.upload_status == "processing"
    assert asset.status().status == "completed"
    assert asset.upload_status == "completed"
    assert asset.wait(show_progress=False).completed == 1
    assert asset.retry() == {"task_id": "task-2", "status": "processing"}
    assert asset.upload_status == "processing"
    assert requests == [
        ("GET", "/api/sdk/data-assets/assets/asset-1/tiled-status/"),
        ("GET", "/api/sdk/data-assets/assets/asset-1/tiled-status/"),
        ("POST", "/api/sdk/data-assets/assets/asset-1/tiled-retry/"),
    ]
    client.close()
