"""The CLI's lidar scene options and commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from unitlab.cli import app
from unitlab.types import ProcessingStatus

runner = CliRunner()
PROJECT_ID = "00000000-0000-0000-0000-000000000001"
ITEM_ID = "00000000-0000-0000-0000-000000000002"


def scene_folder(root, name, frames=2, sensor="lidar"):
    folder = root / name / sensor
    folder.mkdir(parents=True)
    for index in range(frames):
        (folder / f"{index:03d}.pcd").write_bytes(b"cloud")


def no_client(_api_key):
    raise AssertionError("a preview must not contact the server")


def project_client(monkeypatch, calls):
    batch = type(
        "Batch",
        (),
        {"total": 2, "uploaded": 2, "failed": [], "batch_queue_id": "queue-1"},
    )()
    project = type(
        "Project",
        (),
        {
            "upload": lambda self, *args, **kwargs: calls.append(kwargs) or batch,
            "scene_status": lambda self, item_id: (
                calls.append(("status", item_id))
                or ProcessingStatus(
                    "failed", 1, 0, 0, 1, error="No point clouds found."
                )
            ),
            "retry_scene": lambda self, item_id: (
                calls.append(("retry", item_id))
                or {"task_id": "task", "status": "processing"}
            ),
        },
    )()
    projects = type("Projects", (), {"get": lambda self, _project_id: project})()
    client = type("Client", (), {"projects": projects})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)


def test_project_upload_passes_the_scene_options_only_when_given(monkeypatch, tmp_path):
    calls = []
    project_client(monkeypatch, calls)

    plain = runner.invoke(
        app, ["project", "upload", PROJECT_ID, "--source", str(tmp_path)]
    )
    scenes = runner.invoke(
        app,
        [
            "project",
            "upload",
            PROJECT_ID,
            "--source",
            str(tmp_path),
            "--type",
            "pointcloud",
            "--split-sensor-folders",
        ],
    )

    assert (plain.exit_code, scenes.exit_code) == (0, 0)
    assert calls == [
        {"fps": 1.0},
        {"fps": 1.0, "generic_type": "pointcloud", "split_sensor_folders": True},
    ]
    assert "Uploaded 2 of 2 files" in plain.stdout
    assert "Uploaded 2 of 2 scenes" in scenes.stdout


def test_dry_run_lists_the_scenes_and_uploads_nothing(monkeypatch, tmp_path):
    root = tmp_path / "recordings"
    scene_folder(root, "drive_01", frames=2)
    scene_folder(root, "rig", frames=3, sensor="top")
    scene_folder(root, "rig", frames=3, sensor="left")
    (root / "notes.txt").write_text("calibration notes")
    monkeypatch.setattr("unitlab.cli.get_client", no_client)

    result = runner.invoke(
        app,
        [
            "project",
            "upload",
            PROJECT_ID,
            "--source",
            str(root),
            "--type",
            "pointcloud",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == "2 scenes found, nothing uploaded"
    drive, rig = (
        next(line for line in lines if line.strip().startswith(name))
        for name in ("drive_01", "rig")
    )
    assert drive.split() == ["drive_01", "2", "frames", "lidar", "-", "10", "B"]
    assert rig.split() == ["rig", "3", "frames", "left,", "top", "-", "30", "B"]
    assert (
        "can also be read as 2 scenes (--split-sensor-folders)"
        in lines[lines.index(rig) + 1]
    )
    assert lines[-1].strip() == ("1 other file in these folders is not part of a scene")


def test_dry_run_prints_json(monkeypatch, tmp_path):
    scene_folder(tmp_path, "drive_01", frames=2)
    monkeypatch.setattr("unitlab.cli.get_client", no_client)

    result = runner.invoke(
        app,
        [
            "assets",
            "upload",
            str(tmp_path / "drive_01"),
            "--type",
            "pointcloud",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "scenes": [
            {
                "name": "drive_01",
                "source": "folder",
                "frame_count": 2,
                "point_sensors": ["lidar"],
                "cameras": [],
                "file_count": 2,
                "total_bytes": 10,
                "missing_files": 0,
                "notes": [],
                "split_scenes": 0,
            }
        ],
        "unused_files": 0,
        "other_files": 0,
    }


def test_the_scene_flags_need_the_type(monkeypatch, tmp_path):
    monkeypatch.setattr("unitlab.cli.get_client", no_client)

    for flag in ("--dry-run", "--split-sensor-folders"):
        result = runner.invoke(
            app, ["project", "upload", PROJECT_ID, "--source", str(tmp_path), flag]
        )

        assert result.exit_code == 2
        assert "--type pointcloud" in result.output


def test_assets_upload_passes_the_scene_options_only_when_given(monkeypatch, tmp_path):
    calls = []
    result_type = type(
        "Result",
        (),
        {
            "folder_id": "folder-1",
            "folder_name": "Lidar",
            "uploaded": 1,
            "failed": [],
            "assets": [],
        },
    )
    assets = type(
        "Assets",
        (),
        {"upload": lambda self, *args, **kwargs: calls.append(kwargs) or result_type()},
    )()
    client = type("Client", (), {"assets": assets})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)

    plain = runner.invoke(app, ["assets", "upload", str(tmp_path)])
    scenes = runner.invoke(
        app, ["assets", "upload", str(tmp_path), "--type", "pointcloud"]
    )

    assert (plain.exit_code, scenes.exit_code) == (0, 0)
    assert "generic_type" not in calls[0]
    assert "split_sensor_folders" not in calls[0]
    assert calls[1]["generic_type"] == "pointcloud"
    assert "split_sensor_folders" not in calls[1]


def test_scene_status_and_retry_commands(monkeypatch):
    calls = []
    project_client(monkeypatch, calls)

    status = runner.invoke(
        app, ["project", "scene-status", PROJECT_ID, ITEM_ID, "--json"]
    )
    retry = runner.invoke(
        app, ["project", "scene-retry", PROJECT_ID, ITEM_ID, "--json"]
    )

    assert (status.exit_code, retry.exit_code) == (0, 0)
    assert calls == [("status", ITEM_ID), ("retry", ITEM_ID)]
    assert json.loads(status.stdout)["error"] == "No point clouds found."
    assert json.loads(retry.stdout) == {"task_id": "task", "status": "processing"}


def test_asset_status_and_retry_commands(monkeypatch):
    calls = []
    asset = type(
        "Asset",
        (),
        {
            "status": lambda self: (
                calls.append("status") or ProcessingStatus("completed", 1, 1, 0, 0)
            ),
            "retry": lambda self: (
                calls.append("retry") or {"task_id": "task", "status": "processing"}
            ),
        },
    )()
    assets = type(
        "Assets", (), {"asset": lambda self, asset_id: calls.append(asset_id) or asset}
    )()
    client = type("Client", (), {"assets": assets})()
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)

    status = runner.invoke(app, ["assets", "status", ITEM_ID, "--json"])
    retry = runner.invoke(app, ["assets", "retry", ITEM_ID, "--json"])

    assert (status.exit_code, retry.exit_code) == (0, 0)
    assert calls == [ITEM_ID, "status", ITEM_ID, "retry"]
    assert json.loads(status.stdout)["status"] == "completed"
    assert json.loads(retry.stdout)["status"] == "processing"
