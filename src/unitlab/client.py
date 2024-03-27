import asyncio
import glob
import logging
import os
import urllib.parse

import aiofiles
import aiohttp
import requests
import tqdm

from . import exceptions, utils
from .dataset import DatasetUploadHandler

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

    def __init__(self, api_key: str = None, api_url: str = None):
        if api_key is None:
            api_key = utils.get_api_key()
        if api_url is None:
            api_url = utils.get_api_url()

        self.api_key = api_key
        self.api_url = api_url
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
        return {"Authorization": f"Api-Key {self.api_key}"}

    @utils.handle_exceptions
    def _get(self, endpoint):
        return self.api_session.get(
            urllib.parse.urljoin(self.api_url, endpoint), headers=self._get_headers()
        )

    @utils.handle_exceptions
    def _post(self, endpoint, data=None):
        return self.api_session.post(
            urllib.parse.urljoin(self.api_url, endpoint),
            json=data or {},
            headers=self._get_headers(),
        )

    def projects(self, pretty=0):
        return self._get(f"/api/sdk/projects/?pretty={pretty}")

    def project(self, project_id, pretty=0):
        return self._get(f"/api/sdk/projects/{project_id}/?pretty={pretty}")

    def project_members(self, project_id, pretty=0):
        return self._get(f"/api/sdk/projects/{project_id}/members/?pretty={pretty}")

    def upload_data(self, project_id, directory, batch_size=100):
        if not os.path.isdir(directory):
            raise ValueError(f"Directory {directory} does not exist")

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

        async def post_file(session: aiohttp.ClientSession, file: str, project_id: str):
            async with aiofiles.open(file, "rb") as f:
                form_data = aiohttp.FormData()
                form_data.add_field("project", project_id)
                form_data.add_field(
                    "file", await f.read(), filename=os.path.basename(file)
                )
                try:
                    await asyncio.sleep(0.1)
                    async with session.post(
                        urllib.parse.urljoin(self.api_url, "/api/sdk/upload-data/"),
                        data=form_data,
                    ) as response:
                        response.raise_for_status()
                        return 1
                except Exception as e:
                    logger.error(f"Error uploading file {file} - {e}")
                    return 0

        async def main():
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

    def datasets(self, pretty=0):
        return self._get(f"/api/sdk/datasets/?pretty={pretty}")

    def licenses(self):
        return self._get("/api/sdk/licenses/")

    def dataset_download(self, dataset_id, export_type):
        response = self._post(
            f"/api/sdk/datasets/{dataset_id}/",
            data={"download_type": "annotation", "export_type": export_type},
        )

        with self.api_session.get(url=response["file"], stream=True) as r:
            r.raise_for_status()
            filename = f"dataset-{dataset_id}.json"
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            logger.info(f"File: {os.path.abspath(filename)}")
            return os.path.abspath(filename)

    def download_dataset_files(self, dataset_id):
        response = self._post(
            f"/api/sdk/datasets/{dataset_id}/", data={"download_type": "files"}
        )
        folder = f"dataset-files-{dataset_id}"
        os.makedirs(folder, exist_ok=True)
        dataset_files = [
            dataset_file
            for dataset_file in response
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
            with tqdm.tqdm(total=len(dataset_files), ncols=80) as pbar:
                async with aiohttp.ClientSession() as session:
                    tasks = [
                        download_file(session=session, dataset_file=dataset_file)
                        for dataset_file in dataset_files
                    ]
                    for f in asyncio.as_completed(tasks):
                        pbar.update(await f)

        asyncio.run(main())

    def _finalize_dataset(self, dataset_id):
        return self._post(f"/api/sdk/datasets/{dataset_id}/finalize/")

    def _dataset_data_upload(
        self, dataset_id, upload_handler: DatasetUploadHandler, batch_size=15
    ):
        image_ids = upload_handler.getImgIds()
        url = urllib.parse.urljoin(
            self.api_url, f"/api/sdk/datasets/{dataset_id}/upload/"
        )

        async def main():
            with tqdm.tqdm(total=len(image_ids), ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_headers()
                ) as session:
                    try:
                        for i in range((len(image_ids) + batch_size - 1) // batch_size):
                            tasks = []
                            for image_id in image_ids[
                                i * batch_size : min(
                                    (i + 1) * batch_size, len(image_ids)
                                )
                            ]:
                                tasks.append(
                                    upload_handler.upload_image(session, url, image_id)
                                )
                            for f in asyncio.as_completed(tasks):
                                try:
                                    pbar.update(await f)
                                except exceptions.SubscriptionError as e:
                                    raise e
                    except exceptions.SubscriptionError as e:
                        raise e

        asyncio.run(main())

    def dataset_upload(
        self,
        name,
        annotation_type,
        annotation_path,
        data_path,
        license_id=None,
        batch_size=15,
    ):
        upload_handler = DatasetUploadHandler(
            annotation_type, annotation_path, data_path
        )
        dataset_id = self._post(
            "/api/sdk/datasets/create/",
            data={
                "name": name,
                "annotation_type": annotation_type,
                "classes": [
                    {"name": category["name"], "value": category["id"]}
                    for category in upload_handler.categories
                ],
                "license": license_id,
            },
        )["pk"]
        self._dataset_data_upload(dataset_id, upload_handler, batch_size=batch_size)
        self._finalize_dataset(dataset_id)

    def dataset_update(self, pk, annotation_path, data_path, batch_size=15):
        dataset = self._get(f"api/sdk/datasets/{pk}/")
        upload_handler = DatasetUploadHandler(
            dataset["annotation_type"], annotation_path, data_path
        )
        new_dataset = self._post(
            f"/api/sdk/datasets/{pk}/update/",
            data={
                "classes": [
                    {"name": category["name"], "value": category["id"]}
                    for category in sorted(
                        upload_handler.loadCats(upload_handler.getCatIds()),
                        key=lambda x: x["id"],
                    )
                ]
            },
        )
        upload_handler.original_category_referecences = {
            int(k): v for k, v in new_dataset["original_category_referecences"].items()
        }
        self._dataset_data_upload(
            new_dataset["pk"], upload_handler, batch_size=batch_size
        )
        self._finalize_dataset(new_dataset["pk"])
