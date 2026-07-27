from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
import tqdm

from ._http import _extract_error_message, raise_for_response
from .exceptions import NetworkError, SubscriptionError
from .types import UploadFailure, UploadResult

UPLOAD_CONCURRENCY = 20
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 5

EXTENSIONS_BY_GENERIC_TYPE: dict[str, set[str]] = {
    "img": {"jpg", "png", "jpeg", "webp", "gif", "bmp", "ico", "svg"},
    "text": {"txt"},
    "video": {"mp4", "avi", "mov", "webm", "mkv", "m4v", "wmv", "flv"},
    "audio": {"mp3", "wav", "ogg", "aac", "flac", "m4a"},
    "medical": {"dcm", "nii", "nii.gz", "nrrd"},
    "document": {"pdf"},
}


def extension_for_filename(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".nii.gz"):
        return "nii.gz"
    return name.rsplit(".", 1)[-1] if "." in name else ""


def detect_generic_type(filename: str) -> str | None:
    extension = extension_for_filename(filename)
    for generic_type, extensions in EXTENSIONS_BY_GENERIC_TYPE.items():
        if extension in extensions:
            return generic_type
    return None


def known_extensions() -> set[str]:
    return {value for values in EXTENSIONS_BY_GENERIC_TYPE.values() for value in values}


def collect_files(source: str | Path, accepted: set[str] | None = None) -> list[Path]:
    source_path = Path(source).expanduser()
    if source_path.is_file():
        candidates = [source_path]
    elif source_path.is_dir():
        candidates = sorted(path for path in source_path.rglob("*") if path.is_file())
    else:
        raise ValueError(f"Source {source_path} does not exist")
    allowed = accepted if accepted is not None else known_extensions()
    return [path for path in candidates if extension_for_filename(path.name) in allowed]


def run_sync(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


async def _post_file(
    client: httpx.AsyncClient,
    endpoint: str,
    path: Path,
    *,
    data: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("rb") as handle:
            response = await client.post(
                endpoint,
                files={"file": (path.name, handle)},
                data=data,
            )
        if response.status_code in (401, 403):
            raise_for_response(response)
        if response.status_code >= 400:
            return None, _extract_error_message(response)
        raise_for_response(response)
        return response.json(), None
    except SubscriptionError:
        raise
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        return None, str(exc)
    except ValueError:
        return None, "Unexpected response format"


async def _finalize_medical_upload(client, endpoint: str, batch_queue_id: str) -> None:
    last_error = "Medical finalization failed."
    for attempt in range(RETRY_COUNT + 1):
        try:
            response = await client.post(endpoint)
            if response.status_code >= 500:
                last_error = _extract_error_message(response)
                if attempt < RETRY_COUNT:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                break
            raise_for_response(response)
            return
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_error = str(exc)
            if attempt < RETRY_COUNT:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            break
    raise NetworkError(
        f"Medical finalization failed for Batch Queue {batch_queue_id}: {last_error}"
    )


def _project_files(
    source: str | Path,
    upload_info: dict[str, Any],
) -> tuple[list[Path], list[UploadFailure]]:
    accepted = {
        str(value).lower().lstrip(".")
        for value in upload_info.get("accepted_formats", [])
    } or known_extensions()
    files = collect_files(source, accepted)
    max_sizes = {
        str(key): int(value)
        for key, value in (upload_info.get("max_file_sizes") or {}).items()
    }
    project_type = upload_info.get("generic_type")
    fallback = upload_info.get("max_file_size")
    result = []
    failures = []
    for path in files:
        generic_type = detect_generic_type(path.name) or project_type
        max_size = max_sizes.get(generic_type)
        if max_size is None and project_type and fallback is not None:
            max_size = int(fallback)
        if max_size is None or path.stat().st_size <= max_size:
            result.append(path)
        else:
            failures.append(
                UploadFailure(
                    path,
                    f"File is {path.stat().st_size} bytes; "
                    f"maximum is {max_size} bytes.",
                )
            )
    return result, failures


async def _upload_project_async(
    api,
    project_id: str,
    files: list[Path],
    *,
    session_id: str,
    fps: float,
    batch_size: int,
    show_progress: bool,
) -> UploadResult:
    failures: list[UploadFailure] = []
    responses: list[dict[str, Any]] = []
    successful_medical = False
    chunk_size = max(1, min(UPLOAD_CONCURRENCY, batch_size))
    progress = tqdm.tqdm(total=len(files), ncols=80, disable=not show_progress)
    try:
        async with api.async_client() as client:
            for start in range(0, len(files), chunk_size):
                chunk = files[start : start + chunk_size]
                tasks = []
                generic_types = []
                for path in chunk:
                    generic_type = detect_generic_type(path.name)
                    generic_types.append(generic_type)
                    fields = {"session_id": session_id}
                    if generic_type == "video":
                        fields["fps"] = str(fps)
                    tasks.append(
                        _post_file(
                            client,
                            f"/api/sdk/projects/{project_id}/upload-data/",
                            path,
                            data=fields,
                        )
                    )
                results = await asyncio.gather(*tasks)
                for path, generic_type, (payload, error) in zip(
                    chunk, generic_types, results, strict=True
                ):
                    progress.update(1)
                    if error:
                        failures.append(UploadFailure(path, error))
                        continue
                    payload = payload or {}
                    if not payload.get("datasource_id"):
                        failures.append(
                            UploadFailure(
                                path,
                                str(
                                    payload.get("message")
                                    or "Unexpected response: missing datasource_id"
                                ),
                            )
                        )
                        continue
                    responses.append(payload)
                    if generic_type == "medical" and payload.get("datasource_id"):
                        successful_medical = True
            if successful_medical:
                await _finalize_medical_upload(
                    client,
                    f"/api/sdk/projects/{project_id}/medical-upload-sessions/"
                    f"{session_id}/finalize/",
                    session_id,
                )
    finally:
        progress.close()
    result = UploadResult(
        total=len(files),
        uploaded=len(files) - len(failures),
        failed=failures,
        responses=responses,
    )
    if result.uploaded == 0:
        result.raise_on_failure()
    return result


def upload_project(
    api,
    project_id: str,
    source: str | Path,
    *,
    fps: float = 1.0,
    batch_size: int = 100,
    show_progress: bool = True,
) -> tuple[UploadResult, str]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    upload_info = api.get(f"/api/sdk/projects/{project_id}/upload-info/")
    files, preflight_failures = _project_files(source, upload_info)
    if not files and not preflight_failures:
        accepted = upload_info.get("accepted_formats") or sorted(known_extensions())
        raise ValueError(
            "No uploadable files found. Accepted extensions: "
            + ", ".join(sorted(str(value) for value in accepted))
        )
    if not files:
        UploadResult(
            total=len(preflight_failures),
            uploaded=0,
            failed=preflight_failures,
        ).raise_on_failure()
    session_id = str(uuid.uuid4())
    result = run_sync(
        _upload_project_async(
            api,
            project_id,
            files,
            session_id=session_id,
            fps=fps,
            batch_size=batch_size,
            show_progress=show_progress,
        )
    )
    result.total += len(preflight_failures)
    result.failed = preflight_failures + result.failed
    return result, session_id


def _asset_form_data(
    *,
    folder: str | None,
    folder_id: str | None,
    path: str | None,
    tags: list[str] | None,
    custom_metadata: dict[str, Any] | None,
) -> dict[str, str | list[str]]:
    fields: dict[str, str | list[str]] = {}
    if folder:
        fields["folder_name"] = folder
    if folder_id:
        fields["folder_id"] = folder_id
    if path:
        fields["path"] = path
    if tags:
        fields["tags"] = tags
    if custom_metadata is not None:
        fields["custom_metadata"] = json.dumps(
            custom_metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return fields


async def _upload_assets_async(
    api,
    files: list[Path],
    *,
    folder: str | None,
    folder_id: str | None,
    path: str | None,
    tags: list[str] | None,
    custom_metadata: dict[str, Any] | None,
    show_progress: bool,
) -> tuple[UploadResult, str, str]:
    failures: list[UploadFailure] = []
    responses: list[dict[str, Any]] = []
    resolved_folder_id = folder_id
    resolved_folder_name = folder or ""
    progress = tqdm.tqdm(total=len(files), ncols=80, disable=not show_progress)
    try:
        async with api.async_client() as client:
            remaining = list(files)
            while remaining and not resolved_folder_id:
                first = remaining.pop(0)
                payload, error = await _post_file(
                    client,
                    "/api/sdk/data-assets/upload/",
                    first,
                    data=_asset_form_data(
                        folder=folder,
                        folder_id=None,
                        path=path,
                        tags=tags,
                        custom_metadata=custom_metadata,
                    ),
                )
                progress.update(1)
                if error:
                    failures.append(UploadFailure(first, error))
                    continue
                payload = payload or {}
                if not isinstance(payload, dict) or not payload.get("folder_id"):
                    failures.append(
                        UploadFailure(first, "Unexpected response: missing folder_id")
                    )
                    continue
                responses.append(payload)
                resolved_folder_id = str(payload["folder_id"])
                resolved_folder_name = str(payload.get("folder_name", folder or ""))

            for start in range(0, len(remaining), UPLOAD_CONCURRENCY):
                chunk = remaining[start : start + UPLOAD_CONCURRENCY]
                tasks = [
                    _post_file(
                        client,
                        "/api/sdk/data-assets/upload/",
                        file_path,
                        data=_asset_form_data(
                            folder=None,
                            folder_id=resolved_folder_id,
                            path=path,
                            tags=tags,
                            custom_metadata=custom_metadata,
                        ),
                    )
                    for file_path in chunk
                ]
                for file_path, (payload, error) in zip(
                    chunk, await asyncio.gather(*tasks), strict=True
                ):
                    progress.update(1)
                    if error:
                        failures.append(UploadFailure(file_path, error))
                    else:
                        responses.append(payload or {})
    finally:
        progress.close()
    result = UploadResult(
        total=len(files),
        uploaded=len(files) - len(failures),
        failed=failures,
        responses=responses,
    )
    if result.uploaded == 0:
        result.raise_on_failure()
    return result, str(resolved_folder_id), resolved_folder_name


def upload_assets(
    api,
    source: str | Path,
    *,
    folder: str | None = None,
    folder_id: str | None = None,
    path: str | None = None,
    tags: list[str] | None = None,
    custom_metadata: dict[str, Any] | None = None,
    show_progress: bool = True,
) -> tuple[UploadResult, str, str]:
    if folder and folder_id:
        raise ValueError("Use folder or folder_id, not both.")
    files = collect_files(source)
    if not files:
        raise ValueError("No supported files found in the source.")
    if not folder and not folder_id:
        folder = "Untitled upload"
    return run_sync(
        _upload_assets_async(
            api,
            files,
            folder=folder,
            folder_id=folder_id,
            path=path,
            tags=tags,
            custom_metadata=custom_metadata,
            show_progress=show_progress,
        )
    )
