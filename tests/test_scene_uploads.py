"""Lidar scenes through ``upload(..., generic_type="pointcloud")``.

What is checked here is the SDK's side of the scene routes: which routes are
called and with what, that a scene never falls back to the plain upload, how a
folder is sent, and what the caller gets back. Which files form a scene is
checked in ``test_scenes.py`` and ``test_nuscenes.py``.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from urllib.parse import unquote

import httpx
import pytest

from unitlab import (
    AmbiguousUploadCompletionError,
    NetworkError,
    UnitlabClient,
    UnitlabError,
    _uploader,
    detect_scenes,
)
from unitlab.resources.assets import Asset
from unitlab.resources.projects import Project

PROJECT = "/api/sdk/projects/project-1"
ASSETS = "/api/sdk/data-assets"
SCENE_INFO = {
    "enabled": True,
    "accepted_formats": ["zip", "pcd", "bin", "ply"],
    "max_file_size": 1_000,
    "max_frames": 1_000,
    "max_files": 100_000,
    "url_batch": 2,
}


class SceneServer:
    """The scene routes and storage, as one request handler.

    Any route outside the scene's own (the plain upload, the tiled multipart)
    fails the test: a scene must never be sent there.
    """

    def __init__(self, base=PROJECT, *, info=SCENE_INFO):
        self.base = base
        self.info = info
        self.calls = []
        self.puts = {}
        self.put_attempts = Counter()
        self.failing_puts = {}
        self.complete_status = 202
        self.completed = 0

    def routes(self, suffix):
        return [body for route, body in self.calls if route.endswith(suffix)]

    def __call__(self, request):
        path = request.url.path
        if request.url.host == "storage.test":
            assert request.method == "PUT"
            assert "authorization" not in request.headers
            assert "content-type" not in request.headers
            key = unquote(path).lstrip("/")
            self.put_attempts[key] += 1
            if self.failing_puts.get(key, 0) >= self.put_attempts[key]:
                return httpx.Response(503)
            self.puts[key] = request.content
            return httpx.Response(200, headers={"ETag": f'"etag-{key}"'})
        if path.endswith("/upload-info/"):
            info = {
                "accepted_formats": ["png"],
                "max_file_sizes": {"img": 100},
                "generic_type": None,
            }
            if self.info is not None:
                info["pointcloud"] = self.info
            return httpx.Response(200, json=info)
        assert path.startswith(f"{self.base}/pointcloud-"), path
        body = json.loads(request.content)
        route = path[len(self.base) :]
        self.calls.append((route, body))
        if route == "/pointcloud-uploads/initiate/":
            return httpx.Response(
                200,
                json={
                    "upload_token": "file-token",
                    "part_size": body["file_size"],
                    "part_urls": [
                        {"part_number": 1, "url": "https://storage.test/part-1"}
                    ],
                    "expires_in": 3600,
                },
            )
        if route == "/pointcloud-folder-uploads/initiate/":
            return httpx.Response(
                200,
                json={
                    "upload_token": f"token-{body['name']}",
                    "url_batch": self.info["url_batch"],
                    "expires_in": 3600,
                },
            )
        if route == "/pointcloud-folder-uploads/urls/":
            return httpx.Response(
                200,
                json={
                    "urls": [
                        {"path": name, "url": f"https://storage.test/{name}"}
                        for name in body["paths"]
                    ],
                    "expires_in": 3600,
                },
            )
        if route.endswith("/abort/"):
            return httpx.Response(204)
        assert route.endswith("/complete/"), route
        if self.complete_status != 202:
            return httpx.Response(self.complete_status, json={"detail": "lost"})
        self.completed += 1
        if self.base == ASSETS:
            return httpx.Response(
                202,
                json={
                    "asset": {
                        "pk": f"asset-{self.completed}",
                        "file_name": "scene",
                        "generic_type": "pointcloud",
                        "folder_id": "folder-1",
                        "upload_status": "processing",
                    },
                    "folder_id": "folder-1",
                    "folder_name": "Lidar",
                },
            )
        return httpx.Response(
            202,
            json={
                "datasource_id": f"item-{self.completed}",
                "upload_session_id": "queue",
                "upload_status": "processing",
                "task_id": "task",
            },
        )


def client_for(handler, monkeypatch):
    """A client whose API and storage requests both reach ``handler``."""
    transport = httpx.MockTransport(handler)
    native_async_client = httpx.AsyncClient
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    client._api.client.close()
    client._api.client = httpx.Client(
        base_url="http://testserver",
        headers={"Authorization": "Api-Key key"},
        transport=transport,
    )

    def routed_async_client(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return native_async_client(*args, **kwargs)

    client._api.async_client = lambda *, timeout=600.0: native_async_client(
        base_url="http://testserver",
        headers={"Authorization": "Api-Key key"},
        transport=transport,
        timeout=timeout,
    )
    monkeypatch.setattr(httpx, "AsyncClient", routed_async_client)

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(_uploader.asyncio, "sleep", no_sleep)
    return client


def project_of(client):
    return Project("project-1", "Project", {"pk": "project-1"}, client)


def scene_folder(root, name, frames=3, sensor="lidar"):
    """A one-sensor scene folder: ``<name>/<sensor>/000.pcd`` and so on."""
    folder = root / name / sensor
    folder.mkdir(parents=True)
    for index in range(frames):
        (folder / f"{index:03d}.pcd").write_bytes(b"cloud")
    return root / name


def test_a_scene_file_is_sent_through_the_scene_routes(monkeypatch, tmp_path):
    source = tmp_path / "drive.pcd"
    source.write_bytes(b"0123456789")
    server = SceneServer()
    client = client_for(server, monkeypatch)

    result = project_of(client).upload(source, generic_type="pointcloud")

    assert (result.total, result.uploaded, result.failed) == (1, 1, [])
    assert result.data_item_ids == ["item-1"]
    assert server.routes("/pointcloud-uploads/initiate/") == [
        {
            "file_name": "drive.pcd",
            "file_size": 10,
            "session_id": result.batch_queue_id,
        }
    ]
    assert server.puts == {"part-1": b"0123456789"}
    assert server.routes("/pointcloud-uploads/complete/") == [
        {
            "upload_token": "file-token",
            "parts": [{"part_number": 1, "etag": "etag-part-1"}],
        }
    ]
    client.close()


def test_without_the_type_scene_files_are_still_not_uploaded(monkeypatch, tmp_path):
    scene_folder(tmp_path, "drive_01")
    server = SceneServer()
    client = client_for(server, monkeypatch)

    with pytest.raises(ValueError, match="No uploadable files"):
        project_of(client).upload(tmp_path)

    assert server.calls == []
    client.close()


def test_a_zip_is_a_scene_only_when_it_holds_frames(monkeypatch, tmp_path):
    scene = tmp_path / "drive.zip"
    with zipfile.ZipFile(scene, "w") as archive:
        archive.writestr("lidar/000.pcd", b"cloud")
    photos = tmp_path / "photos.zip"
    with zipfile.ZipFile(photos, "w") as archive:
        archive.writestr("__MACOSX/._000.pcd", b"fork")
        archive.writestr("holiday.jpg", b"image")
    server = SceneServer()
    client = client_for(server, monkeypatch)

    result = project_of(client).upload(scene, generic_type="pointcloud")
    with pytest.raises(ValueError, match="must contain"):
        project_of(client).upload(photos, generic_type="pointcloud")

    assert result.uploaded == 1
    assert [body["file_name"] for body in server.routes("/initiate/")] == ["drive.zip"]
    client.close()


def test_a_file_that_is_no_scene_format_is_refused(monkeypatch, tmp_path):
    source = tmp_path / "photo.png"
    source.write_bytes(b"image")
    server = SceneServer()
    client = client_for(server, monkeypatch)

    with pytest.raises(ValueError, match=r"\.zip, \.pcd, \.bin"):
        project_of(client).upload(source, generic_type="pointcloud")

    assert server.calls == []
    client.close()


def test_a_scene_folder_is_sent_file_by_file_in_url_batches(monkeypatch, tmp_path):
    source = scene_folder(tmp_path, "drive_01", frames=3)
    server = SceneServer()
    client = client_for(server, monkeypatch)

    result = project_of(client).upload(source, generic_type="pointcloud")

    assert (result.uploaded, result.data_item_ids) == (1, ["item-1"])
    assert server.routes("/pointcloud-folder-uploads/initiate/") == [
        {
            "name": "drive_01",
            "file_count": 3,
            "total_size": 15,
            "frame_count": 3,
            "session_id": result.batch_queue_id,
        }
    ]
    # url_batch is 2: three files need two requests for URLs.
    assert server.routes("/urls/") == [
        {
            "upload_token": "token-drive_01",
            "paths": ["lidar/000.pcd", "lidar/001.pcd"],
        },
        {"upload_token": "token-drive_01", "paths": ["lidar/002.pcd"]},
    ]
    assert server.puts == {
        "lidar/000.pcd": b"cloud",
        "lidar/001.pcd": b"cloud",
        "lidar/002.pcd": b"cloud",
    }
    assert server.routes("/pointcloud-folder-uploads/complete/") == [
        {"upload_token": "token-drive_01"}
    ]
    assert server.routes("/abort/") == []
    client.close()


def test_a_file_that_fails_once_is_sent_again(monkeypatch, tmp_path):
    source = scene_folder(tmp_path, "drive_01", frames=2)
    server = SceneServer()
    server.failing_puts = {"lidar/001.pcd": 1}
    client = client_for(server, monkeypatch)

    result = project_of(client).upload(source, generic_type="pointcloud")

    assert result.uploaded == 1
    assert server.put_attempts == {"lidar/000.pcd": 1, "lidar/001.pcd": 2}
    assert server.routes("/abort/") == []
    client.close()


def test_a_folder_that_cannot_be_sent_is_aborted_and_the_next_scene_goes_on(
    monkeypatch, tmp_path
):
    scene_folder(tmp_path / "recordings", "drive_01", frames=1)
    scene_folder(tmp_path / "recordings", "drive_02", frames=1, sensor="top")
    server = SceneServer()
    server.failing_puts = {"lidar/000.pcd": 99}
    client = client_for(server, monkeypatch)

    result = project_of(client).upload(
        tmp_path / "recordings", generic_type="pointcloud"
    )

    assert (result.total, result.uploaded) == (2, 1)
    assert [failure.path.name for failure in result.failed] == ["drive_01"]
    # What was sent of the failed scene is deleted; nothing is completed for it.
    assert server.routes("/abort/") == [{"upload_token": "token-drive_01"}]
    assert server.routes("/complete/") == [{"upload_token": "token-drive_02"}]
    client.close()


def test_a_lost_completion_is_ambiguous_and_nothing_is_aborted(monkeypatch, tmp_path):
    source = scene_folder(tmp_path, "drive_01", frames=1)
    server = SceneServer()
    server.complete_status = 500
    client = client_for(server, monkeypatch)

    with pytest.raises(AmbiguousUploadCompletionError):
        project_of(client).upload(source, generic_type="pointcloud")

    assert server.routes("/abort/") == []
    client.close()


def test_a_server_without_scene_upload_is_named_before_anything_is_sent(
    monkeypatch, tmp_path
):
    source = scene_folder(tmp_path, "drive_01")
    server = SceneServer(info=None)
    client = client_for(server, monkeypatch)

    with pytest.raises(UnitlabError, match="does not accept lidar scenes"):
        project_of(client).upload(source, generic_type="pointcloud")

    assert server.calls == []
    client.close()


def test_a_workspace_without_lidar_is_refused_before_anything_is_sent(
    monkeypatch, tmp_path
):
    source = scene_folder(tmp_path, "drive_01")
    server = SceneServer(info={**SCENE_INFO, "enabled": False})
    client = client_for(server, monkeypatch)

    with pytest.raises(UnitlabError, match="not enabled for this workspace"):
        project_of(client).upload(source, generic_type="pointcloud")

    assert server.calls == []
    client.close()


def test_a_scene_over_the_size_limit_fails_before_upload(monkeypatch, tmp_path):
    scene_folder(tmp_path / "recordings", "small", frames=1)
    scene_folder(tmp_path / "recordings", "large", frames=4)
    server = SceneServer(info={**SCENE_INFO, "max_file_size": 10})
    client = client_for(server, monkeypatch)

    result = project_of(client).upload(
        tmp_path / "recordings", generic_type="pointcloud"
    )

    assert (result.total, result.uploaded) == (2, 1)
    assert [failure.path.name for failure in result.failed] == ["large"]
    assert "maximum is 10 bytes" in result.failed[0].error
    assert [body["name"] for body in server.routes("/initiate/")] == ["small"]
    client.close()


def test_scenes_into_assets_name_their_destination_at_completion(monkeypatch, tmp_path):
    scene_folder(tmp_path / "recordings", "drive_01", frames=1)
    scene_folder(tmp_path / "recordings", "drive_02", frames=1)
    server = SceneServer(ASSETS)
    client = client_for(server, monkeypatch)

    result = client.assets.upload(
        tmp_path / "recordings",
        generic_type="pointcloud",
        folder="Lidar",
        tags=["night"],
        custom_metadata={"vehicle": "A"},
    )

    assert (result.uploaded, result.failed) == (2, [])
    assert (result.folder_id, result.folder_name) == ("folder-1", "Lidar")
    assert [asset.data_type for asset in result.assets] == ["pointcloud"] * 2
    # No Batch Queue in the library; the first scene names the folder, the
    # rest use the id the server resolved it to.
    assert "session_id" not in server.routes("/initiate/")[0]
    assert server.routes("/complete/") == [
        {
            "upload_token": "token-drive_01",
            "folder_name": "Lidar",
            "tags": ["night"],
            "custom_metadata": {"vehicle": "A"},
        },
        {
            "upload_token": "token-drive_02",
            "folder_id": "folder-1",
            "tags": ["night"],
            "custom_metadata": {"vehicle": "A"},
        },
    ]
    client.close()


def test_detect_scenes_lists_what_would_upload(tmp_path):
    root = tmp_path / "recordings"
    scene_folder(root, "drive_01", frames=2)
    (root / "scan.pcd").write_bytes(b"cloud")
    (root / "notes.txt").write_text("calibration notes")
    with zipfile.ZipFile(root / "photos.zip", "w") as archive:
        archive.writestr("holiday.jpg", b"image")

    detection = detect_scenes(root)

    assert [(scene.name, scene.source) for scene in detection.scenes] == [
        ("drive_01", "folder"),
        ("scan.pcd", "file"),
    ]
    assert detection.scenes[0].frame_count == 2
    assert sorted(path.name for path in detection.other_files) == [
        "notes.txt",
        "photos.zip",
    ]


def test_split_sensor_folders_reads_each_sensor_folder_as_a_scene(tmp_path):
    rig = tmp_path / "rig"
    for sensor in ("top", "left"):
        scene_folder(tmp_path, "rig", frames=2, sensor=sensor)

    together = detect_scenes(rig)
    apart = detect_scenes(rig, split_sensor_folders=True)

    assert [scene.name for scene in together.scenes] == ["rig"]
    assert together.scenes[0].split is not None
    assert sorted(scene.name for scene in apart.scenes) == ["left", "top"]


def test_a_folder_without_a_scene_says_what_a_scene_is(tmp_path):
    (tmp_path / "notes.txt").write_text("nothing here")

    with pytest.raises(ValueError, match="No lidar scene found"):
        detect_scenes(tmp_path)


def test_scene_status_and_retry_use_the_scene_routes(monkeypatch):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "datasource_id": "item-1",
                    "generic_type": "pointcloud",
                    "upload_status": "failed",
                    "status": "failed",
                    "total": 1,
                    "completed": 0,
                    "processing": 0,
                    "failed": 1,
                    "error": "No point clouds found.",
                    "frame_count": None,
                },
            )
        return httpx.Response(202, json={"task_id": "task", "status": "processing"})

    client = client_for(handler, monkeypatch)
    project = project_of(client)

    status = project.scene_status("item-1")
    retried = project.retry_scene("item-1")

    assert (status.status, status.failed) == ("failed", 1)
    assert (status.error, status.frame_count) == ("No point clouds found.", None)
    assert retried == {"task_id": "task", "status": "processing"}
    assert seen == [
        ("GET", f"{PROJECT}/pointcloud-scenes/item-1/status/"),
        ("POST", f"{PROJECT}/pointcloud-scenes/item-1/retry/"),
    ]
    client.close()


def test_a_scene_asset_is_retried_on_its_own_route(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "asset_id": "asset-1",
                    "upload_status": "completed",
                    "status": "completed",
                    "total": 1,
                    "completed": 1,
                    "processing": 0,
                    "failed": 0,
                    "error": None,
                    "frame_count": 12,
                },
            )
        return httpx.Response(202, json={"task_id": "task", "status": "processing"})

    client = client_for(handler, monkeypatch)
    scene = Asset._from_raw(client, {"pk": "asset-1", "generic_type": "pointcloud"})
    slide = Asset._from_raw(client, {"pk": "asset-2", "generic_type": "pathology"})

    status = scene.status()
    scene.retry()
    slide.retry()

    assert (status.frame_count, status.error) == (12, None)
    assert seen == [
        f"{ASSETS}/assets/asset-1/status/",
        f"{ASSETS}/assets/asset-1/pointcloud-retry/",
        f"{ASSETS}/assets/asset-2/tiled-retry/",
    ]
    client.close()


def test_network_error_is_the_error_of_an_upload_where_nothing_went_through(
    monkeypatch, tmp_path
):
    source = scene_folder(tmp_path, "drive_01", frames=1)
    server = SceneServer()
    server.failing_puts = {"lidar/000.pcd": 99}
    client = client_for(server, monkeypatch)

    with pytest.raises(NetworkError, match="Failed to upload 1 of 1"):
        project_of(client).upload(source, generic_type="pointcloud")

    assert server.routes("/abort/") == [{"upload_token": "token-drive_01"}]
    client.close()
