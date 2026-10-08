"""Splits a nuScenes-format dataset folder into one lidar scene per recording.

Port of the frontend's ``src/utils/pointcloud-nuscenes.ts``. The browser and the
SDK must write the same ``scene.json`` for the same dataset, so change this
module ONLY together with that TypeScript file. Its unit tests are translated
in ``tests/test_nuscenes.py``; every function here names the TypeScript
function it ports and the functions keep the order of that file.

In this layout the files of every scene sit mixed in shared sensor folders
(``samples/LIDAR_TOP/…``, ``samples/CAM_FRONT/…``); only the JSON tables say
which file belongs to which scene and frame. This reads the tables and writes,
per scene, the ``scene.json`` the backend ingests (tree form: the vehicle
``ego`` under ``world``, each sensor mounted on ``ego`` by its calibration, the
vehicle's pose per frame, and each camera's own pose on the frames it has an
image of). The scene's files keep their dataset paths, so the manifest names
them as they are. The manifest is not written to disk: it travels as the
``content`` of a ``SceneFile`` and the uploader sends it with the scene.

Only key frames are taken (the annotated samples, 2 Hz); the in-between sweeps
are left out. Images are already undistorted, so cameras are plain pinhole
with their intrinsics.

Numbers: JavaScript reads every JSON number as a double, Python reads whole
numbers as integers of any size. The arithmetic below is the TypeScript's,
operation by operation, so the values agree; the digits written can differ
(``1.0`` here, ``1`` there), which is why the tests compare parsed values.
"""

from __future__ import annotations

import functools
import json
import math
import posixpath
import re
from dataclasses import dataclass
from typing import Any

from ._scenes import (
    MANIFEST_NAME,
    FolderNode,
    Scene,
    SceneFile,
    files_under,
    lower_name,
    natural_compare,
    read_json,
    relative_to,
)

TABLES = ("scene", "sample", "sample_data", "calibrated_sensor", "sensor", "ego_pose")
# nuScenes lidar sweeps: float32 x y z intensity ring, no header.
LIDAR_BIN_FIELDS = ["x", "y", "z", "intensity", "ring"]
# ``[0-9]`` where the TypeScript has ``\d``: JavaScript's ``\d`` is ASCII only,
# Python's also takes the digits of other scripts.
_VERSION_FOLDER = re.compile(r"v[0-9]+\.[0-9]+-[A-Za-z0-9_]+")
VEHICLE_FRAME = "ego"


@dataclass(frozen=True)
class NuscenesTables:
    """The six tables of a dataset (TypeScript: ``NuscenesTables``).

    Attributes:
        version: Name of the folder that holds them, such as ``v1.0-mini``.
        files: The table files by table name (``TABLES``).
    """

    version: str
    files: dict[str, SceneFile]


def find_nuscenes_tables(node: FolderNode) -> NuscenesTables | None:
    """Returns the tables of a nuScenes layout directly below ``node``, or ``None``.

    Port of ``findNuscenesTables``: a ``samples`` folder beside a folder named
    like a version (``v1.0-mini``) that holds all six tables.
    """
    if "samples" not in node.dirs:
        return None
    for directory in node.dirs.values():
        if not _VERSION_FOLDER.fullmatch(directory.name):
            continue
        by_name = {lower_name(entry.path): entry for entry in directory.files}
        if all(f"{table}.json" in by_name for table in TABLES):
            return NuscenesTables(
                version=directory.name,
                files={table: by_name[f"{table}.json"] for table in TABLES},
            )
    return None


def _to_pose(record: dict[str, Any]) -> dict[str, dict[str, float]]:
    """nuScenes ``[w, x, y, z]`` + ``[x, y, z]`` to the manifest's pose, normalised.

    Port of ``toPose``. A rotation of length zero is written as it is, as the
    TypeScript does (``|| 1``); the ingest refuses it.
    """
    w, x, y, z = record["rotation"][:4]
    norm = math.hypot(w, x, y, z) or 1
    translation = record["translation"]
    return {
        "translation": {"x": translation[0], "y": translation[1], "z": translation[2]},
        "rotation": {"qx": x / norm, "qy": y / norm, "qz": z / norm, "qw": w / norm},
    }


# Quaternions below are ``[w, x, y, z]``, as the dataset writes them.
def _unit(q: list[float]) -> list[float]:
    """Port of ``unit``."""
    norm = math.hypot(q[0], q[1], q[2], q[3]) or 1
    return [q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm]


def _multiply(a: list[float], b: list[float]) -> list[float]:
    """Port of ``multiply``: the Hamilton product ``a·b``."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ]


def _rotate(q: list[float], v: list[float]) -> list[float]:
    """A vector turned by a unit quaternion (``rotate``)."""
    w, x, y, z = q
    cx = y * v[2] - z * v[1]
    cy = z * v[0] - x * v[2]
    cz = x * v[1] - y * v[0]
    return [
        v[0] + 2 * (w * cx + y * cz - z * cy),
        v[1] + 2 * (w * cy + z * cx - x * cz),
        v[2] + 2 * (w * cz + x * cy - y * cx),
    ]


def _is_finite(value: Any) -> bool:
    """``Number.isFinite``: a number, and neither infinite nor NaN."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # a whole number JavaScript would read as Infinity
        return False


def _usable_pose(pose: Any) -> bool:
    """Whether a table row holds a pose that can be reckoned with (``usablePose``)."""
    if not isinstance(pose, dict):
        return False
    translation, rotation = pose.get("translation"), pose.get("rotation")
    return (
        isinstance(translation, list)
        and isinstance(rotation, list)
        and len(translation) == 3
        and len(rotation) == 4
        and all(_is_finite(value) for value in (*translation, *rotation))
        and math.hypot(*rotation) > 1e-6
    )


def _camera_pose_on_frame(
    frame_ego: dict[str, Any], own_ego: dict[str, Any], mounting: dict[str, Any]
) -> dict[str, list[float]]:
    """Where a camera was when it took its image, in the frame's vehicle frame.

    Port of ``cameraPoseOnFrame``. The vehicle frame is the one the frame
    places: the vehicle at the reference lidar's moment.

    A key frame's sensors do not fire together. Each camera is exposed as the
    lidar's beam passes it, up to some tens of milliseconds before the sweep's
    own stamp, and the dataset gives the vehicle's pose at each of those
    moments. Hung on the frame's vehicle pose by its mounting alone, a camera
    would be placed where the vehicle was when the LIDAR finished, and on a
    moving vehicle whatever is drawn on its image would sit beside its object.
    """
    w, x, y, z = _unit(frame_ego["rotation"])
    to_frame = [w, -x, -y, -z]
    own = _unit(own_ego["rotation"])
    mounted = _rotate(own, mounting["translation"])
    return {
        "rotation": _multiply(to_frame, _multiply(own, _unit(mounting["rotation"]))),
        # The two vehicle places are taken apart first: in a map's coordinates
        # each is thousands of metres, their difference centimetres.
        "translation": _rotate(
            to_frame,
            [
                own_ego["translation"][0] - frame_ego["translation"][0] + mounted[0],
                own_ego["translation"][1] - frame_ego["translation"][1] + mounted[1],
                own_ego["translation"][2] - frame_ego["translation"][2] + mounted[2],
            ],
        ),
    }


# What the TypeScript leaves in the manifest where a row has no usable stamp.
_STAMP_TOKEN = "__nuscenes_ns__"


def _stamp_token(microseconds: Any) -> int | str:
    """A row's microsecond stamp as the manifest's whole nanoseconds.

    Port of ``stampToken`` and of the replacement in ``manifestText``.
    Nanosecond stamps exceed JavaScript's exact integers, so the TypeScript
    writes a marker string and swaps it for bare digits in the JSON text.
    Python's integers have no such limit: the number is written directly, with
    the same digits (the rounded microseconds, then ``000``).

    A row without a number as its stamp keeps the marker in the TypeScript's
    manifest (``"__nuscenes_ns__NaN000"``), a string the ingest refuses as
    ``timestamp_ns``. The same string is written here so the same scene is
    refused the same way, instead of passing as a scene without stamps. A
    negative stamp is written as the negative number, which the ingest
    refuses with the same message as the TypeScript's leftover marker.

    Not reproduced, as no dataset has such stamps: a stamp of exactly 0 (the
    TypeScript writes ``0000``, which is not JSON; ``0`` here) and stamps
    above 2**53 microseconds (JavaScript has lost their last digits by then).
    """
    if isinstance(microseconds, bool) or not isinstance(microseconds, (int, float)):
        return f"{_STAMP_TOKEN}NaN000"
    if isinstance(microseconds, float):
        if not math.isfinite(microseconds):
            return f"{_STAMP_TOKEN}NaN000"
        # ``Math.round``: halves go up, where Python's ``round`` goes to even.
        whole = math.floor(microseconds)
        microseconds = whole + 1 if microseconds - whole >= 0.5 else whole
    return microseconds * 1000


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """The manifest as the bytes of its file (``manifestText``).

    ``JSON.stringify`` writes no spaces and leaves characters outside ASCII as
    they are. ``backslashreplace`` only meets half a surrogate pair, which
    JavaScript also writes as ``\\udXXX``.

    Raises:
        ValueError: If a number is infinite or not a number, which JSON has no
            way to write.
    """
    text = json.dumps(
        manifest, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return text.encode("utf-8", errors="backslashreplace")


def _read_table(entry: SceneFile) -> list[Any]:
    """Reads one table: a JSON list of rows (``readTable``).

    Raises:
        ValueError: If the file is not JSON or not a list.
    """
    name = posixpath.basename(entry.path)
    try:
        rows = read_json(entry)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"{name} is not valid JSON") from error
    if not isinstance(rows, list):
        raise ValueError(f"{name} is not a nuScenes table")
    return rows


@dataclass
class _Channel:
    """One sensor of a scene, as the first row that names it describes it.

    TypeScript: ``Channel``.

    Attributes:
        sensor: Its row of ``sensor.json`` (``channel``, ``modality``).
        calibration: Its row of ``calibrated_sensor.json``: the mounting.
        width: Image width in pixels, ``None`` when the row gives none.
        height: Image height in pixels, ``None`` when the row gives none.
        is_bin: Its clouds are headerless ``.bin`` records rather than PCD files.
    """

    sensor: dict[str, Any]
    calibration: dict[str, Any]
    width: Any
    height: Any
    is_bin: bool

    @property
    def name(self) -> Any:
        return self.sensor.get("channel")

    @property
    def modality(self) -> Any:
        return self.sensor.get("modality")


def _point_channel_order(a: _Channel, b: _Channel) -> int:
    """Lidars first, then by name: the comparator of ``pointChannels.sort``."""
    if a.modality == b.modality:
        return natural_compare(a.name, b.name)
    return -1 if a.modality == "lidar" else 1


def _camera_channel_order(a: _Channel, b: _Channel) -> int:
    """By name: the comparator of ``cameraChannels.sort``."""
    return natural_compare(a.name, b.name)


def import_nuscenes_scenes(
    node: FolderNode, tables: NuscenesTables
) -> tuple[list[Scene], int]:
    """Builds one scene per row of ``scene.json`` from the dataset below ``node``.

    Port of ``importNuscenesScenes``.

    Args:
        node: The dataset folder: the one that holds ``samples``.
        tables: Its tables, from ``find_nuscenes_tables``.

    Returns:
        The scenes, and how many of the folder's files they use. A scene
        without a frame, or without a lidar, is left out.

    Raises:
        ValueError: If a table is not a JSON list, or rows are not shaped as
            nuScenes rows. The browser fails on the same datasets ("The
            folder's 3D scenes could not be read") and uploads no scene.
        OSError: If a table cannot be read from disk.
    """
    scenes, samples, sample_data, calibrated, sensors, ego_poses = (
        _read_table(tables.files[table]) for table in TABLES
    )
    try:
        return _scenes_of_tables(
            node, scenes, samples, sample_data, calibrated, sensors, ego_poses
        )
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        # JavaScript throws once for all of these (a row that is no object, a
        # pose without its numbers); one kind of error keeps that for callers.
        raise ValueError(
            f"The nuScenes tables in {tables.version} could not be read: {error!r}"
        ) from error


def _scenes_of_tables(
    node: FolderNode,
    scenes: list[Any],
    samples: list[Any],
    sample_data: list[Any],
    calibrated: list[Any],
    sensors: list[Any],
    ego_poses: list[Any],
) -> tuple[list[Scene], int]:
    """The body of ``importNuscenesScenes`` once the tables are read."""
    sample_by_token = {row.get("token"): row for row in samples}
    calibration_by_token = {row.get("token"): row for row in calibrated}
    sensor_by_token = {row.get("token"): row for row in sensors}
    ego_by_token = {row.get("token"): row for row in ego_poses}
    key_frames_by_sample: dict[Any, list[dict[str, Any]]] = {}
    for row in sample_data:
        if not row.get("is_key_frame") or not row.get("sample_token"):
            continue
        key_frames_by_sample.setdefault(row["sample_token"], []).append(row)
    file_by_path = {
        relative.path: relative
        for relative in (relative_to(node, entry) for entry in files_under(node))
    }

    result: list[Scene] = []
    used_files = 0
    for scene in scenes:
        channels: dict[Any, _Channel] = {}
        frames: list[dict[str, Any]] = []
        files: list[SceneFile] = []
        missing_files = 0
        visited: set[Any] = set()
        token = scene.get("first_sample_token")
        while token and token not in visited:
            visited.add(token)
            sample = sample_by_token.get(token)
            if sample is None:
                break
            token = sample.get("next")
            clouds: dict[Any, str] = {}
            images: dict[Any, str] = {}
            lidar_rows: dict[Any, dict[str, Any]] = {}
            camera_rows: dict[Any, tuple[dict[str, Any], dict[str, Any]]] = {}
            frame_files: list[SceneFile] = []
            for row in key_frames_by_sample.get(sample.get("token"), []):
                calibration = calibration_by_token.get(
                    row.get("calibrated_sensor_token")
                )
                if calibration is None:
                    continue
                sensor = sensor_by_token.get(calibration.get("sensor_token"))
                if sensor is None:
                    continue
                filename = row.get("filename")
                # A file name that is no text names no file, as in JavaScript.
                entry = None
                if isinstance(filename, str):
                    entry = file_by_path.get(filename)
                if entry is None:
                    missing_files += 1
                    continue
                channel = sensor.get("channel")
                if channel not in channels:
                    channels[channel] = _Channel(
                        sensor=sensor,
                        calibration=calibration,
                        width=row.get("width") or None,
                        height=row.get("height") or None,
                        is_bin=filename.lower().endswith(".bin"),
                    )
                frame_files.append(entry)
                if sensor.get("modality") == "camera":
                    images[channel] = filename
                    camera_rows[channel] = (row, calibration)
                else:
                    clouds[channel] = filename
                    if sensor.get("modality") == "lidar":
                        lidar_rows[channel] = row
            # The frame's time and vehicle pose are the reference lidar's: the
            # first lidar by name, as the manifest's ``reference_sensor`` below.
            ordered = sorted(lidar_rows, key=functools.cmp_to_key(natural_compare))
            reference_row = lidar_rows[ordered[0]] if ordered and ordered[0] else None
            if reference_row is None:
                continue
            ego = ego_by_token.get(reference_row.get("ego_pose_token"))
            if ego is None:
                continue
            # A camera took its image at its own moment, with the vehicle at its
            # own place then: the frame says where that put the camera. One whose
            # moment has no vehicle pose stays where its mounting puts it; so does
            # every camera when a row cannot be reckoned with, which leaves such a
            # dataset written exactly as it was before cameras had poses of their
            # own.
            camera_poses: dict[Any, Any] = {}
            if _usable_pose(ego):
                for channel, (row, calibration) in camera_rows.items():
                    own = ego_by_token.get(row.get("ego_pose_token"))
                    if (
                        own is not ego
                        and _usable_pose(own)
                        and _usable_pose(calibration)
                    ):
                        camera_poses[channel] = _to_pose(
                            _camera_pose_on_frame(ego, own, calibration)
                        )
            files.extend(frame_files)
            frame: dict[str, Any] = {
                "timestamp_ns": _stamp_token(reference_row.get("timestamp")),
                "clouds": clouds,
            }
            if images:
                frame["images"] = images
            frame["poses"] = {VEHICLE_FRAME: _to_pose(ego), **camera_poses}
            frames.append(frame)
        if not frames:
            continue

        point_channels = sorted(
            (channel for channel in channels.values() if channel.modality != "camera"),
            key=functools.cmp_to_key(_point_channel_order),
        )
        camera_channels = sorted(
            (channel for channel in channels.values() if channel.modality == "camera"),
            key=functools.cmp_to_key(_camera_channel_order),
        )
        reference = next(
            (channel for channel in point_channels if channel.modality == "lidar"),
            None,
        )
        if reference is None:
            continue

        sensor_specs: dict[Any, dict[str, Any]] = {}
        for channel in point_channels:
            spec: dict[str, Any] = {}
            # A key JavaScript finds undefined is not written at all.
            if "modality" in channel.sensor:
                spec["type"] = channel.modality
            if channel.is_bin and channel.modality == "lidar":
                spec["bin_fields"] = LIDAR_BIN_FIELDS
            sensor_specs[channel.name] = spec
        for channel in camera_channels:
            spec = {"type": "camera"}
            intrinsic = channel.calibration.get("camera_intrinsic")
            if isinstance(intrinsic, list) and len(intrinsic) == 3:
                spec["intrinsics"] = intrinsic
            spec["convention"] = "opencv"
            if channel.width and channel.height:
                spec["width"] = channel.width
                spec["height"] = channel.height
            sensor_specs[channel.name] = spec
        frames_of_reference: dict[Any, dict[str, Any]] = {
            VEHICLE_FRAME: {"parent": "world"}
        }
        for channel in (*point_channels, *camera_channels):
            frames_of_reference[channel.name] = {
                "parent": VEHICLE_FRAME,
                "pose": _to_pose(channel.calibration),
            }
        manifest: dict[str, Any] = {"version": 1}
        if "name" in scene:
            manifest["name"] = scene["name"]
        manifest["sensors"] = sensor_specs
        manifest["frames_of_reference"] = frames_of_reference
        manifest["reference_sensor"] = reference.name
        manifest["frames"] = frames

        content = _manifest_bytes(manifest)
        scene_files = [
            SceneFile(path=MANIFEST_NAME, content=content, size=len(content)),
            *files,
        ]
        used_files += len(files)
        result.append(
            Scene(
                id=f"{node.path}#{scene.get('token')}",
                name=scene.get("name"),
                description=scene.get("description"),
                source="nuscenes",
                files=scene_files,
                frame_count=len(frames),
                point_sensors=[channel.name for channel in point_channels],
                cameras=[channel.name for channel in camera_channels],
                total_bytes=sum(entry.size for entry in scene_files),
                missing_files=missing_files,
            )
        )
    return result, used_files
