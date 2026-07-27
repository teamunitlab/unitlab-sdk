from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..types import _data_type_name
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class DatasetsNamespace(Namespace):
    def list(self) -> list[Dataset]:
        rows = self._all_pages("/api/sdk/datasets/")
        return [Dataset._from_raw(self._client, row) for row in rows]

    def get(self, dataset_id: str) -> Dataset:
        raw = self._api.get(f"/api/sdk/datasets/{dataset_id}/")
        return Dataset._from_raw(self._client, raw)

    def create(
        self,
        name: str,
        *,
        description: str = "",
        folder_ids: Iterable[str] | None = None,
        asset_ids: Iterable[str] | None = None,
    ) -> Dataset:
        payload = {
            "name": name,
            "description": description,
            "folder_ids": [identifier(value) for value in folder_ids or []],
            "asset_ids": [identifier(value) for value in asset_ids or []],
        }
        raw = self._api.post("/api/sdk/datasets/", json=payload)
        return Dataset._from_raw(self._client, raw)

    def _items(
        self,
        dataset_id: str,
        *,
        version: int | None = None,
    ) -> tuple[int | None, list[dict[str, Any]]]:
        params = {"version": version} if version is not None else None
        raw = self._api.get(f"/api/sdk/datasets/{dataset_id}/items/", params=params)
        rows = list(raw.get("results", []))
        version_number = raw.get("version_number")
        next_url = raw.get("next")
        while next_url:
            page = self._api.get(next_url)
            rows.extend(page.get("results", []))
            next_url = page.get("next")
        return version_number, rows


@dataclass
class Dataset:
    id: str
    name: str
    description: str
    current_version_number: int | None
    has_unpublished_changes: bool
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    created: str = ""

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Dataset:
        return cls(
            id=str(raw["pk"]),
            name=str(raw.get("name", "")),
            description=str(raw.get("description", "")),
            current_version_number=raw.get("current_version_number"),
            has_unpublished_changes=bool(raw.get("has_unpublished_changes", False)),
            raw=raw,
            _client=client,
            created=str(raw.get("created", "")),
        )

    def add_sources(
        self,
        *,
        folder_ids: Iterable[str] | None = None,
        asset_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        raw = self._client._api.post(
            f"/api/sdk/datasets/{self.id}/sources/",
            json={
                "folder_ids": [identifier(value) for value in folder_ids or []],
                "asset_ids": [identifier(value) for value in asset_ids or []],
            },
        )
        self.has_unpublished_changes = bool(
            raw.get("draft_changes", {}).get("has_changes", True)
        )
        return {
            "added": raw.get("added", 0),
            "unpublished_changes": dict(raw.get("draft_changes", {})),
        }

    def publish_version(
        self,
        version_title: str,
        *,
        description: str = "",
    ) -> DatasetVersion:
        """Freeze the current Dataset draft as an immutable version.

        Args:
            version_title: User-facing version label.
            description: Optional description of the published changes.

        Returns:
            The newly published version.

        Note:
            Publishing clears this handle's unpublished-change flag and advances
            its current version number.
        """
        raw = self._client._api.post(
            f"/api/sdk/datasets/{self.id}/versions/",
            json={
                "version_title": version_title,
                "description": description,
            },
        )
        version = DatasetVersion._from_raw(self._client, self.id, raw)
        self.current_version_number = version.version_number
        self.has_unpublished_changes = False
        return version

    def versions(self) -> list[DatasetVersion]:
        raw = self._client._api.get(f"/api/sdk/datasets/{self.id}/versions/")
        rows = list(raw.get("versions", []))
        next_url = raw.get("next")
        while next_url:
            page = self._client._api.get(next_url)
            rows.extend(page.get("versions", []))
            next_url = page.get("next")
        return [DatasetVersion._from_raw(self._client, self.id, row) for row in rows]

    def unpublished_changes(self) -> dict[str, Any]:
        raw = self._client._api.get(f"/api/sdk/datasets/{self.id}/versions/")
        return dict(raw.get("draft_changes", {}))

    def list_items(self, *, version: int | None = None) -> list[DatasetItem]:
        """List the working draft or one published snapshot.

        Args:
            version: Published version number. Omit it to list the current draft.

        Returns:
            Items captured by the selected Dataset state.
        """
        version_number, rows = self._client.datasets._items(
            self.id,
            version=version,
        )
        return [
            DatasetItem._from_raw(self._client, self.id, version_number, row)
            for row in rows
        ]


@dataclass
class DatasetVersion:
    dataset_id: str
    version_number: int
    version_title: str
    item_count: int
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    id: str = ""
    description: str = ""
    published_at: str = ""
    created: str = ""
    published_by: dict[str, Any] | None = None
    source_folders: list[Any] = field(default_factory=list)
    change_summary: dict[str, Any] = field(default_factory=dict)
    is_attached: bool = False

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        dataset_id: str,
        raw: dict[str, Any],
    ) -> DatasetVersion:
        return cls(
            dataset_id=dataset_id,
            version_number=int(raw["version_number"]),
            version_title=str(raw.get("version_title", "")),
            item_count=int(raw.get("item_count", 0)),
            raw=raw,
            _client=client,
            id=str(raw.get("pk", "")),
            description=str(raw.get("description", "")),
            published_at=str(raw.get("published_at", "")),
            created=str(raw.get("created", "")),
            published_by=(
                dict(raw["published_by"]) if raw.get("published_by") else None
            ),
            source_folders=list(raw.get("source_folders") or []),
            change_summary=dict(raw.get("change_summary") or {}),
            is_attached=bool(raw.get("is_attached", False)),
        )

    def items(self) -> list[DatasetItem]:
        version_number, rows = self._client.datasets._items(
            self.dataset_id,
            version=self.version_number,
        )
        return [
            DatasetItem._from_raw(self._client, self.dataset_id, version_number, row)
            for row in rows
        ]


@dataclass
class DatasetItem:
    id: str
    dataset_id: str
    version_number: int | None
    file_name: str
    data_type: str
    folder_path: str
    split: str
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    file_size: int | None = None
    tags: list[str] = field(default_factory=list)
    current_name: str | None = None

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        dataset_id: str,
        version_number: int | None,
        raw: dict[str, Any],
    ) -> DatasetItem:
        return cls(
            id=str(raw["pk"]),
            dataset_id=dataset_id,
            version_number=version_number,
            file_name=str(raw.get("file_name", "")),
            data_type=_data_type_name(raw.get("generic_type")),
            folder_path=str(raw.get("folder_path", "")),
            split=str(raw.get("split", "")),
            raw=raw,
            _client=client,
            file_size=(
                int(raw["file_size"]) if raw.get("file_size") is not None else None
            ),
            tags=[str(tag) for tag in raw.get("tags") or []],
            current_name=(
                str(raw["current_name"]) if raw.get("current_name") else None
            ),
        )
