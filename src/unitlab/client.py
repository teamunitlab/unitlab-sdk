import asyncio
import glob
import logging
import os
import re

import aiohttp
import requests
import tqdm

from .exceptions import AuthenticationError
from .utils import ENDPOINTS, send_request


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
            logging.info("Found a Unitlab API key in your environment.")
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
            client.tasks()
            client.close()

        Or use the client as a context manager:

        .. code-block:: python

            with UnitlabClient() as client:
                client.tasks()
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

    def tasks(self):
        """Get a list of all tasks.

        Returns:
            A list of all tasks.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["tasks"],
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def task(self, task_id):
        """Get a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            A task.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["task"].format(task_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def task_data(self, task_id):
        """Get the data of a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            The data of a task.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["task_datasources"].format(task_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def task_members(self, task_id):
        """Get members of a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            Members of a task.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["task_members"].format(task_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def task_statistics(self, task_id):
        """Get the statistics of a task by id.

        Args:
            task_id: The id of the task.
        Returns:
            The statistics of a task.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["task_statistics"].format(task_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

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

        async def post_image(session: aiohttp.ClientSession, image: str, task_id: str):
            with open(image, "rb") as img:
                try:
                    response = await session.request(
                        "POST",
                        url=URL,
                        data=aiohttp.FormData(fields={"task": task_id, "image": img}),
                    )
                    response.raise_for_status()
                    return 1 if response.status == 201 else 0
                except Exception as e:
                    logging.error(f"Error uploading image {image} - {e}")
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
                    for extension in ["*jpg", "*png", "*jpeg", "*webp"]
                )
                for image in images_list
            ]
            filtered_images = []
            for image in images:
                file_size = os.path.getsize(image) / 1024 / 1024
                if file_size > 6:
                    logging.warning(
                        f"Image {image} is too large ({file_size:.4f} megabytes) skipping, max size is 6 MB"
                    )
                    continue
                filtered_images.append(image)

            num_images = len(filtered_images)
            num_batches = (num_images + batch_size - 1) // batch_size

            logging.info(f"Uploading {num_images} images to task {task_id}")
            with tqdm.tqdm(total=num_images, ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_headers()
                ) as session:
                    for i in range(num_batches):
                        await batch_upload(
                            session,
                            filtered_images[
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
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["download_data"].format(task_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
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

    def datasets(self):
        """Get a list of all datasets.

        Returns:
            A list of all datasets.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["datasets"],
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
        return response.json()

    def dataset(self, dataset_id):
        """Download a dataset by id.

        Args:
            dataset_id: The id of the dataset.
        Returns:
            Writes the data to a json file.
        """
        response = send_request(
            {
                "method": "GET",
                "endpoint": ENDPOINTS["dataset"].format(dataset_id),
                "headers": self._get_headers(),
            },
            session=self.api_session,
        )
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
                    filename = f"dataset-{dataset_id}.json"
            else:
                filename = f"dataset-{dataset_id}.json"

            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
        return os.path.abspath(filename)
