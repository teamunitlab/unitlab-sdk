from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient

MAX_PAGES = 10_000


def _endpoint(project_id: str, datasource_id: str) -> str:
    return f"/api/sdk/projects/{project_id}/items/{datasource_id}/annotations/"


def _merge_keyframes(into: dict[str, Any], page: dict[str, Any]) -> None:
    """Add one page's ``{type: {track_id: {frame: geometry}}}`` to ``into``.

    A track spans pages when its frames do: its frames are joined, never
    replaced by the later page's.
    """
    for kind, tracks in (page or {}).items():
        if not isinstance(tracks, dict):
            into[kind] = tracks
            continue
        merged = into.setdefault(kind, {})
        for track_id, frames in tracks.items():
            if isinstance(frames, dict) and isinstance(merged.get(track_id), dict):
                merged[track_id].update(frames)
            else:
                merged[track_id] = frames


@dataclass
class ItemAnnotations:
    """One item's annotations as the server holds them.

    ``objects`` are ``{type, id, class, ...}`` rows (tracks on video and
    medical items); ``keyframes`` holds the frames read when a frame window
    was asked for. ``revision`` is what a save must name.
    """

    datasource_id: str
    project_id: str
    data_type: str
    revision: str | None
    objects: list[dict[str, Any]]
    item_properties: dict[str, Any]
    tags: list[Any]
    keyframes: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    _assignment_id: str | None = field(default=None, repr=False)

    def save(
        self,
        *,
        upsert: list[dict[str, Any]] | None = None,
        delete: list[str] | None = None,
        item_properties: dict[str, Any] | None = None,
        tags: list[Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Save changes against the revision this read returned.

        Only the objects named change; others are kept. On success the
        revision moves on, so a second ``save`` from this object works.

        Raises:
            RevisionConflictError: Someone saved since this read.
            AnnotationValidationError: The server refused the changes.
        """
        result = save_annotations(
            self._client,
            self.project_id,
            self.datasource_id,
            expected_revision=self.revision,
            upsert=upsert,
            delete=delete,
            item_properties=item_properties,
            tags=tags,
            assignment_id=self._assignment_id,
            dry_run=dry_run,
        )
        if not dry_run and result.get("revision"):
            self.revision = result["revision"]
        return result


def get_annotations(
    client: UnitlabClient,
    project_id: str,
    datasource_id: str,
    *,
    frame_start: int | None = None,
    frame_end: int | None = None,
    include_masks: bool = False,
    assignment_id: str | None = None,
    page_size: int = 200,
) -> ItemAnnotations:
    """Read every page of one item's annotations.

    Args:
        frame_start: With video, medical or lidar items, also read keyframes
            from this frame on (to ``frame_end`` or the end).
        include_masks: Include mask run lengths.
        assignment_id: Read a private copy (a Consensus vote) instead.
    """
    params: dict[str, Any] = {"limit": page_size}
    if include_masks:
        params["include_masks"] = "true"
    if assignment_id:
        params["assignment_id"] = assignment_id
    if frame_start is not None:
        params["frame_start"] = frame_start
    if frame_end is not None:
        params["frame_end"] = frame_end
    endpoint = _endpoint(project_id, datasource_id)
    first: dict[str, Any] | None = None
    objects: list[dict[str, Any]] = []
    seen_objects: set[tuple[Any, Any]] = set()
    keyframes: dict[str, Any] = {}
    for _ in range(MAX_PAGES):
        page = client._api.get(endpoint, params=params) or {}
        if first is None:
            first = page
        for obj in page.get("objects") or []:
            identity = (obj.get("type"), obj.get("id"))
            if identity not in seen_objects:
                seen_objects.add(identity)
                objects.append(obj)
        _merge_keyframes(keyframes, page.get("keyframes") or {})
        if page.get("next_offset") is not None:
            params = {**params, "offset": page["next_offset"]}
        elif page.get("next_cursor"):
            params = {**params, "cursor": page["next_cursor"]}
        elif page.get("next_frame") is not None and frame_start is not None:
            params = {**params, "frame_start": page["next_frame"], "offset": 0}
        else:
            break
    first = first or {}
    return ItemAnnotations(
        datasource_id=str(first.get("datasource_id") or datasource_id),
        project_id=str(first.get("project_id") or project_id),
        data_type=str(first.get("data_type") or ""),
        revision=first.get("revision"),
        objects=objects,
        item_properties=dict(first.get("item_properties") or {}),
        tags=list(first.get("tags") or []),
        keyframes=keyframes,
        raw=first,
        _client=client,
        _assignment_id=assignment_id,
    )


def save_annotations(
    client: UnitlabClient,
    project_id: str,
    datasource_id: str,
    *,
    expected_revision: str | None,
    upsert: list[dict[str, Any]] | None = None,
    delete: list[str] | None = None,
    item_properties: dict[str, Any] | None = None,
    tags: list[Any] | None = None,
    assignment_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Add, change or delete objects of one item; others are kept.

    ``expected_revision`` is the ``revision`` the last read returned
    (``None`` before the item's first save).
    """
    payload: dict[str, Any] = {"expected_revision": expected_revision}
    for key, value in (
        ("upsert", upsert),
        ("delete", delete),
        ("item_properties", item_properties),
        ("tags", tags),
        ("assignment_id", assignment_id),
    ):
        if value is not None:
            payload[key] = value
    if dry_run:
        payload["dry_run"] = True
    return client._api.post(_endpoint(project_id, datasource_id), json=payload)
