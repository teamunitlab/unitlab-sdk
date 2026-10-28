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
        """Create a Dataset whose working draft holds the given sources.

        Args:
            name: Dataset name.
            description: Optional description.
            folder_ids: Folders the draft follows: files added to them or their
                sub-folders later join the draft, files moved out or put in
                Trash leave it, and each file keeps its sub-folder path.
            asset_ids: Files added one by one; they stay until removed.

        Returns:
            The new Dataset. It has no published version until
            ``publish_version()`` is called.
        """
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
        # The server's maximum page. Each page of a draft resolves the whole
        # draft, so the default 50 read a 2,000-item draft 40 times; `next`
        # links keep this limit for the pages after the first.
        params: dict[str, Any] = {"limit": 300}
        if version is not None:
            params["version"] = version
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
        """Add folders and files to the working draft.

        Args:
            folder_ids: Folders the draft follows from now on, like those given
                to ``create()``. A dataset made before datasets followed their
                folders gets the files the folders hold now instead.
            asset_ids: Files added one by one. Adding a file, or its folder,
                again brings back a file removed from the draft with
                ``remove_assets()`` or in the web app.

        Returns:
            ``added`` (files new to the draft) and ``unpublished_changes``.
        """
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

    def remove_assets(self, asset_ids: Iterable[str]) -> dict[str, Any]:
        """Remove files from the working draft ("Remove from dataset" in the web app).

        Only the draft changes: the files stay in the library, their folders,
        projects and published versions. A file a followed folder supplies is
        recorded as removed, so the folder does not bring it back; add it again
        with ``add_sources(asset_ids=...)``.

        Args:
            asset_ids: Library file ids (``DatasetItem.id`` of a draft item).

        Returns:
            ``removed`` (files taken out), ``skipped`` (ids not in the draft)
            and ``unpublished_changes``.

        Raises:
            ValidationError: No valid id was given, or the dataset is a
                project's own dataset or a read-only snapshot.
        """
        raw = self._client._api.post(
            f"/api/sdk/datasets/{self.id}/remove-assets/",
            json={"asset_ids": [identifier(value) for value in asset_ids]},
        )
        self.has_unpublished_changes = bool(
            raw.get("draft_changes", {}).get("has_changes", True)
        )
        return {
            "removed": raw.get("removed", 0),
            "skipped": raw.get("skipped", 0),
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
            its current version number. Files in library Trash, and cloud files
            the last sync of their folder did not find in the bucket, are left
            out of the version.
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
            Items captured by the selected Dataset state. The draft leaves out
            files in library Trash and cloud files missing from the bucket, as
            publishing will; a version keeps them (see ``DatasetItem.in_trash``).
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
    """A file in a Dataset draft or published version.

    ``file_name`` is the stored name, the one releases of an attached version
    use (for a file uploaded to a project it is a generated name such as
    ``a91f...3c.jpg``). ``uploaded_name`` is the name shown in the web app
    (``cat.jpg``); for a file uploaded to the library both are the same.
    ``current_name`` is the source file's stored name now, sent only when it
    differs from the one the version captured.
    """

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
    # A published version keeps a file moved to library Trash and marks it
    # here; attaching the version leaves it out. Always False for a draft,
    # which hides such files.
    in_trash: bool = False
    # Servers older than 2026-10-28 do not send it: it then equals file_name.
    uploaded_name: str = ""

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        dataset_id: str,
        version_number: int | None,
        raw: dict[str, Any],
    ) -> DatasetItem:
        file_name = str(raw.get("file_name", ""))
        return cls(
            id=str(raw["pk"]),
            dataset_id=dataset_id,
            version_number=version_number,
            file_name=file_name,
            uploaded_name=str(raw.get("uploaded_name") or file_name),
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
            in_trash=bool(raw.get("in_trash", False)),
        )
