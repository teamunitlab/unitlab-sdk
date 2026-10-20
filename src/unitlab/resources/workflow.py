from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx

from .. import _task_annotations
from .._http import error_text
from ..exceptions import NetworkError
from ..types import _data_type_name
from ._base import identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient

# The server's inline limit for an Agent save (nbackend
# docs/workflow-agent-save-spec.md, "Save"): a serialized document above it
# goes to a signed upload link first and the save names the upload.
INLINE_DOCUMENT_MAX_BYTES = 64 * 1024 * 1024
# Signed storage links carry documents of hundreds of MiB; the API client's
# 60 s budget is too short for them (release downloads use the same value).
_STORAGE_TIMEOUT = 300.0
# A whole-item save of tens of thousands of objects runs about a minute on
# the server (62,640 polygons: ~70 s), past the client's default 60 s.
_SAVE_TIMEOUT = 300.0


def _storage_request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    """One request to a signed storage link: a large document's download or upload.

    Plain ``httpx``, never the API client: the link carries its own signature
    and the API key must not travel to another host. Errors name the HTTP
    status only, never the link, which stays a credential until it expires.
    """
    try:
        response = httpx.request(method, url, timeout=_STORAGE_TIMEOUT, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise NetworkError(f"Storage link answered HTTP {status}", exc) from exc
    except httpx.HTTPError as exc:
        raise NetworkError(error_text(exc), exc) from exc
    return response


class Workflow:
    def __init__(self, client: UnitlabClient, project_id: str):
        self._client = client
        self.project_id = project_id

    @property
    def stages(self) -> list[WorkflowStage]:
        raw = self._client._api.get(
            f"/api/sdk/projects/{self.project_id}/workflow/stages/"
        )
        return [WorkflowStage._from_raw(self, row) for row in raw.get("stages", [])]

    def get_stage(
        self,
        *,
        stage_id: str | None = None,
        name: str | None = None,
        stage_type: str | None = None,
    ) -> WorkflowStage:
        """Resolve exactly one Workflow stage.

        Args:
            stage_id: Stable stage client ID.
            name: Exact stage name.
            stage_type: Stage type such as ``annotate`` or ``review``.

        Returns:
            The only stage matching all supplied filters.

        Raises:
            ValueError: If zero or multiple stages match.
        """
        matches = [
            stage
            for stage in self.stages
            if (stage_id is None or stage.id == stage_id)
            and (name is None or stage.name == name)
            and (stage_type is None or stage.type == stage_type)
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one Workflow stage, found {len(matches)}.")
        return matches[0]

    def get_task(self, task_id: str) -> WorkflowTask:
        return WorkflowTask._fetch(self._client, task_id, project_id=self.project_id)

    def assign_tasks(self, task_ids, *, user_id: str) -> dict[str, Any]:
        return self._client._api.post(
            f"/api/sdk/projects/{self.project_id}/workflow/tasks/assign/",
            json={
                "task_ids": [identifier(task) for task in task_ids],
                "user_id": identifier(user_id),
            },
        )

    def move_tasks(
        self,
        task_ids,
        *,
        destination_stage,
        reason: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Move multiple tasks directly, bypassing normal Workflow edges.

        Args:
            task_ids: Task handles or IDs.
            destination_stage: Destination stage handle or ID.
            reason: Audit reason for the override.
            dry_run: Validate and report impact without moving tasks.

        Returns:
            Bulk-operation counts and validation details.
        """
        return self._client._api.post(
            f"/api/sdk/projects/{self.project_id}/workflow/tasks/move/",
            json={
                "task_ids": [identifier(task) for task in task_ids],
                "stage_id": identifier(destination_stage),
                "reason": reason,
                "dry_run": dry_run,
            },
        )


@dataclass
class WorkflowStage:
    id: str
    uuid: str
    name: str
    type: str
    task_count: int
    raw: dict[str, Any] = field(repr=False)
    _workflow: Workflow = field(repr=False, compare=False)
    sort_order: int = 0
    is_terminal: bool = False

    @classmethod
    def _from_raw(cls, workflow: Workflow, raw: dict[str, Any]) -> WorkflowStage:
        return cls(
            id=str(raw["id"]),
            uuid=str(raw.get("uuid", "")),
            name=str(raw.get("name", "")),
            type=str(raw.get("type", "")),
            task_count=int(raw.get("task_count", 0)),
            raw=raw,
            _workflow=workflow,
            sort_order=int(raw.get("sort_order", 0)),
            is_terminal=bool(raw.get("is_terminal", False)),
        )

    def get_tasks(self, *, include_unavailable: bool = False) -> list[WorkflowTask]:
        rows = self._workflow._client.projects._all_pages(
            f"/api/sdk/projects/{self._workflow.project_id}/workflow/stages/"
            f"{self.id}/tasks/",
            params={"include_unavailable": int(include_unavailable)},
        )
        return [
            WorkflowTask._from_queue(
                self._workflow._client,
                self._workflow.project_id,
                row,
            )
            for row in rows
        ]


@dataclass
class TaskAnnotation:
    """One item of a task, complete, as ``WorkflowTask.get_annotations`` returns it.

    ``document`` is the item's UUEF: the same per-item JSON a UUEF release
    exports (``uuef.schema.json``), whole whatever its size (a large one is
    downloaded from its signed link by the SDK). ``revision`` only says which
    version was read; UUEF saves overwrite the item and never check it.

    Lidar scenes (``generic_type == "pointcloud"``, ``format == "native"``)
    have no UUEF read yet: ``document`` is None and ``result`` holds the
    editor's track-first result, stitched from its keyframe pages. Pass the
    item back to ``save_annotations``.
    """

    datasource_id: str
    generic_type: str
    revision: str | None
    source_url: str | None = field(default=None, repr=False)
    format: str = "uuef"  # "uuef", or "native" for lidar
    document: dict[str, Any] | None = field(default=None, repr=False)
    result: dict[str, Any] | None = field(default=None, repr=False)
    # Lidar only: what the server needs to take changes back (mode, keys), its
    # effective part limits (_task_annotations.item_limits: objects, bytes,
    # keyframes), and hashes of what was read (_task_annotations.snapshot).
    _save: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    _limits: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    _base: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass
class WorkflowTask:
    """A mutable Workflow task handle.

    Successful mutation methods refresh this same instance with its complete
    post-operation state.
    """

    id: str
    project_id: str
    stage_id: str
    stage_type: str
    status: str
    task_status: str
    priority: int
    raw: dict[str, Any] = field(repr=False)
    _client: UnitlabClient = field(repr=False, compare=False)
    name: str = ""
    assigned_to_id: str | None = None
    datasource_id: str | None = None
    data_group_id: str | None = None
    data_type: str = ""
    available_actions: list[str] = field(default_factory=list)
    move_targets: list[dict[str, Any]] = field(default_factory=list)
    task_kind: str = "item_state"
    parent_item_id: str | None = None
    assignment_id: str | None = None
    consensus_summary: dict[str, Any] | None = None

    @classmethod
    def _from_queue(
        cls,
        client: UnitlabClient,
        project_id: str,
        raw: dict[str, Any],
    ) -> WorkflowTask:
        consensus_summary = (
            raw["consensus_summary"]
            if "consensus_summary" in raw
            else raw.get("consensus")
        )
        return cls(
            id=str(raw.get("task_id") or raw["item_id"]),
            project_id=project_id,
            stage_id=str(raw.get("stage_id", "")),
            stage_type=str(raw.get("stage_type", "")),
            status=str(raw.get("status", "")),
            task_status=str(raw.get("task_status", "")),
            priority=int(raw.get("priority", 0)),
            raw=raw,
            _client=client,
            name=str(raw.get("name", "")),
            assigned_to_id=(
                str(raw["assigned_to_id"]) if raw.get("assigned_to_id") else None
            ),
            datasource_id=(
                str(raw["datasource_id"]) if raw.get("datasource_id") else None
            ),
            data_group_id=(
                str(raw.get("project_data_group_id") or raw.get("data_group_id"))
                if raw.get("project_data_group_id") or raw.get("data_group_id")
                else None
            ),
            data_type=_data_type_name(raw.get("generic_type")),
            task_kind=str(raw.get("task_kind") or "item_state"),
            parent_item_id=(
                str(raw["parent_item_id"]) if raw.get("parent_item_id") else None
            ),
            assignment_id=(
                str(raw["assignment_id"]) if raw.get("assignment_id") else None
            ),
            consensus_summary=consensus_summary,
        )

    @classmethod
    def _from_detail(
        cls,
        client: UnitlabClient,
        raw: dict[str, Any],
        *,
        project_id: str = "",
    ) -> WorkflowTask:
        task = raw.get("task", raw)
        queue = raw.get("queue") or {}
        current_stage = task.get("current_stage") or {}
        # Consensus task details retain the parent resource; the queue identifies
        # the private branch. Explicit null also matters when an assignee is cleared.
        datasource_id = queue.get("datasource_id", task.get("datasource_id"))
        assigned_to_id = queue.get("assigned_to_id", task.get("assigned_to_id"))
        consensus_summary = raw.get("consensus_summary")
        if consensus_summary is None:
            consensus_summary = task.get("consensus_summary")
        return cls(
            id=str(task.get("task_id") or task["uuid"]),
            project_id=str(task.get("project_id") or project_id),
            stage_id=str(current_stage.get("id", "")),
            stage_type=str(current_stage.get("type", "")),
            status=str(task.get("status", "")),
            task_status=str(queue.get("task_status", "")),
            priority=int(task.get("priority", 0)),
            raw=raw,
            _client=client,
            name=str(queue.get("name", "")),
            assigned_to_id=str(assigned_to_id) if assigned_to_id else None,
            datasource_id=str(datasource_id) if datasource_id else None,
            data_group_id=(
                str(task.get("project_data_group_id") or task.get("data_group_id"))
                if task.get("project_data_group_id") or task.get("data_group_id")
                else None
            ),
            data_type=_data_type_name(queue.get("generic_type")),
            available_actions=[
                str(value) for value in raw.get("available_actions", [])
            ],
            move_targets=list(raw.get("move_targets", [])),
            task_kind=str(task.get("task_kind") or "item_state"),
            parent_item_id=(
                str(task["parent_item_id"]) if task.get("parent_item_id") else None
            ),
            assignment_id=(
                str(task["assignment_id"]) if task.get("assignment_id") else None
            ),
            consensus_summary=consensus_summary,
        )

    @classmethod
    def _fetch(
        cls,
        client: UnitlabClient,
        task_id: str,
        *,
        project_id: str = "",
    ) -> WorkflowTask:
        raw = client._api.get(f"/api/sdk/workflow-tasks/{task_id}/")
        return cls._from_detail(client, raw, project_id=project_id)

    def claim(self) -> WorkflowTask:
        return self._replace(
            self._client._api.post(f"/api/sdk/workflow-tasks/{self.id}/claim/")
        )

    def assign(self, user_id: str) -> WorkflowTask:
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/assign/",
                json={"user_id": identifier(user_id)},
            )
        )

    def release(self) -> WorkflowTask:
        return self._replace(
            self._client._api.post(f"/api/sdk/workflow-tasks/{self.id}/release/")
        )

    def set_priority(self, priority: int) -> WorkflowTask:
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/priority/",
                json={"priority": priority},
            )
        )

    def get_consensus_comparison(self) -> dict[str, Any]:
        return self._client._api.get(
            f"/api/sdk/workflow-tasks/{self.id}/consensus-comparison/"
        )

    def copy_consensus_component(
        self,
        *,
        source_assignment_id: str,
        component_kind: str,
        component_locator: dict[str, Any],
        operation: str = "add",
        panel_id: str | None = None,
        replacement_locator: dict[str, Any] | None = None,
    ) -> WorkflowTask:
        if operation not in {"add", "replace"}:
            raise ValueError("operation must be 'add' or 'replace'")

        payload: dict[str, Any] = {
            "source_assignment_id": source_assignment_id,
            "component_kind": component_kind,
            "component_locator": component_locator,
            "operation": operation,
            "idempotency_key": str(uuid4()),
        }
        if panel_id is not None:
            payload["panel_id"] = panel_id
        if replacement_locator is not None:
            payload["replacement_locator"] = replacement_locator
        if self.stage_id:
            payload["expected_stage_id"] = self.stage_id
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/consensus-selections/",
                json=payload,
            )
        )

    def _perform(
        self,
        action: str,
        *,
        reason: str = "",
        comment: str = "",
    ) -> WorkflowTask:
        payload = {
            "action": action,
            "rejection_reason": reason,
            "comment": comment,
            "idempotency_key": str(uuid4()),
        }
        if self.stage_id:
            payload["expected_stage_id"] = self.stage_id
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/actions/",
                json=payload,
            )
        )

    def submit(self) -> WorkflowTask:
        return self._perform("complete")

    def approve(self) -> WorkflowTask:
        return self._perform("approve")

    def reject(self, *, reason: str = "", comment: str = "") -> WorkflowTask:
        """Reject a Review task through its configured rejection edge.

        Args:
            reason: Structured or user-facing rejection reason.
            comment: Additional reviewer comment.

        Returns:
            This handle updated to its new Workflow state.
        """
        return self._perform("reject", reason=reason, comment=comment)

    def skip(self) -> WorkflowTask:
        return self._perform("skip")

    def complete_model_run(
        self,
        run_id: str,
        result: dict[str, Any] | list[dict[str, Any]],
        *,
        model_version: str = "",
    ) -> WorkflowTask:
        """Upload one or more final GeoJSON results for a Model-stage run."""
        result_key = "results" if isinstance(result, list) else "result"
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/model-result/",
                json={
                    "run_id": str(run_id),
                    "status": "complete",
                    result_key: result,
                    "model_version": model_version,
                },
            )
        )

    def fail_model_run(self, run_id: str, error: str) -> WorkflowTask:
        """Report a failed asynchronous Model-stage run without advancing it."""
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/model-result/",
                json={"run_id": str(run_id), "status": "failed", "error": error},
            )
        )

    def get_annotations(self, *, only_keyframes: bool = True) -> list[TaskAnnotation]:
        """Read every item of this task (one per Data Group panel) as UUEF.

        ``only_keyframes`` (default, as V7's flag): a track lists its stored
        keyframes only; ``False`` lists every frame it is visible on. Both
        save back safely, because a save keeps only frames marked
        ``keyframe: true``. A document over the server's inline limit comes as
        a signed ``document_url``, downloaded here without the API key, so
        every ``item.document`` is one whole dict.

        Lidar rows (``format == "native"``) keep the native read: their pages
        are fetched and stitched into ``item.result``, every page reading the
        version this read started from.
        """
        raw = self._client._api.get(
            f"/api/sdk/workflow-tasks/{self.id}/annotations/",
            params={"only_keyframes": "true" if only_keyframes else "false"},
        )
        limits = raw.get("save_limits")
        items = []
        for row in raw.get("items", []):
            item = TaskAnnotation(
                datasource_id=str(row["datasource_id"]),
                generic_type=str(row.get("generic_type") or ""),
                revision=None if row.get("revision") is None else str(row["revision"]),
                source_url=row.get("source_url"),
                format=str(row.get("format") or "uuef"),
            )
            if item.format == "native":
                # KeyError on a lidar row without its save contract: guessing
                # one would silently drop every track change at save time.
                item._save = row["save"]
                item.result = _task_annotations.stitch(
                    row.get("result") or {},
                    row.get("pages"),
                    lambda path, params: self._client._api.get(path, params=params),
                )
                item._limits = _task_annotations.item_limits(item._save, limits)
                item._base = _task_annotations.snapshot(item.result, item._save)
            elif row.get("document_url"):
                item.document = _storage_request("GET", row["document_url"]).json()
            else:
                item.document = row.get("document")
            items.append(item)
        return items

    def save_annotations(
        self,
        item: TaskAnnotation,
        document: dict[str, Any],
        *,
        format: str = "uuef",
    ) -> str | None:
        """Overwrite one item with ``document``; return its new revision.

        The document replaces the item whole (nbackend
        docs/workflow-agent-save-spec.md): objects missing from it are
        deleted, no revision is sent and nothing is diffed, so a save made
        meanwhile is overwritten rather than raising ``ConflictError``.
        ``format``: ``"uuef"`` (the read's shape), ``"geojson"`` (a geospatial
        item's RFC 7946 FeatureCollection) or ``"model"`` (an image item's
        custom-model reply JSON); the server refuses (400) a format the
        item's type does not take, and saves nothing. A document over
        ``INLINE_DOCUMENT_MAX_BYTES`` is PUT to a signed upload link first and
        the save names the upload. Afterwards ``item.revision`` is the new
        revision and ``item.document`` the saved UUEF; after a ``geojson`` or
        ``model`` save it is None, as only a new read shows the UUEF the
        server built from it.

        Lidar (``item.format == "native"``) keeps the native save: pass the
        complete new ``result`` (see ``_save_native``).
        """
        if item.format == "native":
            if format != "uuef":
                raise ValueError("A lidar scene saves its native result; omit format")
            return self._save_native(item, document)
        path = f"/api/sdk/workflow-tasks/{self.id}/annotations/"
        body: dict[str, Any] = {
            "datasource_id": str(item.datasource_id),
            "format": format,
        }
        # Measured as httpx 0.28 encodes a json= body (compact UTF-8); a NaN
        # raises ValueError here, as httpx would, before anything is sent.
        encoded = json.dumps(
            document, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
        if len(encoded) > INLINE_DOCUMENT_MAX_BYTES:
            upload = self._client._api.post(
                path + "uploads/", json={**body, "size": len(encoded)}
            )
            _storage_request(
                "PUT",
                upload["upload_url"],
                content=encoded,
                headers={"Content-Type": "application/json"},
            )
            body["document_upload_id"] = upload["upload_id"]
        else:
            body["document"] = document
        del encoded  # the PUT below encodes the body again: one copy at a time
        raw = self._client._api.request("PUT", path, json=body, timeout=_SAVE_TIMEOUT)
        item.revision = str(raw["revision"])
        item.document = document if format == "uuef" else None
        return item.revision

    def _save_native(self, item: TaskAnnotation, result: dict[str, Any]) -> str | None:
        """Lidar's save: only what changed since ``item`` was read is sent.

        A large change goes in parts within the server's limits, each an
        ordinary save carrying the previous part's revision, so it leaves
        several versions. A stale revision raises ``ConflictError`` (``code
        == "revision_conflict"``); parts sent before it stay saved: read again
        and save again, and only what is still missing goes. On success
        ``item`` holds the new revision and result. Unchanged: nothing is
        sent. A track larger than one save takes raises ``ValueError`` before
        anything is sent.
        """
        parts = _task_annotations.plan_parts(
            item._base, result, item._save, item._limits
        )
        revision = item.revision
        for part in parts:
            raw = self._client._api.request(
                "PUT",
                f"/api/sdk/workflow-tasks/{self.id}/annotations/",
                json={
                    "datasource_id": str(item.datasource_id),
                    "revision": revision,
                    "result": part,
                },
            )
            revision = str(raw["revision"])
        item.revision = revision
        item.result = result
        item._base = _task_annotations.snapshot(result, item._save)
        return revision

    def complete_agent(self, run_id: str) -> WorkflowTask:
        """Finish an Agent run; the task advances through the stage's edge.

        Save the item annotations with ``save_annotations`` first.
        """
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/agent-result/",
                json={"run_id": str(run_id), "status": "complete"},
            )
        )

    def fail_agent(self, run_id: str, error: str) -> WorkflowTask:
        """Report a failed Agent run; the task stays in the Agent stage.

        ``error`` is cut to its first 4,000 characters, the most the server
        takes: a longer one is refused (400), which would leave the run open
        until its 7-day timeout instead of failed now.
        """
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/agent-result/",
                json={"run_id": str(run_id), "status": "failed", "error": error[:4000]},
            )
        )

    def move(self, destination_stage, *, reason: str = "") -> WorkflowTask:
        """Move this task directly, bypassing normal Workflow edges.

        Args:
            destination_stage: Destination stage handle or ID.
            reason: Audit reason for the manager override.

        Returns:
            This handle updated to its new Workflow state.
        """
        payload = {
            "stage_id": identifier(destination_stage),
            "reason": reason,
            "idempotency_key": str(uuid4()),
        }
        if self.stage_id:
            payload["expected_stage_id"] = self.stage_id
        return self._replace(
            self._client._api.post(
                f"/api/sdk/workflow-tasks/{self.id}/move/",
                json=payload,
            )
        )

    def get_timeline(self) -> dict[str, Any]:
        return self._client._api.get(f"/api/sdk/workflow-tasks/{self.id}/timeline/")

    def _replace(self, raw: dict[str, Any]) -> WorkflowTask:
        vars(self).update(
            vars(self._from_detail(self._client, raw, project_id=self.project_id))
        )
        return self
