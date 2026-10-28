from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import _scene_uploader, _uploader
from .._waiter import wait_for_status
from ..exceptions import UnitlabError, ValidationError
from ..types import AssetUploadResult, ProcessingStatus, _data_type_name
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class AssetsNamespace(Namespace):
    def upload(
        self,
        source: str | Path,
        *,
        folder: str | None = None,
        folder_id: str | None = None,
        path: str | None = None,
        tags: list[str] | None = None,
        custom_metadata: dict[str, Any] | None = None,
        defer_timeseries_configuration: bool = False,
        generic_type: str | None = None,
        primary_column: str | None = None,
        split_sensor_folders: bool = False,
    ) -> AssetUploadResult:
        """Upload local files into workspace Assets.

        Args:
            source: File or directory to upload.
            folder: Folder name to create or reuse.
            folder_id: Existing destination folder ID.
            path: Logical path created below the destination folder.
            tags: Tags applied to uploaded Assets.
            custom_metadata: User-owned JSON metadata applied to every upload.
            defer_timeseries_configuration: Keep the legacy deferred chart flow
                when ``generic_type="timeseries"`` is explicitly selected.
            generic_type: Explicit upload family, such as ``tabular`` for CSV
                row mode. Omitted CSV Assets remain family-neutral until they
                are attached to a project. ``pointcloud`` uploads lidar
                scenes: ``source`` is then a scene file (``.zip``, ``.pcd``,
                ``.bin``, ``.ply``) or a directory holding one or more scenes,
                and every scene becomes ONE Asset. Without it scene files are
                skipped.
            primary_column: Preferred row-mode CSV text column.
            split_sensor_folders: Lidar scenes only; see
                ``unitlab.detect_scenes``.

        Returns:
            Successful Assets and per-file failures without discarding partial
            success.
        """
        if generic_type == _scene_uploader.SCENE_TYPE:
            # A scene has its own routes and no fallback to the plain upload.
            result, resolved_folder_id, folder_name = (
                _scene_uploader.upload_asset_scenes(
                    self._api,
                    source,
                    folder=folder,
                    folder_id=folder_id,
                    path=path,
                    tags=tags,
                    custom_metadata=custom_metadata,
                    split_sensor_folders=split_sensor_folders,
                    show_progress=sys.stderr.isatty(),
                )
            )
        else:
            if split_sensor_folders:
                raise ValueError(
                    'split_sensor_folders applies only to generic_type="pointcloud".'
                )
            result, resolved_folder_id, folder_name = _uploader.upload_assets(
                self._api,
                source,
                folder=folder,
                folder_id=folder_id,
                path=path,
                tags=tags,
                custom_metadata=custom_metadata,
                defer_timeseries_configuration=defer_timeseries_configuration,
                generic_type=generic_type,
                primary_column=primary_column,
                show_progress=sys.stderr.isatty(),
            )
        assets = [
            Asset._from_raw(self._client, response["asset"])
            for response in result.responses
            if response.get("asset")
        ]
        return AssetUploadResult(
            folder_id=resolved_folder_id,
            folder_name=folder_name,
            uploaded=result.uploaded,
            failed=result.failed,
            assets=assets,
            raw=result.responses,
        )

    def folders(self, *, parent=None) -> list[Folder]:
        params = {"parent_id": identifier(parent)} if parent is not None else None
        rows = self._all_pages("/api/sdk/data-assets/folders/", params=params)
        return [Folder._from_raw(self._client, row) for row in rows]

    def all_folders(self) -> list[Folder]:
        rows = self._all_pages(
            "/api/sdk/data-assets/folders/",
            params={"all": 1},
        )
        return [Folder._from_raw(self._client, row) for row in rows]

    def folder(self, folder_id: str) -> Folder:
        raw = self._api.get(f"/api/sdk/data-assets/folders/{folder_id}/")
        return Folder._from_raw(self._client, raw)

    def asset(self, asset_id: str) -> Asset:
        """An Asset handle by ID, for ``status()``, ``wait()`` and ``retry()``.

        Built from the Asset's status, the one route that answers for a single
        Asset; it carries the data type, which ``retry()`` needs to pick the
        route. Other fields (file name, tags) stay empty: list the folder for
        those.
        """
        raw = self._api.get(
            f"/api/sdk/data-assets/assets/{identifier(asset_id)}/status/"
        )
        return Asset._from_raw(
            self._client,
            {
                "pk": raw.get("asset_id") or identifier(asset_id),
                "generic_type": raw.get("generic_type"),
                "upload_status": raw.get("upload_status", ""),
            },
        )

    def create_folder(self, name: str, *, parent_id: str | None = None) -> Folder:
        payload: dict[str, Any] = {"name": name}
        if parent_id:
            payload["parent_id"] = identifier(parent_id)
        raw = self._api.post("/api/sdk/data-assets/folders/", json=payload)
        return Folder._from_raw(self._client, raw)

    def set_custom_metadata(
        self,
        asset,
        custom_metadata: dict[str, Any] | None,
    ) -> Asset:
        raw = self._api.request(
            "PATCH",
            f"/api/sdk/data-assets/assets/{identifier(asset)}/custom-metadata/",
            json={"custom_metadata": custom_metadata},
        )
        return Asset._from_raw(self._client, raw["asset"])

    def create_cloud_folder(
        self,
        name: str,
        cloud_storage,
        *,
        prefix: str = "",
    ) -> Folder:
        raw = self._api.post(
            "/api/sdk/data-assets/folders/",
            json={
                "name": name,
                "cloud_storage_id": identifier(cloud_storage),
                "prefix": prefix,
            },
        )
        return Folder._from_raw(self._client, raw)


@dataclass
class Folder:
    id: str
    name: str
    parent_id: str | None
    cloud_storage_id: str | None
    prefix: str
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    created: str = ""
    asset_count: int = 0

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Folder:
        return cls(
            id=str(raw["pk"]),
            name=str(raw.get("name", "")),
            parent_id=str(raw["parent_id"]) if raw.get("parent_id") else None,
            cloud_storage_id=(
                str(raw["cloud_storage_id"]) if raw.get("cloud_storage_id") else None
            ),
            prefix=str(raw.get("prefix", "")),
            raw=raw,
            _client=client,
            created=str(raw.get("created", "")),
            asset_count=int(raw.get("asset_count", 0)),
        )

    def children(self) -> list[Folder]:
        return self._client.assets.folders(parent=self)

    def list_items(self) -> list[Asset]:
        rows = self._client.assets._all_pages(
            f"/api/sdk/data-assets/folders/{self.id}/items/"
        )
        return [Asset._from_raw(self._client, row) for row in rows]

    def create_subfolder(self, name: str) -> Folder:
        return self._client.assets.create_folder(name, parent_id=self.id)

    def sync_cloud(self) -> dict[str, Any]:
        """Re-sync one bucket level of this cloud folder (the bucket is only read).

        Returns:
            The server's counts, passed through as sent: ``registered`` (new
            files), ``folders`` (new sub-folders), ``skipped``,
            ``skipped_in_trash`` (files and sub-folders in library Trash: they
            are not added again, restore them instead) and ``missing`` (this
            folder's files the bucket no longer lists; they stay in the library
            but are left out of dataset drafts, new versions and attach until a
            later sync lists them again). ``busy: True`` with zero counts means
            another sync of this folder is running.
        """
        return self._client._api.post(
            f"/api/sdk/data-assets/folders/{self.id}/sync-cloud/"
        )

    def suggest_grouping(self) -> dict[str, Any]:
        return self._client._api.get(
            f"/api/sdk/data-assets/folders/{self.id}/auto-grouping/suggest/"
        )

    def estimate_grouping(self, config: dict[str, Any]) -> dict[str, Any]:
        return self._client._api.post(
            f"/api/sdk/data-assets/folders/{self.id}/auto-grouping/estimate/",
            json=config,
        )

    def auto_group(self, config: dict[str, Any] | None = None) -> GroupingResult:
        """Create Data Groups from folder filenames.

        Args:
            config: Explicit grouping configuration. When omitted, the server's
                suggested configuration is used.

        Returns:
            Counts and the folder containing the created groups.

        Raises:
            ValidationError: If no confident suggestion exists, the configuration
                is invalid, or no valid groups match.
        """
        if config is None:
            suggestion = self.suggest_grouping()
            if not suggestion.get("suggested"):
                raise ValidationError(
                    "No confident grouping pattern was found. Pass a config or "
                    "build one with tiles_from_template()."
                )
            config = {
                key: value
                for key, value in suggestion.items()
                if key
                in {
                    "grouping_keys",
                    "group_name_template",
                    "tiles",
                    "minimum_matched_tiles",
                    "required_tiles",
                    "incomplete_group_handling",
                    "layout_type",
                    "layout",
                    "recursive",
                }
            }
        raw = self._client._api.post(
            f"/api/sdk/data-assets/folders/{self.id}/auto-groups/",
            json=config,
        )
        if not raw.get("valid", True):
            errors = raw.get("errors") or ["Invalid grouping configuration."]
            raise ValidationError("; ".join(str(error) for error in errors))
        if int(raw.get("estimated_valid_groups", 0)) == 0:
            reasons = [
                str(item.get("reason"))
                for item in raw.get("skipped", [])[:3]
                if isinstance(item, dict) and item.get("reason")
            ]
            suffix = f" Top reasons: {', '.join(reasons)}" if reasons else ""
            raise ValidationError(f"No valid Data Groups were found.{suffix}")
        return GroupingResult._from_raw(self._client, raw)


@dataclass
class Asset:
    """A library file.

    ``file_name`` is the stored name, the one releases use (for a file uploaded
    to a project it is a generated name such as ``a91f...3c.jpg``).
    ``uploaded_name`` is the name shown in the web app (``cat.jpg``); for a file
    uploaded to the library both are the same.
    """

    id: str
    file_name: str
    data_type: str
    folder_id: str | None
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    file_size: int | None = None
    tags: list[str] = field(default_factory=list)
    custom_metadata: dict[str, Any] | None = None
    created: str = ""
    upload_status: str = ""
    # Servers older than 2026-10-28 do not send it: it then equals file_name.
    uploaded_name: str = ""

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Asset:
        file_name = str(raw.get("file_name", ""))
        return cls(
            id=str(raw["pk"]),
            file_name=file_name,
            uploaded_name=str(raw.get("uploaded_name") or file_name),
            data_type=_data_type_name(raw.get("generic_type")),
            folder_id=str(raw["folder_id"]) if raw.get("folder_id") else None,
            raw=raw,
            _client=client,
            file_size=int(raw["file_size"]) if raw.get("file_size") else None,
            tags=[str(tag) for tag in raw.get("tags") or []],
            custom_metadata=(
                dict(raw["custom_metadata"])
                if isinstance(raw.get("custom_metadata"), dict)
                else None
            ),
            created=str(raw.get("created", "")),
            upload_status=str(raw.get("upload_status", "")),
        )

    def status(self) -> ProcessingStatus:
        raw = self._client._api.get(f"/api/sdk/data-assets/assets/{self.id}/status/")
        self.upload_status = str(raw.get("upload_status", self.upload_status))
        return ProcessingStatus._from_raw(raw)

    def wait(
        self,
        *,
        timeout: float = 25200,
        on_progress: Callable[[ProcessingStatus], None] | None = None,
        show_progress: bool = True,
    ) -> ProcessingStatus:
        status = wait_for_status(
            self._client._api,
            f"/api/sdk/data-assets/assets/{self.id}/status/",
            resource_name=f"Asset {self.id}",
            timeout=timeout,
            on_progress=on_progress,
            show_progress=show_progress,
        )
        self.upload_status = str(
            status.raw.get("upload_status", status.status or self.upload_status)
        )
        return status

    def retry(self) -> dict[str, Any]:
        # A lidar scene is processed by its own pipeline and has its own
        # retry route; the tiled one refuses it.
        route = (
            "pointcloud-retry"
            if self.data_type == _scene_uploader.SCENE_TYPE
            else "tiled-retry"
        )
        raw = self._client._api.post(f"/api/sdk/data-assets/assets/{self.id}/{route}/")
        self.upload_status = str(raw.get("status", "processing"))
        return raw

    def configure_timeseries(
        self,
        *,
        x_column: str,
        channels: list[str],
    ) -> dict[str, Any]:
        raw = self._client._api.post(
            f"/api/sdk/data-assets/assets/{self.id}/timeseries-configuration/",
            json={"x_column": x_column, "channels": channels},
        )
        self.upload_status = str(raw.get("upload_status", self.upload_status))
        return raw

    def update_custom_metadata(
        self,
        custom_metadata: dict[str, Any] | None,
    ) -> Asset:
        updated = self._client.assets.set_custom_metadata(self, custom_metadata)
        self.custom_metadata = updated.custom_metadata
        self.raw = updated.raw
        return self


@dataclass
class GroupingResult:
    created_count: int
    grouped_folder_id: str | None
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        raw: dict[str, Any],
    ) -> GroupingResult:
        return cls(
            created_count=int(raw.get("created_count", 0)),
            grouped_folder_id=(
                str(raw["grouped_folder_id"]) if raw.get("grouped_folder_id") else None
            ),
            raw=raw,
            _client=client,
        )

    def grouped_folder(self) -> Folder:
        if not self.grouped_folder_id:
            raise UnitlabError("No grouped folder was created.")
        return self._client.assets.folder(self.grouped_folder_id)
