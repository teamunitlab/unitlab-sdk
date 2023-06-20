import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer
from typing_extensions import Annotated

from . import cli
from .client import UnitlabClient

app = typer.Typer()
task_app = typer.Typer()
app.add_typer(task_app, name="task", help="Task commands")

API_KEY = Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")]


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


@task_app.command(name="list", help="Task List")
def task_list(api_key: API_KEY):
    cli.tasks(api_key)


@task_app.command(name="detail", help="Task Detail")
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
):
    get_client(api_key).download_data(str(pk))


@app.command()
def dataset(
    api_key: API_KEY,
    pk: Annotated[Optional[UUID], typer.Argument()] = None,
):
    """
    List or retrieve a dataset if pk is provided
    """
    if pk:
        logging.info(f"File: {get_client(api_key).dataset(pk)}")
    else:
        cli.datasets(api_key)


if __name__ == "__main__":
    app()
