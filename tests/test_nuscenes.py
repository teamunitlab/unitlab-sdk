"""nuScenes datasets in the lidar scene detection (``unitlab._nuscenes``).

The ``detectPointcloudFolderScenes: nuScenes`` cases of the frontend's
``src/__tests__/pointcloud/pointcloudFolderScenes.test.ts``, translated one to
one (each test keeps the title of its ``it(...)``), on the same small dataset:
two recordings, one lidar, one radar and one camera, a sweep that is no key
frame, and files that belong to no scene.

``toBeCloseTo(value, 9)`` allows a difference below ``5e-10`` and the bare
``toBeCloseTo(value)`` one below ``5e-3``; ``close()`` keeps those bounds. The
generated ``scene.json`` is compared as parsed JSON, never as text: Python and
JavaScript write the same numbers with different digits (``1.0`` and ``1``).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from unitlab._scenes import SceneDetection, SceneFile, detect_folder_scenes

LIDAR_US = [1532402927647951, 1532402928147847, 1533151603547590]
QUARTER_TURN = [math.sqrt(0.5), 0, 0, math.sqrt(0.5)]


def close(value: float, digits: int = 9) -> object:
    """``toBeCloseTo(value, digits)``."""
    return pytest.approx(value, abs=10**-digits / 2, rel=0)


def folder(tmp_path: Path, entries: dict[str, object]) -> Path:
    """Writes a picked folder (path -> text or JSON value); returns its path."""
    roots = {path.split("/")[0] for path in entries}
    assert len(roots) == 1, "one picked folder per test"
    for path, content in entries.items():
        target = tmp_path.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content)
        target.write_bytes(text.encode("utf-8"))
    return tmp_path / roots.pop()


def nuscenes_entries(
    *,
    drop_camera: bool = False,
    ego: dict[str, dict[str, list[float]]] | None = None,
    second_lidar: str | None = None,
) -> dict[str, object]:
    """Twin of the TypeScript ``nuscenesFolder()``: the files of the dataset.

    ``second_lidar`` is not in the TypeScript helper: it adds one more lidar
    channel, for the cases where the order of channel names picks the
    reference.
    """
    sensor = [
        {"token": "sl", "channel": "LIDAR_TOP", "modality": "lidar"},
        {"token": "sr", "channel": "RADAR_FRONT", "modality": "radar"},
        {"token": "sc", "channel": "CAM_FRONT", "modality": "camera"},
    ]
    intrinsic = [[1266.4, 0, 816.3], [0, 1266.4, 491.5], [0, 0, 1]]
    calibrated_sensor = [
        {
            "token": "cl",
            "sensor_token": "sl",
            "translation": [0.94, 0, 1.84],
            "rotation": [0.7071068, 0, 0, -0.7071068],
            "camera_intrinsic": [],
        },
        {
            "token": "cr",
            "sensor_token": "sr",
            "translation": [3.41, 0, 0.5],
            "rotation": [1, 0, 0, 0],
            "camera_intrinsic": [],
        },
        {
            "token": "cc",
            "sensor_token": "sc",
            "translation": [1.7, 0, 1.5],
            "rotation": [0.5, -0.5, 0.5, -0.5],
            "camera_intrinsic": intrinsic,
        },
    ]
    channels = [
        ("LIDAR_TOP", "cl", "pcd.bin"),
        ("RADAR_FRONT", "cr", "pcd"),
        ("CAM_FRONT", "cc", "jpg"),
    ]
    if second_lidar:
        sensor.append({"token": "s2", "channel": second_lidar, "modality": "lidar"})
        calibrated_sensor.append(
            {
                "token": "c2",
                "sensor_token": "s2",
                "translation": [0, 0, 2],
                "rotation": [1, 0, 0, 0],
                "camera_intrinsic": [],
            }
        )
        channels.append((second_lidar, "c2", "pcd"))
    scene = [
        {
            "token": "s1",
            "name": "scene-0061",
            "description": "Parked truck",
            "first_sample_token": "a1",
        },
        {
            "token": "s2",
            "name": "scene-0103",
            "description": "Peds",
            "first_sample_token": "b1",
        },
    ]
    sample = [
        {"token": "a1", "timestamp": LIDAR_US[0], "prev": "", "next": "a2"},
        {"token": "a2", "timestamp": LIDAR_US[1], "prev": "a1", "next": ""},
        {"token": "b1", "timestamp": LIDAR_US[2], "prev": "", "next": ""},
    ]
    for row, scene_token in zip(sample, ["s1", "s1", "s2"], strict=True):
        row["scene_token"] = scene_token
    sample_data: list[dict[str, object]] = []
    ego_pose: list[dict[str, object]] = []
    files: dict[str, object] = {}
    for index, row in enumerate(sample):
        for channel, calibration, extension in channels:
            token = f"{row['token']}-{channel}"
            filename = f"samples/{channel}/{row['token']}.{extension}"
            sample_data.append(
                {
                    "token": token,
                    "sample_token": row["token"],
                    "ego_pose_token": token,
                    "calibrated_sensor_token": calibration,
                    "timestamp": row["timestamp"]
                    + (0 if channel == "LIDAR_TOP" else 12_000),
                    "fileformat": "jpg" if extension == "jpg" else "pcd",
                    "is_key_frame": True,
                    "width": 1600 if extension == "jpg" else 0,
                    "height": 900 if extension == "jpg" else 0,
                    "filename": filename,
                }
            )
            ego_pose.append(
                {
                    "token": token,
                    "timestamp": row["timestamp"],
                    "translation": [410 + index, 1179, 0],
                    "rotation": [1, 0, 0, 0],
                    **(ego or {}).get(token, {}),
                }
            )
            dropped = drop_camera and channel == "CAM_FRONT" and row["token"] == "a2"
            if not dropped:
                files[f"v1.0-mini/{filename}"] = f"{channel}-{row['token']}"
    sample_data.append(
        {
            "token": "sweep",
            "sample_token": "a1",
            "ego_pose_token": "a1-LIDAR_TOP",
            "calibrated_sensor_token": "cl",
            "timestamp": LIDAR_US[0] + 50_000,
            "is_key_frame": False,
            "filename": "sweeps/LIDAR_TOP/x.pcd.bin",
        }
    )
    files["v1.0-mini/sweeps/LIDAR_TOP/x.pcd.bin"] = "sweep"
    files["v1.0-mini/maps/m.png"] = "map"
    files["v1.0-mini/LICENSE"] = "license"
    tables = {
        "sensor": sensor,
        "calibrated_sensor": calibrated_sensor,
        "scene": scene,
        "sample": sample,
        "sample_data": sample_data,
        "ego_pose": ego_pose,
    }
    for name, rows in tables.items():
        files[f"v1.0-mini/v1.0-mini/{name}.json"] = rows
    return files


def detect(tmp_path: Path, **options: object) -> SceneDetection:
    return detect_folder_scenes(folder(tmp_path, nuscenes_entries(**options)))


def manifest_file(detection: SceneDetection, scene: int = 0) -> SceneFile:
    return next(
        entry for entry in detection.scenes[scene].files if entry.path == "scene.json"
    )


def manifest_of(detection: SceneDetection, scene: int = 0) -> dict:
    content = manifest_file(detection, scene).content
    assert content is not None
    return json.loads(content.decode("utf-8"))


def first_frame_poses(tmp_path: Path, ego: dict) -> tuple[dict, dict]:
    """Twin of the TypeScript ``firstFramePoses()``."""
    manifest = manifest_of(detect(tmp_path, ego=ego))
    return manifest, manifest["frames"][0]["poses"]


# --- detectPointcloudFolderScenes: nuScenes ---


def test_makes_one_scene_per_recording_from_the_datasets_tables(tmp_path):
    result = detect(tmp_path)

    assert result.datasets == [
        {"kind": "nuscenes", "name": "v1.0-mini", "scene_count": 2}
    ]
    assert [(scene.name, scene.frame_count) for scene in result.scenes] == [
        ("scene-0061", 2),
        ("scene-0103", 1),
    ]
    first = result.scenes[0]
    assert first.source == "nuscenes"
    assert first.description == "Parked truck"
    assert first.point_sensors == ["LIDAR_TOP", "RADAR_FRONT"]
    assert first.cameras == ["CAM_FRONT"]
    assert first.missing_files == 0
    assert sorted(entry.path for entry in first.files) == [
        "samples/CAM_FRONT/a1.jpg",
        "samples/CAM_FRONT/a2.jpg",
        "samples/LIDAR_TOP/a1.pcd.bin",
        "samples/LIDAR_TOP/a2.pcd.bin",
        "samples/RADAR_FRONT/a1.pcd",
        "samples/RADAR_FRONT/a2.pcd",
        "scene.json",
    ]
    assert result.unused_files == 9
    assert result.other_files == []


def test_writes_the_tree_form_manifest_the_ingest_reads(tmp_path):
    result = detect(tmp_path)
    content = manifest_file(result).content
    assert content is not None
    text = content.decode("utf-8")
    manifest = json.loads(text)

    assert f'"timestamp_ns":{LIDAR_US[0]}000' in text
    assert manifest["reference_sensor"] == "LIDAR_TOP"
    assert manifest["sensors"]["LIDAR_TOP"] == {
        "type": "lidar",
        "bin_fields": ["x", "y", "z", "intensity", "ring"],
    }
    assert manifest["sensors"]["RADAR_FRONT"] == {"type": "radar"}
    camera = manifest["sensors"]["CAM_FRONT"]
    assert camera["type"] == "camera"
    assert camera["convention"] == "opencv"
    assert camera["width"] == 1600
    assert camera["height"] == 900
    assert manifest["frames_of_reference"]["ego"] == {"parent": "world"}
    lidar = manifest["frames_of_reference"]["LIDAR_TOP"]
    assert lidar["parent"] == "ego"
    assert lidar["pose"]["rotation"]["qz"] == close(-0.7071068, 2)
    assert lidar["pose"]["rotation"]["qw"] == close(0.7071068, 2)
    frame = manifest["frames"][1]
    assert frame["clouds"] == {
        "LIDAR_TOP": "samples/LIDAR_TOP/a2.pcd.bin",
        "RADAR_FRONT": "samples/RADAR_FRONT/a2.pcd",
    }
    assert frame["images"] == {"CAM_FRONT": "samples/CAM_FRONT/a2.jpg"}
    assert frame["poses"]["ego"]["translation"] == {"x": 411, "y": 1179, "z": 0}


def test_leaves_out_a_file_the_folder_lacks_and_says_so(tmp_path):
    result = detect(tmp_path, drop_camera=True)
    first = result.scenes[0]
    manifest = manifest_of(result)

    assert first.missing_files == 1
    assert first.frame_count == 2
    assert "images" not in manifest["frames"][1]
    assert list(manifest["frames"][1]["poses"]) == ["ego"]


def test_puts_a_camera_where_the_vehicle_was_when_its_image_was_taken(tmp_path):
    manifest, poses = first_frame_poses(
        tmp_path, {"a1-CAM_FRONT": {"translation": [409.5, 1179, 0]}}
    )

    assert list(poses) == ["ego", "CAM_FRONT"]
    assert poses["CAM_FRONT"]["translation"]["x"] == close(1.2)
    assert poses["CAM_FRONT"]["translation"]["y"] == close(0)
    assert poses["CAM_FRONT"]["translation"]["z"] == close(1.5)
    assert poses["CAM_FRONT"]["rotation"]["qw"] == close(0.5)
    assert poses["CAM_FRONT"]["rotation"]["qx"] == close(-0.5)
    assert poses["CAM_FRONT"]["rotation"]["qy"] == close(0.5)
    assert poses["CAM_FRONT"]["rotation"]["qz"] == close(-0.5)
    assert manifest["frames_of_reference"]["CAM_FRONT"]["pose"]["translation"] == {
        "x": 1.7,
        "y": 0,
        "z": 1.5,
    }
    second = manifest["frames"][1]["poses"]["CAM_FRONT"]
    assert second["translation"]["x"] == close(1.7)


def test_reads_the_vehicles_move_in_the_vehicles_own_axes(tmp_path):
    _, poses = first_frame_poses(
        tmp_path,
        {
            "a1-LIDAR_TOP": {"rotation": QUARTER_TURN},
            "a1-CAM_FRONT": {"translation": [410, 1178.5, 0], "rotation": QUARTER_TURN},
        },
    )

    assert poses["CAM_FRONT"]["translation"]["x"] == close(1.2)
    assert poses["CAM_FRONT"]["translation"]["y"] == close(0)
    assert poses["CAM_FRONT"]["translation"]["z"] == close(1.5)
    assert poses["CAM_FRONT"]["rotation"]["qw"] == close(0.5)
    assert poses["CAM_FRONT"]["rotation"]["qx"] == close(-0.5)


def test_turns_a_camera_with_the_vehicle(tmp_path):
    _, poses = first_frame_poses(tmp_path, {"a1-CAM_FRONT": {"rotation": QUARTER_TURN}})

    assert poses["CAM_FRONT"]["translation"]["x"] == close(0)
    assert poses["CAM_FRONT"]["translation"]["y"] == close(1.7)
    assert poses["CAM_FRONT"]["translation"]["z"] == close(1.5)
    assert poses["CAM_FRONT"]["rotation"]["qw"] == close(math.sqrt(0.5))
    assert poses["CAM_FRONT"]["rotation"]["qx"] == close(-math.sqrt(0.5))
    assert poses["CAM_FRONT"]["rotation"]["qy"] == close(0)
    assert poses["CAM_FRONT"]["rotation"]["qz"] == close(0)


def test_leaves_a_camera_on_its_mounting_when_its_own_moment_has_no_usable_pose(
    tmp_path,
):
    _, poses = first_frame_poses(tmp_path, {"a1-CAM_FRONT": {"rotation": [0, 0, 0, 0]}})

    assert list(poses) == ["ego"]


# --- Only on the Python side ---


def test_carries_the_generated_manifest_as_bytes_not_as_a_file_on_disk(tmp_path):
    result = detect(tmp_path)
    scene = result.scenes[0]
    manifest = manifest_file(result)

    assert scene.files[0] is manifest
    assert manifest.source is None
    assert manifest.content is not None
    assert manifest.size == len(manifest.content)
    assert all(
        entry.source is not None and entry.source.is_file() for entry in scene.files[1:]
    )
    assert scene.total_bytes == sum(entry.size for entry in scene.files)
    assert scene.id == "v1.0-mini#s1"
    assert not (tmp_path / "v1.0-mini" / "scene.json").exists()


def test_keeps_the_key_order_the_browser_writes(tmp_path):
    manifest = manifest_of(detect(tmp_path))

    assert list(manifest) == [
        "version",
        "name",
        "sensors",
        "frames_of_reference",
        "reference_sensor",
        "frames",
    ]
    assert manifest["version"] == 1
    assert manifest["name"] == "scene-0061"
    assert list(manifest["sensors"]) == ["LIDAR_TOP", "RADAR_FRONT", "CAM_FRONT"]
    assert list(manifest["sensors"]["CAM_FRONT"]) == [
        "type",
        "intrinsics",
        "convention",
        "width",
        "height",
    ]
    assert list(manifest["frames_of_reference"]) == [
        "ego",
        "LIDAR_TOP",
        "RADAR_FRONT",
        "CAM_FRONT",
    ]
    assert list(manifest["frames"][0]) == ["timestamp_ns", "clouds", "images", "poses"]
    pose = manifest["frames_of_reference"]["RADAR_FRONT"]["pose"]
    assert pose == {
        "translation": {"x": 3.41, "y": 0, "z": 0.5},
        "rotation": {"qx": 0, "qy": 0, "qz": 0, "qw": 1},
    }


def test_takes_the_first_lidar_in_the_browsers_order_as_the_reference(tmp_path):
    # ``naturalCompare`` puts ``_`` before a digit, so LIDAR_TOP stays the
    # reference; an order by code point would make it LIDAR1, whose stamps in
    # this dataset are 12 ms later.
    result = detect(tmp_path, second_lidar="LIDAR1")
    manifest = manifest_of(result)

    assert result.scenes[0].point_sensors == ["LIDAR_TOP", "LIDAR1", "RADAR_FRONT"]
    assert manifest["reference_sensor"] == "LIDAR_TOP"
    assert manifest["frames"][0]["timestamp_ns"] == LIDAR_US[0] * 1000
    assert manifest["sensors"]["LIDAR1"] == {"type": "lidar"}


def test_orders_a_second_lidar_before_the_first_when_its_name_sorts_first(tmp_path):
    result = detect(tmp_path, second_lidar="LIDAR_FRONT")
    manifest = manifest_of(result)

    assert result.scenes[0].point_sensors == [
        "LIDAR_FRONT",
        "LIDAR_TOP",
        "RADAR_FRONT",
    ]
    assert manifest["reference_sensor"] == "LIDAR_FRONT"
    assert manifest["frames"][0]["timestamp_ns"] == (LIDAR_US[0] + 12_000) * 1000


def test_reads_a_folder_without_all_six_tables_by_the_folder_rules(tmp_path):
    entries = nuscenes_entries()
    del entries["v1.0-mini/v1.0-mini/ego_pose.json"]

    result = detect_folder_scenes(folder(tmp_path, entries))

    assert result.datasets == []
    assert all(scene.source != "nuscenes" for scene in result.scenes)


def test_refuses_a_table_that_is_not_a_list_of_rows(tmp_path):
    entries = nuscenes_entries()
    entries["v1.0-mini/v1.0-mini/sample.json"] = {"rows": []}

    with pytest.raises(ValueError, match=r"sample\.json is not a nuScenes table"):
        detect_folder_scenes(folder(tmp_path, entries))


def test_refuses_a_table_that_is_not_json(tmp_path):
    entries = nuscenes_entries()
    entries["v1.0-mini/v1.0-mini/sensor.json"] = "[{"

    with pytest.raises(ValueError, match=r"sensor\.json is not valid JSON"):
        detect_folder_scenes(folder(tmp_path, entries))


def table_row(entries: dict[str, object], table: str, token: str) -> dict:
    rows = entries[f"v1.0-mini/v1.0-mini/{table}.json"]
    assert isinstance(rows, list)
    return next(row for row in rows if row["token"] == token)


def test_refuses_tables_whose_rows_cannot_be_reckoned_with(tmp_path):
    # The browser throws here too, and uploads no scene of the folder.
    entries = nuscenes_entries()
    del table_row(entries, "ego_pose", "a1-LIDAR_TOP")["rotation"]

    with pytest.raises(ValueError, match=r"v1\.0-mini could not be read"):
        detect_folder_scenes(folder(tmp_path, entries))


@pytest.mark.parametrize(
    ("stamp", "written"),
    [
        pytest.param(LIDAR_US[0] + 0.5, (LIDAR_US[0] + 1) * 1000, id="half goes up"),
        pytest.param(LIDAR_US[0] - 0.5, LIDAR_US[0] * 1000, id="not to the even one"),
        pytest.param(LIDAR_US[0] + 0.25, LIDAR_US[0] * 1000, id="below half goes down"),
        pytest.param(None, "__nuscenes_ns__NaN000", id="no stamp keeps the marker"),
    ],
)
def test_writes_a_frames_stamp_as_the_browser_rounds_it(tmp_path, stamp, written):
    # Written values produced by Node 22 from the TypeScript on the same rows.
    entries = nuscenes_entries()
    row = table_row(entries, "sample_data", "a1-LIDAR_TOP")
    if stamp is None:
        del row["timestamp"]
    else:
        row["timestamp"] = stamp

    manifest = manifest_of(detect_folder_scenes(folder(tmp_path, entries)))

    assert manifest["frames"][0]["timestamp_ns"] == written
