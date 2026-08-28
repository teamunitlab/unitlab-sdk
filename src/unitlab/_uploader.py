from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
import tqdm

from ._http import _extract_error_message, raise_for_response
from .exceptions import (
    AmbiguousUploadCompletionError,
    NetworkError,
    SubscriptionError,
)
from .types import UploadFailure, UploadResult

UPLOAD_CONCURRENCY = 20
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 5
TILED_PART_CONCURRENCY = 3
TILED_PART_MAX_ATTEMPTS = 3
TILED_PART_RETRY_DELAY_SECONDS = 2
TILED_MULTIPART_MIN_TIFF_BYTES = 8 * 1024 * 1024
AMBIGUOUS_TIFF_EXTENSIONS = {"tif", "tiff"}
GEOSPATIAL_TILED_EXTENSIONS = {
    "jp2",
    "cog",
    "geotiff",
    "gtif",
    "gtiff",
    "img",
    "ntf",
    "nitf",
}
# BIF and AVS require the backend's OpenSlide 4.0.1+ image contract.
PATHOLOGY_TILED_EXTENSIONS = {
    "svs",
    "avs",
    "ndpi",
    "scn",
    "bif",
    "svslide",
    "tf2",
    "tf8",
    "btf",
}
TILED_EXTENSIONS = (
    AMBIGUOUS_TIFF_EXTENSIONS | GEOSPATIAL_TILED_EXTENSIONS | PATHOLOGY_TILED_EXTENSIONS
)

EXTENSIONS_BY_GENERIC_TYPE: dict[str, set[str]] = {
    "img": {"jpg", "png", "jpeg", "webp", "gif", "bmp", "ico", "svg"},
    "text": {"txt"},
    "html": {"html", "htm"},
    "video": {"mp4", "avi", "mov", "webm", "mkv", "m4v", "wmv", "flv"},
    "audio": {"mp3", "wav", "ogg", "aac", "flac", "m4a"},
    "medical": {"dcm", "nii", "nii.gz", "nrrd"},
    "document": {"pdf"},
    "timeseries": {"csv"},
    "geospatial": AMBIGUOUS_TIFF_EXTENSIONS | GEOSPATIAL_TILED_EXTENSIONS,
    "pathology": PATHOLOGY_TILED_EXTENSIONS,
}


def extension_for_filename(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".nii.gz"):
        return "nii.gz"
    return name.rsplit(".", 1)[-1] if "." in name else ""


def detect_generic_type(filename: str) -> str | None:
    extension = extension_for_filename(filename)
    if extension in AMBIGUOUS_TIFF_EXTENSIONS:
        return None
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


class _FallbackToSimpleUploadError(Exception):
    pass


class _TiledUploadRejectedError(Exception):
    pass


class _FilePartStream(httpx.AsyncByteStream):
    def __init__(self, path: Path, start: int, size: int):
        self.path = path
        self.start = start
        self.size = size

    async def __aiter__(self):
        remaining = self.size
        with self.path.open("rb") as handle:
            handle.seek(self.start)
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise OSError(f"Unexpected end of file: {self.path}")
                remaining -= len(chunk)
                yield chunk


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise NetworkError("Unexpected response format", exc) from exc
    if not isinstance(payload, dict):
        raise NetworkError("Unexpected response format")
    return payload


def _can_fallback_from_initiate(response: httpx.Response) -> bool:
    if response.status_code == 404:
        return True
    return not response.is_success and (
        "direct_upload_unavailable" in _extract_error_message(response)
    )


def _should_use_tiled_multipart(path: Path) -> bool:
    extension = extension_for_filename(path.name)
    if extension not in TILED_EXTENSIONS:
        return False
    return extension not in AMBIGUOUS_TIFF_EXTENSIONS or (
        path.stat().st_size > TILED_MULTIPART_MIN_TIFF_BYTES
    )


async def _put_tiled_part(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    path: Path,
    *,
    url: str,
    start: int,
    size: int,
) -> str:
    last_error: Exception | None = None
    for attempt in range(TILED_PART_MAX_ATTEMPTS):
        try:
            async with semaphore:
                response = await client.put(
                    url,
                    content=_FilePartStream(path, start, size),
                    headers={"Content-Length": str(size)},
                )
            response.raise_for_status()
            etag = response.headers.get("etag")
            if not etag:
                raise NetworkError("Part upload returned no ETag.")
            return etag.strip('"')
        except (httpx.HTTPError, OSError, NetworkError) as exc:
            last_error = exc
            if attempt + 1 < TILED_PART_MAX_ATTEMPTS:
                await asyncio.sleep(TILED_PART_RETRY_DELAY_SECONDS * (attempt + 1))
    raise NetworkError(f"Multipart part upload failed: {last_error}", last_error)


async def _abort_tiled_upload(
    client: httpx.AsyncClient,
    endpoint: str,
    upload_token: str,
) -> None:
    with suppress(httpx.HTTPError, httpx.TimeoutException):
        await client.post(f"{endpoint}/abort/", json={"upload_token": upload_token})


async def _upload_tiled_file(
    api_client: httpx.AsyncClient,
    storage_client: httpx.AsyncClient,
    part_semaphore: asyncio.Semaphore,
    endpoint: str,
    path: Path,
    *,
    session_id: str | None = None,
    complete_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    file_size = path.stat().st_size
    initiate = {
        "file_name": path.name,
        "file_size": file_size,
    }
    if session_id:
        initiate["session_id"] = session_id
    try:
        response = await api_client.post(f"{endpoint}/initiate/", json=initiate)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise _TiledUploadRejectedError(str(exc)) from exc
    if _can_fallback_from_initiate(response):
        raise _FallbackToSimpleUploadError(_extract_error_message(response))
    if response.status_code in (401, 403):
        raise_for_response(response)
    if response.status_code >= 400:
        raise _TiledUploadRejectedError(_extract_error_message(response))
    initiated = _response_json(response)
    upload_token = str(initiated.get("upload_token") or "")
    try:
        part_size = int(initiated["part_size"])
        part_urls = list(initiated["part_urls"])
        if not upload_token or part_size < 1 or not part_urls:
            raise ValueError("missing multipart fields")
        part_urls.sort(key=lambda part: int(part["part_number"]))
        if [int(part["part_number"]) for part in part_urls] != list(
            range(1, len(part_urls) + 1)
        ):
            raise ValueError("invalid multipart part numbers")
        if len(part_urls) != max(1, (file_size + part_size - 1) // part_size) or any(
            not part.get("url") for part in part_urls
        ):
            raise ValueError("invalid multipart part URLs")
        part_tasks = [
            asyncio.create_task(
                _put_tiled_part(
                    storage_client,
                    part_semaphore,
                    path,
                    url=str(part["url"]),
                    start=(int(part["part_number"]) - 1) * part_size,
                    size=min(
                        part_size,
                        file_size - (int(part["part_number"]) - 1) * part_size,
                    ),
                )
            )
            for part in part_urls
        ]
        try:
            parts = await asyncio.gather(*part_tasks)
        except Exception:
            for task in part_tasks:
                task.cancel()
            await asyncio.gather(*part_tasks, return_exceptions=True)
            raise
    except (KeyError, TypeError, ValueError, NetworkError) as exc:
        if upload_token:
            await _abort_tiled_upload(api_client, endpoint, upload_token)
        if isinstance(exc, NetworkError):
            raise
        raise NetworkError(
            f"Invalid multipart initiation response: {exc}", exc
        ) from exc

    completion = {
        "upload_token": upload_token,
        "parts": [
            {"part_number": int(part["part_number"]), "etag": etag}
            for part, etag in zip(part_urls, parts, strict=True)
        ],
        **(complete_fields or {}),
    }
    try:
        response = await api_client.post(f"{endpoint}/complete/", json=completion)
        raise_for_response(response)
        return _response_json(response)
    except Exception as exc:
        raise AmbiguousUploadCompletionError(
            "The upload finished but its confirmation was lost. Check the data "
            "list before re-uploading; the file may already be processing.",
            exc,
        ) from exc


async def _upload_file(
    api_client: httpx.AsyncClient,
    storage_client: httpx.AsyncClient,
    part_semaphore: asyncio.Semaphore,
    path: Path,
    *,
    simple_endpoint: str,
    simple_data: dict[str, Any],
    tiled_endpoint: str,
    session_id: str | None = None,
    complete_fields: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if _should_use_tiled_multipart(path):
        try:
            return (
                await _upload_tiled_file(
                    api_client,
                    storage_client,
                    part_semaphore,
                    tiled_endpoint,
                    path,
                    session_id=session_id,
                    complete_fields=complete_fields,
                ),
                None,
            )
        except _FallbackToSimpleUploadError:
            pass
        except _TiledUploadRejectedError as exc:
            return None, str(exc)
    return await _post_file(
        api_client,
        simple_endpoint,
        path,
        data=simple_data,
    )


async def _gather_uploads(tasks):
    """Let every started file settle before surfacing an uncertain completion."""
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            raise result
    return results


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
    generic_type: str | None = None,
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
        file_generic_type = (
            generic_type or detect_generic_type(path.name) or project_type
        )
        max_size = max_sizes.get(file_generic_type)
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
    generic_type: str | None,
    primary_column: str | None,
    batch_size: int,
    show_progress: bool,
) -> UploadResult:
    failures: list[UploadFailure] = []
    responses: list[dict[str, Any]] = []
    successful_medical = False
    batch_error: Exception | None = None
    chunk_size = max(1, min(UPLOAD_CONCURRENCY, batch_size))
    progress = tqdm.tqdm(total=len(files), ncols=80, disable=not show_progress)
    try:
        part_semaphore = asyncio.Semaphore(TILED_PART_CONCURRENCY)
        async with (
            api.async_client() as client,
            httpx.AsyncClient(timeout=600.0) as storage_client,
        ):
            for start in range(0, len(files), chunk_size):
                chunk = files[start : start + chunk_size]
                tasks = []
                generic_types = []
                for path in chunk:
                    file_generic_type = generic_type or detect_generic_type(path.name)
                    generic_types.append(file_generic_type)
                    fields = {"session_id": session_id}
                    if file_generic_type == "video":
                        fields["fps"] = str(fps)
                    if generic_type is not None:
                        fields["generic_type"] = generic_type
                    if primary_column is not None:
                        fields["primary_column"] = primary_column
                    tasks.append(
                        _upload_file(
                            client,
                            storage_client,
                            part_semaphore,
                            path,
                            simple_endpoint=(
                                f"/api/sdk/projects/{project_id}/upload-data/"
                            ),
                            simple_data=fields,
                            tiled_endpoint=(
                                f"/api/sdk/projects/{project_id}/tiled-uploads"
                            ),
                            session_id=session_id,
                        )
                    )
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for path, generic_type, result in zip(
                    chunk, generic_types, results, strict=True
                ):
                    progress.update(1)
                    if isinstance(result, Exception):
                        batch_error = batch_error or result
                        continue
                    payload, error = result
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
                if batch_error:
                    break
            if successful_medical:
                await _finalize_medical_upload(
                    client,
                    f"/api/sdk/projects/{project_id}/medical-upload-sessions/"
                    f"{session_id}/finalize/",
                    session_id,
                )
            if batch_error:
                raise batch_error
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
    generic_type: str | None = None,
    primary_column: str | None = None,
    batch_size: int = 100,
    show_progress: bool = True,
) -> tuple[UploadResult, str]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    upload_info = api.get(f"/api/sdk/projects/{project_id}/upload-info/")
    files, preflight_failures = _project_files(source, upload_info, generic_type)
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
            generic_type=generic_type,
            primary_column=primary_column,
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
    defer_timeseries_configuration: bool,
    generic_type: str | None,
    primary_column: str | None,
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
    if defer_timeseries_configuration:
        fields["defer_timeseries_configuration"] = "true"
    if generic_type is not None:
        fields["generic_type"] = generic_type
    if primary_column is not None:
        fields["primary_column"] = primary_column
    return fields


def _asset_complete_data(
    *,
    folder: str | None,
    folder_id: str | None,
    path: str | None,
    tags: list[str] | None,
    custom_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "folder_name": folder,
            "folder_id": folder_id,
            "path": path,
            "tags": tags,
            "custom_metadata": custom_metadata,
        }.items()
        if value is not None
    }


def _asset_response_error(
    payload: Any, expected_folder_id: str | None = None
) -> str | None:
    if not isinstance(payload, dict):
        return "Unexpected response format"
    folder_id = payload.get("folder_id")
    if not folder_id:
        return "Unexpected response: missing folder_id"
    if expected_folder_id and str(folder_id) != expected_folder_id:
        return "Unexpected response: wrong folder_id"
    if not isinstance(payload.get("asset"), dict):
        return "Unexpected response: missing asset"
    return None


async def _upload_assets_async(
    api,
    files: list[Path],
    *,
    folder: str | None,
    folder_id: str | None,
    path: str | None,
    tags: list[str] | None,
    custom_metadata: dict[str, Any] | None,
    defer_timeseries_configuration: bool,
    generic_type: str | None,
    primary_column: str | None,
    show_progress: bool,
) -> tuple[UploadResult, str, str]:
    failures: list[UploadFailure] = []
    responses: list[dict[str, Any]] = []
    resolved_folder_id = folder_id
    resolved_folder_name = folder or ""
    progress = tqdm.tqdm(total=len(files), ncols=80, disable=not show_progress)
    try:
        part_semaphore = asyncio.Semaphore(TILED_PART_CONCURRENCY)
        async with (
            api.async_client() as client,
            httpx.AsyncClient(timeout=600.0) as storage_client,
        ):
            remaining = list(files)
            while remaining and not resolved_folder_id:
                first = remaining.pop(0)
                payload, error = await _upload_file(
                    client,
                    storage_client,
                    part_semaphore,
                    first,
                    simple_endpoint="/api/sdk/data-assets/upload/",
                    simple_data=_asset_form_data(
                        folder=folder,
                        folder_id=None,
                        path=path,
                        tags=tags,
                        custom_metadata=custom_metadata,
                        defer_timeseries_configuration=defer_timeseries_configuration,
                        generic_type=generic_type,
                        primary_column=primary_column,
                    ),
                    tiled_endpoint="/api/sdk/data-assets/tiled-uploads",
                    complete_fields=_asset_complete_data(
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
                response_error = _asset_response_error(payload)
                if response_error:
                    failures.append(UploadFailure(first, response_error))
                    continue
                responses.append(payload)
                resolved_folder_id = str(payload["folder_id"])
                resolved_folder_name = str(payload.get("folder_name", folder or ""))

            for start in range(0, len(remaining), UPLOAD_CONCURRENCY):
                chunk = remaining[start : start + UPLOAD_CONCURRENCY]
                tasks = []
                for file_path in chunk:
                    tasks.append(
                        _upload_file(
                            client,
                            storage_client,
                            part_semaphore,
                            file_path,
                            simple_endpoint="/api/sdk/data-assets/upload/",
                            simple_data=_asset_form_data(
                                folder=None,
                                folder_id=resolved_folder_id,
                                path=path,
                                tags=tags,
                                custom_metadata=custom_metadata,
                                defer_timeseries_configuration=defer_timeseries_configuration,
                                generic_type=generic_type,
                                primary_column=primary_column,
                            ),
                            tiled_endpoint="/api/sdk/data-assets/tiled-uploads",
                            complete_fields=_asset_complete_data(
                                folder=None,
                                folder_id=resolved_folder_id,
                                path=path,
                                tags=tags,
                                custom_metadata=custom_metadata,
                            ),
                        )
                    )
                for file_path, (payload, error) in zip(
                    chunk, await _gather_uploads(tasks), strict=True
                ):
                    progress.update(1)
                    if error:
                        failures.append(UploadFailure(file_path, error))
                    else:
                        payload = payload or {}
                        response_error = _asset_response_error(
                            payload, resolved_folder_id
                        )
                        if response_error:
                            failures.append(UploadFailure(file_path, response_error))
                        else:
                            responses.append(payload)
    finally:
        progress.close()
    result = UploadResult(
        total=len(files),
        uploaded=len(responses),
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
    defer_timeseries_configuration: bool = False,
    generic_type: str | None = None,
    primary_column: str | None = None,
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
            defer_timeseries_configuration=defer_timeseries_configuration,
            generic_type=generic_type,
            primary_column=primary_column,
            show_progress=show_progress,
        )
    )
