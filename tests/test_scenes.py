"""Folder rules of the lidar scene detection (``unitlab._scenes``).

The cases of the frontend's ``src/__tests__/pointcloud/pointcloudFolderScenes.test.ts``
(folder rules, backend layouts) and the split cases of
``pointcloudFolderScenesDialog.test.ts``, translated one to one: each test keeps
the title of its ``it(...)``. The browser hands the detector ``File`` objects
with a relative path; here the same tree is written under ``tmp_path`` and the
folder is picked by its path. The nuScenes cases are in ``test_nuscenes.py``.

The tests below the translated ones cover what only the Python side has: the
walk of a real directory, the manifest read from bytes, and the collation key
that stands in for the browser's ``localeCompare``.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path

import pytest

from unitlab import _scenes
from unitlab._scenes import (
    Scene,
    SceneDetection,
    SceneFile,
    SceneSplit,
    backend_natural_key,
    detect_folder_scenes,
    natural_compare,
    scenes_to_upload,
)


def folder(tmp_path: Path, entries: dict[str, object]) -> Path:
    """Writes a picked folder and returns its path.

    Twin of the TypeScript helper ``folder()``: keys are paths as the browser
    reports them (``<picked folder>/<path below it>``), values the file's text
    or a value written as JSON. All keys share their first part, the folder
    the user picks.
    """
    roots = {path.split("/")[0] for path in entries}
    assert len(roots) == 1, "one picked folder per test"
    for path, content in entries.items():
        target = tmp_path.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content)
        target.write_bytes(text.encode("utf-8"))
    return tmp_path / roots.pop()


def detect(tmp_path: Path, entries: dict[str, object]) -> SceneDetection:
    return detect_folder_scenes(folder(tmp_path, entries))


def by_path(files: list[SceneFile]) -> list[str]:
    return sorted(entry.path for entry in files)


def assert_scene(scene: Scene, **expected: object) -> None:
    """``toMatchObject`` for a scene: only the named fields are compared."""
    actual = {name: getattr(scene, name) for name in expected}
    assert actual == expected


# --- detectPointcloudFolderScenes: folder rules ---


def test_makes_one_scene_of_a_folder_of_clouds_with_matching_image_folders_as_cameras(
    tmp_path,
):
    result = detect(
        tmp_path,
        {
            "drive/000.pcd": "a",
            "drive/001.pcd": "b",
            "drive/front/000.jpg": "c",
            "drive/notes/readme.txt": "d",
        },
    )

    assert len(result.scenes) == 1
    scene = result.scenes[0]
    assert_scene(
        scene,
        name="drive",
        source="folder",
        frame_count=2,
        point_sensors=["lidar"],
        cameras=["front"],
    )
    assert by_path(scene.files) == ["000.pcd", "001.pcd", "front/000.jpg"]
    assert result.unused_files == 1
    assert result.other_files == []


def test_makes_one_scene_of_sensor_subfolders_that_share_frame_names(tmp_path):
    result = detect(
        tmp_path,
        {
            "rig/lidar/0.pcd": "a",
            "rig/lidar/1.pcd": "b",
            "rig/radar/0.pcd": "c",
            "rig/front/0.jpg": "d",
        },
    )

    assert len(result.scenes) == 1
    assert_scene(
        result.scenes[0],
        name="rig",
        frame_count=2,
        point_sensors=["lidar", "radar"],
        cameras=["front"],
    )
    assert by_path(result.scenes[0].files) == [
        "front/0.jpg",
        "lidar/0.pcd",
        "lidar/1.pcd",
        "radar/0.pcd",
    ]


def test_splits_subfolders_that_share_no_frame_names_into_separate_scenes(tmp_path):
    result = detect(tmp_path, {"set/a/0.pcd": "a", "set/b/9.pcd": "b"})

    assert [scene.name for scene in result.scenes] == ["a", "b"]
    assert all(scene.frame_count == 1 for scene in result.scenes)


def test_descends_into_folders_whose_children_are_scenes(tmp_path):
    result = detect(tmp_path, {"top/s1/lidar/0.pcd": "a", "top/s2/lidar/0.pcd": "b"})

    assert [scene.name for scene in result.scenes] == ["s1", "s2"]
    assert by_path(result.scenes[0].files) == ["lidar/0.pcd"]


def test_takes_a_folder_with_our_scene_json_as_it_is(tmp_path):
    result = detect(
        tmp_path,
        {
            "s/scene.json": {
                "version": 1,
                "sensors": {"top": {"type": "lidar"}, "cam": {"type": "camera"}},
                "frames": [{"lidar": "x/0.bin"}],
            },
            "s/x/0.bin": "a",
        },
    )

    assert_scene(
        result.scenes[0],
        source="manifest",
        frame_count=1,
        point_sensors=["top"],
        cameras=["cam"],
    )
    assert by_path(result.scenes[0].files) == ["scene.json", "x/0.bin"]


def test_counts_ply_clouds_as_frames_alone_or_beside_the_other_formats(tmp_path):
    result = detect(
        tmp_path,
        {
            "scan/000.ply": "a",
            "scan/001.PLY": "b",
            "scan/002.pcd": "c",
            "scan/front/000.jpg": "d",
        },
    )

    assert len(result.scenes) == 1
    assert_scene(
        result.scenes[0],
        name="scan",
        frame_count=3,
        point_sensors=["lidar"],
        cameras=["front"],
    )
    assert by_path(result.scenes[0].files) == [
        "000.ply",
        "001.PLY",
        "002.pcd",
        "front/000.jpg",
    ]


def test_leaves_loose_files_and_folders_without_clouds_to_the_ordinary_upload(
    tmp_path,
):
    # The TypeScript case also passes a loose ``single.pcd`` (a file picked
    # without a folder) and checks ``hasFolderPaths``. A directory has no loose
    # files, every file in it is in a folder, so only the folder half is here.
    root = folder(tmp_path, {"photos/a.jpg": "a", "photos/more/b.txt": "b"})

    result = detect_folder_scenes(root)

    assert result.scenes == []
    assert result.other_files == [root / "a.jpg", root / "more" / "b.txt"]
    assert result.unused_files == 0


# --- detectPointcloudFolderScenes: layouts read as the backend reads them ---


def test_takes_a_sensors_and_a_cameras_data_folder_for_the_folder_above_kitti_raw(
    tmp_path,
):
    drive = "2011_09_26/2011_09_26_drive_0001_sync"
    result = detect(
        tmp_path,
        {
            f"{drive}/velodyne_points/data/0000000000.bin": "a",
            f"{drive}/velodyne_points/data/0000000001.bin": "b",
            f"{drive}/velodyne_points/timestamps.txt": "t",
            f"{drive}/image_02/data/0000000000.png": "c",
            f"{drive}/image_02/data/0000000001.png": "d",
            f"{drive}/image_03/data/0000000000.png": "e",
            f"{drive}/oxts/data/0000000000.txt": "f",
        },
    )

    assert len(result.scenes) == 1
    scene = result.scenes[0]
    assert_scene(
        scene,
        name="2011_09_26_drive_0001_sync",
        frame_count=2,
        point_sensors=["velodyne_points"],
        cameras=["image_02", "image_03"],
    )
    assert by_path(scene.files) == [
        "image_02/data/0000000000.png",
        "image_02/data/0000000001.png",
        "image_03/data/0000000000.png",
        "velodyne_points/data/0000000000.bin",
        "velodyne_points/data/0000000001.bin",
    ]
    assert result.other_files == []
    assert result.unused_files == 2


def test_turns_folder_names_into_sensor_names_instead_of_leaving_the_folders_out(
    tmp_path,
):
    result = detect(
        tmp_path,
        {
            "rig/Lidar Front/0.pcd": "a",
            "rig/lidar.rear/0.pcd": "b",
            "rig/Camera 1/0.jpg": "c",
        },
    )

    assert len(result.scenes) == 1
    assert_scene(
        result.scenes[0],
        name="rig",
        point_sensors=["Lidar_Front", "lidar_rear"],
        cameras=["Camera_1"],
    )
    assert by_path(result.scenes[0].files) == [
        "Camera 1/0.jpg",
        "Lidar Front/0.pcd",
        "lidar.rear/0.pcd",
    ]


def test_keeps_a_single_sensors_name_as_the_backend_does_with_its_cameras_beside_it(
    tmp_path,
):
    result = detect(tmp_path, {"take/my lidar/0.pcd": "a", "take/cam/0.jpg": "b"})

    assert len(result.scenes) == 1
    assert_scene(
        result.scenes[0], name="take", point_sensors=["lidar"], cameras=["cam"]
    )
    assert result.scenes[0].split is None
    assert result.other_files == []


def test_makes_separate_scenes_of_folders_that_would_get_one_sensor_name(tmp_path):
    result = detect(tmp_path, {"x/a b/0.pcd": "a", "x/a_b/0.pcd": "b"})

    assert [scene.name for scene in result.scenes] == ["a b", "a_b"]


def test_says_why_an_image_folder_is_not_a_camera_of_the_scene(tmp_path):
    result = detect(
        tmp_path,
        {
            "s/000.pcd": "a",
            "s/front/000.jpg": "b",
            "s/holiday/IMG_1.jpg": "c",
            "s/thermal/000.webp": "d",
            "s/calib/000.txt": "e",
        },
    )

    scene = result.scenes[0]
    assert scene.cameras == ["front"]
    assert scene.notes == [
        "“holiday” is not used as a camera: its image names match no frame.",
        "“thermal” is not used as a camera: only .jpg and .png images are read.",
    ]


def test_carries_no_notes_when_every_image_folder_is_used(tmp_path):
    result = detect(
        tmp_path,
        {"s/000.pcd": "a", "s/front/000.jpg": "b", "s/calib/000.txt": "c"},
    )

    # ``notes`` is absent in TypeScript; the dataclass's form of that is empty.
    assert result.scenes[0].notes == []


def test_offers_folders_with_the_same_file_names_as_separate_scenes_too(tmp_path):
    result = detect(
        tmp_path,
        {
            "drives/seq_1/000.pcd": "a",
            "drives/seq_1/001.pcd": "b",
            "drives/seq_2/000.pcd": "c",
            "drives/cam/000.jpg": "d",
        },
    )

    assert len(result.scenes) == 1
    scene = result.scenes[0]
    assert_scene(
        scene, name="drives", point_sensors=["seq_1", "seq_2"], cameras=["cam"]
    )
    assert scene.split is not None
    assert [part.name for part in scene.split.scenes] == ["seq_1", "seq_2"]
    assert_scene(
        scene.split.scenes[0],
        id="drives/seq_1",
        frame_count=2,
        point_sensors=["lidar"],
        cameras=[],
    )
    assert by_path(scene.split.scenes[0].files) == ["000.pcd", "001.pcd"]
    assert scene.split.extra_unused_files == 1


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        pytest.param(
            ["lidar10", "lidar2"], ["lidar2", "lidar10"], id="digit runs by their value"
        ),
        pytest.param(["8", "007"], ["007", "8"], id="leading zeros do not count"),
        pytest.param(
            ["1532402927647951001", "1532402927647951000"],
            ["1532402927647951000", "1532402927647951001"],
            id="stamps longer than a number holds",
        ),
        pytest.param(["b", "A", "c"], ["A", "b", "c"], id="letters without their case"),
        pytest.param(
            ["os_2", "os1", "os-3"],
            ["os1", "os-3", "os_2"],
            id="punctuation by code point",
        ),
        pytest.param(
            ["lidar_top", "lidar"], ["lidar", "lidar_top"], id="a shorter name first"
        ),
    ],
)
def test_orders_folder_names_like_the_backend(names, expected):
    assert sorted(names, key=backend_natural_key) == expected


def test_picks_the_reference_sensor_the_backend_picks(tmp_path):
    result = detect(
        tmp_path,
        {
            "r/os_2/0.bin": "a",
            "r/os_2/1.bin": "b",
            "r/os_2/2.bin": "c",
            "r/os1/0.bin": "d",
        },
    )

    assert_scene(result.scenes[0], point_sensors=["os1", "os_2"], frame_count=1)


# --- pointcloud folder scenes dialog: the split choice (rowsOf, unusedFiles) ---


def dialog_scene(name: str, **overrides: object) -> Scene:
    """Twin of the dialog test's ``scene()`` factory."""
    fields: dict[str, object] = {
        "id": name,
        "name": name,
        "source": "folder",
        "files": [SceneFile(path="0.pcd", source=Path("0.pcd"), size=1)],
        "frame_count": 3,
        "point_sensors": ["lidar"],
        "cameras": [],
        "total_bytes": 10,
        "missing_files": 0,
    }
    return Scene(**{**fields, **overrides})


def merged() -> Scene:
    return dialog_scene(
        "drives",
        point_sensors=["seq_1", "seq_2"],
        cameras=["cam"],
        split=SceneSplit(
            scenes=[dialog_scene("seq_1"), dialog_scene("seq_2", total_bytes=500)],
            extra_unused_files=4,
        ),
    )


def dialog_detection(scenes: list[Scene], unused_files: int = 0) -> SceneDetection:
    return SceneDetection(
        scenes=scenes, unused_files=unused_files, other_files=[], datasets=[]
    )


def test_uploads_a_folder_of_same_named_files_as_one_scene_unless_told_otherwise():
    rows, unused = scenes_to_upload(dialog_detection([merged(), dialog_scene("other")]))

    assert [row.name for row in rows] == ["drives", "other"]
    assert unused == 0


def test_lists_and_uploads_the_folders_as_separate_scenes_when_the_user_says_they_are():
    detection = dialog_detection([merged(), dialog_scene("other")], 1)
    assert scenes_to_upload(detection)[1] == 1

    rows, unused = scenes_to_upload(detection, split_sensor_folders=True)

    # The dialog leaves ``seq_2`` unticked because it is over the size limit of
    # that test; the limit is the uploader's business, so both parts are rows.
    assert [row.name for row in rows] == ["seq_1", "seq_2", "other"]
    assert unused == 5


def test_goes_back_to_one_scene_ticked_again():
    detection = dialog_detection([merged()])

    scenes_to_upload(detection, split_sensor_folders=True)
    rows, unused = scenes_to_upload(detection)

    assert [row.name for row in rows] == ["drives"]
    assert unused == 0


# --- Only on the Python side: a real directory instead of File objects ---


def test_drops_noise_files_silently(tmp_path):
    result = detect(
        tmp_path,
        {
            "drive/000.pcd": "a",
            "drive/.DS_Store": "x",
            "drive/._000.pcd": "x",
            "drive/Thumbs.db": "x",
            "drive/front/desktop.ini": "x",
            "drive/__MACOSX/000.pcd": "x",
            "drive/.cache/001.pcd": "x",
        },
    )

    assert by_path(result.scenes[0].files) == ["000.pcd"]
    assert result.scenes[0].frame_count == 1
    assert result.unused_files == 0
    assert result.other_files == []


def test_scene_files_point_at_the_files_on_disk_with_posix_paths(tmp_path):
    root = folder(
        tmp_path,
        {"drive/000.pcd": "abc", "drive/front/000.jpg": "12345", "drive/x.txt": "?"},
    )

    scene = detect_folder_scenes(root).scenes[0]

    files = {entry.path: entry for entry in scene.files}
    assert files["000.pcd"] == SceneFile(
        path="000.pcd", source=root / "000.pcd", size=3
    )
    assert files["front/000.jpg"].source == root / "front" / "000.jpg"
    assert all(entry.content is None for entry in scene.files)
    assert scene.total_bytes == 8
    assert scene.id == "drive"


def test_accepts_the_folder_as_text_and_names_the_scene_after_it(tmp_path):
    root = folder(tmp_path, {"drive/000.pcd": "a"})

    result = detect_folder_scenes(os.fspath(root) + os.sep)

    assert [scene.name for scene in result.scenes] == ["drive"]


def test_lists_sibling_scenes_in_natural_order(tmp_path):
    # Different file names, or the three folders would be sensors of one scene.
    result = detect(
        tmp_path,
        {"top/s10/a.pcd": "a", "top/s2/b.pcd": "b", "top/S1/c.pcd": "c"},
    )

    assert [scene.name for scene in result.scenes] == ["S1", "s2", "s10"]


def test_does_not_follow_symlinked_directories(tmp_path):
    root = folder(tmp_path, {"drive/000.pcd": "a"})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "000.jpg").write_bytes(b"x")
    try:
        (root / "front").symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available here")

    result = detect_folder_scenes(root)

    assert result.scenes[0].cameras == []
    assert by_path(result.scenes[0].files) == ["000.pcd"]
    assert result.unused_files == 0


def test_refuses_a_path_that_is_not_a_folder(tmp_path):
    root = folder(tmp_path, {"drive/000.pcd": "a"})

    with pytest.raises(NotADirectoryError):
        detect_folder_scenes(root / "000.pcd")


MANIFEST = '{"sensors": {"top": {"type": "lidar"}}, "frames": [{}, {}]}'


@pytest.mark.parametrize(
    ("content", "source"),
    [
        pytest.param(MANIFEST.encode(), "manifest", id="plain"),
        pytest.param(b"\xef\xbb\xbf" + MANIFEST.encode(), "manifest", id="bom dropped"),
        pytest.param(
            MANIFEST.replace("top", "t\udcffp").encode("utf-8", "surrogateescape"),
            "manifest",
            id="bad bytes replaced",
        ),
        pytest.param(b'{"frames": [NaN]}', "folder", id="NaN is not JSON"),
        pytest.param(b'{"frames": [Infinity]}', "folder", id="Infinity is not JSON"),
        pytest.param(b'{"frames": {"0": {}}}', "folder", id="frames not a list"),
        pytest.param(b'[{"frames": []}]', "folder", id="not an object"),
        pytest.param(b"{", "folder", id="broken"),
    ],
)
def test_reads_a_manifest_the_way_the_browser_does(tmp_path, content, source):
    root = folder(tmp_path, {"s/0.pcd": "a"})
    (root / "scene.json").write_bytes(content)

    scene = detect_folder_scenes(root).scenes[0]

    assert scene.source == source
    assert scene.frame_count == (2 if source == "manifest" else 1)


def test_does_not_read_a_manifest_larger_than_the_backend_reads(tmp_path, monkeypatch):
    root = folder(tmp_path, {"s/0.pcd": "a", "s/scene.json": MANIFEST})
    assert detect_folder_scenes(root).scenes[0].source == "manifest"

    monkeypatch.setattr(_scenes, "_MANIFEST_MAX_BYTES", len(MANIFEST) - 1)

    assert detect_folder_scenes(root).scenes[0].source == "folder"


def test_lists_manifest_sensors_that_are_not_cameras_as_point_sensors(tmp_path):
    result = detect(
        tmp_path,
        {
            "s/Scene.JSON": {
                "sensors": {"a": {"type": "radar"}, "b": {}, "c": None, "d": 5},
                "frames": [],
            },
        },
    )

    assert_scene(
        result.scenes[0],
        source="manifest",
        frame_count=0,
        point_sensors=["a", "b", "c", "d"],
        cameras=[],
    )


def test_orders_names_like_the_browsers_collation():
    # Expected order produced by Node 22 (ICU 76) with the TypeScript
    # ``naturalCompare``: punctuation before digits before letters, digit runs
    # by value, case and accents ignored.
    names = [
        "scene-10", "scene-9", "Scene_2", "scene 3", "scene.4", "scene1", "SCENE",
        "scenery", "LIDAR_TOP", "LIDAR1", "LIDAR-1", "lidar10", "Lidar2", "lidar(5)",
        "007", "8", "1.10", "1.5", "a+b", "a$b", "a~b", "a b", "ab", "a#b",
    ]  # fmt: skip

    assert sorted(names, key=functools.cmp_to_key(natural_compare)) == [
        "1.5", "1.10", "007", "8", "a b", "a#b", "a+b", "a~b", "a$b", "ab",
        "LIDAR_TOP", "LIDAR-1", "lidar(5)", "LIDAR1", "Lidar2", "lidar10", "SCENE",
        "scene 3", "Scene_2", "scene-9", "scene-10", "scene.4", "scene1", "scenery",
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("a", "A"),
        ("x007", "x7"),
        ("x00", "x0"),
        ("caméra", "camera"),
        ("straße", "strasse"),
        ("a\x01b", "ab"),
        ("٣", "3"),
    ],
)
def test_compares_names_the_browser_calls_equal_as_equal(left, right):
    assert natural_compare(left, right) == 0
    assert natural_compare(right, left) == 0


@pytest.mark.parametrize(
    ("left", "right", "sign"),
    [
        pytest.param(
            f"scene{chr(0x2013)}1", "scene1", -1, id="an en dash is punctuation"
        ),
        pytest.param("²", "2", 1, id="a superscript is no number"),
        pytest.param("a²", "a3", 1, id="a superscript after every number"),
        pytest.param("x1²", "x13", -1, id="a superscript ends the number"),
        pytest.param("①", "1", 1, id="a circled digit is no number"),
        pytest.param("я", "z", 1, id="other scripts after latin"),
    ],
)
def test_places_characters_outside_ascii_by_their_kind(left, right, sign):
    # Signs produced by Node 22 (ICU 76) with the TypeScript ``naturalCompare``.
    # Outside ASCII the order is an approximation; these are the kinds it keeps.
    assert natural_compare(left, right) == sign
    assert natural_compare(right, left) == -sign
