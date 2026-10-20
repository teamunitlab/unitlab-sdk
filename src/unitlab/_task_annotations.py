"""Lidar's native read and save for ``WorkflowTask``; every other family is UUEF.

Contract: nbackend docs/workflow-agent.md ("SDK") and
docs/workflow-agent-save-spec.md. Every family but lidar reads and saves one
UUEF document per item, whole, with no diff (resources/workflow.py). A lidar
scene (row ``format: "native"``) still uses the editor's track-first result,
which the server never builds whole, so:

- Read: ``GET annotations/`` gives the scene's tracks light plus ``pages``;
  ``stitch`` fetches every keyframe page into ``result["tracks"][key][id]``.
- Save: ``plan_parts`` compares the new result with ``snapshot`` (a hash per
  track taken at read time, never a second copy) and returns the changes as
  ``track_delta`` request bodies. Small saves are one body; larger ones are
  split within the item's limits (``item_limits``) and sent one after
  another, each part an ordinary save carrying the previous part's revision.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from typing import Any

ITEM_FIELDS = ("item_properties", "data_tags")
# Leave headroom under the server's byte cap for the envelope around objects.
BYTE_HEADROOM = 0.9
# The server's own caps, for a read that did not state them. ``keyframes``
# caps the keyframes of a part's upserted tracks; None = no cap.
DEFAULT_LIMITS = {"objects": 5000, "bytes": 32 * 1024 * 1024, "keyframes": None}


def item_limits(
    save: dict[str, Any], save_limits: dict[str, Any] | None
) -> dict[str, Any]:
    """One item's part limits: its row's ``save.limits`` (the server's caps for
    that type, e.g. lidar 2,000 tracks / 20,000 keyframes), else the read's
    top-level ``save_limits``, else ``DEFAULT_LIMITS`` (an older server)."""
    return save.get("limits") or save_limits or DEFAULT_LIMITS


def _keyframes(track: dict[str, Any]) -> int:
    return len(track.get("keyframes") or ())


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _size(value: Any) -> int:
    # Same measure as the server's cap (tiled_object_utils.compact_byte_size).
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode())


def stitch(
    result: dict[str, Any],
    pages: dict[str, Any] | None,
    fetch: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Fetch every keyframe page of a scene and merge it into its light ``result``."""
    cursor = None
    while pages:
        params = dict(pages.get("params") or {})
        if cursor:
            params["cursor"] = cursor
        page = fetch(pages["path"], params)
        for key, tracks in (page.get("keyframes") or {}).items():
            for track_id, frames in tracks.items():
                result["tracks"][key][track_id]["keyframes"].update(frames)
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return result


def _owned(result: dict[str, Any], save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``{key: {id: track}}`` for the track keys a save may change."""
    owned: dict[str, dict[str, Any]] = {}
    for key in save.get("keys") or []:
        rows = (result.get("tracks") or {}).get(key) or {}
        if not isinstance(rows, dict):
            raise ValueError(f"result['tracks'][{key!r}] must map ids to tracks")
        owned[key] = dict(rows)
    return owned


def _rest(result: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in result.items() if name != "tracks"}


def snapshot(result: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    """What a later save compares against: hashes only."""
    return {
        "objects": {
            key: {identity: _digest(obj) for identity, obj in rows.items()}
            for key, rows in _owned(result, save).items()
        },
        "rest": {name: _digest(value) for name, value in _rest(result).items()},
    }


def _refers(track: dict[str, Any]) -> bool:
    """A track pointing at another (relations, a lidar camera box's cuboid)."""
    return bool(track.get("relations")) or bool(track.get("linked_track_id"))


def plan_parts(
    base: dict[str, Any],
    result: dict[str, Any],
    save: dict[str, Any],
    limits: dict[str, Any],
) -> list[dict[str, Any]]:
    """``track_delta`` request bodies (``result`` of each PUT) that turn the
    read into ``result``.

    Empty when nothing changed. Raises ValueError, before anything is sent,
    for a change the server cannot take here (a read-only key such as
    ``segments3d``, a top-level key other than the item fields, one track
    larger than one save takes).
    """
    rest = _rest(result)
    fields: dict[str, Any] = {}
    for name in sorted(set(rest) | set(base["rest"])):
        before = base["rest"].get(name)
        after = _digest(rest[name]) if name in rest else None
        if before == after:
            continue
        if name not in ITEM_FIELDS:
            raise ValueError(
                f"{name!r} cannot be changed here; change tracks, "
                "item_properties or data_tags"
            )
        fields[name] = rest.get(name, {} if name == "item_properties" else [])

    deletes: list[tuple[str, str]] = []
    upserts: list[tuple[str, str, Any]] = []
    read_only = set(save.get("read_only_keys") or [])
    owned = _owned(result, save)
    for key, rows in owned.items():
        before = base["objects"].get(key) or {}
        changed = [
            (key, identity, obj)
            for identity, obj in rows.items()
            if before.get(identity) != _digest(obj)
        ]
        gone = [(key, identity) for identity in before if identity not in rows]
        if key in read_only and (changed or gone):
            raise ValueError(
                f"{key} cannot be changed through the SDK; leave it as it was read"
            )
        upserts += changed
        deletes += gone
    if not (deletes or upserts or fields):
        return []

    max_objects = max(1, int(limits.get("objects") or DEFAULT_LIMITS["objects"]))
    max_bytes = int((limits.get("bytes") or DEFAULT_LIMITS["bytes"]) * BYTE_HEADROOM)
    # Tracks that point at others go last, so their targets exist first.
    upserts.sort(key=lambda row: _refers(row[2]))
    max_keyframes = limits.get("keyframes", DEFAULT_LIMITS["keyframes"])
    if max_keyframes is not None:
        # A track is never split across parts (the server replaces it whole),
        # so one longer than the cap can never be sent: refuse up front
        # rather than send earlier parts and fail on its own.
        for key, identity, track in upserts:
            count = _keyframes(track)
            if count > max_keyframes:
                raise ValueError(
                    f"Track {identity!r} in {key} has {count} keyframes; one save "
                    f"takes at most {max_keyframes}, so it cannot be saved here"
                )

    # Same reasoning for size: a track is never split, so one over
    # the byte cap would fail on its own after earlier parts were saved.
    for key, identity, obj in upserts:
        if _size(obj) > max_bytes:
            raise ValueError(
                f"{key} {identity!r} is {_size(obj)} bytes; one save takes at most "
                f"{max_bytes}, so it cannot be saved here"
            )

    def fits(count: int, size: int, keyframes: int) -> bool:
        return (
            count <= max_objects
            and size <= max_bytes
            and (max_keyframes is None or keyframes <= max_keyframes)
        )

    removed: list[tuple[str, str, str, Any]] = [
        ("delete", key, identity, None) for key, identity in deletes
    ]
    written: list[tuple[str, str, str, Any]] = [
        ("upsert", key, identity, obj) for key, identity, obj in upserts
    ]
    moved = {entry[2] for entry in removed} & {entry[2] for entry in written}
    if moved:
        # An id moved to another key: the server refuses one save that deletes
        # and upserts the same id, so the deletes go in parts of their own.
        chunks = list(_chunks(removed, fits)) + list(_chunks(written, fits))
    else:
        chunks = list(_chunks(removed + written, fits))
    return [
        _body(chunk, fields if index == len(chunks) - 1 else {})
        for index, chunk in enumerate(chunks)
    ]


def _chunks(
    entries: list[tuple[str, str, str, Any]],
    fits: Callable[[int, int, int], bool],
) -> Iterable[list[tuple[str, str, str, Any]]]:
    chunk: list[tuple[str, str, str, Any]] = []
    size = keyframes = 0
    for entry in entries:
        entry_size = 0 if entry[0] == "delete" else _size(entry[3])
        # Only an upserted track carries keyframes (a delete none).
        entry_keyframes = _keyframes(entry[3]) if entry[0] == "upsert" else 0
        if chunk and not fits(
            len(chunk) + 1, size + entry_size, keyframes + entry_keyframes
        ):
            yield chunk
            chunk, size, keyframes = [], 0, 0
        chunk.append(entry)
        size += entry_size
        keyframes += entry_keyframes
    yield chunk  # may be empty: a save of item fields only


def _body(
    chunk: list[tuple[str, str, str, Any]], fields: dict[str, Any]
) -> dict[str, Any]:
    body: dict[str, Any] = {"save_mode": "track_delta"}
    for kind, key, identity, value in chunk:
        if kind == "delete":
            body.setdefault("deleted_tracks", {}).setdefault(key, []).append(identity)
        else:
            body.setdefault("upserted_tracks", {}).setdefault(key, {})[identity] = value
    return {**body, **fields}
