from enum import Enum
from pathlib import Path
from uuid import UUID

import typer
import validators
from typing_extensions import Annotated

from . import utils
from .client import UnitlabClient

app = typer.Typer()
project_app = typer.Typer()
dataset_app = typer.Typer()

app.add_typer(project_app, name="project", help="Project commands")
app.add_typer(dataset_app, name="dataset", help="Dataset commands")


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
    api_url: Annotated[str, typer.Option()] = "https://api.unitlab.ai",
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


if __name__ == "__main__":
    app()
