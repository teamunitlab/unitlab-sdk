from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import _uploader
from .._waiter import wait_for_processing
from ..types import (
    AttachPreview,
    AttachResult,
    ProcessingStatus,
    UploadFailure,
    _data_type_name,
)
from ._base import Namespace, identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient

    from .workflow import Workflow


class ProjectsNamespace(Namespace):
    def list(self) -> list[Project]:
        rows = self._api.get("/api/sdk/projects/")
        return [Project._from_raw(self._client, row) for row in rows]

    def get(self, project_id: str) -> Project:
        row = self._api.get(f"/api/sdk/projects/{project_id}/")
        return Project._from_raw(self._client, row)

    def create(self, name: str, *, ontology_hash: str | None = None) -> Project:
        payload = {"name": name}
        if ontology_hash is not None:
            payload["ontology_hash"] = identifier(ontology_hash)
        row = self._api.post("/api/sdk/projects/", json=payload)
        return Project._from_raw(self._client, row)


@dataclass
class DataUnit:
    id: str
    project_id: str
    kind: str
    name: str
    data_type: str
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    status: str = "new"
    priority: int = 0
    created_at: str = ""
    datasource_id: str | None = None
    group_id: str | None = None
    batch_queue_id: str | None = None
    folder_path: str = ""
    file_size: int | None = None
    thumbnail_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)
    data_types: list[str] = field(default_factory=list)
    workflow_task_id: str | None = None
    stage_id: str | None = None
    assigned_to_id: str | None = None

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        project_id: str,
        raw: dict[str, Any],
    ) -> DataUnit:
        return cls(
            id=str(raw["id"]),
            project_id=project_id,
            kind=str(raw.get("kind", "datasource")),
            name=str(raw.get("name", "")),
            data_type=_data_type_name(raw.get("data_type")),
            raw=raw,
            _client=client,
            status=str(raw.get("status", "new")),
            priority=int(raw.get("priority") or 0),
            created_at=str(raw.get("created_at", "")),
            datasource_id=(
                str(raw["datasource_id"]) if raw.get("datasource_id") else None
            ),
            group_id=str(raw["group_id"]) if raw.get("group_id") else None,
            batch_queue_id=(
                str(raw["batch_queue_id"]) if raw.get("batch_queue_id") else None
            ),
            folder_path=str(raw.get("folder_path", "")),
            file_size=raw.get("file_size"),
            thumbnail_url=(
                str(raw["thumbnail_url"]) if raw.get("thumbnail_url") else None
            ),
            metadata=dict(raw.get("metadata") or {}),
            items=list(raw.get("items") or []),
            data_types=[
                _data_type_name(value) for value in raw.get("data_types") or []
            ],
            workflow_task_id=(
                str(raw["workflow_task_id"]) if raw.get("workflow_task_id") else None
            ),
            stage_id=str(raw["stage_id"]) if raw.get("stage_id") else None,
            assigned_to_id=(
                str(raw["assigned_to_id"]) if raw.get("assigned_to_id") else None
            ),
        )


@dataclass
class AttachedSource:
    id: str
    project_id: str
    name: str
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    folder_id: str | None = None
    dataset_id: str | None = None
    dataset_version: int | None = None

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        project_id: str,
        raw: dict[str, Any],
    ) -> AttachedSource:
        return cls(
            id=str(raw["source_link_id"]),
            project_id=project_id,
            name=str(raw.get("name", "")),
            raw=raw,
            _client=client,
            folder_id=(
                str(raw["source_folder_id"]) if raw.get("source_folder_id") else None
            ),
            dataset_id=(
                str(raw["source_dataset_id"]) if raw.get("source_dataset_id") else None
            ),
            dataset_version=raw.get("source_dataset_version_number"),
        )

    def detach_preview(self) -> dict[str, Any]:
        return self._client._api.get(
            f"/api/sdk/projects/{self.project_id}/attached-sources/"
            f"{self.id}/detach-preview/"
        )

    def detach(self) -> dict[str, Any]:
        return self._client._api.post(
            f"/api/sdk/projects/{self.project_id}/attached-sources/{self.id}/detach/"
        )


@dataclass
class Project:
    id: str
    name: str
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    created: str = ""
    creator: str | None = None
    description: str = ""
    data_item_count: int = 0
    ontology_hash: str | None = None

    @property
    def workflow(self) -> Workflow:
        from .workflow import Workflow

        return Workflow(self._client, self.id)

    @classmethod
    def _from_raw(cls, client: UnitlabClient, raw: dict[str, Any]) -> Project:
        return cls(
            id=str(raw["pk"]),
            name=str(raw.get("name", "")),
            raw=raw,
            _client=client,
            created=str(raw.get("created", "")),
            creator=str(raw["creator"]) if raw.get("creator") else None,
            description=str(raw.get("description", "")),
            data_item_count=int(raw.get("number_of_data", 0)),
            ontology_hash=(
                str(raw["ontology_hash"]) if raw.get("ontology_hash") else None
            ),
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        payload = {
            key: value
            for key, value in {"name": name, "description": description}.items()
            if value is not None
        }
        if not payload:
            return self
        raw = self._client._api.request(
            "PATCH",
            f"/api/sdk/projects/{self.id}/",
            json=payload,
        )
        vars(self).update(vars(Project._from_raw(self._client, raw)))
        return self

    def delete(self) -> None:
        self._client._api.request("DELETE", f"/api/sdk/projects/{self.id}/")

    def data_units(
        self,
        *,
        search: str | None = None,
        data_type: str | None = None,
        status: str | None = None,
        batch_queue: str | None = None,
        kind: str | None = None,
    ) -> list[DataUnit]:
        """List loose files and Data Groups as Project work units.

        Args:
            search: Case-insensitive name search.
            data_type: Concrete data type such as ``image`` or ``video``.
            status: Current Workflow status.
            batch_queue: Restrict results to one Batch Queue ID.
            kind: Restrict results to ``datasource`` or ``group``.

        Returns:
            Matching work units without duplicating group members as loose files.
        """
        params = {
            key: value
            for key, value in {
                "search": search,
                "data_type": data_type,
                "status": status,
                "batch_queue": identifier(batch_queue) if batch_queue else None,
                "kind": kind,
            }.items()
            if value is not None
        }
        rows = self._client.projects._all_pages(
            f"/api/sdk/projects/{self.id}/data-units/",
            params=params,
        )
        return [DataUnit._from_raw(self._client, self.id, row) for row in rows]

    def upload(
        self,
        source: str | Path,
        *,
        fps: float = 1.0,
        batch_size: int = 100,
    ) -> UploadBatch:
        """Upload local files into this Project.

        Args:
            source: File or directory to upload.
            fps: Frame rate used for uploaded video.
            batch_size: Files scheduled per local upload batch.

        Returns:
            Local upload results and the server-side Batch Queue ID. Server
            processing may still be running.
        """
        result, session_id = _uploader.upload_project(
            self._client._api,
            self.id,
            source,
            fps=fps,
            batch_size=batch_size,
            show_progress=sys.stderr.isatty(),
        )
        batch = UploadBatch(
            project_id=self.id,
            batch_queue_id=session_id,
            total=result.total,
            uploaded=result.uploaded,
            failed=result.failed,
            data_item_ids=[
                str(response["datasource_id"])
                for response in result.responses
                if response.get("datasource_id")
            ],
            raw=result.responses,
            _client=self._client,
        )
        return batch

    def import_cloud(
        self,
        cloud_storage,
        paths: Iterable[str],
        *,
        fps: float | None = None,
    ) -> UploadBatch:
        """Import cloud files or folders into this Project.

        Args:
            cloud_storage: Cloud storage handle or ID.
            paths: Provider paths to import.
            fps: Frame rate required when imported data contains video.

        Returns:
            A Batch Queue handle for the server-side import.

        Raises:
            ValueError: If no paths are supplied.
        """
        path_list = [str(path) for path in paths]
        if not path_list:
            raise ValueError("Select at least one cloud path.")
        payload: dict[str, Any] = {"server_files": path_list}
        if fps is not None:
            payload["fps"] = fps
        storage_id = identifier(cloud_storage)
        raw = self._client._api.post(
            f"/api/sdk/projects/{self.id}/cloud-storages/{storage_id}/import/",
            json=payload,
        )
        batch = UploadBatch(
            project_id=self.id,
            batch_queue_id=str(raw["upload_session_id"]),
            total=int(raw.get("file_count", 0)),
            uploaded=int(raw.get("file_count", 0)),
            failed=[],
            data_item_ids=[],
            raw=[raw],
            _client=self._client,
        )
        return batch

    def attach_preview(
        self,
        *,
        folder_ids: Iterable[str] | None = None,
        dataset_ids: Iterable[str] | None = None,
        dataset_versions: Iterable[dict[str, Any]] | None = None,
        fps: float | None = None,
    ) -> AttachPreview:
        """Validate an attachment selection without modifying the Project.

        Args:
            folder_ids: Workspace folders to attach.
            dataset_ids: Datasets whose latest published versions are attached.
            dataset_versions: Exact ``dataset_id`` and ``version_number`` pairs.
            fps: Frame rate required when selected data contains video.

        Returns:
            Resolved counts and validation requirements.
        """
        payload = self._attach_payload(
            folder_ids=folder_ids,
            dataset_ids=dataset_ids,
            dataset_versions=dataset_versions,
            fps=fps,
        )
        raw = self._client._api.post(
            f"/api/sdk/projects/{self.id}/attach-data/preview/",
            json=payload,
        )
        return AttachPreview._from_raw(raw)

    def attach(
        self,
        *,
        folder_ids: Iterable[str] | None = None,
        dataset_ids: Iterable[str] | None = None,
        dataset_versions: Iterable[dict[str, Any]] | None = None,
        fps: float | None = None,
    ) -> AttachResult:
        """Attach published workspace data to this Project.

        Args:
            folder_ids: Workspace folders to attach.
            dataset_ids: Datasets whose latest published versions are attached.
            dataset_versions: Exact ``dataset_id`` and ``version_number`` pairs.
            fps: Frame rate required when selected data contains video.

        Returns:
            Created IDs, attachment counts, and an optional Batch Queue ID.
        """
        payload = self._attach_payload(
            folder_ids=folder_ids,
            dataset_ids=dataset_ids,
            dataset_versions=dataset_versions,
            fps=fps,
        )
        raw = self._client._api.post(
            f"/api/sdk/projects/{self.id}/attach-data/commit/",
            json=payload,
        )
        return AttachResult._from_raw(raw)

    def attached_sources(self) -> list[AttachedSource]:
        rows = self._client._api.get(f"/api/sdk/projects/{self.id}/attached-sources/")
        return [AttachedSource._from_raw(self._client, self.id, row) for row in rows]

    def detach_source(self, source, *, preview: bool = False) -> dict[str, Any]:
        """Preview or detach one attached source from this Project.

        Args:
            source: Attached source handle or ID.
            preview: Return impact counts without detaching.

        Returns:
            Preview counts or the completed detach result.

        Note:
            Detaching preserves the source data and other Projects.
        """
        source_id = identifier(source)
        suffix = "detach-preview/" if preview else "detach/"
        endpoint = f"/api/sdk/projects/{self.id}/attached-sources/{source_id}/{suffix}"
        if preview:
            return self._client._api.get(endpoint)
        return self._client._api.post(endpoint)

    def _attach_payload(
        self,
        *,
        folder_ids,
        dataset_ids,
        dataset_versions,
        fps,
    ) -> dict[str, Any]:
        payload = {
            "folder_ids": [identifier(value) for value in folder_ids or []],
            "dataset_ids": [identifier(value) for value in dataset_ids or []],
            "dataset_versions": list(dataset_versions or []),
        }
        if not any(payload.values()):
            raise ValueError("Select at least one folder or dataset.")
        if fps is not None:
            payload["fps"] = fps
        return payload

    def batch_queues(self) -> list[BatchQueue]:
        rows = self._client.projects._all_pages(
            f"/api/sdk/projects/{self.id}/upload-sessions/"
        )
        return [BatchQueue._from_raw(self._client, self.id, row) for row in rows]

    def batch_queue(self, batch_queue_id: str) -> BatchQueue:
        row = self._client._api.get(
            f"/api/sdk/projects/{self.id}/upload-sessions/{batch_queue_id}/"
        )
        return BatchQueue._from_raw(self._client, self.id, row)


@dataclass
class UploadBatch:
    project_id: str
    batch_queue_id: str | None
    total: int
    uploaded: int
    failed: list[UploadFailure]
    data_item_ids: list[str]
    raw: list[dict[str, Any]] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)

    def status(self) -> ProcessingStatus:
        if not self.batch_queue_id:
            raise ValueError("This upload has no Batch Queue id.")
        raw = self._client._api.get(
            f"/api/sdk/projects/{self.project_id}/upload-sessions/"
            f"{self.batch_queue_id}/status/"
        )
        return ProcessingStatus._from_raw(raw)

    def wait(
        self,
        *,
        timeout: float = 1800,
        on_progress: Callable[[ProcessingStatus], None] | None = None,
        show_progress: bool = True,
    ) -> ProcessingStatus:
        """Wait for this upload's server-side Batch Queue.

        Args:
            timeout: Maximum seconds to wait.
            on_progress: Callback invoked after each status poll.
            show_progress: Show terminal progress when stderr is interactive.

        Returns:
            The terminal processing status.

        Raises:
            ProcessingTimeoutError: If processing exceeds ``timeout``.
        """
        if not self.batch_queue_id:
            raise ValueError("This upload has no Batch Queue id.")
        return wait_for_processing(
            self._client._api,
            self.project_id,
            self.batch_queue_id,
            timeout=timeout,
            on_progress=on_progress,
            show_progress=show_progress,
        )


@dataclass
class BatchQueue:
    id: str
    project_id: str
    name: str
    created: str
    item_count: int
    data_type_counts: dict[str, int]
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    state: str | None = None
    completed: int | None = None
    processing: int | None = None
    failed: int | None = None

    @classmethod
    def _from_raw(
        cls,
        client: UnitlabClient,
        project_id: str,
        raw: dict[str, Any],
    ) -> BatchQueue:
        return cls(
            id=str(raw["pk"]),
            project_id=project_id,
            name=str(raw.get("name", "")),
            created=str(raw.get("created", "")),
            item_count=int(raw.get("item_count", 0)),
            data_type_counts={
                _data_type_name(key): int(value)
                for key, value in raw.get("data_type_counts", {}).items()
            },
            raw=raw,
            _client=client,
            state=str(raw["status"]) if raw.get("status") else None,
            completed=int(raw["completed"]) if "completed" in raw else None,
            processing=int(raw["processing"]) if "processing" in raw else None,
            failed=int(raw["failed"]) if "failed" in raw else None,
        )

    def refresh(self) -> BatchQueue:
        raw = self._client._api.get(
            f"/api/sdk/projects/{self.project_id}/upload-sessions/{self.id}/"
        )
        vars(self).update(
            vars(BatchQueue._from_raw(self._client, self.project_id, raw))
        )
        return self

    def status(self) -> ProcessingStatus:
        raw = self._client._api.get(
            f"/api/sdk/projects/{self.project_id}/upload-sessions/{self.id}/status/"
        )
        return ProcessingStatus._from_raw(raw)

    def data(self) -> list[dict[str, Any]]:
        """List normalized files associated with this Batch Queue.

        Returns:
            Dictionaries containing ``id``, ``file_name``, ``data_type``, and
            upload ``status``.
        """
        rows = self._client.projects._all_pages(
            f"/api/sdk/projects/{self.project_id}/upload-sessions/{self.id}/data/"
        )
        return [
            {
                "id": str(row.get("datasource_id", "")),
                "file_name": str(row.get("file_name", "")),
                "data_type": _data_type_name(row.get("generic_type")),
                "status": str(row.get("upload_status", "")),
            }
            for row in rows
        ]

    def wait(
        self,
        *,
        timeout: float = 1800,
        on_progress: Callable[[ProcessingStatus], None] | None = None,
        show_progress: bool = False,
    ) -> ProcessingStatus:
        """Wait until this Batch Queue reaches a terminal state.

        Args:
            timeout: Maximum seconds to wait.
            on_progress: Callback invoked after each status poll.
            show_progress: Show terminal progress when stderr is interactive.

        Returns:
            The terminal processing status.

        Raises:
            ProcessingTimeoutError: If processing exceeds ``timeout``.
        """
        return wait_for_processing(
            self._client._api,
            self.project_id,
            self.id,
            timeout=timeout,
            on_progress=on_progress,
            show_progress=show_progress,
        )
