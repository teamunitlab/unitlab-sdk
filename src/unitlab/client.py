import asyncio
import glob
import logging
import os
import re

import aiohttp
import requests
import tqdm

from .exceptions import AuthenticationError, NetworkError

BASE_URL = "https://api-dev.unitlab.ai/api/cli"

ENPOINTS = {
    "ai_model_list": BASE_URL + "/task-parent/",
    "ai_model_detail": BASE_URL + "/task-parent/{}/",
    "task_list": BASE_URL + "/task/",
    "task_detail": BASE_URL + "/task/{}/",
    "task_data_sources": BASE_URL + "/task/{}/datasource/",
    "task_members": BASE_URL + "/task/{}/members/",
    "task_statistics": BASE_URL + "/task/{}/statistics/",
    "task_upload_datasources": BASE_URL + "/task/upload-datasource/",
    "task_download_data": BASE_URL + "/task/{}/download-data/",
    "datasource_result": BASE_URL + "/datasource/{}/result/",
    "datasets": BASE_URL + "/datasets/",
    "dataset_detail": BASE_URL + "/datasets/{}/",
}

logging.basicConfig(level=logging.INFO)
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

    def __init__(self, api_key: str = None, check_connection: bool = True):
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
        if check_connection:
            try:
                r = self.api_session.get(
                    f"{BASE_URL}/api-status/", headers=self._get_auth_header()
                )
                r.raise_for_status()
                if r.status_code == 200:
                    logger.info("Successfully connected to the Unitlab.ai API.")
            except NetworkError:
                raise AuthenticationError(
                    message="Something went wrong. Did you use the right API key?"
                )

    def close(self) -> None:
        """Close :class:`UnitlabClient` connections.

        You can manually close the Unitlab client's connections:

        .. code-block:: python

            client = UnitlabClient()
            client.task_list()
            client.close()

        Or use the client as a context manager:

        .. code-block:: python

            with UnitlabClient() as client:
                client.task_list()
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

    def _get_auth_header(self):
        return {"Authorization": f"Api-Key {self.api_key}"} if self.api_key else None

    def task_list(self):
        """Get a list of all tasks.

        Returns:
            A list of all tasks.
        """
        r = self.api_session.get(ENPOINTS["task_list"], headers=self._get_auth_header())
        r.raise_for_status()
        return r.json()

    def task_detail(self, task_id):
        """Get a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            A task.
        """
        r = self.api_session.get(
            ENPOINTS["task_detail"].format(task_id),
            headers=self._get_auth_header(),
        )
        r.raise_for_status()
        return r.json()

    def task_data(self, task_id):
        """Get the data of a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            The data of a task.
        """
        r = self.api_session.get(
            ENPOINTS["task_data_sources"].format(task_id),
            headers=self._get_auth_header(),
        )
        r.raise_for_status()
        return r.json()

    def task_members(self, task_id):
        """Get the members of a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            The members of a task.
        """
        r = self.api_session.get(
            ENPOINTS["task_members"].format(task_id),
            headers=self._get_auth_header(),
        )
        r.raise_for_status()
        return r.json()

    def task_statistics(self, task_id):
        """Get the statistics of a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            The statistics of a task.
        """
        r = self.api_session.get(
            ENPOINTS["task_statistics"].format(task_id),
            headers=self._get_auth_header(),
        )
        r.raise_for_status()
        return r.json()

    def upload_data(self, task_id, directory, batch_size=100):
        """Upload data to a task by id.

        Args:
            task_id: The id of the task.
            directory: The directory of images to upload.
            batch_size: The batch size of images to upload.
        Returns:
            The upload status.
        """

        if not os.path.isdir(directory):
            raise ValueError(f"Directory {directory} does not exist")

        async def post_image(session: aiohttp.ClientSession, image: str, task_id: str):
            with open(image, "rb") as img:
                try:
                    response = await session.request(
                        "POST",
                        url=ENPOINTS["task_upload_datasources"],
                        data=aiohttp.FormData(fields={"task": task_id, "image": img}),
                    )
                    return 1 if response.status == 201 else 0
                except Exception as e:
                    logger.error(f"Error uploading image {image} - {e}")
                    return 0

        async def batch_upload(
            session: aiohttp.ClientSession, batch: list, task_id: str, pbar: tqdm.tqdm
        ):
            tasks = []
            for image in batch:
                tasks.append(post_image(session=session, image=image, task_id=task_id))
            for f in asyncio.as_completed(tasks):
                pbar.update(await f)

        async def main():
            images = [
                image
                for images_list in (
                    glob.glob(os.path.join(directory, "") + extension)
                    for extension in ["*jpg", "*png"]
                )
                for image in images_list
            ]
            num_images = len(images)
            num_batches = (num_images + batch_size - 1) // batch_size

            logger.info(f"Uploading {num_images} images to task {task_id}")
            with tqdm.tqdm(total=num_images, ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_auth_header()
                ) as session:
                    for i in range(num_batches):
                        await batch_upload(
                            session,
                            images[
                                i * batch_size : min((i + 1) * batch_size, num_images)
                            ],
                            task_id,
                            pbar,
                        )

        asyncio.run(main())

    def download_data(self, task_id):
        """Download data from a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            Writes the data to a json file.
        """
        response = self.api_session.get(
            url=ENPOINTS["task_download_data"].format(task_id),
            headers=self._get_auth_header(),
        )
        response.raise_for_status()
        with self.api_session.get(
            url=response.json()["file"],
            stream=True,
        ) as r:
            r.raise_for_status()
            if "Content-Disposition" in r.headers.keys():
                content_disposition = r.headers["Content-Disposition"]
                filename_match = re.search('filename="(.+)"', content_disposition)
                if filename_match:
                    filename = filename_match.group(1)
                else:
                    filename = f"task-data-{task_id}.json"
            else:
                filename = f"task-data-{task_id}.json"

            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            return os.path.abspath(filename)

    def ai_models(self):
        """Get a list of all ai models.

        Returns:
            A list of all ai models.
        """
        r = self.api_session.get(
            ENPOINTS["ai_model_list"], headers=self._get_auth_header()
        )
        r.raise_for_status()
        return r.json()

    def ai_model(self, ai_model_id):
        """Get an ai model by id.

        Args:
            ai_model_id: The id of the ai model.
        Returns:
            An ai model.
        """
        r = self.api_session.get(
            ENPOINTS["ai_model_detail"].format(ai_model_id),
            headers=self._get_auth_header(),
        )
        r.raise_for_status()
        return r.json()

    def datasets(self):
        """Get a list of all datasets.

        Returns:
            A list of all datasets.
        """
        r = self.api_session.get(ENPOINTS["datasets"], headers=self._get_auth_header())
        r.raise_for_status()
        return r.json()

    def dataset(self, dataset_id):
        """Get a dataset by id.

        Args:
            dataset_id: The id of the dataset.
        Returns:
            A dataset.
        """
        r = self.api_session.get(
            ENPOINTS["dataset_detail"].format(dataset_id),
            headers=self._get_auth_header(),
        )
        r.raise_for_status()
        return r.json()["file"]

    def datasource_result(self, datasource_id):
        raise NotImplementedError
