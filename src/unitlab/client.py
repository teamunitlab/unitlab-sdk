from __future__ import annotations

import asyncio
import functools
import logging
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import tqdm

from ._config import get_api_key, get_api_url
from .exceptions import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
    SubscriptionError,
    TimeoutError,
)

logger = logging.getLogger(__name__)

_UPLOAD_CONCURRENCY = 20
_DOWNLOAD_CONCURRENCY = 50


def _extract_error_message(response: httpx.Response) -> str:
    """Extract a human-readable message from an error response."""
    try:
        body = response.json()
        if isinstance(body, dict):
            for key in ("detail", "message"):
                if key in body:
                    return str(body[key])
            parts = []
            for field, errors in body.items():
                if isinstance(errors, list):
                    parts.append(f"{field}: {', '.join(str(e) for e in errors)}")
                else:
                    parts.append(f"{field}: {errors}")
            if parts:
                return "; ".join(parts)
    except (ValueError, KeyError):
        pass
    return response.text


def handle_exceptions(f):
    """Catch exceptions and throw Unitlab exceptions."""

    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            r = f(self, *args, **kwargs)
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException as e:
            raise TimeoutError(message=str(e), detail=e) from e
        except httpx.HTTPStatusError as e:
            text = _extract_error_message(e.response)
            if e.response.status_code == 401:
                raise AuthenticationError(
                    message="Authentication failed", detail=e
                ) from e
            if e.response.status_code == 403:
                msg = f"Forbidden: {e.response.status_code} {e.response.reason_phrase}"
                raise SubscriptionError(message=msg, detail=e) from e
            if e.response.status_code == 404 or "not found" in text.lower():
                raise NotFoundError(message=text, detail=e) from e
            raise NetworkError(message=text, detail=e) from e
        except ValueError as e:
            raise NetworkError(message="Unexpected response format", detail=e) from e
        except httpx.HTTPError as e:
            raise NetworkError(message=str(e), detail=e) from e

    return wrapper


def _safe_path(base: str, untrusted: str) -> str:
    """Resolve *untrusted* relative to *base* and reject path traversal."""
    base = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base, untrusted))
    if not target.startswith(base + os.sep) and target != base:
        raise ValueError(f"Path traversal detected: {untrusted!r}")
    return target


class UnitlabClient:
    """A client with a connection to the Unitlab.ai platform.

    Note:
        Please refer to the `Python SDK quickstart
        <https://docs.unitlab.ai/cli-python-sdk/unitlab-python-sdk>`__
        for a full example of working with the Python SDK.

    First install the SDK.

    .. code-block:: bash

        pip install --upgrade unitlab

    Import the ``unitlab`` package in your python file and set up
    a client with an API key. An API key can be created on
    `unitlab.ai <https://unitlab.ai/>`__.

    .. code-block:: python

        from unitlab import UnitlabClient
        api_key = 'YOUR_API_KEY'
        client = UnitlabClient(api_key)

    Or store your Unitlab API key in your environment
    (``UNITLAB_API_KEY = 'YOUR_API_KEY'``):

    .. code-block:: python

        from unitlab import UnitlabClient
        client = UnitlabClient()

    Args:
        api_key: Your Unitlab.ai API key. If not given, reads
            ``UNITLAB_API_KEY`` from the environment, then falls
            back to the config file. Defaults to :obj:`None`.
        api_url: Base URL for the Unitlab API. Falls back to
            the configured URL or ``https://api.unitlab.ai``.
    Raises:
        :exc:`~unitlab.exceptions.AuthenticationError`: If no
            API key can be resolved from any source.
    """

    def __init__(self, api_key: str | None = None, api_url: str | None = None) -> None:
        self.api_key: str = (
            api_key or os.environ.get("UNITLAB_API_KEY") or get_api_key()
        )
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Pass api_key, set UNITLAB_API_KEY, "
                "or run `unitlab configure`."
            )
        self.api_url: str = (
            api_url or os.environ.get("UNITLAB_API_URL") or get_api_url()
        )
        self._client = httpx.Client(
            base_url=self.api_url,
            headers={"Authorization": f"Api-Key {self.api_key}"},
            transport=httpx.HTTPTransport(retries=3),
            timeout=60.0,
        )

    def close(self) -> None:
        """Close :class:`UnitlabClient` connections.

        You can manually close the Unitlab client's connections:

        .. code-block:: python

            client = UnitlabClient()
            client.projects()
            client.close()

        Or use the client as a context manager:

        .. code-block:: python

            with UnitlabClient() as client:
                client.projects()
        """
        self._client.close()

    def __enter__(self) -> UnitlabClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()

    @handle_exceptions
    def _get(self, endpoint: str) -> httpx.Response:
        return self._client.get(endpoint)

    @handle_exceptions
    def _post(
        self, endpoint: str, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        return self._client.post(endpoint, json=data if data is not None else {})

    def projects(self, pretty: int = 0) -> Any:
        return self._get(f"/api/sdk/projects/?pretty={pretty}")

    def project(self, project_id: str, pretty: int = 0) -> Any:
        return self._get(f"/api/sdk/projects/{project_id}/?pretty={pretty}")

    def project_members(self, project_id: str, pretty: int = 0) -> Any:
        return self._get(f"/api/sdk/projects/{project_id}/members/?pretty={pretty}")

    def project_upload_info(self, project_id: str) -> Any:
        return self._get(f"/api/sdk/projects/{project_id}/upload-info/")

    def project_upload_data(
        self,
        project_id: str,
        directory: str | Path,
        batch_size: int = 100,
        sentences_per_chunk: int = 10,
        fps: float = 1.0,
    ) -> None:
        directory = str(directory)
        if not os.path.isdir(directory):
            raise ValueError(f"Directory {directory} does not exist")

        upload_info = self.project_upload_info(project_id)
        accepted_formats: set[str] = set(upload_info["accepted_formats"])
        max_file_size_bytes: int = upload_info["max_file_size"]
        generic_type: str = upload_info["generic_type"]

        # Single-pass file discovery with os.scandir
        files: list[str] = []
        with os.scandir(directory) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                ext = entry.name.rsplit(".", 1)[-1] if "." in entry.name else ""
                if ext.lower() in accepted_formats:
                    files.append(entry.path)

        filtered_files: list[str] = []
        max_file_size_mb = max_file_size_bytes / 1024 / 1024
        for file in files:
            file_size_bytes = os.path.getsize(file)
            if file_size_bytes > max_file_size_bytes:
                file_size_mb = file_size_bytes / 1024 / 1024
                logger.warning(
                    f"File {file} is too large "
                    f"({file_size_mb:.4f} MB) skipping, "
                    f"max size is {max_file_size_mb:.2f} MB"
                )
                continue
            filtered_files.append(file)

        num_files = len(filtered_files)
        num_batches = (num_files + batch_size - 1) // batch_size
        semaphore = asyncio.Semaphore(_UPLOAD_CONCURRENCY)

        # Medical projects use session-based upload with finalize
        session_id = str(uuid.uuid4()) if generic_type == "medical" else None

        async def post_file(
            client: httpx.AsyncClient, file: str, project_id: str
        ) -> int:
            async with semaphore:
                extra_data: dict[str, str] = {}
                if generic_type == "text":
                    extra_data["sentences_per_chunk"] = str(sentences_per_chunk)
                elif generic_type == "video":
                    extra_data["fps"] = str(fps)
                if session_id:
                    extra_data["session_id"] = session_id

                try:
                    with open(file, "rb") as f:
                        response = await client.post(
                            f"/api/sdk/projects/{project_id}/upload-data/",
                            files={"file": (os.path.basename(file), f)},
                            data=extra_data,
                        )
                        response.raise_for_status()
                        return 1
                except Exception as e:
                    logger.error(f"Error uploading file {file} - {e}")
                    return 0

        async def main() -> None:
            logger.info(f"Uploading {num_files} files to project {project_id}")
            with tqdm.tqdm(total=num_files, ncols=80) as pbar:
                async with httpx.AsyncClient(
                    base_url=self.api_url,
                    headers={"Authorization": f"Api-Key {self.api_key}"},
                    timeout=600.0,
                ) as client:
                    for i in range(num_batches):
                        tasks = [
                            post_file(client=client, file=file, project_id=project_id)
                            for file in filtered_files[
                                i * batch_size : min((i + 1) * batch_size, num_files)
                            ]
                        ]
                        for f in asyncio.as_completed(tasks):
                            pbar.update(await f)

                    # Finalize medical session after all uploads
                    if session_id:
                        response = await client.post(
                            f"/api/sdk/projects/{project_id}/"
                            f"medical-upload-sessions/{session_id}/finalize/",
                        )
                        response.raise_for_status()
                        logger.info("Medical session finalized")

        asyncio.run(main())

    def datasets(self, pretty: int = 0) -> Any:
        return self._get(f"/api/sdk/datasets/?pretty={pretty}")

    def dataset_download(
        self,
        dataset_id: str,
        export_type: str,
        split_type: str | None = None,
    ) -> str:
        data: dict[str, Any] = {
            "download_type": "annotation",
            "export_type": export_type,
        }
        if split_type is not None:
            data["split_type"] = split_type

        response = self._post(f"/api/sdk/datasets/{dataset_id}/", data=data)

        file_url = response["file"]
        try:
            with httpx.stream("GET", file_url, timeout=300.0) as r:
                r.raise_for_status()

                parsed_url = urlparse(file_url)
                filename = os.path.basename(parsed_url.path)

                with open(filename, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
                logger.info(f"File: {os.path.abspath(filename)}")
                return os.path.abspath(filename)
        except httpx.HTTPError as e:
            raise NetworkError(message=f"Failed to download file: {e}", detail=e) from e

    def dataset_download_files(self, dataset_id: str) -> str:
        """Download files from a dataset.

        Args:
            dataset_id: UUID of the dataset/release to download.

        Returns:
            Path to the download folder.
        """
        response = self._post(
            f"/api/sdk/datasets/{dataset_id}/", data={"download_type": "files"}
        )
        base_folder = str(dataset_id)
        os.makedirs(base_folder, exist_ok=True)

        files_to_download: list[dict[str, str]] = []
        for dataset_file in response:
            file_name: str = dataset_file["file_name"]
            file_path = _safe_path(base_folder, file_name)

            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            if "content" in dataset_file:
                if not os.path.isfile(file_path):
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(dataset_file["content"])
            elif "source" in dataset_file and not os.path.isfile(file_path):
                files_to_download.append(
                    {
                        "file_name": file_name,
                        "source": dataset_file["source"],
                        "file_path": file_path,
                    }
                )

        if not files_to_download:
            return base_folder

        semaphore = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)

        async def download_file(
            client: httpx.AsyncClient, dataset_file: dict[str, str]
        ) -> int:
            async with semaphore:
                try:
                    async with client.stream("GET", dataset_file["source"]) as r:
                        r.raise_for_status()
                        with open(dataset_file["file_path"], "wb") as f:
                            async for chunk in r.aiter_bytes():
                                f.write(chunk)
                        return 1
                except Exception as e:
                    logger.error(
                        f"Error downloading file {dataset_file['file_name']} - {e}"
                    )
                    return 0

        async def main() -> None:
            with tqdm.tqdm(total=len(files_to_download), ncols=80) as pbar:
                async with httpx.AsyncClient(
                    timeout=600.0, follow_redirects=True
                ) as client:
                    tasks = [
                        download_file(client=client, dataset_file=df)
                        for df in files_to_download
                    ]
                    for f in asyncio.as_completed(tasks):
                        pbar.update(await f)

        asyncio.run(main())
        return base_folder
