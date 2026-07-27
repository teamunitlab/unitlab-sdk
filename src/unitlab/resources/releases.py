from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import _downloader
from ..types import _data_type_name
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


class ReleasesNamespace(Namespace):
    def list(self) -> list[Release]:
        rows = self._api.get("/api/sdk/releases/")
        return [Release._from_raw(self._client, row) for row in rows]

    def get(self, release_id: str) -> Release:
        raw = self._api.get(f"/api/sdk/releases/{release_id}/")
        return Release._from_raw(self._client, raw)

    def create(
        self,
        project,
        *,
        export_type: str = "UUEF",
        split_ratios: dict[str, int] | None = None,
        include_download_tokens: bool = False,
        upload_sessions=None,
        data_types=None,
        bundle_formats: dict[str, str] | None = None,
        license_id: str | None = None,
    ) -> Release:
        """Create an annotation Release from a Project snapshot.

        Args:
            project: Project handle or ID.
            export_type: Primary annotation export format.
            split_ratios: Percentage assigned to each output split.
            include_download_tokens: Include temporary download tokens.
            upload_sessions: Optional Batch Queue handles or IDs to include.
            data_types: Optional public data types to include. ``multimodal``
                includes every available concrete type.
            bundle_formats: Per-concrete-data-type formats for multimodal bundles.
            license_id: Optional Dataset license ID.

        Returns:
            The created Release.
        """
        payload: dict[str, Any] = {
            "export_type": export_type,
            "split_ratios": split_ratios or {"train": 100},
            "include_download_tokens": include_download_tokens,
        }
        if upload_sessions is not None:
            payload["upload_sessions"] = [
                identifier(value) for value in upload_sessions
            ]
        if data_types is not None:
            normalized_types = [str(value).lower() for value in data_types]
            if "multimodal" not in normalized_types:
                payload["generic_types"] = [
                    "img" if value == "image" else value for value in normalized_types
                ]
        if bundle_formats is not None:
            if any(str(value).lower() == "multimodal" for value in bundle_formats):
                raise ValueError(
                    "bundle_formats must use concrete data types such as image, "
                    "medical, or text."
                )
            payload["bundle_formats"] = {
                (
                    "img"
                    if str(data_type).lower() == "image"
                    else str(data_type).lower()
                ): export_format
                for data_type, export_format in bundle_formats.items()
            }
        if license_id is not None:
            payload["license"] = identifier(license_id)
        raw = self._api.post(
            f"/api/sdk/projects/{identifier(project)}/releases/",
            json=payload,
        )
        return Release._from_raw(self._client, raw)


@dataclass
class Release:
    id: str
    name: str
    version: str
    data_item_count: int
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    data_type: str = ""
    download_formats: list[str] = field(default_factory=list)
    is_public: bool = False

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Release:
        formats = raw.get("download_formats") or []
        if isinstance(formats, str):
            formats = [value.strip() for value in formats.split(",") if value.strip()]
        return cls(
            id=str(raw["pk"]),
            name=str(raw.get("name", "")),
            version=str(raw.get("version", "")),
            data_item_count=int(raw.get("number_of_data") or 0),
            raw=raw,
            _client=client,
            data_type=_data_type_name(raw.get("generic_type")),
            download_formats=[str(value) for value in formats],
            is_public=bool(raw.get("is_public", False)),
        )

    def download(self, split: str | None = None) -> str:
        """Download annotations for one split or the combined Release.

        Args:
            split: Optional split name such as ``train`` or ``test``.

        Returns:
            Absolute path to the downloaded archive.
        """
        return _downloader.download_annotation(self._client._api, self.id, split)

    def download_files(self, dest: str | Path | None = None) -> str:
        """Download the source files represented by this Release.

        Args:
            dest: Destination directory; defaults to the Release ID.

        Returns:
            Path to the populated directory.
        """
        return _downloader.download_files(self._client._api, self.id, dest)
