# ruff: noqa: B008
from __future__ import annotations

import json
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

import typer

from . import __version__, _config
from ._grouping import tiles_from_template
from .client import UnitlabClient
from .exceptions import UnitlabError
from .ontology import OntologyStructure

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
app = typer.Typer(
    help="Manage Unitlab projects, data, Ontologies, and Releases.",
    epilog=(
        "Example: unitlab project list\n"
        "Docs: https://docs.unitlab.ai\n"
        "Support: https://github.com/teamunitlab/unitlab-sdk/issues"
    ),
    no_args_is_help=False,
    context_settings=CONTEXT_SETTINGS,
)
project_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
batch_queue_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
assets_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
folders_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
dataset_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
workflow_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
release_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
ontology_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
cloud_app = typer.Typer(context_settings=CONTEXT_SETTINGS)
embeddings_app = typer.Typer(context_settings=CONTEXT_SETTINGS)

app.add_typer(project_app, name="project", help="Project commands")
app.add_typer(batch_queue_app, name="batch-queue", help="Batch Queue commands")
app.add_typer(assets_app, name="assets", help="Assets commands")
app.add_typer(folders_app, name="folders", help="Folder commands")
app.add_typer(dataset_app, name="dataset", help="Dataset commands")
app.add_typer(workflow_app, name="workflow", help="Workflow Task commands")
app.add_typer(release_app, name="release", help="Release commands")
app.add_typer(ontology_app, name="ontology", help="Ontology commands")
app.add_typer(cloud_app, name="cloud", help="Cloud storage commands")
app.add_typer(
    embeddings_app,
    name="embeddings",
    help="Custom embedding space commands",
)

API_KEY = Annotated[
    str | None,
    typer.Option(
        help=(
            "The API key obtained from Unitlab. If omitted, reads "
            "UNITLAB_API_KEY, then the configured key."
        )
    ),
]
JSON_OUTPUT = Annotated[bool, typer.Option("--json", help="Print JSON output")]


class DownloadType(str, Enum):
    annotation = "annotation"
    files = "files"


class EmbeddingLevel(str, Enum):
    asset = "asset"
    frame = "frame"


EMBEDDING_UPLOAD_BATCH_SIZE = 1000


def get_client(api_key: str | None) -> UnitlabClient:
    return UnitlabClient(api_key=api_key)


def _parse_custom_metadata(
    value: str,
    option: str = "--custom-metadata",
) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{option} must be valid JSON") from exc
    if parsed is not None and not isinstance(parsed, dict):
        raise typer.BadParameter(f"{option} must be a JSON object or null")
    return parsed


def _load_custom_metadata(
    value: str | None,
    file: Path | None,
    *,
    required: bool = False,
) -> dict[str, Any] | None:
    if value is not None and file is not None:
        raise typer.BadParameter(
            "Use --custom-metadata or --custom-metadata-file, not both"
        )
    if value is None and file is None:
        if required:
            raise typer.BadParameter(
                "Provide --custom-metadata or --custom-metadata-file"
            )
        return None
    if file is not None:
        try:
            value = file.read_text()
        except OSError as exc:
            raise typer.BadParameter(
                f"--custom-metadata-file could not be read: {exc}"
            ) from exc
    return _parse_custom_metadata(
        value,
        "--custom-metadata-file" if file is not None else "--custom-metadata",
    )


def _load_vector(path: Path) -> list[float]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"Could not read vector JSON from {path}") from exc
    if not isinstance(value, list) or any(
        not isinstance(item, (int, float)) or isinstance(item, bool) for item in value
    ):
        raise typer.BadParameter("Vector file must contain one JSON array of numbers")
    return [float(item) for item in value]


def _embedding_jsonl_batches(path: Path):
    batch = []
    found_item = False
    try:
        with path.open() as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                found_item = True
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise typer.BadParameter(
                        f"Invalid JSON on line {line_number} of {path}"
                    ) from exc
                if not isinstance(item, dict):
                    raise typer.BadParameter(
                        f"Line {line_number} of {path} must be a JSON object"
                    )
                missing = {"asset_id", "vector"} - item.keys()
                if missing:
                    fields = ", ".join(sorted(missing))
                    raise typer.BadParameter(
                        f"Line {line_number} of {path} is missing: {fields}"
                    )
                batch.append(item)
                if len(batch) == EMBEDDING_UPLOAD_BATCH_SIZE:
                    yield batch
                    batch = []
    except OSError as exc:
        raise typer.BadParameter(f"Could not read {path}") from exc
    if not found_item:
        raise typer.BadParameter(f"{path} contains no embeddings")
    if batch:
        yield batch


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in fields(value)
            if field.name != "raw" and not field.name.startswith("_")
        }
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


SUMMARY_FIELDS = (
    "id",
    "name",
    "title",
    "file_name",
    "kind",
    "type",
    "version",
    "status",
    "state",
    "data_type",
    "item_count",
    "data_item_count",
    "dimensions",
    "model_name",
    "ann_index_status",
    "vector_search_supported",
    "task_count",
    "created_count",
)


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str, separators=(",", ":"))
    return "-" if value is None else str(value)


def _summary(value: Any) -> str:
    if not isinstance(value, dict):
        return _display(value)
    pairs = [
        (key, value[key])
        for key in SUMMARY_FIELDS
        if key in value and value[key] not in (None, "")
    ]
    if not pairs:
        pairs = [
            (key, item)
            for key, item in value.items()
            if not isinstance(item, (dict, list))
        ][:4]
    return "  ".join(f"{key}={_display(item)}" for key, item in pairs)


def emit(value: Any, json_output: bool = False) -> None:
    value = _jsonable(value)
    if json_output:
        typer.echo(json.dumps(value, default=str, indent=2))
    elif isinstance(value, list):
        for item in value:
            typer.echo(_summary(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            typer.echo(f"{key}: {_display(item)}")
    else:
        typer.echo(value)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the installed version and exit",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
):
    """Manage Unitlab from the command line."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(help="Configure credentials")
def configure(
    api_key: Annotated[str | None, typer.Option(help="API key from Unitlab")] = None,
    api_url: Annotated[str | None, typer.Option(help="API base URL")] = None,
):
    if api_key is None and api_url is None:
        raise typer.BadParameter("Provide --api-key, --api-url, or both")
    if api_url is not None:
        parsed = urlsplit(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise typer.BadParameter("Invalid API URL")
    _config.write_config(api_key=api_key, api_url=api_url)
    typer.echo("Configuration saved.")


@project_app.command(name="list", help="Project list")
def project_list(api_key: API_KEY = None, json_output: JSON_OUTPUT = False):
    emit(get_client(api_key).projects.list(), json_output)


@project_app.command(name="detail", help="Project detail")
def project_detail(
    pk: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).projects.get(str(pk)), json_output)


@project_app.command(name="create", help="Create a project")
def project_create(
    name: str,
    ontology: UUID | None = typer.Option(None, "--ontology"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).projects.create(
            name,
            ontology_hash=str(ontology) if ontology else None,
        ),
        json_output,
    )


@project_app.command(name="update", help="Rename or describe a project")
def project_update(
    project_id: UUID,
    name: str | None = typer.Option(None),
    description: str | None = typer.Option(None),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key)
        .projects.get(str(project_id))
        .update(name=name, description=description),
        json_output,
    )


@project_app.command(name="delete", help="Delete a project")
def project_delete(
    project_id: UUID,
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
    api_key: API_KEY = None,
):
    if not yes and not typer.confirm("Delete this project?"):
        raise typer.Abort()
    get_client(api_key).projects.get(str(project_id)).delete()
    typer.echo("Project deleted.")


@project_app.command(name="data-units", help="List a project's Data Units")
def project_data_units(
    project_id: UUID,
    search: str | None = typer.Option(None),
    data_type: str | None = typer.Option(None, "--data-type"),
    status: str | None = typer.Option(None),
    batch_queue: UUID | None = typer.Option(None, "--batch-queue"),
    kind: str | None = typer.Option(None),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    project = get_client(api_key).projects.get(str(project_id))
    emit(
        project.data_units(
            search=search,
            data_type=data_type,
            status=status,
            batch_queue=str(batch_queue) if batch_queue else None,
            kind=kind,
        ),
        json_output,
    )


@project_app.command(name="data-unit", help="Show one Project Data Unit")
def project_data_unit(
    project_id: UUID,
    data_unit_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_data_unit(str(project_id), str(data_unit_id)),
        json_output,
    )


@project_app.command(name="sources", help="List attached project sources")
def project_sources(
    project_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).projects.get(str(project_id)).attached_sources(),
        json_output,
    )


@project_app.command(name="detach-source", help="Detach a source from a project")
def project_detach_source(
    project_id: UUID,
    source_link_id: UUID,
    preview: bool = typer.Option(False),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    project = get_client(api_key).projects.get(str(project_id))
    emit(
        project.detach_source(str(source_link_id), preview=preview),
        json_output,
    )


@project_app.command(help="Upload local data into a project Batch Queue")
def upload(
    pk: UUID,
    source: Annotated[
        Path,
        typer.Option(
            "--source",
            "--directory",
            help="File or directory to upload",
        ),
    ],
    api_key: API_KEY = None,
    fps: Annotated[float, typer.Option(help="Frames per second for video")] = 1.0,
    json_output: JSON_OUTPUT = False,
):
    client = get_client(api_key)
    batch = client.projects.get(str(pk)).upload(
        source,
        fps=fps,
    )
    if json_output:
        emit(
            {
                "total": batch.total,
                "uploaded": batch.uploaded,
                "failed": len(batch.failed),
                "batch_queue_id": batch.batch_queue_id,
            },
            True,
        )
    else:
        typer.echo(f"Uploaded {batch.uploaded} of {batch.total} files")
    if batch.failed:
        raise typer.Exit(code=1)


@project_app.command(name="import-cloud", help="Import cloud paths into a project")
def project_import_cloud(
    pk: UUID,
    cloud_storage_id: UUID,
    paths: list[str] = typer.Argument(...),
    api_key: API_KEY = None,
    fps: Annotated[float | None, typer.Option(help="Video FPS")] = None,
    json_output: JSON_OUTPUT = False,
):
    client = get_client(api_key)
    batch = client.projects.get(str(pk)).import_cloud(
        str(cloud_storage_id),
        paths,
        fps=fps,
    )
    emit(
        {
            "file_count": batch.total,
            "batch_queue_id": batch.batch_queue_id,
        },
        json_output,
    )


@project_app.command(name="attach", help="Attach published data to a project")
def project_attach(
    pk: UUID,
    folder: list[UUID] | None = typer.Option(None, "--folder"),
    dataset: list[UUID] | None = typer.Option(None, "--dataset"),
    dataset_version: list[str] | None = typer.Option(None, "--dataset-version"),
    fps: float | None = typer.Option(None),
    preview: bool = typer.Option(False, help="Preview without attaching"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    versions = []
    for value in dataset_version or []:
        try:
            dataset_id, number = value.rsplit(":", 1)
            versions.append({"dataset_id": dataset_id, "version_number": int(number)})
        except ValueError as exc:
            raise typer.BadParameter("Use DATASET_ID:VERSION") from exc
    project = get_client(api_key).projects.get(str(pk))
    selection = {
        "folder_ids": [str(value) for value in folder or []],
        "dataset_ids": [str(value) for value in dataset or []],
        "dataset_versions": versions,
        "fps": fps,
    }
    if preview:
        emit(project.attach_preview(**selection), json_output)
        return
    result = project.attach(**selection)
    emit(
        {
            "data_item_ids": result.data_item_ids,
            "batch_queue_id": result.batch_queue_id,
            "created_count": result.created_count,
            "unassigned_count": result.unassigned_count,
            "already_attached_count": result.already_attached_count,
            "resolved_asset_count": result.resolved_asset_count,
            "attachment_ids": result.attachment_ids,
            "data_group_ids": result.data_group_ids,
            "project_dataset_version_number": (result.project_dataset_version_number),
        },
        json_output,
    )


@batch_queue_app.command(name="list", help="List a project's Batch Queues")
def batch_queue_list(
    project_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    queues = get_client(api_key).projects.get(str(project_id)).batch_queues()
    emit(queues, json_output)


@batch_queue_app.command(name="detail", help="Show one Batch Queue")
def batch_queue_detail(
    project_id: UUID,
    batch_queue_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    queue = (
        get_client(api_key)
        .projects.get(str(project_id))
        .batch_queue(str(batch_queue_id))
    )
    emit(queue, json_output)


@batch_queue_app.command(name="wait", help="Wait for a Batch Queue")
def batch_queue_wait(
    project_id: UUID,
    batch_queue_id: UUID,
    timeout: float = typer.Option(1800),
    api_key: API_KEY = None,
):
    status = (
        get_client(api_key)
        .projects.get(str(project_id))
        .batch_queue(str(batch_queue_id))
        .wait(timeout=timeout, show_progress=sys.stderr.isatty())
    )
    emit(status, True)


@batch_queue_app.command(name="status", help="Show Batch Queue processing status")
def batch_queue_status(
    project_id: UUID,
    batch_queue_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    queue = (
        get_client(api_key)
        .projects.get(str(project_id))
        .batch_queue(str(batch_queue_id))
    )
    emit(queue.status(), json_output)


@batch_queue_app.command(name="data", help="List data in a Batch Queue")
def batch_queue_data(
    project_id: UUID,
    batch_queue_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    queue = (
        get_client(api_key)
        .projects.get(str(project_id))
        .batch_queue(str(batch_queue_id))
    )
    emit(queue.data(), json_output)


@assets_app.command(name="upload", help="Upload files into Assets")
def assets_upload(
    source: Path,
    folder: str | None = typer.Option(None),
    folder_id: UUID | None = typer.Option(None),
    path: str | None = typer.Option(None),
    tag: list[str] | None = typer.Option(None, "--tag"),
    custom_metadata: str | None = typer.Option(
        None,
        "--custom-metadata",
        help="JSON object or null applied to every uploaded Asset",
    ),
    custom_metadata_file: Path | None = typer.Option(
        None,
        "--custom-metadata-file",
        help="Path to a JSON object or null applied to every uploaded Asset",
    ),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    metadata = _load_custom_metadata(custom_metadata, custom_metadata_file)
    result = get_client(api_key).assets.upload(
        source,
        folder=folder,
        folder_id=str(folder_id) if folder_id else None,
        path=path,
        tags=tag,
        custom_metadata=metadata,
    )
    emit(
        {
            "folder_id": result.folder_id,
            "folder_name": result.folder_name,
            "uploaded": result.uploaded,
            "failed": len(result.failed),
            "assets": [
                {
                    "id": asset.id,
                    "file_name": asset.file_name,
                    "data_type": asset.data_type,
                    "folder_id": asset.folder_id,
                    "custom_metadata": asset.custom_metadata,
                }
                for asset in result.assets
            ],
        },
        json_output,
    )
    if result.failed:
        raise typer.Exit(code=1)


@assets_app.command(name="set-metadata", help="Replace an Asset's custom metadata")
def assets_set_metadata(
    asset_id: UUID,
    custom_metadata: str | None = typer.Option(
        None,
        "--custom-metadata",
        help="JSON object or null replacing the Asset's custom metadata",
    ),
    custom_metadata_file: Path | None = typer.Option(
        None,
        "--custom-metadata-file",
        help="Path to a JSON object or null replacing the Asset's custom metadata",
    ),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    metadata = _load_custom_metadata(
        custom_metadata,
        custom_metadata_file,
        required=True,
    )
    asset = get_client(api_key).assets.set_custom_metadata(
        str(asset_id),
        metadata,
    )
    emit(
        {
            "id": asset.id,
            "file_name": asset.file_name,
            "custom_metadata": asset.custom_metadata,
        },
        json_output,
    )


@folders_app.command(name="create", help="Create a folder")
def folder_create(
    name: str,
    parent: UUID | None = typer.Option(None),
    cloud_storage: UUID | None = typer.Option(None, "--cloud-storage"),
    prefix: str = typer.Option(""),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    client = get_client(api_key)
    if cloud_storage:
        result = client.assets.create_cloud_folder(
            name,
            str(cloud_storage),
            prefix=prefix,
        )
    else:
        result = client.assets.create_folder(
            name,
            parent_id=str(parent) if parent else None,
        )
    emit(result, json_output)


@folders_app.command(name="list", help="List folders")
def folder_list(
    parent: UUID | None = typer.Option(None),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    assets = get_client(api_key).assets
    folders = assets.folders(parent=str(parent)) if parent else assets.all_folders()
    emit(folders, json_output)


@folders_app.command(name="sync-cloud", help="Sync a cloud folder")
def folder_sync_cloud(
    folder_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).assets.folder(str(folder_id)).sync_cloud(),
        json_output,
    )


@folders_app.command(name="detail", help="Show a folder")
def folder_detail(
    folder_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).assets.folder(str(folder_id)), json_output)


@assets_app.command(name="group", help="Create Data Groups")
def assets_group(
    folder_id: UUID,
    config: Path | None = typer.Option(None),
    template: str | None = typer.Option(None),
    tile_values: list[str] | None = typer.Option(None, "--tile-values"),
    preview: bool = typer.Option(False, help="Suggest or estimate without creating"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    grouping = None
    if config:
        grouping = json.loads(config.read_text())
    elif template:
        parsed = {}
        for value in tile_values or []:
            key, raw_values = value.split("=", 1)
            parsed[key] = raw_values.split(",")
        grouping = tiles_from_template(template, parsed)
    folder = get_client(api_key).assets.folder(str(folder_id))
    if preview:
        result = (
            folder.estimate_grouping(grouping)
            if grouping is not None
            else folder.suggest_grouping()
        )
        emit(result, json_output)
        return
    result = folder.auto_group(grouping)
    emit(result, json_output)


@embeddings_app.command(name="list", help="List custom embedding spaces")
def embeddings_list(
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).embedding_spaces.list(), json_output)


@embeddings_app.command(name="create", help="Create a custom embedding space")
def embeddings_create(
    name: str,
    dimensions: int = typer.Option(..., min=1, max=4096),
    model_name: str | None = typer.Option(None, "--model-name"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).embedding_spaces.create(
            name,
            dimensions=dimensions,
            model_name=model_name,
        ),
        json_output,
    )


@embeddings_app.command(name="detail", help="Show a custom embedding space")
def embeddings_detail(
    space_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).embedding_spaces.get(str(space_id)), json_output)


@embeddings_app.command(name="delete", help="Delete a custom embedding space")
def embeddings_delete(
    space_id: UUID,
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
    api_key: API_KEY = None,
):
    if not yes and not typer.confirm("Delete this embedding space?"):
        raise typer.Abort()
    get_client(api_key).embedding_spaces.get(str(space_id)).delete()
    typer.echo("Embedding space deleted.")


@embeddings_app.command(name="upsert", help="Add or replace one embedding")
def embeddings_upsert(
    space_id: UUID,
    asset_id: UUID,
    vector_file: Path = typer.Option(..., "--vector-file"),
    frame_index: int | None = typer.Option(None, "--frame-index", min=0),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    space = get_client(api_key).embedding_spaces.get(str(space_id))
    emit(
        space.upsert(
            str(asset_id),
            _load_vector(vector_file),
            frame_index=frame_index,
        ),
        json_output,
    )


@embeddings_app.command(name="upload", help="Upload embeddings from JSONL")
def embeddings_upload(
    space_id: UUID,
    jsonl: Path,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    space = get_client(api_key).embedding_spaces.get(str(space_id))
    submitted = created = updated = batches = 0
    result_space_id = space.id
    for batch in _embedding_jsonl_batches(jsonl):
        result = space.upsert_many(batch)
        result_space_id = str(result.get("space_id", result_space_id))
        submitted += int(result.get("submitted", len(batch)))
        created += int(result.get("created", 0))
        updated += int(result.get("updated", 0))
        batches += 1
    emit(
        {
            "space_id": result_space_id,
            "submitted": submitted,
            "created": created,
            "updated": updated,
            "batches": batches,
        },
        json_output,
    )


@embeddings_app.command(name="search", help="Search with a query vector")
def embeddings_search(
    space_id: UUID,
    vector_file: Path = typer.Option(..., "--vector-file"),
    limit: int | None = typer.Option(None, min=1, max=100),
    project: UUID | None = typer.Option(None, "--project"),
    level: EmbeddingLevel = typer.Option(EmbeddingLevel.asset),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    space = get_client(api_key).embedding_spaces.get(str(space_id))
    emit(
        space.search(
            _load_vector(vector_file),
            limit=limit,
            project_id=str(project) if project else None,
            level=level.value,
        ),
        json_output,
    )


@dataset_app.command(name="list", help="List datasets")
def dataset_list(
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).datasets.list(), json_output)


@dataset_app.command(name="create", help="Create a dataset")
def dataset_create(
    name: str,
    folder: list[UUID] | None = typer.Option(None, "--folder"),
    asset: list[UUID] | None = typer.Option(None, "--asset"),
    description: str = typer.Option(""),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    result = get_client(api_key).datasets.create(
        name,
        description=description,
        folder_ids=[str(value) for value in folder or []],
        asset_ids=[str(value) for value in asset or []],
    )
    emit(result, json_output)


@dataset_app.command(name="detail", help="Show a dataset")
def dataset_detail(
    dataset_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).datasets.get(str(dataset_id)), json_output)


@dataset_app.command(name="add-sources", help="Add sources to a dataset")
def dataset_add_sources(
    dataset_id: UUID,
    folder: list[UUID] | None = typer.Option(None, "--folder"),
    asset: list[UUID] | None = typer.Option(None, "--asset"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    result = (
        get_client(api_key)
        .datasets.get(str(dataset_id))
        .add_sources(
            folder_ids=[str(value) for value in folder or []],
            asset_ids=[str(value) for value in asset or []],
        )
    )
    emit(result, json_output)


@dataset_app.command(name="publish", help="Publish a dataset version")
def dataset_publish(
    dataset_id: UUID,
    title: str = typer.Option(...),
    description: str = typer.Option(""),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    result = (
        get_client(api_key)
        .datasets.get(str(dataset_id))
        .publish_version(
            title,
            description=description,
        )
    )
    emit(result, json_output)


@dataset_app.command(name="versions", help="List dataset versions")
def dataset_versions(
    dataset_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).datasets.get(str(dataset_id)).versions(),
        json_output,
    )


@dataset_app.command(
    name="unpublished-changes",
    help="Show a dataset's Unpublished changes",
)
def dataset_unpublished_changes(
    dataset_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    changes = get_client(api_key).datasets.get(str(dataset_id)).unpublished_changes()
    emit(changes, json_output)


@folders_app.command(name="items", help="List items in a folder")
def folder_items(
    folder_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).assets.folder(str(folder_id)).list_items(),
        json_output,
    )


@dataset_app.command(name="items", help="List draft or published Dataset items")
def dataset_items(
    dataset_id: UUID,
    version: int | None = typer.Option(None, min=1),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).datasets.get(str(dataset_id)).list_items(version=version),
        json_output,
    )


@workflow_app.command(name="stages", help="List a Project's Workflow stages")
def workflow_stages(
    project_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).projects.get(str(project_id)).workflow.stages, json_output)


@workflow_app.command(name="tasks", help="List tasks in one Workflow stage")
def workflow_tasks(
    project_id: UUID,
    stage: str = typer.Option(...),
    include_unavailable: bool = typer.Option(False),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    workflow = get_client(api_key).projects.get(str(project_id)).workflow
    emit(
        workflow.get_stage(stage_id=stage).get_tasks(
            include_unavailable=include_unavailable
        ),
        json_output,
    )


@workflow_app.command(name="task", help="Show one Workflow Task")
def workflow_task(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).get_workflow_task(str(task_id)), json_output)


@workflow_app.command(name="claim", help="Claim a Workflow Task")
def workflow_claim(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).get_workflow_task(str(task_id)).claim(), json_output)


@workflow_app.command(name="assign", help="Assign a Workflow Task")
def workflow_assign(
    task_id: UUID,
    user_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_workflow_task(str(task_id)).assign(str(user_id)),
        json_output,
    )


@workflow_app.command(name="release", help="Release a Workflow Task")
def workflow_release(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).get_workflow_task(str(task_id)).release(), json_output)


@workflow_app.command(name="priority", help="Set Workflow Task priority")
def workflow_priority(
    task_id: UUID,
    priority: int,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_workflow_task(str(task_id)).set_priority(priority),
        json_output,
    )


@workflow_app.command(name="submit", help="Send a task through its forward edge")
def workflow_submit(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_workflow_task(str(task_id)).submit(),
        json_output,
    )


@workflow_app.command(name="approve", help="Approve a Review task")
def workflow_approve(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_workflow_task(str(task_id)).approve(),
        json_output,
    )


@workflow_app.command(name="reject", help="Reject a Review task")
def workflow_reject(
    task_id: UUID,
    reason: str = typer.Option(""),
    comment: str = typer.Option(""),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key)
        .get_workflow_task(str(task_id))
        .reject(reason=reason, comment=comment),
        json_output,
    )


@workflow_app.command(name="skip", help="Send a task through its skip edge")
def workflow_skip(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_workflow_task(str(task_id)).skip(),
        json_output,
    )


@workflow_app.command(name="move", help="Move a task directly to another stage")
def workflow_move(
    task_id: UUID,
    stage_id: str,
    reason: str = typer.Option(""),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key)
        .get_workflow_task(str(task_id))
        .move(stage_id, reason=reason),
        json_output,
    )


@workflow_app.command(name="timeline", help="Show Workflow Task history")
def workflow_timeline(
    task_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).get_workflow_task(str(task_id)).get_timeline(),
        json_output,
    )


@workflow_app.command(name="bulk-assign", help="Assign multiple Workflow Tasks")
def workflow_bulk_assign(
    project_id: UUID,
    task: list[UUID] = typer.Option(..., "--task"),
    user_id: UUID = typer.Option(..., "--user"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    workflow = get_client(api_key).projects.get(str(project_id)).workflow
    emit(
        workflow.assign_tasks(
            [str(value) for value in task],
            user_id=str(user_id),
        ),
        json_output,
    )


@workflow_app.command(name="bulk-move", help="Move multiple Workflow Tasks")
def workflow_bulk_move(
    project_id: UUID,
    task: list[UUID] = typer.Option(..., "--task"),
    stage_id: str = typer.Option(..., "--stage"),
    reason: str = typer.Option(""),
    dry_run: bool = typer.Option(False),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    workflow = get_client(api_key).projects.get(str(project_id)).workflow
    emit(
        workflow.move_tasks(
            [str(value) for value in task],
            destination_stage=stage_id,
            reason=reason,
            dry_run=dry_run,
        ),
        json_output,
    )


@release_app.command(name="list", help="List Releases")
def release_list(api_key: API_KEY = None, json_output: JSON_OUTPUT = False):
    emit(get_client(api_key).releases.list(), json_output)


@release_app.command(name="download", help="Download a Release")
def release_download(
    pk: UUID,
    download_type: DownloadType = typer.Option(DownloadType.annotation),
    split_type: str | None = typer.Option(None),
    dest: Path | None = typer.Option(None),
    api_key: API_KEY = None,
):
    release = get_client(api_key).releases.get(str(pk))
    result = (
        release.download(split_type)
        if download_type == DownloadType.annotation
        else release.download_files(dest=dest)
    )
    typer.echo(result)


@release_app.command(name="detail", help="Show a Release")
def release_detail(
    release_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).releases.get(str(release_id)), json_output)


@release_app.command(name="create", help="Create a Release from a project")
def release_create(
    project_id: UUID,
    export_type: str = typer.Option("UUEF", "--format"),
    splits: str = typer.Option("train=100"),
    data_type: list[str] | None = typer.Option(None, "--data-type"),
    include_download_tokens: bool = typer.Option(False),
    license_id: UUID | None = typer.Option(None, "--license"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    try:
        split_ratios = {
            key: int(value)
            for key, value in (part.split("=", 1) for part in splits.split(","))
        }
    except ValueError as exc:
        raise typer.BadParameter(
            "Use SPLIT=PERCENT, for example train=80,test=20"
        ) from exc
    client = get_client(api_key)
    release = client.releases.create(
        client.projects.get(str(project_id)),
        export_type=export_type,
        split_ratios=split_ratios,
        data_types=data_type,
        include_download_tokens=include_download_tokens,
        license_id=str(license_id) if license_id else None,
    )
    emit(release, json_output)


@ontology_app.command(name="list", help="List Ontologies")
def ontology_list(
    title_eq: str | None = typer.Option(None, "--title-eq"),
    title_like: str | None = typer.Option(None, "--title-like"),
    desc_eq: str | None = typer.Option(None, "--description-eq"),
    desc_like: str | None = typer.Option(None, "--description-like"),
    created_before: str | None = typer.Option(None, "--created-before"),
    created_after: str | None = typer.Option(None, "--created-after"),
    edited_before: str | None = typer.Option(None, "--edited-before"),
    edited_after: str | None = typer.Option(None, "--edited-after"),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(
        get_client(api_key).ontologies.list(
            title_eq=title_eq,
            title_like=title_like,
            desc_eq=desc_eq,
            desc_like=desc_like,
            created_before=created_before,
            created_after=created_after,
            edited_before=edited_before,
            edited_after=edited_after,
        ),
        json_output,
    )


@ontology_app.command(name="detail", help="Show an Ontology")
def ontology_detail(
    ontology_id: UUID,
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    emit(get_client(api_key).ontologies.get(str(ontology_id)), json_output)


@ontology_app.command(name="create", help="Create an Ontology")
def ontology_create(
    title: str,
    description: str = typer.Option(""),
    data_type: str = typer.Option("image", "--data-type"),
    structure: Path | None = typer.Option(None),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    structure_data = json.loads(structure.read_text()) if structure else None
    emit(
        get_client(api_key).ontologies.create(
            title,
            description=description,
            data_type=data_type,
            structure=structure_data,
        ),
        json_output,
    )


@ontology_app.command(name="update", help="Update an Ontology")
def ontology_update(
    ontology_id: UUID,
    title: str | None = typer.Option(None),
    description: str | None = typer.Option(None),
    data_type: str | None = typer.Option(None, "--data-type"),
    structure: Path | None = typer.Option(None),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    ontology = get_client(api_key).ontologies.get(str(ontology_id))
    if title is not None:
        ontology.title = title
    if description is not None:
        ontology.description = description
    if data_type is not None:
        ontology.data_type = data_type
    if structure is not None:
        ontology.structure = OntologyStructure.from_dict(
            json.loads(structure.read_text())
        )
    ontology.save()
    emit(ontology, json_output)


@cloud_app.command(name="list", help="List cloud storage integrations")
def cloud_list(api_key: API_KEY = None, json_output: JSON_OUTPUT = False):
    emit(get_client(api_key).cloud_storages.list(), json_output)


@cloud_app.command(name="browse", help="Browse cloud storage")
def cloud_browse(
    cloud_storage_id: UUID,
    prefix: str = typer.Option(""),
    project: UUID | None = typer.Option(None),
    page_size: int = typer.Option(500, min=1, max=1000),
    api_key: API_KEY = None,
    json_output: JSON_OUTPUT = False,
):
    entries = list(
        get_client(api_key)
        .cloud_storages.get(str(cloud_storage_id))
        .browse(
            prefix=prefix,
            project=str(project) if project else None,
            page_size=page_size,
        )
    )
    emit(entries, json_output)


def main() -> None:
    try:
        app()
    except (UnitlabError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
