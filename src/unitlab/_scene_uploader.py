"""Uploading lidar scenes (data type ``pointcloud``).

Spec: the backend repository's ``docs/sdk-lidar-coverage.md``.

A scene is ONE item whatever it is made of: a ``.pcd``/``.ply``/``.bin``
cloud, a ``.zip`` archive, or a folder of frames with its camera images. It is
sent only when the caller names the type (``generic_type="pointcloud"``);
without it these files are skipped exactly as before this module existed.

Flow, the same for a project and for Data Assets::

    detect_scenes(source)              which scenes the source holds
        _scenes.detect_folder_scenes   the browser's rules, ported
        _is_scene_zip                  a zip counts only if it lists frames
    _upload_scenes                     one scene after another
        _upload_scene_file             multipart, the helper tiled files use
        _upload_scene_folder           initiate -> urls -> PUT each -> complete

Two deliberate differences from every other upload in ``_uploader``:

* There is NO fallback to the plain upload route. That route would file a
  scene as an unknown file, and a scene can be gigabytes. A server without
  direct upload, or without these routes, is a failure with that reason.
* The scene routes are their own (``…/pointcloud-uploads``,
  ``…/pointcloud-folder-uploads``). Their tokens are not accepted on the tiled
  routes and the reverse.

Nothing about a scene is decided here beyond what to send: limits, quota and
the ingest are the server's. The limits in ``upload-info`` are only used to
refuse a scene before its bytes are sent.
"""

from __future__ import annotations

import asyncio
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import tqdm

from . import _uploader
from ._http import _extract_error_message, error_text, raise_for_response
from ._scenes import (
    Scene,
    SceneDetection,
    SceneFile,
    detect_folder_scenes,
    scenes_to_upload,
)
from .exceptions import AmbiguousUploadCompletionError, NetworkError, UnitlabError
from .types import UploadFailure, UploadResult

SCENE_TYPE = "pointcloud"
# Mirrors the server's ``pointcloud_service.UPLOAD_EXTENSIONS``.
CLOUD_EXTENSIONS = ("pcd", "bin", "ply")
# Robot recordings the server converts into a scene: MCAP, ROS 1 bag, ROS 2 .db3.
RECORDING_EXTENSIONS = ("mcap", "bag", "db3")
SCENE_FILE_EXTENSIONS = ("zip", *CLOUD_EXTENSIONS, *RECORDING_EXTENSIONS)
SCENE_MANIFEST_NAME = "scene.json"
# Files of one folder scene sent at once; the browser's FOLDER_FILE_CONCURRENCY.
FOLDER_FILE_CONCURRENCY = 6

NOT_A_SCENE_FORMAT = (
    "A lidar scene is a .zip, .pcd, .bin or .ply file, a recording (.mcap, .bag, "
    ".db3), or a folder of such frames."
)
# The browser's wording for the same refusal.
NOT_A_SCENE_ZIP = (
    "A 3D scene archive must contain .pcd, .bin or .ply frames or a scene.json."
)
UNSUPPORTED_SERVER = (
    "This Unitlab server does not accept lidar scenes through the SDK yet."
)


class _SceneRefusedError(Exception):
    """One scene could not be uploaded; the other scenes of the call go on."""


# ── What a source holds ──────────────────────────────────────────────────────


def _is_scene_zip_member(name: str) -> bool:
    # Directory entries end in a slash; macOS zips add `__MACOSX/._x.pcd`
    # resource forks that are not frames.
    if name.endswith("/") or "__MACOSX" in name.split("/"):
        return False
    base = name.rsplit("/", 1)[-1].lower()
    return base == SCENE_MANIFEST_NAME or base.endswith(
        tuple(f".{extension}" for extension in CLOUD_EXTENSIONS)
    )


def _is_scene_zip(path: Path) -> bool:
    """Whether a ``.zip`` is a lidar scene: it lists a frame or a manifest.

    The browser's ``isPointcloudSceneZip``. Only the archive's directory is
    read, never a member, so this is cheap for a multi-gigabyte archive. A file
    that is not a zip, or cannot be read, is not a scene: a stray archive of
    photos must never become a failed scene item.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    return any(_is_scene_zip_member(name) for name in names)


def _is_scene_file(path: Path) -> bool:
    extension = _uploader.extension_for_filename(path.name)
    return (
        extension in CLOUD_EXTENSIONS
        or extension in RECORDING_EXTENSIONS
        or (extension == "zip" and _is_scene_zip(path))
    )


def _file_scene(path: Path) -> Scene:
    """The scene one file is: the file itself, uploaded as it is."""
    size = path.stat().st_size
    is_archive = _uploader.extension_for_filename(path.name) == "zip"
    return Scene(
        id=str(path),
        name=path.name,
        source="file",
        files=[SceneFile(path=path.name, source=path, size=size)],
        # One cloud file is one frame; an archive's frames are only known to
        # the server's ingest.
        frame_count=None if is_archive else 1,
        point_sensors=[],
        cameras=[],
        total_bytes=size,
    )


def detect_scenes(
    source: str | Path, *, split_sensor_folders: bool = False
) -> SceneDetection:
    """Find the lidar scenes ``source`` holds, without sending anything.

    This is what ``upload(source, generic_type="pointcloud")`` would upload,
    and the SDK's replacement for the browser's confirmation dialog: look at
    the result before sending gigabytes.

    Args:
        source: A scene file (``.zip``, ``.pcd``, ``.bin``, ``.ply``) or a
            directory. A directory is read by the browser's rules: a
            ``scene.json``, point clouds with their camera folders, one sensor
            per subfolder, or a nuScenes dataset (one scene per recording).
            Scene files left over in the directory are one scene each.
        split_sensor_folders: Several sensor folders that share file names are
            read as ONE scene with several sensors, the browser's default.
            File names cannot tell that apart from several recordings numbered
            alike; pass True to read each folder as a scene of its own. Scenes
            with such a second reading have ``split`` set.

    Returns:
        The scenes in upload order, ``unused_files`` (files inside scene
        folders that no scene uses) and ``other_files`` (files that are not
        part of any scene). Neither of the last two is uploaded.

    Raises:
        ValueError: ``source`` does not exist, is a file that is not a scene,
            or is a directory without any scene.
    """
    source_path = Path(source).expanduser()
    if source_path.is_file():
        extension = _uploader.extension_for_filename(source_path.name)
        if extension not in SCENE_FILE_EXTENSIONS:
            raise ValueError(f"{source_path.name}: {NOT_A_SCENE_FORMAT}")
        if extension == "zip" and not _is_scene_zip(source_path):
            raise ValueError(f"{source_path.name}: {NOT_A_SCENE_ZIP}")
        return SceneDetection(
            scenes=[_file_scene(source_path)],
            unused_files=0,
            other_files=[],
            datasets=[],
        )
    if not source_path.is_dir():
        raise ValueError(f"Source {source_path} does not exist")
    detection = detect_folder_scenes(source_path)
    scenes, unused_files = scenes_to_upload(
        detection, split_sensor_folders=split_sensor_folders
    )
    scenes = list(scenes)
    other_files = []
    for path in detection.other_files:
        # As in the browser: what the folder rules left over still goes up as
        # a scene of its own when it is a scene file.
        if _is_scene_file(path):
            scenes.append(_file_scene(path))
        else:
            other_files.append(path)
    if not scenes:
        raise ValueError(f"No lidar scene found in {source_path}. {NOT_A_SCENE_FORMAT}")
    return SceneDetection(
        scenes=scenes,
        unused_files=unused_files,
        other_files=other_files,
        datasets=detection.datasets,
    )


def _scene_path(scene: Scene) -> Path:
    """What an ``UploadFailure`` names: the file, or the scene by its name."""
    if scene.source == "file" and scene.files[0].source is not None:
        return scene.files[0].source
    # A dataset recording can come without a name; its id is always set.
    return Path(scene.name or scene.id)


# ── Sending one scene ────────────────────────────────────────────────────────


async def _api_post(
    client: httpx.AsyncClient, url: str, body: dict[str, Any]
) -> dict[str, Any]:
    """One control call of a scene upload; a refusal fails only this scene.

    401 and 403 raise instead (the key, the plan or a permission): they would
    refuse every other scene as well. 404 means the server has no scene routes.
    """
    try:
        response = await client.post(url, json=body)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise _SceneRefusedError(error_text(exc)) from exc
    if response.status_code in (401, 403):
        raise_for_response(response)
    if response.status_code == 404:
        raise _SceneRefusedError(UNSUPPORTED_SERVER)
    if response.status_code >= 400:
        raise _SceneRefusedError(_extract_error_message(response))
    return _uploader._response_json(response)


async def _upload_scene_file(
    api_client: httpx.AsyncClient,
    storage_client: httpx.AsyncClient,
    part_semaphore: asyncio.Semaphore,
    endpoint: str,
    scene: Scene,
    *,
    session_id: str | None,
    complete_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Send a one-file scene with the multipart helper tiled files use.

    The helper signals "use the plain upload instead" for a server without
    direct upload; for a scene that is a failure, never a fallback.
    """
    try:
        return await _uploader._upload_tiled_file(
            api_client,
            storage_client,
            part_semaphore,
            endpoint,
            scene.files[0].source,
            session_id=session_id,
            complete_fields=complete_fields,
        )
    except _uploader._FallbackToSimpleUploadError as exc:
        raise _SceneRefusedError(
            f"Lidar scene upload is not available on this server: {exc}"
        ) from exc
    except _uploader._TiledUploadRejectedError as exc:
        raise _SceneRefusedError(str(exc)) from exc
    except NetworkError as exc:
        # A part that would not upload fails this scene. Subclasses (an
        # ambiguous completion, a plan refusal) must stop the whole call.
        if type(exc) is not NetworkError:
            raise
        raise _SceneRefusedError(str(exc)) from exc


async def _put_scene_file(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    file: SceneFile,
    url_of: Callable[[str, str | None], Awaitable[str]],
) -> None:
    """PUT one file of a folder scene to its presigned URL, with retries.

    Sent without a ``Content-Type``, like multipart parts: a SigV2-signed URL
    (local MinIO) signs the type as empty and would answer 403 otherwise. A 403
    means the URL expired; ``url_of`` then asks the server for a fresh one.
    """
    last_error: Exception | None = None
    rejected_url = None
    for attempt in range(_uploader.TILED_PART_MAX_ATTEMPTS):
        try:
            async with semaphore:
                url = await url_of(file.path, rejected_url)
                response = await client.put(
                    url,
                    content=(
                        file.content
                        if file.content is not None
                        else _uploader._FilePartStream(file.source, 0, file.size)
                    ),
                    headers={"Content-Length": str(file.size)},
                )
                rejected_url = url if response.status_code == 403 else None
            response.raise_for_status()
            return
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt + 1 < _uploader.TILED_PART_MAX_ATTEMPTS:
                await asyncio.sleep(
                    _uploader.TILED_PART_RETRY_DELAY_SECONDS * (attempt + 1)
                )
    raise NetworkError(
        f"Upload of {file.path} failed: {error_text(last_error)}", last_error
    )


async def _upload_scene_folder(
    api_client: httpx.AsyncClient,
    storage_client: httpx.AsyncClient,
    endpoint: str,
    scene: Scene,
    *,
    session_id: str | None,
    complete_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Send a scene made of many files: initiate, URLs in batches, PUTs, complete.

    The browser's ``uploadPointcloudFolderScene``. The item is created by
    complete; until then the files only sit under the scene's own storage
    prefix, and a failure calls abort, which deletes them. Initiate carries the
    frame count the detection found, so a scene the ingest is certain to refuse
    (too many frames, more frames than data units left) is refused before a
    byte is sent.

    A failure of complete itself is ambiguous (the item may exist): nothing is
    aborted then, as for multipart uploads.
    """
    body: dict[str, Any] = {
        # The server requires a name; a dataset recording can lack one.
        "name": scene.name or "scene",
        "file_count": len(scene.files),
        "total_size": max(1, scene.total_bytes),
    }
    if scene.frame_count:
        body["frame_count"] = scene.frame_count
    if session_id:
        body["session_id"] = session_id
    initiated = await _api_post(api_client, f"{endpoint}/initiate/", body)
    upload_token = str(initiated.get("upload_token") or "")
    if not upload_token:
        raise _SceneRefusedError("Unexpected response: missing upload_token")

    urls: dict[str, str] = {}
    url_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(FOLDER_FILE_CONCURRENCY)

    async def request_urls(paths: list[str]) -> None:
        answer = await _api_post(
            api_client,
            f"{endpoint}/urls/",
            {"upload_token": upload_token, "paths": paths},
        )
        fresh = {str(entry["path"]): str(entry["url"]) for entry in answer["urls"]}
        for path in paths:
            if not fresh.get(path):
                raise NetworkError(f"No upload URL for {path}")
        urls.update(fresh)

    async def url_of(path: str, rejected_url: str | None) -> str:
        async with url_lock:
            if rejected_url is not None and urls[path] == rejected_url:
                await request_urls([path])
            return urls[path]

    try:
        batch = max(1, int(initiated.get("url_batch") or 500))
        for start in range(0, len(scene.files), batch):
            chunk = scene.files[start : start + batch]
            await request_urls([file.path for file in chunk])
            tasks = [
                asyncio.create_task(
                    _put_scene_file(storage_client, semaphore, file, url_of)
                )
                for file in chunk
            ]
            try:
                await asyncio.gather(*tasks)
            except Exception:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
    except (_SceneRefusedError, NetworkError, KeyError, TypeError, ValueError) as exc:
        await _uploader._abort_tiled_upload(api_client, endpoint, upload_token)
        if isinstance(exc, NetworkError) and type(exc) is not NetworkError:
            raise
        raise _SceneRefusedError(str(exc)) from exc

    try:
        response = await api_client.post(
            f"{endpoint}/complete/",
            json={"upload_token": upload_token, **(complete_fields or {})},
        )
        raise_for_response(response)
        return _uploader._response_json(response)
    except Exception as exc:
        raise AmbiguousUploadCompletionError(
            "The upload finished but its confirmation was lost. Check the data "
            "list before re-uploading; the scene may already be processing.",
            exc,
        ) from exc


# ── Sending every scene of a call ────────────────────────────────────────────


async def _upload_scenes(
    api,
    scenes: list[Scene],
    *,
    endpoint: str,
    session_id: str | None = None,
    complete_fields: Callable[[], dict[str, Any]] | None = None,
    response_error: Callable[[Any], str | None],
    show_progress: bool,
) -> UploadResult:
    """Upload ``scenes`` one after another and collect what happened to each.

    ``complete_fields`` is called per scene because the Data Assets destination
    changes after the first one (a folder name becomes the id the server
    resolved). ``response_error`` says whether a completion reply is usable.
    Scenes go one at a time: a scene already sends several files or parts at
    once.
    """
    responses: list[dict[str, Any]] = []
    failures: list[UploadFailure] = []
    progress = tqdm.tqdm(total=len(scenes), ncols=80, disable=not show_progress)
    try:
        part_semaphore = asyncio.Semaphore(_uploader.TILED_PART_CONCURRENCY)
        async with (
            api.async_client() as api_client,
            httpx.AsyncClient(timeout=600.0) as storage_client,
        ):
            for scene in scenes:
                fields = complete_fields() if complete_fields else None
                try:
                    if scene.source == "file":
                        payload = await _upload_scene_file(
                            api_client,
                            storage_client,
                            part_semaphore,
                            f"{endpoint}/pointcloud-uploads",
                            scene,
                            session_id=session_id,
                            complete_fields=fields,
                        )
                    else:
                        payload = await _upload_scene_folder(
                            api_client,
                            storage_client,
                            f"{endpoint}/pointcloud-folder-uploads",
                            scene,
                            session_id=session_id,
                            complete_fields=fields,
                        )
                    error = response_error(payload)
                except _SceneRefusedError as exc:
                    error = str(exc)
                if error:
                    failures.append(UploadFailure(_scene_path(scene), error))
                else:
                    responses.append(payload)
                progress.update(1)
    finally:
        progress.close()
    result = UploadResult(
        total=len(scenes),
        uploaded=len(responses),
        failed=failures,
        responses=responses,
    )
    if result.uploaded == 0:
        result.raise_on_failure()
    return result


def _project_response_error(payload: Any) -> str | None:
    if isinstance(payload, dict) and payload.get("datasource_id"):
        return None
    return "Unexpected response: missing datasource_id"


def upload_project_scenes(
    api,
    project_id: str,
    source: str | Path,
    *,
    split_sensor_folders: bool = False,
    show_progress: bool = True,
) -> tuple[UploadResult, str]:
    """Upload the scenes of ``source`` into a project's new Batch Queue.

    Returns what ``_uploader.upload_project`` returns, with one entry per
    scene. ``upload-info`` is read first: a server without scene upload, or a
    workspace where lidar is off, is named before the source is even scanned,
    and a scene over the size limit is a failure before upload.
    """
    upload_info = api.get(f"/api/sdk/projects/{project_id}/upload-info/")
    limits = upload_info.get("pointcloud")
    if not isinstance(limits, dict):
        raise UnitlabError(UNSUPPORTED_SERVER, code="pointcloud_unsupported")
    if not limits.get("enabled"):
        raise UnitlabError(
            "Point-cloud scenes are not enabled for this workspace.",
            code="pointcloud_not_enabled",
        )
    max_size = limits.get("max_file_size")
    scenes: list[Scene] = []
    too_large: list[UploadFailure] = []
    for scene in detect_scenes(
        source, split_sensor_folders=split_sensor_folders
    ).scenes:
        if max_size is not None and scene.total_bytes > int(max_size):
            too_large.append(
                UploadFailure(
                    _scene_path(scene),
                    f"Scene is {scene.total_bytes} bytes; "
                    f"maximum is {int(max_size)} bytes.",
                )
            )
        else:
            scenes.append(scene)
    if not scenes:
        UploadResult(
            total=len(too_large), uploaded=0, failed=too_large
        ).raise_on_failure()
    session_id = str(uuid.uuid4())
    result = _uploader.run_sync(
        _upload_scenes(
            api,
            scenes,
            endpoint=f"/api/sdk/projects/{project_id}",
            session_id=session_id,
            response_error=_project_response_error,
            show_progress=show_progress,
        )
    )
    result.total += len(too_large)
    result.failed = too_large + result.failed
    return result, session_id


def upload_asset_scenes(
    api,
    source: str | Path,
    *,
    folder: str | None = None,
    folder_id: str | None = None,
    path: str | None = None,
    tags: list[str] | None = None,
    custom_metadata: dict[str, Any] | None = None,
    split_sensor_folders: bool = False,
    show_progress: bool = True,
) -> tuple[UploadResult, str, str]:
    """Upload the scenes of ``source`` into workspace Assets.

    Returns what ``_uploader.upload_assets`` returns. The destination travels
    with each completion; the first scene may name a folder to create, the
    following ones use the id the server answered with. There is no
    ``upload-info`` without a project, so limits and the lidar gate are the
    server's refusal at initiate, before any byte is sent.
    """
    if folder and folder_id:
        raise ValueError("Use folder or folder_id, not both.")
    scenes = detect_scenes(source, split_sensor_folders=split_sensor_folders).scenes
    if not folder and not folder_id:
        folder = "Untitled upload"
    destination = {"folder": folder, "folder_id": folder_id, "folder_name": ""}

    def complete_fields() -> dict[str, Any]:
        return _uploader._asset_complete_data(
            folder=destination["folder"],
            folder_id=destination["folder_id"],
            path=path,
            tags=tags,
            custom_metadata=custom_metadata,
        )

    def response_error(payload: Any) -> str | None:
        error = _uploader._asset_response_error(payload, destination["folder_id"])
        if error is None:
            destination.update(
                folder=None,
                folder_id=str(payload["folder_id"]),
                folder_name=str(payload.get("folder_name", "")),
            )
        return error

    result = _uploader.run_sync(
        _upload_scenes(
            api,
            scenes,
            endpoint="/api/sdk/data-assets",
            complete_fields=complete_fields,
            response_error=response_error,
            show_progress=show_progress,
        )
    )
    return result, str(destination["folder_id"] or ""), destination["folder_name"]
