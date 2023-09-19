import logging
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer
from typing_extensions import Annotated

from . import cli
from .client import UnitlabClient

app = typer.Typer()
task_app = typer.Typer()
dataset_app = typer.Typer()
app.add_typer(task_app, name="task", help="Task commands")
app.add_typer(dataset_app, name="dataset", help="Dataset commands")

API_KEY = Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")]


class DownloadType(str, Enum):
    annotation = "annotation"
    file = "file"


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


@task_app.command(name="list", help="Task list")
def task_list(api_key: API_KEY):
    cli.tasks(api_key)


@task_app.command(name="detail", help="Task detail")
def task_detail(pk: UUID, api_key: API_KEY):
    cli.task(api_key, pk)


@task_app.command(help="Task datasources")
def data(pk: UUID, api_key: API_KEY):
    cli.task_data(api_key, pk)


@task_app.command(help="Task members")
def members(pk: UUID, api_key: API_KEY):
    cli.task_members(api_key, pk)


@task_app.command(help="Task statistics")
def statistics(pk: UUID, api_key: API_KEY):
    cli.task_statistics(api_key, pk)


@task_app.command(help="Upload data")
def upload(
    pk: UUID,
    api_key: API_KEY,
    directory: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    get_client(api_key).upload_data(str(pk), directory=directory)


@task_app.command(help="Download data")
def download(
    pk: UUID,
    api_key: API_KEY,
    download_type: Annotated[
        DownloadType,
        typer.Option(help="Download type (annotation, file)"),
    ] = DownloadType.annotation,
    export_type: Annotated[
        str, typer.Option(help="Export type (coco, yolov8, etc)")
    ] = None,
):
    if download_type == DownloadType.annotation and not export_type:
        raise typer.BadParameter(
            "Export type is required when download type is annotation"
        )
    get_client(api_key).download_data(pk, download_type.value, export_type)


@dataset_app.command(name="list", help="List datasets")
def dataset_list(
    api_key: API_KEY,
):
    cli.datasets(api_key)


@dataset_app.command(name="download", help="Download dataset")
def dataset_download(
    pk: Annotated[Optional[UUID], typer.Argument()],
    api_key: API_KEY,
    download_type: Annotated[
        DownloadType,
        typer.Option(help="Download type (annotation, file)"),
    ] = DownloadType.annotation,
    export_type: Annotated[
        str, typer.Option(help="Export type (coco, yolov8, etc)")
    ] = None,
):
    if download_type == DownloadType.annotation and not export_type:
        raise typer.BadParameter(
            "Export type is required when download type is annotation"
        )
    get_client(api_key).dataset_download(pk, download_type.value, export_type)


if __name__ == "__main__":
    app()
