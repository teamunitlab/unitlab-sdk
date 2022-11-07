import asyncio
import glob
import logging
import os
import aiohttp
logging.basicConfig(level=logging.INFO, format=None)


async def post_image(session: aiohttp.ClientSession, image: str, task_id: str):
    with open(image, "rb") as img:
        response = await session.request(
            "POST",
            url="https://api.unitlab.ai/api/task-image-upload/",
            data=aiohttp.FormData(fields={"task": task_id, "image": img}),
        )
        logging.info(await response.json())


async def data_upload(folder:str, api_key:str, task_id:str):
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


def upload_data(folder:str, api_key:str, task_id:str):
    asyncio.run(data_upload(folder, api_key, task_id))
