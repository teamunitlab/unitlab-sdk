from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import NetworkError


def _data_type_name(value: Any) -> str:
    name = str(value or "").lower()
    return {"img": "image"}.get(name, name)


@dataclass(frozen=True)
class ProcessingStatus:
    status: str
    total: int
    completed: int
    processing: int
    failed: int
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    # Set for a lidar scene only: why its processing failed, and how many
    # frames it has once processing ended. Declared after ``raw`` so existing
    # positional construction keeps its meaning.
    error: str | None = None
    frame_count: int | None = None

    @classmethod
    def _from_raw(cls, raw: dict[str, Any]) -> ProcessingStatus:
        return cls(
            status=str(raw.get("status", "processing")),
            total=int(raw.get("total", 0)),
            completed=int(raw.get("completed", 0)),
            processing=int(raw.get("processing", 0)),
            failed=int(raw.get("failed", 0)),
            raw=raw,
            error=str(raw["error"]) if raw.get("error") else None,
            frame_count=(
                int(raw["frame_count"]) if raw.get("frame_count") is not None else None
            ),
        )


@dataclass(frozen=True)
class UploadFailure:
    path: Path
    error: str


@dataclass
class UploadResult:
    total: int
    uploaded: int
    failed: list[UploadFailure] = field(default_factory=list)
    responses: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def raise_on_failure(self) -> None:
        if not self.failed:
            return
        first = "; ".join(
            f"{failure.path.name}: {failure.error}" for failure in self.failed[:5]
        )
        if len(self.failed) > 5:
            first += f"; and {len(self.failed) - 5} more"
        raise NetworkError(
            f"Failed to upload {len(self.failed)} of {self.total} files. {first}"
        )


@dataclass
class AssetUploadResult:
    folder_id: str
    folder_name: str
    uploaded: int
    failed: list[UploadFailure] = field(default_factory=list)
    assets: list[Any] = field(default_factory=list)
    raw: list[dict[str, Any]] = field(default_factory=list, repr=False)


@dataclass(frozen=True)
class AttachPreview:
    requires_fps: bool
    resolved_asset_count: int
    already_attached_count: int
    will_publish_version: bool = False
    dataset_version_count: int = 0
    video_count: int = 0
    processing_video_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    # Selected datasets without a published version, each ``{"dataset_id",
    # "name"}``. ``attach()`` leaves them out unless ``publish_unpublished``.
    unpublished_datasets: list[dict[str, Any]] = field(default_factory=list)
    # Files the attach will leave out, by reason: ``{"in_trash": n,
    # "missing_in_bucket": n}`` (library Trash; cloud files the last Re-sync
    # did not list). Empty from a server older than 2026-10-27.
    skipped_files: dict[str, int] = field(default_factory=dict)

    @classmethod
    def _from_raw(cls, raw: dict[str, Any]) -> AttachPreview:
        return cls(
            requires_fps=bool(raw.get("requires_fps", False)),
            resolved_asset_count=int(raw.get("resolved_unique_asset_count", 0)),
            already_attached_count=int(raw.get("already_attached_count", 0)),
            will_publish_version=bool(raw.get("will_publish_project_version", False)),
            dataset_version_count=int(raw.get("dataset_version_count", 0)),
            video_count=int(raw.get("video_count", 0)),
            processing_video_count=int(raw.get("processing_video_count", 0)),
            raw=raw,
            unpublished_datasets=list(raw.get("unpublished_datasets") or []),
            skipped_files=dict(raw.get("skipped_files") or {}),
        )


@dataclass(frozen=True)
class AttachResult:
    created_count: int
    unassigned_count: int
    data_item_ids: list[str]
    batch_queue_id: str | None
    project_dataset_version_number: int | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    already_attached_count: int = 0
    resolved_asset_count: int = 0
    attachment_ids: list[str] = field(default_factory=list)
    data_group_ids: list[str] = field(default_factory=list)
    # Datasets left out, each ``{"dataset_id", "name", "reason", "detail"}``
    # with reason ``unpublished`` or ``publish_failed``.
    skipped_datasets: list[dict[str, Any]] = field(default_factory=list)
    # Datasets published as v1 by ``publish_unpublished``, each
    # ``{"dataset_id", "name", "version_number"}``.
    published_datasets: list[dict[str, Any]] = field(default_factory=list)
    # Files left out, by reason, as ``AttachPreview.skipped_files``. Counts
    # files of the attached versions only: selected folders and files are
    # published first, which already leaves such files out, so the preview's
    # counts can be higher.
    skipped_files: dict[str, int] = field(default_factory=dict)

    @classmethod
    def _from_raw(cls, raw: dict[str, Any]) -> AttachResult:
        return cls(
            created_count=int(raw.get("created_count", 0)),
            unassigned_count=int(raw.get("unassigned_count", 0)),
            data_item_ids=[
                str(value) for value in raw.get("created_datasource_ids", [])
            ],
            batch_queue_id=(
                str(raw["upload_session_id"]) if raw.get("upload_session_id") else None
            ),
            project_dataset_version_number=raw.get("project_dataset_version_number"),
            raw=raw,
            already_attached_count=int(raw.get("already_attached_count", 0)),
            resolved_asset_count=int(raw.get("resolved_unique_asset_count", 0)),
            attachment_ids=[str(value) for value in raw.get("link_ids", [])],
            data_group_ids=[
                str(value) for value in raw.get("created_project_group_ids", [])
            ],
            skipped_datasets=list(raw.get("skipped_datasets") or []),
            published_datasets=list(raw.get("published_datasets") or []),
            skipped_files=dict(raw.get("skipped_files") or {}),
        )


@dataclass(frozen=True)
class CloudEntry:
    name: str
    type: str
    size: int | None
    is_extension_allowed: bool
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def _from_raw(cls, raw: dict[str, Any]) -> CloudEntry:
        raw_type = str(raw.get("type", ""))
        return cls(
            name=str(raw.get("name", "")),
            type={"REG": "file", "DIR": "folder"}.get(raw_type, raw_type.lower()),
            size=raw.get("size"),
            is_extension_allowed=bool(raw.get("is_extension_allowed", True)),
            raw=raw,
        )
