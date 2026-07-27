import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from unitlab import UnitlabError, __version__
from unitlab.cli import _jsonable, app, main
from unitlab.resources.projects import Project

runner = CliRunner()


def test_configure_uses_stdlib_url_validation(monkeypatch):
    monkeypatch.setattr("unitlab.cli._config.write_config", lambda **_values: None)
    valid = runner.invoke(app, ["configure", "--api-url", "http://localhost:8000"])
    invalid = runner.invoke(app, ["configure", "--api-url", "ftp://example.com"])
    assert valid.exit_code == 0
    assert invalid.exit_code != 0


def test_cli_exposes_canonical_command_trees():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "project",
        "batch-queue",
        "assets",
        "folders",
        "dataset",
        "workflow",
        "release",
        "ontology",
        "cloud",
    ):
        assert command in result.stdout

    project_help = runner.invoke(app, ["project", "--help"])
    assert project_help.exit_code == 0
    for command in (
        "create",
        "list",
        "detail",
        "upload",
        "import-cloud",
        "update",
        "delete",
        "data-unit",
        "data-units",
        "sources",
        "detach-source",
    ):
        assert command in project_help.stdout
    assert "upload-requirements" not in project_help.stdout
    assert "sessions" not in project_help.stdout
    assert "wait" not in project_help.stdout

    for command in ("upload", "import-cloud"):
        command_help = runner.invoke(app, ["project", command, "--help"])
        assert command_help.exit_code == 0
        assert "--wait" not in command_help.stdout
    attach_help = runner.invoke(app, ["project", "attach", "--help"])
    assert attach_help.exit_code == 0
    assert "--asset" not in attach_help.stdout

    dataset_help = runner.invoke(app, ["dataset", "--help"])
    assert dataset_help.exit_code == 0
    assert "download" not in dataset_help.stdout
    for command in (
        "create",
        "detail",
        "add-sources",
        "items",
        "publish",
        "versions",
        "unpublished-changes",
    ):
        assert command in dataset_help.stdout
    publish_help = runner.invoke(app, ["dataset", "publish", "--help"])
    assert publish_help.exit_code == 0
    assert "--splits" not in publish_help.stdout

    batch_help = runner.invoke(app, ["batch-queue", "--help"])
    assert batch_help.exit_code == 0
    for command in ("list", "detail", "status", "data", "wait"):
        assert command in batch_help.stdout

    folders_help = runner.invoke(app, ["folders", "--help"])
    assert folders_help.exit_code == 0
    assert "items" in folders_help.stdout
    assert "upload" not in folders_help.stdout

    workflow_help = runner.invoke(app, ["workflow", "--help"])
    assert workflow_help.exit_code == 0
    for command in (
        "stages",
        "tasks",
        "task",
        "claim",
        "assign",
        "release",
        "priority",
        "submit",
        "approve",
        "reject",
        "skip",
        "move",
        "timeline",
        "bulk-assign",
        "bulk-move",
    ):
        assert command in workflow_help.stdout

    release_help = runner.invoke(app, ["release", "--help"])
    assert release_help.exit_code == 0
    assert "create" in release_help.stdout

    ontology_help = runner.invoke(app, ["ontology", "--help"])
    assert ontology_help.exit_code == 0
    for command in ("list", "detail", "create", "update"):
        assert command in ontology_help.stdout

    assets_help = runner.invoke(app, ["assets", "--help"])
    assert assets_help.exit_code == 0
    assert "set-metadata" in assets_help.stdout
    for command in ("upload", "set-metadata"):
        command_help = runner.invoke(app, ["assets", command, "--help"])
        assert "--custom-metadata" in command_help.stdout
        assert "--custom-metadata-file" in command_help.stdout


def test_cli_basics():
    no_command = runner.invoke(app, [])
    short_help = runner.invoke(app, ["-h"])
    version = runner.invoke(app, ["--version"])

    assert no_command.exit_code == 0
    assert "Manage Unitlab projects" in no_command.stdout
    assert "Example: unitlab project list" in no_command.stdout
    assert "https://docs.unitlab.ai" in no_command.stdout
    assert "https://github.com/teamunitlab/unitlab-sdk/issues" in no_command.stdout
    assert short_help.exit_code == 0
    assert "Project commands" in short_help.stdout
    assert version.exit_code == 0
    assert version.stdout.strip() == __version__


def test_human_output_is_concise(monkeypatch):
    project = Project(
        id="project-1",
        name="Review",
        raw={"pk": "project-1"},
        _client=object(),
    )
    projects = type("Projects", (), {"list": lambda self: [project]})()
    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: type("Client", (), {"projects": projects})(),
    )

    result = runner.invoke(app, ["project", "list"])

    assert result.exit_code == 0
    assert "id=project-1" in result.stdout
    assert "name=Review" in result.stdout
    assert "Project(" not in result.stdout


def test_dataset_list_only_lists_datasets(monkeypatch):
    class Datasets:
        @staticmethod
        def list():
            return [{"pk": "dataset-1"}]

    client = type("Client", (), {"datasets": Datasets()})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)

    result = runner.invoke(app, ["dataset", "list"])
    assert result.exit_code == 0
    assert "dataset-1" in result.stdout

    duplicate = runner.invoke(app, ["dataset", "list", "--kind", "releases"])
    assert duplicate.exit_code != 0


def test_json_output_uses_public_resource_names():
    project = Project(
        id="project-1",
        name="Review",
        raw={"pk": "project-1", "backend_only": True},
        _client=object(),
    )
    output = _jsonable(project)
    assert output["id"] == "project-1"
    assert output["name"] == "Review"
    assert output["data_item_count"] == 0
    assert "pk" not in output
    assert "backend_only" not in output


def test_project_data_unit_uses_project_scope(monkeypatch):
    calls = []
    client = type(
        "Client",
        (),
        {
            "get_data_unit": lambda self, project_id, unit_id: (
                calls.append((project_id, unit_id)) or {"id": unit_id}
            ),
        },
    )()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)
    project_id = "00000000-0000-0000-0000-000000000001"
    unit_id = "00000000-0000-0000-0000-000000000002"

    result = runner.invoke(
        app,
        ["project", "data-unit", project_id, unit_id, "--json"],
    )

    assert result.exit_code == 0
    assert calls == [(project_id, unit_id)]
    assert unit_id in result.stdout


def test_project_upload_exits_nonzero_on_partial_failure(monkeypatch, tmp_path):
    calls = []
    batch = type(
        "Batch",
        (),
        {
            "total": 2,
            "uploaded": 1,
            "failed": [object()],
            "batch_queue_id": "queue-1",
        },
    )()
    project = type(
        "Project",
        (),
        {"upload": lambda self, *args, **kwargs: calls.append((args, kwargs)) or batch},
    )()
    projects = type("Projects", (), {"get": lambda self, _project_id: project})()
    client = type("Client", (), {"projects": projects})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)

    result = runner.invoke(
        app,
        [
            "project",
            "upload",
            "00000000-0000-0000-0000-000000000001",
            "--directory",
            str(tmp_path),
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert '"failed": 1' in result.stdout
    assert "show_progress" not in calls[0][1]


def test_assets_cli_supports_custom_metadata(monkeypatch, tmp_path):
    calls = []
    metadata = {"region": "CA-BC", "camera": {"settings": ["night"]}}
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text(json.dumps(metadata))
    asset = SimpleNamespace(
        id="asset-1",
        file_name="image.png",
        data_type="image",
        folder_id="folder-1",
        custom_metadata=metadata,
    )
    upload = SimpleNamespace(
        folder_id="folder-1",
        folder_name="Regional",
        uploaded=1,
        failed=[],
        assets=[asset],
    )

    class Assets:
        @staticmethod
        def upload(source, **kwargs):
            calls.append(("upload", source, kwargs))
            return upload

        @staticmethod
        def set_custom_metadata(asset_id, custom_metadata):
            calls.append(("set", asset_id, custom_metadata))
            return asset

    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: SimpleNamespace(assets=Assets()),
    )

    upload_result = runner.invoke(
        app,
        [
            "assets",
            "upload",
            str(tmp_path),
            "--custom-metadata-file",
            str(metadata_file),
            "--json",
        ],
    )
    set_result = runner.invoke(
        app,
        [
            "assets",
            "set-metadata",
            "00000000-0000-0000-0000-000000000001",
            "--custom-metadata-file",
            str(metadata_file),
            "--json",
        ],
    )

    assert upload_result.exit_code == 0
    assert set_result.exit_code == 0
    assert calls[0][2]["custom_metadata"] == metadata
    assert calls[1] == (
        "set",
        "00000000-0000-0000-0000-000000000001",
        metadata,
    )
    assert '"custom_metadata"' in upload_result.stdout
    assert '"custom_metadata"' in set_result.stdout


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("{", "must be valid JSON"),
        ("[]", "must be a JSON object or null"),
    ],
)
def test_assets_cli_rejects_non_object_custom_metadata(
    monkeypatch,
    tmp_path,
    value,
    message,
):
    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: pytest.fail("invalid metadata reached the SDK"),
    )

    result = runner.invoke(
        app,
        [
            "assets",
            "upload",
            str(tmp_path),
            "--custom-metadata",
            value,
        ],
    )

    assert result.exit_code != 0
    assert message in result.output


@pytest.mark.parametrize("command", ["upload", "set-metadata"])
def test_assets_cli_custom_metadata_options_are_mutually_exclusive(
    monkeypatch,
    tmp_path,
    command,
):
    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: pytest.fail("invalid metadata reached the SDK"),
    )
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text("{}")
    target = (
        str(tmp_path) if command == "upload" else "00000000-0000-0000-0000-000000000001"
    )

    result = runner.invoke(
        app,
        [
            "assets",
            command,
            target,
            "--custom-metadata",
            "{}",
            "--custom-metadata-file",
            str(metadata_file),
        ],
    )

    assert result.exit_code != 0
    assert "not both" in result.output


def test_assets_set_metadata_requires_inline_or_file(monkeypatch):
    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: pytest.fail("missing metadata reached the SDK"),
    )

    result = runner.invoke(
        app,
        [
            "assets",
            "set-metadata",
            "00000000-0000-0000-0000-000000000001",
        ],
    )

    assert result.exit_code != 0
    assert "Provide --custom-metadata or --custom-metadata-file" in result.output


def test_assets_set_metadata_accepts_null(monkeypatch):
    calls = []
    asset = SimpleNamespace(
        id="asset-1",
        file_name="image.png",
        custom_metadata=None,
    )

    class Assets:
        @staticmethod
        def set_custom_metadata(asset_id, custom_metadata):
            calls.append((asset_id, custom_metadata))
            return asset

    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: SimpleNamespace(assets=Assets()),
    )

    result = runner.invoke(
        app,
        [
            "assets",
            "set-metadata",
            "00000000-0000-0000-0000-000000000001",
            "--custom-metadata",
            "null",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [("00000000-0000-0000-0000-000000000001", None)]
    assert '"custom_metadata": null' in result.stdout


def test_ontology_list_passes_supported_filters(monkeypatch):
    calls = []

    class Ontologies:
        @staticmethod
        def list(**filters):
            calls.append(filters)
            return []

    client = type("Client", (), {"ontologies": Ontologies()})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)

    result = runner.invoke(
        app,
        [
            "ontology",
            "list",
            "--title-eq",
            "Cats",
            "--title-like",
            "Cat",
            "--description-eq",
            "Labels",
            "--description-like",
            "Lab",
            "--created-before",
            "2026-01-01",
            "--created-after",
            "2025-01-01",
            "--edited-before",
            "2026-02-01",
            "--edited-after",
            "2025-02-01",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        {
            "title_eq": "Cats",
            "title_like": "Cat",
            "desc_eq": "Labels",
            "desc_like": "Lab",
            "created_before": "2026-01-01",
            "created_after": "2025-01-01",
            "edited_before": "2026-02-01",
            "edited_after": "2025-02-01",
        }
    ]


def test_folder_list_defaults_to_all_and_parent_scopes(monkeypatch):
    calls = []

    class Assets:
        @staticmethod
        def all_folders():
            calls.append("all")
            return ["all-folders"]

        @staticmethod
        def folders(*, parent):
            calls.append(parent)
            return ["child-folders"]

    client = type("Client", (), {"assets": Assets()})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)

    result = runner.invoke(app, ["folders", "list"])
    assert result.exit_code == 0
    assert "all-folders" in result.stdout

    parent_id = "00000000-0000-0000-0000-000000000001"
    result = runner.invoke(
        app,
        ["folders", "list", "--parent", parent_id],
    )
    assert result.exit_code == 0
    assert "child-folders" in result.stdout
    assert calls == ["all", parent_id]

    help_result = runner.invoke(app, ["folders", "list", "--help"])
    assert help_result.exit_code == 0
    assert "--all" not in help_result.stdout

    folders_help = runner.invoke(app, ["folders", "--help"])
    assert folders_help.exit_code == 0
    assert "Asset folder" not in folders_help.stdout

    assets_help = runner.invoke(app, ["assets", "--help"])
    assert assets_help.exit_code == 0
    assert "folder" not in assets_help.stdout.lower()


def test_console_entrypoint_prints_concise_sdk_errors(monkeypatch, capsys):
    def fail():
        raise UnitlabError("Actionable failure")

    monkeypatch.setattr("unitlab.cli.app", fail)
    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 1
    assert capsys.readouterr().err == "Error: Actionable failure\n"
