import argparse
import asyncio
import errno
import glob
import logging
import os
import pprint
from uuid import UUID

import aiohttp
import requests

BASE_URL = "https://api-new.unitlab.ai/api/cli/"

ENPOINTS = {
    "ai_model_list": BASE_URL + "task-parent/",
    "ai_model_detail": BASE_URL + "task-parent/{}/",
    "task_list": BASE_URL + "task/",
    "task_detail": BASE_URL + "task/{}/",
    "task_data_sources": BASE_URL + "task/{}/datasource/",
    "task_members": BASE_URL + "task/{}/members/",
    "task_statistics": BASE_URL + "task/{}/statistics/",
    "task_upload_datasources": BASE_URL + "task/upload-datasource/",
}

api_key_template = {
    "type": str,
    "dest": "api_key",
    "nargs": "?",
    "required": True,
    "help": "The api-key that obtained from unitlab.ai",
}


def get_headers(namespace):
    return {"Authorization": f"Api-Key {namespace.api_key}"}


def validate_uuid(uuid):
    try:
        UUID(uuid, version=4)
    except ValueError:
        raise argparse.ArgumentTypeError("Invalid UUID")
    return uuid


def ai_model_list(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__],
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def ai_model_detail(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def task_list(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__],
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def task_detail(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def task_data_sources(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def task_members(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def task_statistics(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    pprint.pprint(r.json())


def task_upload_datasources(namespace):
    logging.basicConfig(level=logging.INFO, format=None)

    try:
        os.makedirs(namespace.input_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    async def post_image(session: aiohttp.ClientSession, image: str, task_id: str):
        with open(image, "rb") as img:
            response = await session.request(
                "POST",
                url=ENPOINTS[namespace.func.__name__],
                data=aiohttp.FormData(fields={"task": task_id, "image": img}),
            )
            logging.info(await response.json())

    async def data_upload(folder: str, api_key: str, task_id: str):
        async with aiohttp.ClientSession(
            headers={"Authorization": f"Api-Key {api_key}"}
        ) as session:
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
                tasks.append(post_image(session=session, image=image, task_id=task_id))
            return await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(data_upload(namespace.input_dir, namespace.api_key, namespace.uuid))
