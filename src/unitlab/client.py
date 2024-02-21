import asyncio
import glob
import logging
import os

import aiofiles
import aiohttp
import requests
import tqdm

from .dataset import DatasetUploadHandler
from .exceptions import AuthenticationError
from .utils import BASE_URL, ENDPOINTS, send_request

logger = logging.getLogger(__name__)


class UnitlabClient:
    """A client with a connection to the Unitlab.ai platform.

    Note:
        Please refer to the `Python SDK quickstart <https://docs.unitlab.ai/tutorials/python-sdk-quickstart>`__ for a full example of working with the Python SDK.

    First install the SDK.

    .. code-block:: bash

        pip install --upgrade unitlab

    Import the ``unitlab`` package in your python file and set up a client with an API key. An API key can be created on <https://unitlab.ai/>`__.

    .. code-block:: python

        from unitlab import UnitlabClient
        api_key = 'YOUR_API_KEY'
        client = UnitlabClient(api_key)

    Or store your Unitlab API key in your environment (``UNITLAB_API_KEY = 'YOUR_API_KEY'``):

    .. code-block:: python

        from unitlab import UnitlabClient
        client = UnitlabClient()

    Args:
        api_key: Your Unitlab.ai API key. If no API key given, reads ``UNITLAB_API_KEY`` from the environment. Defaults to :obj:`None`.
    Raises:
        :exc:`~unitlab.exceptions.AuthenticationError`: If an invalid API key is used or (when not passing the API key directly) if ``UNITLAB_API_KEY`` is not found in your environment.
    """

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.getenv("UNITLAB_API_KEY")
            if api_key is None:
                raise AuthenticationError(
                    message="Please provide the api_key argument or set UNITLAB_API_KEY in your environment."
                )
            logger.info("Found a Unitlab API key in your environment.")
        self.api_key = api_key
        self.api_session = requests.Session()
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

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

    def _get_headers(self):
        return {"Authorization": f"Api-Key {self.api_key}"} if self.api_key else None

    def projects(self):
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["projects"],
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def project(self, project_id):
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["project"].format(project_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def project_members(self, project_id):
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["project_members"].format(project_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def upload_data(self, project_id, directory, batch_size=100):
        if not os.path.isdir(directory):
            raise ValueError(f"Directory {directory} does not exist")

        # set correct host
        send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["check"],
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        URL = os.environ["UNITLAB_BASE_URL"] + ENDPOINTS["upload_data"]

        async def post_file(
            session: aiohttp.ClientSession, file: str, project_id: str, retries=3
        ):
            for _ in range(retries):
                try:
                    with open(file, "rb") as f:
                        response = await session.request(
                            "POST",
                            url=URL,
                            data=aiohttp.FormData(
                                fields={"project": project_id, "file": f}
                            ),
                        )
                        response.raise_for_status()
                        return 1 if response.status == 201 else 0
                except aiohttp.client_exceptions.ServerDisconnectedError as e:
                    logger.warning(f"Error: {e}: Retrying...")
                    await asyncio.sleep(0.1)
                    continue
                except Exception as e:
                    logger.error(f"Error uploading file {file} - {e}")
                    return 0

        async def batch_upload(
            session: aiohttp.ClientSession,
            batch: list,
            project_id: str,
            pbar: tqdm.tqdm,
        ):
            tasks = []
            for file in batch:
                tasks.append(
                    post_file(session=session, file=file, project_id=project_id)
                )
            for f in asyncio.as_completed(tasks):
                pbar.update(await f)

        async def main():
            files = [
                file
                for files_list in (
                    glob.glob(os.path.join(directory, "") + extension)
                    for extension in ["*jpg", "*png", "*jpeg", "*webp"]
                )
                for file in files_list
            ]
            filtered_files = []
            for file in files:
                file_size = os.path.getsize(file) / 1024 / 1024
                if file_size > 6:
                    logger.warning(
                        f"File {file} is too large ({file_size:.4f} megabytes) skipping, max size is 6 MB"
                    )
                    continue
                filtered_files.append(file)

            num_files = len(filtered_files)
            num_batches = (num_files + batch_size - 1) // batch_size

            logger.info(f"Uploading {num_files} files to project {project_id}")
            with tqdm.tqdm(total=num_files, ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_headers()
                ) as session:
                    for i in range(num_batches):
                        await batch_upload(
                            session,
                            filtered_files[
                                i * batch_size : min((i + 1) * batch_size, num_files)
                            ],
                            project_id,
                            pbar,
                        )

        asyncio.run(main())

    def datasets(self):
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["datasets"],
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def dataset_download(self, dataset_id, export_type):
        response = send_request(
            {
                "method": "POST",
                "endpoint": ENDPOINTS["dataset"].format(dataset_id),
                "headers": self._get_headers(),
                "json": {"download_type": "annotation", "export_type": export_type},
            },
            session=self.api_session,
        )
        with self.api_session.get(url=response.json()["file"], stream=True) as r:
            r.raise_for_status()
            filename = f"dataset-{dataset_id}.json"
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            logger.info(f"File: {os.path.abspath(filename)}")
            return os.path.abspath(filename)

    def download_dataset_files(self, dataset_id):
        response = send_request(
            {
                "method": "POST",
                "endpoint": ENDPOINTS["dataset"].format(dataset_id),
                "headers": self._get_headers(),
                "json": {"download_type": "files"},
            },
            session=self.api_session,
        )
        folder = f"dataset-files-{dataset_id}"
        os.makedirs(folder, exist_ok=True)
        dataset_files = [
            dataset_file
            for dataset_file in response.json()
            if not os.path.isfile(os.path.join(folder, dataset_file["file_name"]))
        ]

        async def download_file(session: aiohttp.ClientSession, dataset_file: dict):
            async with session.get(url=dataset_file["source"]) as r:
                try:
                    r.raise_for_status()
                except Exception as e:
                    logger.error(
                        f"Error downloading file {dataset_file['file_name']} - {e}"
                    )
                    return 0
                async with aiofiles.open(
                    os.path.join(folder, dataset_file["file_name"]), "wb"
                ) as f:
                    async for chunk in r.content.iter_any():
                        await f.write(chunk)
                    return 1

        async def main():
            async with aiohttp.ClientSession() as session:
                tasks = [
                    download_file(session=session, dataset_file=dataset_file)
                    for dataset_file in dataset_files
                ]
                with tqdm.tqdm(total=len(dataset_files), ncols=80) as pbar:
                    for f in asyncio.as_completed(tasks):
                        pbar.update(await f)

        asyncio.run(main())

    def create_dataset(self, name, annotation_type, categories):
        response = self.api_session.post(
            url=f"{BASE_URL}/api/sdk/datasets/create/",
            headers=self._get_headers(),
            json={
                "name": name,
                "annotation_type": annotation_type,
                "classes": [
                    {"name": category["name"], "value": category["id"]}
                    for category in categories
                ],
            },
        )
        response.raise_for_status()
        response = response.json()
        return response["pk"]

    def dataset_upload(
        self, name, annotation_type, annotation_path, data_path, batch_size=100
    ):
        import random

        handler = DatasetUploadHandler(annotation_type, annotation_path, data_path)
        dataset_id = self.create_dataset(name, annotation_type, handler.categories)
        img_ids = handler.getImgIds()
        random.shuffle(img_ids)
        image_ids = img_ids[:1000]
        num_batches = (len(image_ids) + batch_size - 1) // batch_size

        async def main():
            with tqdm.tqdm(total=len(image_ids), ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_headers()
                ) as session:
                    for i in range(num_batches):
                        tasks = []
                        for image_id in image_ids[
                            i * batch_size : min((i + 1) * batch_size, len(image_ids))
                        ]:
                            tasks.append(
                                handler.upload_image(session, dataset_id, image_id)
                            )
                        for f in asyncio.as_completed(tasks):
                            pbar.update(await f)

        asyncio.run(main())
        self.dataset_download(dataset_id, "COCO")
