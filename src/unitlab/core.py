import argparse
import asyncio
import glob
import os
import re
from io import BytesIO
from uuid import UUID

import aiohttp
import cv2
import numpy as np
import requests
import tqdm
from PIL import Image, ImageColor, ImageDraw

from unitlab import pretty

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
    r.raise_for_status()
    pretty.print_ai_model(r.json(), many=True)


def ai_model_detail(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    r.raise_for_status()
    pretty.print_ai_model(r.json(), many=False)


def task_list(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__],
        headers=get_headers(namespace),
    )
    r.raise_for_status()
    pretty.print_task(r.json(), many=True)


def task_detail(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    r.raise_for_status()
    pretty.print_task(r.json(), many=False)


def task_data_sources(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    r.raise_for_status()
    pretty.print_data_sources(r.json())


def task_members(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    r.raise_for_status()
    pretty.print_members(r.json())


def task_statistics(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    pretty.print_task_statistics(r.json())


def task_upload_datasources(namespace):
    if not os.path.exists(namespace.input_dir):
        raise ValueError(f"Directory {namespace.input_dir} does not exist.")

    async def upload_images(session, endpoint, task_id, images, progress_bar):
        for file_path in images:
            with open(file_path, "rb") as image:
                async with session.post(
                    endpoint,
                    data=aiohttp.FormData(fields={"task": task_id, "image": image}),
                ) as response:
                    if response.status != 201:
                        raise Exception(
                            f"Failed to upload file {file_path}. HTTP status code: {response.status}"
                        )
                    progress_bar.update(os.path.getsize(file_path))
                    await response.read()

    async def upload_images_in_batches(
        folder: str, api_key: str, task_id: str, batch_size=1000
    ):
        images = [
            image
            for images_list in [
                glob.glob(os.path.join(folder, "") + extension)
                for extension in ["*jpg", "*png"]
            ]
            for image in images_list
        ]
        total_size = sum(os.path.getsize(f) for f in images)
        endpoint = ENPOINTS[namespace.func.__name__]

        with tqdm.tqdm(total=total_size, unit="B", unit_scale=True) as progress_bar:
            async with aiohttp.ClientSession(
                headers={"Authorization": f"Api-Key {api_key}"}
            ) as session:
                for i in range(0, len(images), batch_size):
                    batch_images = images[i : i + batch_size]
                    tasks = [
                        asyncio.create_task(
                            upload_images(
                                session, endpoint, task_id, batch_images, progress_bar
                            )
                        )
                    ]
                    await asyncio.gather(*tasks)

    try:
        asyncio.run(
            upload_images_in_batches(
                namespace.input_dir, namespace.api_key, namespace.uuid, batch_size=1000
            )
        )
    except Exception as e:
        print(str(e))


def task_download_data(namespace):
    response = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    response.raise_for_status()
    session = requests.Session()
    with session.get(
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
                filename = f"task-data-{namespace.uuid}.json"
        else:
            filename = f"task-data-{namespace.uuid}.json"

        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


def datasource_result(namespace):
    r = requests.get(
        url=ENPOINTS[namespace.func.__name__].format(namespace.uuid),
        headers=get_headers(namespace),
    )
    r.raise_for_status()
    if r.status_code == 204:
        print("No results yet")
        return
    result = r.json()
    if result["render_type"] == "img_segmentation":
        bitmap = np.array(Image.open(BytesIO(requests.get(result["source"]).content)))
        classes = result["classes"]
        bitmap = bitmap[:, :, 0] if len(bitmap.shape) > 2 else bitmap
        bitmap = np.array(bitmap)
        label_values = [list(ImageColor.getcolor(l["color"], "RGB")) for l in classes]
        label_values.insert(0, [0, 0, 0])  # Add background color
        label_values = np.array(label_values)
        thumbnail = label_values[bitmap.astype(int)]
        thumbnail = np.array(thumbnail).astype(np.uint8)
        thumbnail = cv2.cvtColor(thumbnail, cv2.COLOR_RGB2RGBA)
        thumbnail[thumbnail[:, :, 3] == 255, 3] = 128
        thumbnail = Image.fromarray(thumbnail)
        return thumbnail.show()
    elif result["render_type"] == "img_bbox":
        rotation = result.get("image", {}).get("rotation", 0)
        boxes = result["bboxes"]
        canvas = Image.open(BytesIO(requests.get(result["source"]).content))
        if rotation:
            canvas = canvas.rotate(rotation, expand=False)
        for line in boxes:
            for box in line:
                poly = box["box"]
                class_ = box["class"]
                label_values = [
                    list(ImageColor.getcolor(l["color"], "RGB"))
                    for l in result["classes"]
                ]
                class_color = label_values[class_]
                poly = [(p[0], p[1]) for p in poly]
                ImageDraw.Draw(canvas).polygon(poly, outline=tuple(class_color))
        return canvas.show()
    print("No results yet")
