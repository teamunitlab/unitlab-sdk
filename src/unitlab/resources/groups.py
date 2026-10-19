from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .._waiter import POLL_DELAYS
from ..exceptions import ProcessingTimeoutError, UnitlabError
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient

JOB_DONE_STATUSES = ("succeeded", "failed")


@dataclass
class TileSpec:
    """One tile of a Data Group made by hand.

    Args:
        tile_id: Stable id of the tile inside its group (letters, digits,
            ``_``, ``-`` or ``.``).
        asset: Asset handle or id of the file shown in the tile; ``None`` makes
            an empty (missing) tile.
        title: Label shown on the tile; defaults to ``tile_id``.
        required: The group cannot move on until this tile is annotated.
        read_only: The tile is shown for reference and never takes labels.
        alignment: For a timeseries tile, ``{"align_to_tile_id": ..., "mode":
            "frame" | "time", "offset": 0}``: the tile whose timeline it follows.
    """

    tile_id: str
    asset: Any = None
    title: str | None = None
    required: bool = False
    read_only: bool = False
    alignment: dict[str, Any] | None = None

    def _payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tile_id": self.tile_id,
            "title": self.title or self.tile_id,
            "asset_id": identifier(self.asset) if self.asset is not None else None,
            "required": self.required,
            "read_only": self.read_only,
        }
        if self.alignment:
            payload["alignment"] = self.alignment
        return payload


def _tile_payloads(tiles) -> list[dict[str, Any]]:
    return [
        tile._payload() if isinstance(tile, TileSpec) else dict(tile) for tile in tiles
    ]


@dataclass
class DataGroup:
    """A library Data Group: several files annotated together as one item."""

    id: str
    name: str
    revision: int
    tiles: list[dict[str, Any]]
    settings: dict[str, Any]
    custom_metadata: dict[str, Any]
    source_kind: str
    config_id: str | None
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> DataGroup:
        return cls(
            id=str(raw.get("pk") or raw.get("id")),
            name=str(raw.get("name", "")),
            revision=int(raw.get("revision") or 0),
            tiles=list(raw.get("tiles") or []),
            settings=dict(raw.get("settings") or {}),
            custom_metadata=dict(raw.get("custom_metadata") or {}),
            source_kind=str(raw.get("source_kind") or ""),
            config_id=str(raw["config_id"]) if raw.get("config_id") else None,
            raw=raw,
            _client=client,
        )

    def _apply(self, other: DataGroup) -> DataGroup:
        for name in (
            "name",
            "revision",
            "tiles",
            "settings",
            "custom_metadata",
            "source_kind",
            "config_id",
            "raw",
        ):
            setattr(self, name, getattr(other, name))
        return self

    def refresh(self) -> DataGroup:
        return self._apply(self._client.data_groups.get(self.id))

    def update(
        self,
        *,
        name: str | None = None,
        layout: dict[str, Any] | None = None,
        multi_layer: bool | None = None,
        custom_metadata: dict[str, Any] | None = None,
        add_tiles: list[TileSpec | dict[str, Any]] | None = None,
        update_tiles: list[dict[str, Any]] | None = None,
        remove_tiles: list[str] | None = None,
    ) -> DataGroup:
        """Edit the group. Raises ConflictError if it changed since it was read.

        ``update_tiles`` entries name a tile by ``tile_id`` and change only the
        keys they send (``title``, ``required``, ``read_only``, ``alignment``,
        ``asset_id``).
        """
        payload: dict[str, Any] = {"expected_revision": self.revision}
        if name is not None:
            payload["name"] = name
        if layout is not None:
            payload["layout"] = layout
        if multi_layer is not None:
            payload["settings"] = {**self.settings, "multi_layer": multi_layer}
        if custom_metadata is not None:
            payload["custom_metadata"] = custom_metadata
        upsert = _tile_payloads(add_tiles or []) + [
            dict(entry) for entry in update_tiles or []
        ]
        if upsert or remove_tiles:
            payload["tiles"] = {"upsert": upsert, "delete": list(remove_tiles or [])}
        raw = self._client._api.request(
            "PATCH", f"/api/sdk/data-assets/groups/{self.id}/", json=payload
        )
        return self._apply(DataGroup._from_raw(self._client, raw))

    def delete(self) -> None:
        self._client._api.request("DELETE", f"/api/sdk/data-assets/groups/{self.id}/")


@dataclass
class GroupingJob:
    """A large auto-grouping run that continues on the server."""

    id: str
    status: str
    progress: dict[str, Any]
    error: str
    grouped_folder_id: str | None
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> GroupingJob:
        return cls(
            id=str(raw.get("job_id")),
            status=str(raw.get("status") or "pending"),
            progress=dict(raw.get("progress") or {}),
            error=str(raw.get("error") or ""),
            grouped_folder_id=(
                str(raw["grouped_folder_id"]) if raw.get("grouped_folder_id") else None
            ),
            raw=raw,
            _client=client,
        )

    def refresh(self) -> GroupingJob:
        fresh = self._client.data_groups.job(self.id)
        self.status, self.progress, self.error = (
            fresh.status,
            fresh.progress,
            fresh.error,
        )
        self.grouped_folder_id, self.raw = fresh.grouped_folder_id, fresh.raw
        return self

    def wait(self, *, timeout: float = 7200) -> GroupingJob:
        """Block until the run finished.

        Raises:
            UnitlabError: With code ``grouping_failed`` when the run failed.
            ProcessingTimeoutError: When it is still running after ``timeout``.
        """
        deadline = time.monotonic() + timeout
        attempt = 0
        while self.status not in JOB_DONE_STATUSES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProcessingTimeoutError(
                    f"Grouping job {self.id} is still running after "
                    f"{timeout:g} seconds."
                )
            time.sleep(min(POLL_DELAYS[min(attempt, len(POLL_DELAYS) - 1)], remaining))
            attempt += 1
            self.refresh()
        if self.status == "failed":
            raise UnitlabError(
                f"Grouping job {self.id} failed: {self.error or 'unknown error'}",
                code="grouping_failed",
            )
        return self


class DataGroupsNamespace(Namespace):
    def get(self, group) -> DataGroup:
        raw = self._api.get(f"/api/sdk/data-assets/groups/{identifier(group)}/")
        return DataGroup._from_raw(self._client, raw)

    def list(self, folder) -> list[DataGroup]:
        rows = self._all_pages(
            f"/api/sdk/data-assets/folders/{identifier(folder)}/groups/"
        )
        return [DataGroup._from_raw(self._client, row) for row in rows]

    def create(
        self,
        folder,
        name: str,
        tiles: list[TileSpec | dict[str, Any]],
        *,
        layout: dict[str, Any] | None = None,
        multi_layer: bool = False,
        custom_metadata: dict[str, Any] | None = None,
    ) -> DataGroup:
        """Make one Data Group in a library folder from named files."""
        payload: dict[str, Any] = {
            "name": name,
            "tiles": _tile_payloads(tiles),
            "settings": {"multi_layer": multi_layer},
        }
        if layout is not None:
            payload["layout"] = layout
        if custom_metadata is not None:
            payload["custom_metadata"] = custom_metadata
        raw = self._api.post(
            f"/api/sdk/data-assets/folders/{identifier(folder)}/groups/", json=payload
        )
        return DataGroup._from_raw(self._client, raw)

    def job(self, job_id: str) -> GroupingJob:
        raw = self._api.get(f"/api/sdk/data-assets/auto-grouping-jobs/{job_id}/")
        return GroupingJob._from_raw(self._client, raw)

    def rerun(self, config_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        """Run a saved auto-grouping config again into its own grouped folder.

        New files become new groups or fill tiles an existing group lacked;
        nothing already grouped changes. Returns the counts, and ``job_id``
        when the run continues in the background.
        """
        return self._api.post(
            f"/api/sdk/data-assets/auto-grouping-configs/{config_id}/rerun/",
            json={"dry_run": dry_run},
        )


@dataclass
class GroupLayer:
    """What belongs to a project Data Group as a whole.

    ``properties`` holds group property answers keyed by the property's
    value (as a string); ``links`` joins objects of different tiles that are
    the same real thing: ``{id, kind: "link" | "layer", class, members:
    [{tile_id, object_id, family}]}``.
    """

    group_id: str
    revision: str | None
    version: int
    properties: dict[str, Any]
    links: list[dict[str, Any]]
    problems: list[dict[str, Any]]
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def _from_raw(cls, raw: dict[str, Any]) -> GroupLayer:
        return cls(
            group_id=str(raw.get("group_id", "")),
            revision=raw.get("revision"),
            version=int(raw.get("version") or 0),
            properties=dict(raw.get("properties") or {}),
            links=list(raw.get("links") or []),
            problems=list(raw.get("problems") or []),
            raw=raw,
        )


@dataclass
class ProjectGroup:
    """A Data Group of a project: one work unit made of several tiles."""

    id: str
    project_id: str
    name: str
    tiles: list[dict[str, Any]]
    settings: dict[str, Any]
    layer_revision: str | None
    readiness: dict[str, Any] | None
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)

    @classmethod
    def _from_raw(
        cls, client: UnitlabClient, project_id: str, raw: dict[str, Any]
    ) -> ProjectGroup:
        return cls(
            id=str(raw.get("id")),
            project_id=project_id,
            name=str(raw.get("name", "")),
            tiles=list(raw.get("tiles") or []),
            settings=dict(raw.get("settings") or {}),
            layer_revision=raw.get("layer_revision"),
            readiness=raw.get("readiness"),
            raw=raw,
            _client=client,
        )

    @property
    def _layer_endpoint(self) -> str:
        return f"/api/sdk/projects/{self.project_id}/groups/{self.id}/layer/"

    def tile(self, tile_id: str) -> dict[str, Any] | None:
        return next(
            (tile for tile in self.tiles if tile.get("tile_id") == tile_id), None
        )

    def layer(self) -> GroupLayer:
        return GroupLayer._from_raw(self._client._api.get(self._layer_endpoint))

    def save_layer(
        self,
        *,
        properties: dict[str, Any] | None = None,
        links: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
        layer: GroupLayer | None = None,
    ) -> dict[str, Any]:
        """Replace the group layer with a new version.

        Pass the ``layer`` you read (its revision is checked) or
        ``expected_revision``. Leaving ``properties`` or ``links`` out keeps
        what ``layer`` holds.

        Raises:
            RevisionConflictError: The layer changed since it was read.
        """
        base = layer or GroupLayer(
            group_id=self.id,
            revision=expected_revision,
            version=0,
            properties={},
            links=[],
            problems=[],
            raw={},
        )
        result = self._client._api.request(
            "PUT",
            self._layer_endpoint,
            json={
                "expected_revision": base.revision
                if expected_revision is None
                else expected_revision,
                "properties": base.properties if properties is None else properties,
                "links": base.links if links is None else links,
            },
        )
        self.layer_revision = result.get("revision")
        return result


class ProjectGroupsNamespace:
    """``project.groups``: the project's Data Groups and their layers."""

    def __init__(self, client: UnitlabClient, project_id: str):
        self._client = client
        self._project_id = project_id

    def list(self) -> list[ProjectGroup]:
        rows = Namespace(self._client)._all_pages(
            f"/api/sdk/projects/{self._project_id}/groups/"
        )
        return [
            ProjectGroup._from_raw(self._client, self._project_id, row) for row in rows
        ]

    def get(self, group) -> ProjectGroup:
        raw = self._client._api.get(
            f"/api/sdk/projects/{self._project_id}/groups/{identifier(group)}/"
        )
        return ProjectGroup._from_raw(self._client, self._project_id, raw)

    def import_layer(
        self, document: dict[str, Any] | str, *, dry_run: bool = True
    ) -> dict[str, Any]:
        """Apply a UUEF ``groups/<id>.json`` document to the matching group.

        Args:
            document: The parsed document, or a path to it.
            dry_run: Only report what would change (the default).

        Returns:
            ``{group_id, group_name, properties, unknown_properties, links,
            dropped_members, dry_run, revision?}``.
        """
        if isinstance(document, str):
            with open(document, encoding="utf-8-sig") as handle:
                document = json.load(handle)
        return self._client._api.post(
            f"/api/sdk/projects/{self._project_id}/data-groups/layer-import/",
            json={"document": document, "dry_run": dry_run},
        )
