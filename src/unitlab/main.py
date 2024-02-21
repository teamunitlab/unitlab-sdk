from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer
from typing_extensions import Annotated

from .client import UnitlabClient
from .utils import ENDPOINTS, send_request

app = typer.Typer()
project_app = typer.Typer()
dataset_app = typer.Typer()

app.add_typer(project_app, name="project", help="Project commands")
app.add_typer(dataset_app, name="dataset", help="Dataset commands")

API_KEY = Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")]


class DownloadType(str, Enum):
    annotation = "annotation"
    files = "files"


class AnnotationType(str, Enum):
    img_bbox = "img_bbox"
    img_polygon = "img_polygon"
    img_semantic_segmentation = "img_semantic_segmentation"
    img_skeleton = "img_skeleton"


def get_client(api_key: str) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


def get_headers(api_key):
    return {"Authorization": f"Api-Key {api_key}"}


@project_app.command(name="list", help="Project list")
def project_list(api_key: API_KEY):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_projects"],
        }
    )
    print(response.json())


@project_app.command(name="detail", help="Project detail")
def project_detail(pk: UUID, api_key: API_KEY):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_project"].format(pk),
        }
    )
    print(response.json())


@project_app.command(help="Project members")
def members(pk: UUID, api_key: API_KEY):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_project_members"].format(pk),
        }
    )
    print(response.json())


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


@dataset_app.command(name="list", help="List datasets")
def dataset_list(
    api_key: API_KEY,
):
    response = send_request(
        {
            "method": "GET",
            "headers": get_headers(api_key),
            "endpoint": ENDPOINTS["cli_datasets"],
        }
    )
    print(response.json())


@dataset_app.command(name="upload", help="Upload dataset")
def dataset_upload(
    api_key: API_KEY,
    name: Annotated[str, typer.Option(help="Name of the dataset")],
    annotation_type: Annotated[
        AnnotationType,
        typer.Option(
            help="Annotation type (img_bbox, img_polygon, img_semantic_segmentation, img_skeleton)"
        ),
    ],
    annotation_path: Annotated[Path, typer.Option(help="Path to the COCO json file")],
    data_path: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
    batch_size: Annotated[
        int, typer.Option(help="Batch size for uploading images")
    ] = 100,
):
    get_client(api_key).dataset_upload(
        name, annotation_type, annotation_path, data_path, batch_size
    )


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
        get_client(api_key).dataset_download(pk, export_type)
    get_client(api_key).download_dataset_files(pk)
