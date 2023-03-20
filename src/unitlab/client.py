import asyncio
import errno
import glob
import os
import re

import aiohttp
import requests
import tqdm

from unitlab.core import BASE_URL, ENPOINTS
from unitlab.exceptions import AuthenticationError, NetworkError


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
        api_key: Your Segments.ai API key. If no API key given, reads ``SEGMENTS_API_KEY`` from the environment. Defaults to :obj:`None`.
    Raises:
        :exc:`~segments.exceptions.AuthenticationError`: If an invalid API key is used or (when not passing the API key directly) if ``SEGMENTS_API_KEY`` is not found in your environment.
    """

    def __init__(
        self,
        api_key: str = None,
    ):
        if api_key is None:
            api_key = os.getenv("SEGMENTS_API_KEY")
            if api_key is None:
                raise AuthenticationError(
                    message="Please provide the api_key argument or set SEGMENTS_API_KEY in your environment."
                )
            else:
                print("Found a Segments API key in your environment.")

        self.api_key = api_key

        # https://realpython.com/python-requests/#performance
        # https://stackoverflow.com/questions/21371809/cleanly-setting-max-retries-on-python-requests-get-or-post-method
        # https://stackoverflow.com/questions/23013220/max-retries-exceeded-with-url-in-requests
        self.api_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.api_session.mount("http://", adapter)
        self.api_session.mount("https://", adapter)

        try:
            r = self.api_session.get(
                f"{BASE_URL}/api-status/", headers=self._get_auth_header()
            )
            r.raise_for_status()
            if r.status_code == 200:
                print("Successfully connected to the Unitlab.ai API.")
        except NetworkError:
            raise AuthenticationError(
                message="Something went wrong. Did you use the right API key?"
            )

    # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
    def close(self) -> None:
        """Close :class:`UnitlabClient` connections.

        You can manually close the Segments client's connections:

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

    # Use UnitlabClient as a context manager (e.g., with UnitlabClient() as client: client.add_dataset()).
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

    # available endpoints
    # {task-list,task-detail,task-data,task-members,task-statistics,task-upload-data,ai-model-list,ai-model-detail}

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

    def task_upload_data(self, task_id, directory):
        """Upload data to a task by id.

        Args:
            task_id: The id of the task.
            directory: The directory of images to upload.
        Returns:
            The upload status.
        """
        try:
            os.makedirs(directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        async def post_image(session: aiohttp.ClientSession, image: str, task_id: str):
            with open(image, "rb") as img:
                await session.request(
                    "POST",
                    url=ENPOINTS["task_upload_datasources"],
                    data=aiohttp.FormData(fields={"task": task_id, "image": img}),
                )
                return os.path.getsize(image)

        async def data_upload(folder: str, task_id: str):
            async with aiohttp.ClientSession(
                headers=self._get_auth_header()
            ) as session:
                total_bytes = 0
                tasks = []
                images = [
                    image
                    for images_list in [
                        glob.glob(os.path.join(folder, "") + extension)
                        for extension in ["*jpg", "*png"]
                    ]
                    for image in images_list
                ]
                for image in images:
                    total_bytes += os.path.getsize(image)
                for image in images:
                    tasks.append(
                        post_image(session=session, image=image, task_id=task_id)
                    )

                pbar = tqdm.tqdm(
                    total=total_bytes,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    ncols=80,
                )
                for f in asyncio.as_completed(tasks):
                    value = await f
                    pbar.update(value)

        asyncio.run(data_upload(directory, task_id))

    def task_download_data(self, task_id):
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

    def ai_model_list(self):
        """Get a list of all ai models.

        Returns:
            A list of all ai models.
        """
        r = self.api_session.get(
            ENPOINTS["ai_model_list"], headers=self._get_auth_header()
        )
        r.raise_for_status()
        return r.json()

    def ai_model_detail(self, ai_model_id):
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
