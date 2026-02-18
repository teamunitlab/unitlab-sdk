from __future__ import annotations

import asyncio
import functools
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
import requests
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


def handle_exceptions(f):
    """Catch exceptions and throw Unitlab exceptions."""

    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            r = f(self, *args, **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout as e:
            raise TimeoutError(message=str(e), detail=e) from e
        except requests.exceptions.HTTPError as e:
            text = e.response.text.lower()
            if e.response.status_code == 401:
                raise AuthenticationError(
                    message="Authentication failed", detail=e
                ) from e
            if e.response.status_code == 403:
                raise SubscriptionError(
                    message=f"Forbidden: {e.response.status_code} {e.response.reason}",
                    detail=e,
                ) from e
            if "not found" in text:
                raise NotFoundError(message=text, detail=e) from e
            raise NetworkError(message=text, detail=e) from e
        except requests.exceptions.RequestException as e:
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
        self.api_session = requests.Session()
        self.api_session.headers["Authorization"] = f"Api-Key {self.api_key}"
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.api_session.mount("http://", adapter)
        self.api_session.mount("https://", adapter)

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
        self.api_session.close()

    def __enter__(self) -> UnitlabClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Api-Key {self.api_key}"}

    @handle_exceptions
    def _get(self, endpoint: str) -> requests.Response:
        return self.api_session.get(urljoin(self.api_url, endpoint))

    @handle_exceptions
    def _post(
        self, endpoint: str, data: dict[str, Any] | None = None
    ) -> requests.Response:
        return self.api_session.post(
            urljoin(self.api_url, endpoint),
            json=data if data is not None else {},
        )

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

        async def post_file(
            session: aiohttp.ClientSession, file: str, project_id: str
        ) -> int:
            async with semaphore, aiofiles.open(file, "rb") as f:
                form_data = aiohttp.FormData()
                form_data.add_field(
                    "file", await f.read(), filename=os.path.basename(file)
                )
                if generic_type == "text":
                    form_data.add_field("sentences_per_chunk", str(sentences_per_chunk))
                elif generic_type == "video":
                    form_data.add_field("fps", str(fps))

                try:
                    async with session.post(
                        urljoin(
                            self.api_url, f"/api/sdk/projects/{project_id}/upload-data/"
                        ),
                        data=form_data,
                    ) as response:
                        response.raise_for_status()
                        return 1
                except Exception as e:
                    logger.error(f"Error uploading file {file} - {e}")
                    return 0

        async def main() -> None:
            logger.info(f"Uploading {num_files} files to project {project_id}")
            with tqdm.tqdm(total=num_files, ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_headers()
                ) as session:
                    for i in range(num_batches):
                        tasks = []
                        for file in filtered_files[
                            i * batch_size : min((i + 1) * batch_size, num_files)
                        ]:
                            tasks.append(
                                post_file(
                                    session=session, file=file, project_id=project_id
                                )
                            )
                        for f in asyncio.as_completed(tasks):
                            pbar.update(await f)

        asyncio.run(main())

    def datasets(self, pretty: int = 0) -> Any:
        return self._get(f"/api/sdk/datasets/?pretty={pretty}")

    def dataset_download(
        self, dataset_id: str, export_type: str, split_type: str
    ) -> str:
        response = self._post(
            f"/api/sdk/datasets/{dataset_id}/",
            data={
                "download_type": "annotation",
                "export_type": export_type,
                "split_type": split_type,
            },
        )

        with requests.get(url=response["file"], stream=True) as r:
            r.raise_for_status()

            parsed_url = urlparse(response["file"])
            filename = os.path.basename(parsed_url.path)

            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            logger.info(f"File: {os.path.abspath(filename)}")
            return os.path.abspath(filename)

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
            session: aiohttp.ClientSession, dataset_file: dict[str, str]
        ) -> int:
            async with semaphore, session.get(url=dataset_file["source"]) as r:
                try:
                    r.raise_for_status()
                except Exception as e:
                    logger.error(
                        f"Error downloading file {dataset_file['file_name']} - {e}"
                    )
                    return 0
                async with aiofiles.open(dataset_file["file_path"], "wb") as f:
                    async for chunk in r.content.iter_any():
                        await f.write(chunk)
                    return 1

        async def main() -> None:
            with tqdm.tqdm(total=len(files_to_download), ncols=80) as pbar:
                async with aiohttp.ClientSession() as session:
                    tasks = [
                        download_file(session=session, dataset_file=df)
                        for df in files_to_download
                    ]
                    for f in asyncio.as_completed(tasks):
                        pbar.update(await f)

        asyncio.run(main())
        return base_folder
