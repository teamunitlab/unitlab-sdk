from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ..types import _data_type_name
from ._base import identifier

if TYPE_CHECKING:
    from unitlab.client import UnitlabClient


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

    @classmethod
    def _from_queue(
        cls,
        client: UnitlabClient,
        project_id: str,
        raw: dict[str, Any],
    ) -> WorkflowTask:
        return cls(
            id=str(raw["item_id"]),
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
        return cls(
            id=str(task["uuid"]),
            project_id=str(task.get("project_id") or project_id),
            stage_id=str(current_stage.get("id", "")),
            stage_type=str(current_stage.get("type", "")),
            status=str(task.get("status", "")),
            task_status=str(queue.get("task_status", "")),
            priority=int(task.get("priority", 0)),
            raw=raw,
            _client=client,
            name=str(queue.get("name", "")),
            assigned_to_id=(
                str(task["assigned_to_id"]) if task.get("assigned_to_id") else None
            ),
            datasource_id=(
                str(task["datasource_id"]) if task.get("datasource_id") else None
            ),
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
