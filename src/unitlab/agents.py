"""Verify signed Agent webhooks; the work itself goes through ``WorkflowTask``.

The webhook carries IDs only, for ONE task. A receiver verifies it, then
opens the task with ``client.get_workflow_task(event.task.task_id)`` and uses
``get_annotations`` / ``save_annotations`` / ``complete_agent`` /
``fail_agent`` with its workspace API key. Nothing here makes HTTP calls.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

EVENT_TYPE = "ai.unitlab.agent.task.ready.v1"
# Sent by the stage's "Test connection" button: no work, answer 2xx.
TEST_EVENT_TYPE = "ai.unitlab.agent.test.v1"
_SIGNING_HEADERS = ("webhook-id", "webhook-timestamp", "webhook-signature")


def verify_agent_webhook(
    body: bytes,
    headers: Mapping[str, str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
) -> None:
    """Verify Standard Webhooks headers against the original, unparsed body.

    Accepts the configured plain signing secret or a ``whsec_`` base64 key.
    Retries retain their webhook ID; applications should deduplicate work by
    ``run_id`` after verification. Signature verification alone does not store IDs.
    """
    if not isinstance(body, bytes):
        raise ValueError("body must be the original request bytes")
    if not secret or tolerance_seconds < 0:
        raise ValueError("A signing secret and nonnegative tolerance are required")
    normalized = {key.lower(): value for key, value in headers.items()}
    # Only a repeated signing header is ambiguous (which id or timestamp was
    # signed?). Proxies and tunnels repeat others (Via, X-Forwarded-For), and
    # http.server's headers keep every copy, so those must not fail.
    signing = [key.lower() for key in headers]
    signing = [name for name in signing if name in _SIGNING_HEADERS]
    if len(signing) != len(set(signing)):
        raise ValueError("Duplicate webhook headers")
    webhook_id = normalized.get("webhook-id", "")
    timestamp = normalized.get("webhook-timestamp", "")
    signatures = normalized.get("webhook-signature", "")
    if not webhook_id or not timestamp.isascii() or not timestamp.isdecimal():
        raise ValueError("Missing or invalid webhook headers")
    if abs(time.time() - int(timestamp)) > tolerance_seconds:
        raise ValueError("Webhook timestamp is outside the allowed tolerance")
    key = secret.encode()
    if secret.startswith("whsec_"):
        try:
            key = base64.b64decode(secret[6:], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid whsec_ signing secret") from exc
        if not key:
            raise ValueError("Invalid whsec_ signing secret")
    signed = f"{webhook_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest())
    for signature in signatures.split():
        version, separator, value = signature.partition(",")
        if (
            version == "v1"
            and separator
            and hmac.compare_digest(value.encode(), expected)
        ):
            return
    raise ValueError("Invalid webhook signature")


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty string")
    return value


@dataclass(frozen=True)
class AgentTaskRef:
    """The event's one task: IDs only, no token, no HTTP calls."""

    task_id: str
    run_id: str
    datasource_ids: tuple[str, ...]


def _task_ref(value: Any) -> AgentTaskRef:
    """Validate ``data.task``; a missing, null or list value is not an object."""
    row = _object(value, "data.task")
    task_id = _text(row.get("task_id"), "task_id")
    # task_id becomes a URL path segment in WorkflowTask calls.
    if not all(char.isascii() and (char.isalnum() or char in "-_") for char in task_id):
        raise ValueError("Invalid task_id")
    datasource_ids = row.get("datasource_ids")
    if not isinstance(datasource_ids, list) or not datasource_ids:
        raise ValueError("datasource_ids must be a nonempty list")
    datasource_ids = tuple(_text(value, "datasource_id") for value in datasource_ids)
    if len(set(datasource_ids)) != len(datasource_ids):
        raise ValueError("Duplicate datasource_id in task")
    return AgentTaskRef(
        task_id=task_id,
        run_id=_text(row.get("run_id"), "run_id"),
        datasource_ids=datasource_ids,
    )


@dataclass(frozen=True)
class AgentWebhook:
    id: str
    type: str
    # None only on a test event: the workflow may not be saved yet.
    project_id: str | None
    workflow_id: str | None
    stage_id: str | None
    # One task per event (no batching); None only on a test event.
    task: AgentTaskRef | None

    @property
    def is_test(self) -> bool:
        """True for a "Test connection" event, which carries no task."""
        return self.type == TEST_EVENT_TYPE

    @classmethod
    def verify(
        cls,
        body: bytes,
        headers: Mapping[str, str],
        secret: str,
        *,
        tolerance_seconds: int = 300,
    ) -> AgentWebhook:
        """Authenticate and parse a CloudEvents 1.0 Agent event.

        A task-ready ``data`` is ``{"project_id", "workflow_id", "stage_id",
        "task": {"task_id", "run_id", "datasource_ids": [...]}}``; any
        missing or wrongly typed field raises ``ValueError``. A test event
        (``is_test``) may have null IDs and must have ``"task": null``.
        """
        verify_agent_webhook(body, headers, secret, tolerance_seconds=tolerance_seconds)
        return cls.parse(body)

    @classmethod
    def parse(cls, body: bytes) -> AgentWebhook:
        """Parse an Agent event WITHOUT checking a signature.

        For a stage saved without a signing secret, whose events are unsigned
        (as on the Webhook stage). With a secret, use ``verify``.
        """
        raw = _object(json.loads(body), "webhook")
        event_type = raw.get("type")
        if raw.get("specversion") != "1.0" or event_type not in (
            EVENT_TYPE,
            TEST_EVENT_TYPE,
        ):
            raise ValueError("Expected a CloudEvents 1.0 Agent event")
        event_id = _text(raw.get("id"), "id")
        _text(raw.get("source"), "source")
        data = _object(raw.get("data"), "data")
        # data.tasks (a list) is the retired shape: name it in the error
        # instead of reporting a missing data.task.
        if "tasks" in data:
            raise ValueError("Unsupported Agent event: data.tasks, expected data.task")
        if event_type == TEST_EVENT_TYPE:
            if "task" not in data or data["task"] is not None:
                raise ValueError("A test event must have data.task null")
            ids = {
                name: None if data.get(name) is None else _text(data[name], name)
                for name in ("project_id", "workflow_id", "stage_id")
            }
            return cls(id=event_id, type=event_type, task=None, **ids)
        return cls(
            id=event_id,
            type=event_type,
            project_id=_text(data.get("project_id"), "project_id"),
            workflow_id=_text(data.get("workflow_id"), "workflow_id"),
            stage_id=_text(data.get("stage_id"), "stage_id"),
            task=_task_ref(data.get("task")),
        )
