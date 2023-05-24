import logging
from pathlib import Path
from uuid import UUID

import typer
from typing_extensions import Annotated

from . import cli
from .client import UnitlabClient

app = typer.Typer()

API_KEY = Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")]


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


@app.command(help="Task list")
def tasks(api_key: API_KEY):
    cli.tasks(api_key)


@app.command(help="Task detail")
def task(pk: UUID, api_key: API_KEY):
    cli.task(api_key, pk)


@app.command(help="Task datasources")
def task_data(pk: UUID, api_key: API_KEY):
    cli.task_data(api_key, pk)


@app.command(help="Task workers")
def task_workers(pk: UUID, api_key: API_KEY):
    cli.task_workers(api_key, pk)


@app.command(help="Task statistics")
def task_statistics(pk: UUID, api_key: API_KEY):
    cli.task_statistics(api_key, pk)


@app.command(help="Upload data")
def upload_data(
    pk: UUID,
    api_key: API_KEY,
    directory: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    get_client(api_key).upload_data(str(pk), directory=directory)


@app.command(help="Download data")
def download_data(pk: UUID, api_key: API_KEY):
    logging.info(f"File: {get_client(api_key).download_data(pk)}")


@app.command(help="AI models")
def ai_models(api_key: API_KEY):
    cli.ai_models(api_key)


@app.command(help="AI model")
def ai_model(pk: UUID, api_key: API_KEY):
    cli.ai_model(api_key, pk)


@app.command(help="Datasets")
def datasets(api_key: API_KEY):
    cli.datasets(api_key)


@app.command(help="Dataset")
def dataset(pk: UUID, api_key: API_KEY):
    logging.info(f"File: {get_client(api_key).dataset(pk)}")


if __name__ == "__main__":
    app()
