import os
from pathlib import Path
from uuid import UUID

import typer
from typing_extensions import Annotated

from . import pretty
from .client import UnitlabClient

app = typer.Typer()

API_KEY = Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")]


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key, check_connection=False)


@app.command(help="Task list")
def tasks(api_key: API_KEY):
    pretty.print_task(get_client(api_key).task_list(), many=True)


@app.command(help="Task detail")
def task(task_id: UUID, api_key: API_KEY):
    pretty.print_task(get_client(api_key).task_detail(task_id=task_id), many=False)


@app.command(help="Task datasources")
def task_data(task_id: UUID, api_key: API_KEY):
    pretty.print_data_sources(get_client(api_key).task_data(task_id=task_id))


@app.command(help="Task members")
def task_members(task_id: UUID, api_key: API_KEY):
    pretty.print_members(get_client(api_key).task_members(task_id=task_id))


@app.command(help="Task statistics")
def task_statistics(pk: UUID, api_key: API_KEY):
    pretty.print_task_statistics(get_client(api_key).task_statistics(task_id=pk))


@app.command(help="Upload data")
def upload_data(
    pk: UUID,
    api_key: API_KEY,
    directory: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    get_client(api_key).upload_data(task_id=str(pk), directory=directory)


@app.command(help="Download data")
def download_data(pk: UUID, api_key: API_KEY):
    print("File:", get_client(api_key).download_data(task_id=pk))


@app.command(help="Datasource result")
def datasource_result(pk: UUID, api_key: API_KEY):
    get_client(api_key).datasource_result(pk)


@app.command(help="AI models")
def ai_models(api_key: API_KEY):
    pretty.print_ai_model(get_client(api_key).ai_models(), many=True)


@app.command(help="AI model")
def ai_model(pk: UUID, api_key: API_KEY):
    pretty.print_ai_model(get_client(api_key).ai_model(pk), many=False)


@app.command(help="Datasets")
def datasets(api_key: API_KEY):
    pretty.print_datasets(get_client(api_key).datasets())


@app.command(help="Dataset")
def dataset(pk: UUID, api_key: API_KEY):
    print("File: ", get_client(api_key).dataset(pk))


if __name__ == "__main__":
    app()
