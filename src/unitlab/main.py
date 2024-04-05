from enum import Enum
from pathlib import Path
from uuid import UUID

import typer
import validators
from typing_extensions import Annotated

from .client import UnitlabClient
from .utils import get_api_key, write_config

app = typer.Typer()
project_app = typer.Typer()
dataset_app = typer.Typer()

app.add_typer(project_app, name="project", help="Project commands")
app.add_typer(dataset_app, name="dataset", help="Dataset commands")


API_KEY = Annotated[
    str,
    typer.Option(
        default_factory=get_api_key, help="The api-key obtained from unitlab.ai"
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


@app.command()
def configure(
    api_key: Annotated[str, typer.Option(help="The api-key obtained from unitlab.ai")],
    api_url: Annotated[str, typer.Option()] = "https://api.unitlab.ai",
):
    if not validators.url(api_url, simple_host=True):
        raise typer.BadParameter("Invalid api url")
    write_config(api_key=api_key, api_url=api_url)


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
    get_client(api_key).upload_data(str(pk), directory=directory)


@dataset_app.command(name="list", help="List datasets")
def dataset_list(api_key: API_KEY):
    print(get_client(api_key).datasets(pretty=1))


@dataset_app.command(name="upload", help="Upload dataset")
def dataset_upload(
    api_key: API_KEY,
    name: Annotated[str, typer.Option(help="Name of the dataset")],
    annotation_type: Annotated[AnnotationType, typer.Option(help="Annotation format")],
    annotation_path: Annotated[Path, typer.Option(help="Path to the COCO json file")],
    data_path: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    client = get_client(api_key)
    licenses = client.licenses()
    chosen_license = None
    if licenses:
        LicenseEnum = Enum(
            "LicenseEnum",
            {license["pk"]: str(idx) for idx, license in enumerate(licenses)},
        )
        help_prompt = ", ".join(
            f"{idx}: {license['name']}" for idx, license in enumerate(licenses)
        )
        chosen_license = typer.prompt(f"Select license {help_prompt}", type=LicenseEnum)
    client.dataset_upload(
        name,
        annotation_type.value,
        annotation_path,
        data_path,
        license_id=chosen_license.name if chosen_license else None,
    )


@dataset_app.command(name="update", help="Update dataset")
def dataset_update(
    pk: UUID,
    api_key: API_KEY,
    annotation_path: Annotated[Path, typer.Option(help="Path to the COCO json file")],
    data_path: Annotated[
        Path, typer.Option(help="Directory containing the data to be uploaded")
    ],
):
    get_client(api_key).dataset_update(pk, annotation_path, data_path)


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


if __name__ == "__main__":
    app()
