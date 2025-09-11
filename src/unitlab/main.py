from enum import Enum
from pathlib import Path
from uuid import UUID
import logging
import threading

import typer
import validators
from typing_extensions import Annotated
import psutil
import uvicorn 
from fastapi import FastAPI,Response


from . import utils
from .client import UnitlabClient



app = typer.Typer()
project_app = typer.Typer()
dataset_app = typer.Typer()
agent_app = typer.Typer()


app.add_typer(project_app, name="project", help="Project commands")
app.add_typer(dataset_app, name="dataset", help="Dataset commands")
app.add_typer(agent_app, name="agent", help="Agent commands")


API_KEY = Annotated[
    str,
    typer.Option(
        default_factory=utils.get_api_key, help="The api-key obtained from unitlab.ai"
    ),
]


class DownloadType(str, Enum):
    annotation = "annotation"
    files = "files"


class AnnotationType(str, Enum):
    IMG_BBOX = "img_bbox"
    IMG_SEMANTIC_SEGMENTATION = "img_semantic_segmentation"
    IMG_INSTANCE_SEGMENTATION = "img_instance_segmentation"
    IMG_POLYGON = "img_polygon"
    IMG_LINE = "img_line"
    IMG_POINT = "img_point"




@app.command(help="Configure the credentials")
def configure(
    api_key: Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")],
    api_url: Annotated[str, typer.Option()] = "https://localhost/",
):
    if not validators.url(api_url, simple_host=True):
        raise typer.BadParameter("Invalid api url")
    utils.write_config(api_key=api_key, api_url=api_url)


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


@project_app.command(name="list", help="Project list")
def project_list(api_key: API_KEY):
    print(get_client(api_key).projects(pretty=1))


@project_app.command(name="detail", help="Project detail")
def project_detail(pk: UUID, api_key: API_KEY):
    print(get_client(api_key).project(project_id=pk, pretty=1))


@project_app.command(help="Project members")
def members(pk: UUID, api_key: API_KEY):
    print(get_client(api_key).project_members(project_id=pk, pretty=1))


@project_app.command(help="Upload data")
def upload(
    pk: UUID,
    api_key: API_KEY,
    directory: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    get_client(api_key).project_upload_data(str(pk), directory=directory)


@dataset_app.command(name="list", help="List datasets")
def dataset_list(api_key: API_KEY):
    print(get_client(api_key).datasets(pretty=1))


@dataset_app.command(name="download", help="Download dataset")
def dataset_download(
    pk: UUID,
    api_key: API_KEY,
    download_type: Annotated[
        DownloadType,
        typer.Option(help="Download type (annotation, files)"),
    ] = DownloadType.annotation,
    export_type: Annotated[
        str, typer.Option(help="Export type (COCO, YOLOv8, YOLOv5)")
    ] = "COCO",
):
    if download_type == DownloadType.annotation:
        if not export_type:
            raise typer.BadParameter(
                "Export type is required when download type is annotation"
            )
        return get_client(api_key).dataset_download(pk, export_type)
    get_client(api_key).dataset_download_files(pk)


@agent_app.command(name="run", help="Run the device agent with Jupyter, SSH tunnels and metrics")
def run_agent(
    api_key: API_KEY,
    device_id: Annotated[str, typer.Option(help="Device ID")] = None,
    base_domain: Annotated[str, typer.Option(help="Base domain for tunnels")] = "api-dev.unitlab.ai",
  
):

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    server_url = 'https://api-dev.unitlab.ai/'
    
    if not device_id:
        import uuid
        import platform

        hostname = platform.node().replace('.', '-').replace(' ', '-')[:20]
        random_suffix = str(uuid.uuid4())[:8]
        device_id = f"{hostname}-{random_suffix}"
        print(f"📝 Generated unique device ID: {device_id}")
          

    client = UnitlabClient(api_key=api_key)
    client.initialize_device_agent(
        server_url=server_url,
        device_id=device_id,
        base_domain=base_domain
    )

    try:
        client.run_device_agent()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        client.cleanup_device_agent()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
