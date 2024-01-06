from pathlib import Path
from uuid import UUID

import typer
from typing_extensions import Annotated

from . import cli
from .client import UnitlabClient

app = typer.Typer()
project_app = typer.Typer()
app.add_typer(project_app, name="project", help="Project commands")

API_KEY = Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")]


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


@project_app.command(name="list", help="Project list")
def project_list(api_key: API_KEY):
    cli.projects(api_key)


@project_app.command(name="detail", help="Project detail")
def project_detail(pk: UUID, api_key: API_KEY):
    cli.project(api_key, pk)


@project_app.command(help="Project members")
def members(pk: UUID, api_key: API_KEY):
    cli.project_members(api_key, pk)


@project_app.command(help="Upload data")
def upload(
    pk: UUID,
    api_key: API_KEY,
    directory: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    get_client(api_key).upload_data(str(pk), directory=directory)


if __name__ == "__main__":
    app()
