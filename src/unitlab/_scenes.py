"""Which lidar scenes a folder on disk holds: the browser's rules, for the SDK.

Port of the frontend's ``src/utils/pointcloud-folder-scenes.ts``, plus the split
choice of ``src/components/upload-modal/pointcloud-folder-scenes-dialog.vue``
(``scenes_to_upload``). The web uploader decides in the browser which files of a
picked folder form which scene; an upload with ``generic_type="pointcloud"`` has
to decide exactly the same, or one folder would become different items
depending on how it was sent. Change this module ONLY together with that
TypeScript file. Its unit tests are translated in ``tests/test_scenes.py``;
every function here names the TypeScript function it ports and the functions
keep the order of that file, so the two can be read side by side.

Flow: ``detect_folder_scenes(root)`` lists every file below ``root`` with the
path a browser reports for a picked folder (``<root name>/<path below it>``),
groups the files into scenes and returns what the confirmation dialog shows.
``scenes_to_upload`` then applies the one choice that dialog offers. The
uploader sends each scene as ONE item: its files under one storage prefix,
each at its ``SceneFile.path`` below that prefix.

Rules, tried at each folder from the top down (the backend's ingest reads the
result the same way):

0. A recognised dataset (``_nuscenes.py``): its tables decide the scenes and a
   ``scene.json`` is written for each.
1. A folder with our own ``scene.json`` (an object with ``frames``) is a scene.
2. A folder with point clouds directly inside, and none in its subfolders, is
   a scene with one sensor; image subfolders whose file names match the frames
   are its cameras.
3. A folder whose subfolders hold point clouds, nothing deeper, is one scene
   with a sensor per subfolder, when those subfolders share file names (the
   same frame exists in each). Otherwise each subfolder is its own scene.
4. Otherwise each subfolder is looked at by the same rules.

In rules 2 and 3 a sensor or camera folder may keep its files one level down,
in a ``data`` folder of its own (KITTI raw: ``velodyne_points/data/``), and a
folder name becomes a sensor name with what a name cannot hold turned into
``_``; both exactly as the backend's ``_plan_from_folders`` does it.

Shared file names are what sensors of one scene have, and also what separate
recordings have when they number their frames alike. Names cannot tell the two
apart, so a rule 3 scene of several sensors carries the other reading too
(``Scene.split``) and ``scenes_to_upload`` takes it on request.

Backend twins: where the TypeScript mirrors the backend's
``api/v1/unitlabel/pointcloud_ingest.py`` (``_natural_key``, ``_extension``,
``_basename``, ``_sensor_name``, ``_folder_sensor_name``), the lines here are
copied from the backend instead of translated from the TypeScript, so the SDK
and the ingest cannot disagree. The backend is not imported: the SDK ships
without it. Each copy says so where it stands.

What cannot be the browser's exactly is said where it happens: the order a
directory is listed in (``_folder_entries``) and the order of names the
browser sorts with its own locale (``natural_compare``).
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import stat
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

# Copied from the backend's ingest: the manifest's name and the formats it
# reads. A format added there has to be added here and in the TypeScript.
MANIFEST_NAME = "scene.json"
CLOUD_EXTENSIONS = ("pcd", "bin", "ply")
IMAGE_EXTENSIONS = ("jpg", "jpeg", "png")
# Image formats a camera folder may hold that the ingest does not read. Only
# used to say why such a folder is left out.
_UNREAD_IMAGE_EXTENSIONS = ("webp", "bmp", "tif", "tiff", "gif")
# The backend reads at most this much of a manifest (``max_manifest_bytes``).
_MANIFEST_MAX_BYTES = 16 * 1024 * 1024
# Backend: ``_NAME_PATTERN`` and ``_NOT_A_NAME_CHARACTER``. Sensor names are
# keys of the derivative's paths and of the label arrays.
_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
_NOT_A_NAME_CHARACTER = re.compile(r"[^A-Za-z0-9_-]")
# A sensor's or camera's files may sit one level down, in this folder.
_DATA_FOLDER = "data"


@dataclass(frozen=True)
class SceneFile:
    """One file of a scene (TypeScript: ``SceneUploadFile``).

    Exactly one of ``source`` and ``content`` is set: a file on disk, or a file
    made here (the ``scene.json`` written for a nuScenes scene).

    Attributes:
        path: POSIX path below the scene's root; becomes the object key below
            the scene's storage prefix.
        source: The file on disk.
        content: The bytes of a generated file.
        size: Size in bytes.
    """

    path: str
    source: Path | None = None
    content: bytes | None = None
    size: int = 0


@dataclass
class SceneSplit:
    """The other reading of a scene of several sensor folders.

    Attributes:
        scenes: The same folders read as one scene per sensor folder.
        extra_unused_files: How many more (or fewer) files that reading leaves
            unused: it drops the cameras of the merged reading, as nothing
            says whose they are.
    """

    scenes: list[Scene]
    extra_unused_files: int


@dataclass
class Scene:
    """One lidar scene found in a folder (TypeScript: ``PointcloudFolderScene``).

    Attributes:
        id: The scene folder's path from the picked folder's name down
            (``drives/seq_1``); for a nuScenes scene, the dataset folder's path,
            ``#`` and the scene's token. Unique within one detection.
        name: The folder's name, or the recording's name in a dataset.
        source: ``"manifest"`` (rule 1), ``"folder"`` (rules 2 and 3) or
            ``"nuscenes"`` (rule 0).
        files: The files to upload, each with its path below the scene.
        frame_count: Frames the scene will have; sent with the upload so the
            server can refuse on its frame limits before a byte is sent.
            Detection always sets a number. ``None`` is for scenes the
            uploader builds itself from one archive (``source="file"``), whose
            frames are only known after the ingest.
        point_sensors: Names of the lidar and radar sensors.
        cameras: Names of the cameras.
        total_bytes: Sum of the sizes of ``files``.
        missing_files: Files the dataset's tables name but the folder lacks.
        description: The recording's description in a dataset.
        notes: Image folders of the scene that are left out, each with the
            reason. Empty where the TypeScript leaves ``notes`` out.
        split: The second reading; only on a scene of several sensor folders
            that was put together by their shared file names.
    """

    id: str
    name: str
    source: str
    files: list[SceneFile]
    frame_count: int | None
    point_sensors: list[str]
    cameras: list[str]
    total_bytes: int
    missing_files: int = 0
    description: str | None = None
    notes: list[str] = field(default_factory=list)
    split: SceneSplit | None = None


@dataclass
class SceneDetection:
    """What a folder holds (TypeScript: ``PointcloudFolderDetection``).

    Attributes:
        scenes: The scenes, in the order the dialog lists them.
        unused_files: Files inside a scene or dataset folder that no scene
            uses; they are not uploaded.
        other_files: Files outside every scene folder, as absolute paths; the
            caller decides what becomes of them.
        datasets: One ``{"kind": "nuscenes", "name": str, "scene_count": int}``
            per recognised dataset folder.
    """

    scenes: list[Scene]
    unused_files: int
    other_files: list[Path]
    datasets: list[dict[str, Any]]


# ``eq=False``: nodes are compared by identity, as the TypeScript compares its
# objects (``sensorFolders.includes(dir)``); a field-by-field comparison would
# walk whole subtrees.
@dataclass(eq=False)
class FolderNode:
    """A folder of the picked tree (TypeScript: ``FolderNode``).

    Attributes:
        name: The folder's own name.
        path: Its path from the picked folder's name down.
        files: Its own files, each with the same kind of path.
        dirs: Its subfolders by name, in the order they were first seen.
    """

    name: str
    path: str
    files: list[SceneFile] = field(default_factory=list)
    dirs: dict[str, FolderNode] = field(default_factory=dict)


def _folder_entries(root: Path) -> list[SceneFile]:
    """Lists the files below ``root`` as a browser lists a picked folder.

    Stands in for ``fileRelativePath``: a picked folder arrives in the browser
    as its files, each with ``webkitRelativePath`` = the folder's own name, then
    the path below it. The name is part of the path on purpose: the picked
    folder itself can be a scene, and its name is then the scene's name.

    Differences from the browser:

    * Order. The browser's order is the operating system's; here names are
      sorted, so one folder always gives one result. The rules read the order
      only where they take "the first" of names they cannot tell apart: two
      names in one folder that differ only by case (``scene.json`` and
      ``Scene.JSON``, ``data`` and ``Data``), sensor folders that differ only
      by case or leading zeros (``7`` and ``007``: which one is the
      reference), and the listing of sibling scenes whose names differ only
      by case, accents or leading zeros.
    * Symbolic links to folders are not followed (a loop would never end);
      a link to a file counts as that file.

    Folders the noise rule drops are not entered: every file below them would
    be dropped by ``_is_noise_path`` anyway, and a ``.git`` can hold thousands.

    Args:
        root: Absolute path of the folder.

    Returns:
        Regular files only, each with its path on disk and its size.
    """
    # A drive root has no name; the rules need one top folder to start from.
    name = root.name or "folder"
    entries: list[SceneFile] = []
    for directory, folders, names in os.walk(root, followlinks=False):
        folders[:] = sorted(part for part in folders if not _is_noise_path(part))
        below = Path(directory).relative_to(root).parts
        for filename in sorted(names):
            source = Path(directory, filename)
            try:
                status = source.stat()
            except OSError:  # a dangling link, or a file removed meanwhile
                continue
            if not stat.S_ISREG(status.st_mode):
                continue
            entries.append(
                SceneFile(
                    # Joined with "/" by hand: the path is an object key, not a
                    # path of this operating system.
                    path="/".join((name, *below, filename)),
                    source=source,
                    size=status.st_size,
                )
            )
    return entries


def lower_name(path: str) -> str:
    """Returns the file name of ``path``, lower-cased (``lowerName``)."""
    return path.rsplit("/", 1)[-1].lower()


def _extension(path: str) -> str:
    """Backend: ``_extension``. What follows the last dot, lower-cased."""
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def is_cloud_path(path: str) -> bool:
    """Whether the ingest reads ``path`` as a point cloud (``isCloudPath``).

    Written as the backend's ``_is_cloud``. The TypeScript asks whether the
    lower-cased file name ends with ``.pcd``, ``.bin`` or ``.ply``; that is the
    same question, as a dot in a folder name leaves a ``/`` in the extension.
    """
    return _extension(path) in CLOUD_EXTENSIONS


def _is_image_path(path: str) -> bool:
    """Backend: ``_is_image`` (``isImagePath``)."""
    return _extension(path) in IMAGE_EXTENSIONS


def _is_unread_image_path(path: str) -> bool:
    """Whether ``path`` is an image the ingest does not read (``isUnreadImagePath``)."""
    return _extension(path) in _UNREAD_IMAGE_EXTENSIONS


def _folder_sensor_name(name: str) -> str:
    """A folder's name as a sensor name: what a name cannot hold becomes ``_``.

    Port of ``cleanName``; the line is the backend's ``_folder_sensor_name``,
    which names the sensor for real. A folder called ``Camera 1`` is still that
    camera: it becomes ``Camera_1`` instead of being left out.
    """
    return _NOT_A_NAME_CHARACTER.sub("_", name)[:64]


def _is_noise_path(path: str) -> bool:
    """Whether a file is clutter of an operating system (``isNoisePath``).

    This is the TypeScript rule, not the backend's ``_is_noise``, which drops
    less: the browser never sends these files, so the backend's rule only ever
    meets archives. Any part of the path counts, the picked folder's own name
    included: a folder named ``.scans`` holds no scene for the browser either.
    """
    return any(
        part == "__MACOSX"
        or part.startswith(".")
        or part.lower() in ("thumbs.db", "desktop.ini")
        for part in path.split("/")
    )


def _frame_key(path: str) -> str:
    """File name without its extension: how frames are matched across sensors.

    Port of ``frameKey``; the line is the backend's ``_basename``. The two
    differ only on names that begin with a dot, which are noise and never get
    here.
    """
    return posixpath.splitext(posixpath.basename(path))[0]


# ASCII in the order of the browsers' collation (ICU root): white space,
# punctuation, symbols, then every number, then letters. Read from Node 22
# (ICU 76) with the TypeScript comparator; ``tests/test_scenes.py`` pins it.
_COLLATION_ORDER = "\t\n\x0b\x0c\r _-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$"
_COLLATION_RANK = {character: rank for rank, character in enumerate(_COLLATION_ORDER)}
# Punctuation and symbols outside ASCII: the collation spreads them among the
# ASCII ones; here they follow them, which keeps them before every number.
_OTHER_SYMBOL_RANK = len(_COLLATION_ORDER)
_NUMBER_RANK = _OTHER_SYMBOL_RANK + 1
_LETTER_RANK = _NUMBER_RANK + 1


def _collation_key(text: str) -> list[tuple[int, int]]:
    """Sort key of ``natural_compare``: one ``(rank, value)`` pair per unit."""
    key: list[tuple[int, int]] = []
    # The digits are split off before anything is folded: a superscript or a
    # circled digit folds to a digit, and the collation does not count those
    # as part of a number.
    for index, part in enumerate(re.split(r"(\d+)", text)):
        if index % 2:
            # A run of digits is one number, wherever it stands ("numeric").
            key.append((_NUMBER_RANK, int(part)))
            continue
        # Case, accents and width do not count ("sensitivity: base").
        for character in unicodedata.normalize("NFKD", part).casefold():
            rank = _COLLATION_RANK.get(character)
            if rank is not None:
                key.append((rank, 0))
            elif unicodedata.combining(character) or not character.isprintable():
                continue  # accents; control and format characters
            elif unicodedata.category(character)[0] in "PS":
                key.append((_OTHER_SYMBOL_RANK, ord(character)))
            else:
                key.append((_LETTER_RANK, ord(character)))
    return key


def natural_compare(a: str, b: str) -> int:
    """Compares two names as the dialog orders them (``naturalCompare``).

    The TypeScript is ``a.localeCompare(b, undefined, {numeric: true,
    sensitivity: "base"})``: the browser's own collation, in the user's locale.
    The standard library has no such thing, so this rebuilds its order for an
    English-language browser:

    * ASCII names compare exactly as there (``_COLLATION_ORDER``), digit runs
      by their value, case ignored.
    * Other characters are an approximation: accents and width are ignored,
      punctuation stays before numbers, and what is left sorts after the
      ASCII letters by code point. The collation knows more (``ø`` is an
      ``o`` to it, ``æ`` is ``ae``).
    * A browser in another language can order even plain letters differently
      (Lithuanian puts ``y`` with ``i``, Estonian ``z`` after ``s``); that is
      not followed.

    Where it matters: the order sibling scenes are listed in (order only), and
    in ``_nuscenes.py`` the choice of the reference lidar among several, which
    changes the manifest.

    Returns:
        A negative number, zero or a positive number, like the TypeScript.
    """
    left, right = _collation_key(a), _collation_key(b)
    return (left > right) - (left < right)


def backend_natural_key(text: str) -> list[int | str]:
    """Sort key for the order the backend puts folder names in.

    Port of ``backendNaturalCompare``, as a key instead of a comparator; the
    rule is the backend's ``_natural_key``: runs of digits by their value,
    everything else lower-cased and by code point. The first sensor folder in
    this order is the scene's reference, whose files are the frames, so the
    SDK and the ingest have to pick the same one; ``natural_compare`` follows
    the browser's collation and differs on names with punctuation.

    The backend tells digit runs by ``part.isdigit()``, this by the position
    in the split (every second part is a run). Both give the same key for
    every name the backend can key; the backend raises on a name such as
    ``10²``, whose ``²`` passes ``isdigit()`` and fails ``int()``.
    """
    return [
        int(part) if index % 2 else part.lower()
        for index, part in enumerate(re.split(r"(\d+)", text))
    ]


def _build_tree(entries: list[SceneFile]) -> FolderNode:
    """Builds the folder tree of the listed files (``buildTree``)."""
    root = FolderNode(name="", path="")
    for entry in entries:
        parts = entry.path.split("/")
        node = root
        for part in parts[:-1]:
            child = node.dirs.get(part)
            if child is None:
                child = FolderNode(
                    name=part, path=f"{node.path}/{part}" if node.path else part
                )
                node.dirs[part] = child
            node = child
        node.files.append(entry)
    return root


def files_under(node: FolderNode) -> list[SceneFile]:
    """Returns every file in ``node`` and below it (``filesUnder``)."""
    files = list(node.files)
    for child in node.dirs.values():
        files.extend(files_under(child))
    return files


def _has_cloud_under(node: FolderNode) -> bool:
    """Whether ``node`` or a folder below it holds a point cloud (``hasCloudUnder``)."""
    return any(is_cloud_path(entry.path) for entry in node.files) or any(
        _has_cloud_under(child) for child in node.dirs.values()
    )


def relative_to(node: FolderNode, entry: SceneFile) -> SceneFile:
    """Returns ``entry`` re-rooted at ``node``: its path below that folder.

    Port of ``relativeTo``. This is the path the file is uploaded under.
    """
    return replace(entry, path=entry.path[len(node.path) + 1 :])


def _scene_of(
    node: FolderNode,
    source: str,
    files: list[SceneFile],
    *,
    frame_count: int,
    point_sensors: list[str],
    cameras: list[str],
) -> Scene:
    """Makes the scene of the folder ``node`` (``sceneOf``)."""
    return Scene(
        id=node.path,
        name=node.name,
        source=source,
        files=files,
        frame_count=frame_count,
        point_sensors=point_sensors,
        cameras=cameras,
        total_bytes=sum(entry.size for entry in files),
    )


def _not_json(constant: str) -> Any:
    raise ValueError(f"{constant} is not JSON")


def read_json(entry: SceneFile) -> Any:
    """Reads a file as the browser's ``JSON.parse(await file.text())`` does.

    ``Blob.text()`` decodes UTF-8, drops a byte order mark and replaces bytes
    that are not UTF-8; ``JSON.parse`` refuses ``NaN`` and ``Infinity``, which
    Python's parser takes unless told otherwise. A scene must not be a
    manifest scene here and a folder scene in the browser because of that.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the text is not JSON.
        RecursionError: If the JSON is nested too deep to read.
    """
    data = entry.content if entry.source is None else entry.source.read_bytes()
    text = (data or b"").decode("utf-8-sig", errors="replace")
    return json.loads(text, parse_constant=_not_json)


def _read_manifest(entry: SceneFile) -> dict[str, Any] | None:
    """Returns our own manifest when ``entry`` is one, else ``None``.

    Port of ``readManifest``: an object whose ``frames`` is a list, of at most
    the size the backend reads. Anything else, unreadable files included, is
    not a manifest and the folder rules apply.
    """
    if entry.size > _MANIFEST_MAX_BYTES:
        return None
    try:
        parsed = read_json(entry)
    except (OSError, ValueError, RecursionError):
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("frames"), list):
        return parsed
    return None


def _manifest_sensors(manifest: dict[str, Any]) -> list[tuple[str, Any]]:
    """The manifest's sensors as ``Object.entries(manifest.sensors || {})``.

    A list counts by position, as it does in JavaScript; the backend refuses
    such a manifest later, but until then the dialog shows these names.
    """
    sensors = manifest.get("sensors")
    if isinstance(sensors, dict):
        return list(sensors.items())
    if isinstance(sensors, list):
        return [(str(index), spec) for index, spec in enumerate(sensors)]
    return []


def _data_folder_of(directory: FolderNode) -> FolderNode | None:
    """Returns the ``data`` folder of ``directory``, if any (``dataFolderOf``)."""
    return next(
        (
            child
            for child in directory.dirs.values()
            if child.name.lower() == _DATA_FOLDER
        ),
        None,
    )


def _clouds_in(directory: FolderNode) -> list[SceneFile]:
    """Returns the point clouds directly in ``directory`` (``cloudsIn``)."""
    return [entry for entry in directory.files if is_cloud_path(entry.path)]


def _cloud_holder(directory: FolderNode) -> FolderNode | None:
    """Returns the folder holding the clouds of the sensor folder ``directory``.

    Port of ``cloudHolder``: ``directory`` itself, or its ``data`` folder.
    ``None`` when ``directory`` is not one sensor, because its clouds sit in
    more than one place below it (the backend refuses such a folder).
    """
    data = _data_folder_of(directory)
    holder = directory if _clouds_in(directory) else data
    if holder is None:
        return None
    inside = sum(1 for entry in files_under(directory) if is_cloud_path(entry.path))
    held = len(_clouds_in(holder))
    return holder if held > 0 and held == inside else None


def _image_files_of(directory: FolderNode, wanted=_is_image_path) -> list[SceneFile]:
    """A camera folder's images: its own and those of its ``data`` folder.

    Port of ``imageFilesOf``. ``wanted`` picks the formats.
    """
    data = _data_folder_of(directory)
    files = [*directory.files, *(data.files if data else [])]
    return [entry for entry in files if wanted(entry.path)]


def _sensor_names(folders: list[FolderNode]) -> list[str] | None:
    """Sensor names of the cloud folders of one scene, as the backend gives them.

    Port of ``sensorNames``; the backend's rule is in ``_plan_from_folders``.
    One sensor keeps its folder's name when that is a name as it stands (else
    ``lidar``): scenes already annotated are keyed by it, so it is not cleaned
    like the names of several sensors. ``None`` when two folders would get the
    same name, which the backend refuses.
    """
    if len(folders) == 1:
        name = folders[0].name
        # Backend: ``_sensor_name``.
        return [name if _NAME_PATTERN.fullmatch(name) else "lidar"]
    names = [_folder_sensor_name(directory.name) for directory in folders]
    return names if len(set(names)) == len(names) else None


def _camera_folders(
    candidates: list[FolderNode], frame_names: set[str], sensors: list[str]
) -> tuple[list[tuple[str, list[SceneFile]]], list[str]]:
    """Picks the camera folders of a scene (``cameraFolders``).

    Cameras are image folders whose file names line up with the scene's
    frames. An image folder that is left out gets a note with the reason, so a
    scene never silently comes out without a camera the user put there. A name
    already taken stays with the folder that had it first, in the backend's
    order.

    Returns:
        The cameras as ``(name, files)`` pairs, and the notes.
    """
    cameras: list[tuple[str, list[SceneFile]]] = []
    notes: list[str] = []
    taken = set(sensors)
    for directory in sorted(
        candidates, key=lambda candidate: backend_natural_key(candidate.name)
    ):
        images = _image_files_of(directory)
        if not images:
            if _image_files_of(directory, _is_unread_image_path):
                notes.append(
                    f"“{directory.name}” is not used as a camera: "
                    "only .jpg and .png images are read."
                )
            continue
        name = _folder_sensor_name(directory.name)
        if not any(_frame_key(entry.path) in frame_names for entry in images):
            notes.append(
                f"“{directory.name}” is not used as a camera: "
                "its image names match no frame."
            )
        elif name in taken:
            notes.append(
                f"“{directory.name}” is not used as a camera: "
                f"another folder already has the name {name}."
            )
        else:
            taken.add(name)
            cameras.append((name, images))
    return cameras, notes


def _scene_at(node: FolderNode) -> Scene | None:
    """Returns the scene the folder ``node`` is, by rules 1 to 3 (``sceneAt``)."""
    # Rule 1: our own manifest says what every file is.
    manifest_entry = next(
        (entry for entry in node.files if lower_name(entry.path) == MANIFEST_NAME),
        None,
    )
    manifest = _read_manifest(manifest_entry) if manifest_entry else None
    if manifest is not None:
        sensors = [
            (name, spec.get("type") if isinstance(spec, dict) else None)
            for name, spec in _manifest_sensors(manifest)
        ]
        return _scene_of(
            node,
            "manifest",
            [relative_to(node, entry) for entry in files_under(node)],
            frame_count=len(manifest["frames"]),
            point_sensors=[name for name, kind in sensors if kind != "camera"],
            cameras=[name for name, kind in sensors if kind == "camera"],
        )

    children = list(node.dirs.values())
    direct_clouds = _clouds_in(node)

    # Rule 2: clouds directly in the folder, none further down.
    if direct_clouds and not any(_has_cloud_under(child) for child in children):
        frames = {_frame_key(entry.path) for entry in direct_clouds}
        cameras, notes = _camera_folders(children, frames, ["lidar"])
        camera_files = [entry for _, files in cameras for entry in files]
        scene = _scene_of(
            node,
            "folder",
            [relative_to(node, entry) for entry in [*direct_clouds, *camera_files]],
            frame_count=len(frames),
            point_sensors=["lidar"],
            cameras=[name for name, _ in cameras],
        )
        scene.notes = notes
        return scene

    # Rule 3: one sensor per subfolder, matched across folders by file name.
    sensor_folders = sorted(
        (child for child in children if _has_cloud_under(child)),
        key=lambda child: backend_natural_key(child.name),
    )
    holders = [
        holder for holder in map(_cloud_holder, sensor_folders) if holder is not None
    ]
    if not direct_clouds and sensor_folders and len(holders) == len(sensor_folders):
        frames_of = [
            {_frame_key(entry.path) for entry in _clouds_in(holder)}
            for holder in holders
        ]
        # The first folder in the backend's order is the reference: its files
        # are the frames, the others add the file of the same name.
        reference = frames_of[0]
        names = _sensor_names(sensor_folders)
        if names is not None and all(frames & reference for frames in frames_of[1:]):
            cameras, notes = _camera_folders(
                [child for child in children if child not in sensor_folders],
                reference,
                names,
            )
            clouds = [entry for holder in holders for entry in _clouds_in(holder)]
            camera_files = [entry for _, files in cameras for entry in files]
            scene = _scene_of(
                node,
                "folder",
                [relative_to(node, entry) for entry in [*clouds, *camera_files]],
                frame_count=len(reference),
                point_sensors=names,
                cameras=[name for name, _ in cameras],
            )
            scene.notes = notes
            if len(sensor_folders) < 2:
                return scene
            # The other reading of the same folders: each one a recording of
            # its own.
            parts = [
                part for part in map(_scene_at, sensor_folders) if part is not None
            ]
            if len(parts) == len(sensor_folders):
                scene.split = SceneSplit(
                    scenes=parts,
                    extra_unused_files=len(scene.files)
                    - sum(len(part.files) for part in parts),
                )
            return scene
    return None


def detect_folder_scenes(root: str | Path) -> SceneDetection:
    """Groups the files of the folder ``root`` into lidar scenes.

    Port of ``detectPointcloudFolderScenes`` for a picked folder: what the
    browser finds when the user picks ``root``. Nothing is uploaded and no
    request is made; only JSON manifests and dataset tables are read.

    Args:
        root: The folder to look in. It may be a scene itself, hold scenes at
            any depth, or be a nuScenes dataset.

    Returns:
        The scenes, the count of files in scene folders that no scene uses,
        the files outside every scene, and the datasets recognised.

    Raises:
        NotADirectoryError: If ``root`` is not a folder.
        ValueError: If a nuScenes dataset's tables cannot be read. The browser
            reports the same case as "The folder's 3D scenes could not be
            read" and uploads no scene of the folder.
        OSError: If the folder or a dataset table cannot be read from disk.
    """
    # Imported here: the two modules use each other, as the TypeScript files do.
    from ._nuscenes import find_nuscenes_tables, import_nuscenes_scenes

    # Made absolute without resolving links, so the picked folder keeps the
    # name the user gave it and the paths returned work from any directory.
    folder = Path(os.path.abspath(root))
    if not folder.is_dir():
        raise NotADirectoryError(f"{root} is not a folder")
    entries = [
        entry for entry in _folder_entries(folder) if not _is_noise_path(entry.path)
    ]
    tree = _build_tree(entries)
    detection = SceneDetection(scenes=[], unused_files=0, other_files=[], datasets=[])
    claimed: set[str] = set()

    def claim(node: FolderNode, used: int) -> None:
        under = files_under(node)
        claimed.update(entry.path for entry in under)
        detection.unused_files += max(0, len(under) - used)

    def visit(node: FolderNode) -> None:
        tables = find_nuscenes_tables(node)
        if tables:
            scenes, used_files = import_nuscenes_scenes(node, tables)
            if scenes:
                detection.scenes.extend(scenes)
                detection.datasets.append(
                    {"kind": "nuscenes", "name": node.name, "scene_count": len(scenes)}
                )
                claim(node, used_files)
                return
        scene = _scene_at(node)
        if scene:
            detection.scenes.append(scene)
            claim(node, len(scene.files))
            return
        # Rule 4. The order only decides how the scenes are listed.
        for child in sorted(
            node.dirs.values(), key=lambda child: _collation_key(child.name)
        ):
            visit(child)

    # The tree's root stands above the picked folder and has no files: with a
    # directory there are no loose files, which the browser never makes a scene.
    for child in tree.dirs.values():
        visit(child)
    detection.other_files = [
        entry.source
        for entry in entries
        if entry.path not in claimed and entry.source is not None
    ]
    # Noise files are dropped silently, as the folder walk already does.
    return detection


def scenes_to_upload(
    detection: SceneDetection, *, split_sensor_folders: bool = False
) -> tuple[list[Scene], int]:
    """Returns the dialog's rows and its count of unused files.

    Port of ``rowsOf``, ``isSplit`` and ``unusedFiles`` of the confirmation
    dialog. There the user switches single scenes to their other reading; here
    one flag switches every scene that has one. The dialog's ticks and its
    size limit are the caller's business.

    Args:
        detection: The result of ``detect_folder_scenes``; it is not changed.
        split_sensor_folders: Take ``Scene.split`` wherever a scene carries
            it: each sensor folder becomes a scene of its own. The cameras of
            the merged reading are then left out, as nothing says whose they
            are, and count as unused.

    Returns:
        The scenes to upload, in the dialog's order, and how many files of
        the scene folders are not part of any of them.
    """
    rows: list[Scene] = []
    unused_files = detection.unused_files
    for scene in detection.scenes:
        if split_sensor_folders and scene.split:
            rows.extend(scene.split.scenes)
            unused_files += scene.split.extra_unused_files
        else:
            rows.append(scene)
    return rows, unused_files
