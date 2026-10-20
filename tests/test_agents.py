import base64
import hashlib
import hmac
import http.client
import importlib.util
import json
from dataclasses import fields
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event, Thread

import httpx
import pytest

from unitlab import (
    AgentTaskRef,
    AgentWebhook,
    ConflictError,
    NetworkError,
    TaskAnnotation,
    UnitlabClient,
    verify_agent_webhook,
)
from unitlab.resources.workflow import WorkflowTask

NOW = 1_800_000_000
SECRET = "example-signing-secret-for-tests-only"
ORIGIN = "https://api.example.test"
TASK_PATH = "/api/sdk/workflow-tasks/task-1/"


def sign(body, *, secret=SECRET, timestamp=NOW):
    key = (
        base64.b64decode(secret[6:]) if secret.startswith("whsec_") else secret.encode()
    )
    digest = hmac.new(key, f"event-1.{timestamp}.".encode() + body, hashlib.sha256)
    return {
        "webhook-id": "event-1",
        "webhook-timestamp": str(timestamp),
        "webhook-signature": "v1," + base64.b64encode(digest.digest()).decode(),
    }


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr("unitlab.agents.time.time", lambda: NOW)


@pytest.fixture
def event():
    return {
        "specversion": "1.0",
        "id": "event-1",
        "source": "/workflows/workflow-1/stages/stage-1",
        "type": "ai.unitlab.agent.task.ready.v1",
        "data": {
            "project_id": "project-1",
            "workflow_id": "workflow-1",
            "stage_id": "stage-1",
            "task": {
                "task_id": "task-1",
                "run_id": "run-1",
                "datasource_ids": ["source-1", "source-2"],
            },
        },
    }


def parse(event):
    body = json.dumps(event).encode()
    return AgentWebhook.verify(body, sign(body), SECRET)


# --- Signature verification ---


def test_parses_ids_only_event(event):
    webhook = parse(event)
    assert webhook == AgentWebhook(
        id="event-1",
        type="ai.unitlab.agent.task.ready.v1",
        project_id="project-1",
        workflow_id="workflow-1",
        stage_id="stage-1",
        task=AgentTaskRef("task-1", "run-1", ("source-1", "source-2")),
    )
    assert not webhook.is_test
    # Refs are plain IDs: no token, URL, or client to call with.
    assert [f.name for f in fields(AgentTaskRef)] == [
        "task_id",
        "run_id",
        "datasource_ids",
    ]


def test_unsigned_event_parses_without_a_secret(event):
    # A stage saved without a signing secret sends unsigned events.
    assert AgentWebhook.parse(json.dumps(event).encode()) == parse(event)


@pytest.mark.parametrize("offset", [-300, 0, 300])
def test_signature_accepts_both_clock_boundaries(offset):
    body = b'{"example": "raw bytes"}'
    verify_agent_webhook(body, sign(body, timestamp=NOW + offset), SECRET)


@pytest.mark.parametrize("offset", [-301, 301])
def test_stale_and_future_signature_rejected(offset):
    with pytest.raises(ValueError, match="timestamp"):
        verify_agent_webhook(b"{}", sign(b"{}", timestamp=NOW + offset), SECRET)


def test_signature_uses_original_body_and_rejects_tampering():
    body = b'{ "hello": "world" }'
    with pytest.raises(ValueError, match="signature"):
        verify_agent_webhook(b'{"hello":"world"}', sign(body), SECRET)
    with pytest.raises(ValueError, match="signature"):
        verify_agent_webhook(body, sign(body), "wrong-secret")


def test_tampered_event_rejected_before_parsing(event):
    body = json.dumps(event).encode()
    headers = sign(body)
    event["data"]["task"]["task_id"] = "task-2"
    with pytest.raises(ValueError, match="signature"):
        AgentWebhook.verify(json.dumps(event).encode(), headers, SECRET)


def test_signature_accepts_rotation_and_case_insensitive_headers():
    body = b"{}"
    headers = {key.title(): value for key, value in sign(body).items()}
    headers["Webhook-Signature"] = (
        "v2,ignore v1,invalid " + headers["Webhook-Signature"]
    )
    verify_agent_webhook(body, headers, SECRET)


def test_signature_accepts_whsec_base64_secret(event):
    secret = "whsec_" + base64.b64encode(b"test-key").decode()
    verify_agent_webhook(b"{}", sign(b"{}", secret=secret), secret)
    body = json.dumps(event).encode()
    assert AgentWebhook.verify(body, sign(body, secret=secret), secret).task
    with pytest.raises(ValueError, match="signature"):
        # The whsec_ key is the decoded bytes, never the literal string.
        verify_agent_webhook(b"{}", sign(b"{}", secret=secret[6:]), secret)


@pytest.mark.parametrize("secret", ["", "whsec_", "whsec_not-base64"])
def test_invalid_secret_rejected(secret):
    with pytest.raises(ValueError):
        verify_agent_webhook(b"{}", sign(b"{}"), secret)


@pytest.mark.parametrize(
    "name", ["webhook-id", "webhook-timestamp", "webhook-signature"]
)
def test_missing_signature_header_rejected(name):
    headers = sign(b"{}")
    del headers[name]
    with pytest.raises(ValueError):
        verify_agent_webhook(b"{}", headers, SECRET)


@pytest.mark.parametrize("timestamp", ["nan", "\u0661", "1800000000,1800000000", "-1"])
def test_invalid_timestamp_rejected(timestamp):
    headers = sign(b"{}")
    headers["webhook-timestamp"] = timestamp
    with pytest.raises(ValueError):
        verify_agent_webhook(b"{}", headers, SECRET)


def test_duplicate_headers_and_nonbyte_body_rejected():
    headers = sign(b"{}")
    headers["Webhook-Id"] = "different-id"
    with pytest.raises(ValueError, match="Duplicate"):
        verify_agent_webhook(b"{}", headers, SECRET)
    with pytest.raises(ValueError, match="bytes"):
        verify_agent_webhook("{}", sign(b"{}"), SECRET)


def test_only_a_repeated_signing_header_is_refused():
    # http.server's headers keep every copy; proxies repeat Via and the like.
    headers = http.client.HTTPMessage()
    for name, value in sign(b"{}").items():
        headers[name] = value
    headers["Via"] = "1.1 proxy-a"
    headers["via"] = "1.1 proxy-b"
    verify_agent_webhook(b"{}", headers, SECRET)
    headers["Webhook-Timestamp"] = str(NOW)
    with pytest.raises(ValueError, match="Duplicate"):
        verify_agent_webhook(b"{}", headers, SECRET)


# --- Strict parsing of the IDs-only event ---


def test_non_json_body_rejected():
    with pytest.raises(ValueError):
        AgentWebhook.verify(b"not json", sign(b"not json"), SECRET)


@pytest.mark.parametrize(
    "field,value",
    [
        ("specversion", "0.3"),
        ("type", "ai.unitlab.agent.task.ready.v2"),
        # The retired list-shape type is no longer an Agent event.
        ("type", "ai.unitlab.agent.tasks.ready.v1"),
        ("id", ""),
        ("source", None),
        ("data", []),
    ],
)
def test_invalid_envelope_rejected(event, field, value):
    event[field] = value
    with pytest.raises(ValueError):
        parse(event)


@pytest.mark.parametrize(
    "field,value",
    [
        ("project_id", None),
        ("project_id", 1),
        ("workflow_id", ""),
        ("stage_id", ["stage-1"]),
        # Exactly one task object: never null, a list or a bare ID.
        ("task", None),
        ("task", []),
        ("task", [{"task_id": "task-1", "run_id": "run-1", "datasource_ids": ["d"]}]),
        ("task", "task-1"),
    ],
)
def test_invalid_data_rejected(event, field, value):
    event["data"][field] = value
    with pytest.raises(ValueError):
        parse(event)


@pytest.mark.parametrize("field", ["project_id", "workflow_id", "stage_id", "task"])
def test_missing_data_field_rejected(event, field):
    del event["data"][field]
    with pytest.raises(ValueError):
        parse(event)


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", "../other"),
        ("task_id", 7),
        ("run_id", ""),
        ("run_id", None),
        ("datasource_ids", []),
        ("datasource_ids", "source-1"),
        ("datasource_ids", [1]),
        ("datasource_ids", [""]),
    ],
)
def test_invalid_task_rejected(event, field, value):
    event["data"]["task"][field] = value
    with pytest.raises(ValueError):
        parse(event)


@pytest.mark.parametrize("field", ["task_id", "run_id", "datasource_ids"])
def test_missing_task_field_rejected(event, field):
    del event["data"]["task"][field]
    with pytest.raises(ValueError):
        parse(event)


def connection_test_event(project_id=None):
    return {
        "specversion": "1.0",
        "id": "event-1",
        "source": "/workflows/unsaved",
        "type": "ai.unitlab.agent.test.v1",
        "data": {
            "test": True,
            "project_id": project_id,
            "workflow_id": None,
            "stage_id": None,
            "task": None,
        },
    }


@pytest.mark.parametrize("project_id", [None, "project-1"])
def test_test_event_parses_with_null_ids(project_id):
    webhook = parse(connection_test_event(project_id))
    assert webhook.is_test
    assert webhook.type == "ai.unitlab.agent.test.v1"
    assert (webhook.project_id, webhook.workflow_id, webhook.stage_id) == (
        project_id,
        None,
        None,
    )
    assert webhook.task is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("task", {"task_id": "t", "run_id": "r", "datasource_ids": ["d"]}),
        ("task", []),
        ("project_id", ""),
        ("stage_id", 5),
    ],
)
def test_invalid_test_event_rejected(field, value):
    event = connection_test_event()
    event["data"][field] = value
    with pytest.raises(ValueError):
        parse(event)


def test_test_event_without_task_key_rejected():
    event = connection_test_event()
    del event["data"]["task"]
    with pytest.raises(ValueError, match=r"data\.task null"):
        parse(event)


def test_retired_tasks_list_shape_rejected(event):
    # Refused by name, alone or beside a valid task, on both event kinds.
    task = event["data"].pop("task")
    event["data"]["tasks"] = [task]
    with pytest.raises(ValueError, match=r"data\.tasks"):
        parse(event)
    event["data"]["task"] = task
    with pytest.raises(ValueError, match=r"data\.tasks"):
        parse(event)
    test_event = connection_test_event()
    test_event["data"]["tasks"] = []
    with pytest.raises(ValueError, match=r"data\.tasks"):
        parse(test_event)


@pytest.mark.parametrize("field", ["project_id", "workflow_id", "stage_id"])
def test_task_ready_event_with_null_id_rejected(event, field):
    event["data"][field] = None
    with pytest.raises(ValueError):
        parse(event)


def test_duplicate_datasource_rejected(event):
    event["data"]["task"]["datasource_ids"] = ["source-1", "source-1"]
    with pytest.raises(ValueError, match="Duplicate datasource_id"):
        parse(event)


# --- WorkflowTask calls (workspace API key) ---


def task_detail(stage="agent"):
    return {"task": {"uuid": "task-1", "current_stage": {"id": stage, "type": stage}}}


@pytest.fixture
def api():
    """A client whose transport records requests and answers from ``routes``.

    A route is ``(status, payload)`` or a callable ``request -> (status,
    payload)`` (pages by cursor, successive PUT answers).
    """
    seen = []
    routes = {}
    client = UnitlabClient(api_key="test-only", api_url=ORIGIN)
    client._api.client.close()

    def handler(request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        assert request.headers["Authorization"] == "Api-Key test-only"
        answer = routes[(request.method, request.url.path)]
        status, payload = answer(request) if callable(answer) else answer
        return httpx.Response(status, json=payload)

    client._api.client = httpx.Client(
        base_url=ORIGIN,
        headers={"Authorization": "Api-Key test-only"},
        transport=httpx.MockTransport(handler),
    )
    routes[("GET", TASK_PATH)] = (200, task_detail())
    try:
        yield client, routes, seen
    finally:
        client.close()


def test_get_workflow_task_by_id(api):
    client, _, seen = api
    task = client.get_workflow_task("task-1")
    assert (task.id, task.stage_type) == ("task-1", "agent")
    assert seen == [("GET", TASK_PATH, None)]


ANNOTATIONS = TASK_PATH + "annotations/"
UPLOADS = ANNOTATIONS + "uploads/"
PAGES = ANNOTATIONS + "pages/"
SIGNED = "https://media.example.test/signed"
LIDAR_SAVE = {"mode": "track_delta", "keys": ["cuboids3d"], "read_only_keys": []}
CONFLICT = (409, {"detail": "The annotations changed.", "code": "revision_conflict"})
DOC = {
    "version": "1.0",
    "media": {"id": "source-1"},
    "classes": [{"value": 1, "name": "car"}],
    "labels": [{"id": "a", "class_value": 1}],
}
SAVED = {
    "task_id": "task-1",
    "datasource_id": "source-1",
    "revision": "h:2",
    "history_id": "h2",
    "created": 0,
    "updated": 1,
    "deleted": 0,
}


def uuef_row(datasource_id, revision="h:1", document=DOC, **extra):
    return {
        "datasource_id": datasource_id,
        "generic_type": "img",
        "revision": revision,
        "source_url": None,
        "format": "uuef",
        "document": document,
        **extra,
    }


def lidar_row(result, revision="h:1", save=LIDAR_SAVE, **extra):
    return {
        "datasource_id": "scene",
        "generic_type": "pointcloud",
        "revision": revision,
        "source_url": None,
        "format": "native",
        "result": result,
        "pages": None,
        "save": save,
        **extra,
    }


def lidar_tracks(**tracks):
    return {"tracks": {"cuboids3d": tracks}, "item_properties": {}}


def read(client, routes, rows, **kwargs):
    routes[("GET", ANNOTATIONS)] = (
        200,
        {
            "task_id": "task-1",
            "stage_id": "agent",
            "stage_type": "agent",
            "items": rows,
        },
    )
    task = WorkflowTask._from_detail(client, task_detail())
    return task, task.get_annotations(**kwargs)


def replies(*answers):
    """Successive answers for one route, in order (a split lidar save's PUTs)."""
    queue = list(answers)
    return lambda request: queue.pop(0)


@pytest.fixture
def storage(monkeypatch):
    """Signed storage links (large documents): answers by method and URL.

    Records ``(method, url, content type, body)``; no API key may go there.
    """
    seen = []
    links = {}

    def handler(request):
        assert "Authorization" not in request.headers
        url = str(request.url)
        seen.append(
            (request.method, url, request.headers.get("Content-Type"), request.content)
        )
        return httpx.Response(**links[(request.method, url)])

    transport = httpx.MockTransport(handler)

    def fake_request(method, url, **kwargs):
        with httpx.Client(transport=transport) as client:
            return client.request(method, url, **kwargs)

    monkeypatch.setattr("unitlab.resources.workflow.httpx.request", fake_request)
    return links, seen


# --- UUEF read and save ---


def test_get_annotations_reads_uuef_inline_and_by_link(api, storage):
    client, routes, seen = api
    links, fetched = storage
    url = "https://storage.example.test/doc.json?X-Amz-Signature=secret"
    large = {**DOC, "labels": [{"id": f"l{n}", "class_value": 1} for n in range(3)]}
    links[("GET", url)] = {"status_code": 200, "json": large}
    by_link = uuef_row("source-2", "h:7", generic_type="geospatial")
    del by_link["document"]
    by_link.update(document_url=url, document_bytes=70 * 1024 * 1024)
    _, items = read(client, routes, [uuef_row("source-1", source_url=SIGNED), by_link])
    assert items == [
        TaskAnnotation("source-1", "img", "h:1", SIGNED, "uuef", DOC),
        TaskAnnotation("source-2", "geospatial", "h:7", None, "uuef", large),
    ]
    assert [path for _method, path, _body in seen] == [ANNOTATIONS]
    assert [(method, link) for method, link, *_ in fetched] == [("GET", url)]
    assert "example.test" not in repr(items)


def test_only_keyframes_defaults_to_true_and_can_be_turned_off(api):
    client, routes, _ = api
    asked = []

    def answer(request):
        asked.append(request.url.params.get("only_keyframes"))
        return 200, {"items": []}

    routes[("GET", ANNOTATIONS)] = answer
    task = WorkflowTask._from_detail(client, task_detail())
    assert task.get_annotations() == []
    assert task.get_annotations(only_keyframes=False) == []
    assert asked == ["true", "false"]


def test_a_failed_document_link_names_the_status_never_the_link(api, storage):
    client, routes, _ = api
    links, _ = storage
    url = "https://storage.example.test/doc.json?X-Amz-Signature=secret"
    links[("GET", url)] = {"status_code": 403}
    row = uuef_row("source-1", document_url=url)
    del row["document"]
    with pytest.raises(NetworkError) as exc:
        read(client, routes, [row])
    assert "403" in str(exc.value)
    assert "secret" not in str(exc.value)


def test_save_annotations_overwrites_the_item_whole_every_time(api):
    client, routes, seen = api
    task, [item] = read(client, routes, [uuef_row("source-1")])
    routes[("PUT", ANNOTATIONS)] = (200, SAVED)
    seen.clear()
    new = {**DOC, "labels": []}
    assert task.save_annotations(item, new) == "h:2"
    put = (
        "PUT",
        ANNOTATIONS,
        {"datasource_id": "source-1", "format": "uuef", "document": new},
    )
    assert seen == [put]
    assert (item.revision, item.document) == ("h:2", new)
    # No diff: the same document is sent again, with no revision to check.
    task.save_annotations(item, item.document)
    assert seen == [put, put]


@pytest.mark.parametrize(
    "format,document",
    [
        ("geojson", {"type": "FeatureCollection", "features": []}),
        ("model", {"bboxes": [], "polygons": [], "classes": []}),
    ],
)
def test_save_annotations_passes_another_format_through(api, format, document):
    client, routes, seen = api
    task, [item] = read(client, routes, [uuef_row("source-1")])
    routes[("PUT", ANNOTATIONS)] = (200, SAVED)
    seen.clear()
    assert task.save_annotations(item, document, format=format) == "h:2"
    assert seen == [
        (
            "PUT",
            ANNOTATIONS,
            {"datasource_id": "source-1", "format": format, "document": document},
        )
    ]
    # Only a new read shows the UUEF the server built from it.
    assert (item.revision, item.document) == ("h:2", None)


def upload_route(routes, url):
    routes[("POST", UPLOADS)] = (
        201,
        {"upload_id": "up-1", "upload_url": url, "expires_at": "2026-10-20T12:00:00Z"},
    )


def test_a_document_over_the_inline_limit_goes_through_an_upload(
    api, storage, monkeypatch
):
    client, routes, seen = api
    links, sent = storage
    task, [item] = read(client, routes, [uuef_row("source-1")])
    url = "https://storage.example.test/upload?X-Amz-Signature=secret"
    upload_route(routes, url)
    links[("PUT", url)] = {"status_code": 200}
    routes[("PUT", ANNOTATIONS)] = (200, SAVED)
    new = {**DOC, "labels": [{"id": "é", "class_value": 1}]}
    encoded = json.dumps(new, ensure_ascii=False, separators=(",", ":")).encode()
    monkeypatch.setattr(
        "unitlab.resources.workflow.INLINE_DOCUMENT_MAX_BYTES", len(encoded) - 1
    )
    seen.clear()
    assert task.save_annotations(item, new, format="geojson") == "h:2"
    fields = {"datasource_id": "source-1", "format": "geojson"}
    assert seen == [
        ("POST", UPLOADS, {**fields, "size": len(encoded)}),
        ("PUT", ANNOTATIONS, {**fields, "document_upload_id": "up-1"}),
    ]
    assert sent == [("PUT", url, "application/json", encoded)]
    # Exactly at the limit: inline.
    monkeypatch.setattr(
        "unitlab.resources.workflow.INLINE_DOCUMENT_MAX_BYTES", len(encoded)
    )
    seen.clear()
    task.save_annotations(item, new)
    assert [(method, path) for method, path, _body in seen] == [("PUT", ANNOTATIONS)]
    assert seen[0][2]["document"] == new


def test_a_failed_upload_saves_nothing(api, storage, monkeypatch):
    client, routes, seen = api
    links, _ = storage
    monkeypatch.setattr("unitlab.resources.workflow.INLINE_DOCUMENT_MAX_BYTES", 1)
    task, [item] = read(client, routes, [uuef_row("source-1")])
    url = "https://storage.example.test/upload?X-Amz-Signature=secret"
    upload_route(routes, url)
    links[("PUT", url)] = {"status_code": 403}
    seen.clear()
    with pytest.raises(NetworkError, match="403"):
        task.save_annotations(item, {**DOC, "labels": []})
    assert [path for _method, path, _body in seen] == [UPLOADS]
    assert (item.revision, item.document) == ("h:1", DOC)


# --- Lidar: the native read and save, unchanged ---


def test_lidar_reads_natively_and_stitches_keyframe_pages(api):
    client, routes, seen = api
    asked = []

    def page(request):
        asked.append(dict(request.url.params))
        return 200, {"keyframes": {"cuboids3d": {"car": {"9": {"x": 9}}}}}

    routes[("GET", PAGES)] = page
    light = lidar_tracks(car={"ranges": [[0, 9]], "value": 1, "keyframes": {}})
    pages = {"path": PAGES, "params": {"datasource_id": "scene", "version": 3}}
    _, [item] = read(client, routes, [lidar_row(light, pages=pages)])
    assert (item.format, item.document) == ("native", None)
    assert item.result == lidar_tracks(
        car={"ranges": [[0, 9]], "value": 1, "keyframes": {"9": {"x": 9}}}
    )
    assert [path for _method, path, _body in seen] == [ANNOTATIONS, PAGES]
    assert asked == [{"datasource_id": "scene", "version": "3"}]


def test_lidar_save_sends_only_changed_tracks_with_the_revision(api):
    client, routes, seen = api
    car = {"ranges": [[0, 9]], "value": 1, "keyframes": {"0": {}}}
    task, [item] = read(client, routes, [lidar_row(lidar_tracks(car=car))])
    routes[("PUT", ANNOTATIONS)] = (200, {"revision": "h:2"})
    seen.clear()
    assert task.save_annotations(item, lidar_tracks(car=car)) == "h:1"
    assert seen == []
    result = lidar_tracks(car=car, van=car)
    assert task.save_annotations(item, result) == "h:2"
    assert seen == [
        (
            "PUT",
            ANNOTATIONS,
            {
                "datasource_id": "scene",
                "revision": "h:1",
                "result": {
                    "save_mode": "track_delta",
                    "upserted_tracks": {"cuboids3d": {"van": car}},
                },
            },
        )
    ]
    assert (item.revision, item.result) == ("h:2", result)
    with pytest.raises(ValueError, match="native result"):
        task.save_annotations(item, result, format="geojson")


def test_lidar_stale_revision_raises_conflict(api):
    client, routes, _ = api
    task, [item] = read(client, routes, [lidar_row(lidar_tracks(), "h:old")])
    routes[("PUT", ANNOTATIONS)] = CONFLICT
    car = {"ranges": [[0, 9]], "value": 1, "keyframes": {}}
    with pytest.raises(ConflictError) as exc:
        task.save_annotations(item, lidar_tracks(car=car))
    assert exc.value.code == "revision_conflict"
    assert (item.revision, item.result) == ("h:old", lidar_tracks())


def test_lidar_conflict_on_a_later_part_leaves_the_item_as_read(api):
    client, routes, seen = api
    limits = {"objects": 2, "bytes": 32 * 1024 * 1024}
    save = {**LIDAR_SAVE, "limits": limits}
    task, [item] = read(client, routes, [lidar_row(lidar_tracks(), save=save)])
    routes[("PUT", ANNOTATIONS)] = replies((200, {"revision": "h:2"}), CONFLICT)
    seen.clear()
    # Three new tracks at two per part: the second part conflicts.
    car = {"ranges": [[0, 9]], "value": 1, "keyframes": {}}
    with pytest.raises(ConflictError):
        task.save_annotations(item, lidar_tracks(a=car, b=car, c=car))
    assert [body["revision"] for _method, _path, body in seen] == ["h:1", "h:2"]
    assert (item.revision, item.result) == ("h:1", lidar_tracks())


def test_fail_agent_cuts_a_long_error_to_the_server_limit(api):
    client, routes, seen = api
    routes[("POST", TASK_PATH + "agent-result/")] = (
        200,
        {"run_id": "run-1", "status": "failed", "stage_id": "agent", **task_detail()},
    )
    task = WorkflowTask._from_detail(client, task_detail())
    # The server counts characters, not bytes.
    task.fail_agent("run-1", "é" * 4001)
    assert seen[-1][2]["error"] == "é" * 4000


def test_a_lidar_row_save_limits_override_the_read_limits(api):
    client, routes, seen = api
    limits = {"objects": 2000, "bytes": 32 * 1024 * 1024, "keyframes": 3}
    empty = lidar_tracks()
    routes[("GET", ANNOTATIONS)] = (
        200,
        {
            "save_limits": {"objects": 5000, "bytes": limits["bytes"]},
            "items": [lidar_row(empty, save={**LIDAR_SAVE, "limits": limits})],
        },
    )
    task = WorkflowTask._from_detail(client, task_detail())
    [item] = task.get_annotations()
    assert item._limits == limits
    routes[("PUT", ANNOTATIONS)] = replies(
        (200, {"revision": "h:2"}), (200, {"revision": "h:3"})
    )
    seen.clear()

    def track(count):
        return {
            "ranges": [[0, 9]],
            "value": 1,
            "keyframes": {str(n): {} for n in range(count)},
        }

    # The read's limits (5,000, no keyframe cap) would send one part.
    result = lidar_tracks(a=track(2), b=track(2))
    assert task.save_annotations(item, result) == "h:3"
    assert [
        (body["revision"], list(body["result"]["upserted_tracks"]["cuboids3d"]))
        for _method, _path, body in seen
    ] == [("h:1", ["a"]), ("h:2", ["b"])]
    seen.clear()
    longer = lidar_tracks(**result["tracks"]["cuboids3d"], c=track(4))
    with pytest.raises(ValueError, match="'c' in cuboids3d has 4 keyframes"):
        task.save_annotations(item, longer)
    assert seen == []
    assert item.revision == "h:3"


@pytest.mark.parametrize(
    "failed,body",
    [
        (False, {"run_id": "run-1", "status": "complete"}),
        (True, {"run_id": "run-1", "status": "failed", "error": "model failed"}),
    ],
)
def test_complete_and_fail_agent(api, failed, body):
    client, routes, seen = api
    stage = "agent" if failed else "review"
    routes[("POST", TASK_PATH + "agent-result/")] = (
        200,
        {
            "task_id": "task-1",
            "run_id": "run-1",
            "status": body["status"],
            "stage_id": stage,
            **task_detail(stage),
        },
    )
    task = WorkflowTask._from_detail(client, task_detail())
    if failed:
        assert task.fail_agent("run-1", "model failed") is task
    else:
        assert task.complete_agent("run-1") is task
    assert seen == [("POST", TASK_PATH + "agent-result/", body)]
    assert task.stage_type == stage


# --- Example receiver, end to end against a local fake API ---


def test_example_receiver_reads_saves_and_completes(event, monkeypatch):
    example_path = Path(__file__).parents[1] / "examples" / "agent_webhook.py"
    spec = importlib.util.spec_from_file_location("agent_example", example_path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    calls = []
    read_path = ANNOTATIONS + "?only_keyframes=true"
    annotations = {
        "task_id": "task-1",
        "stage_id": "stage-1",
        "stage_type": "agent",
        "items": [uuef_row("source-1")],
    }

    class FakeApi(BaseHTTPRequestHandler):
        def _answer(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            calls.append((self.command, self.path, body))
            payload = {
                ("GET", TASK_PATH): task_detail(),
                ("GET", read_path): annotations,
                ("PUT", TASK_PATH + "annotations/"): {"revision": "rev-2"},
                ("POST", TASK_PATH + "agent-result/"): task_detail("review"),
            }[(self.command, self.path)]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def do_GET(self):
            self._answer()

        def do_PUT(self):
            self._answer()

        def do_POST(self):
            self._answer()

        def log_message(self, *args):
            pass

    fake_api = HTTPServer(("127.0.0.1", 0), FakeApi)
    api_thread = Thread(target=fake_api.serve_forever, daemon=True)
    api_thread.start()
    monkeypatch.setenv("UNITLAB_AGENT_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("UNITLAB_API_KEY", "test-only")
    monkeypatch.setenv("UNITLAB_API_URL", f"http://127.0.0.1:{fake_api.server_port}")
    ready = Event()
    servers = []

    def create_server(address, handler):
        server = HTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        ready.set()
        return server

    monkeypatch.setattr(example, "ThreadingHTTPServer", create_server)
    worker = Thread(target=example.main, daemon=True)
    worker.start()
    assert ready.wait(2)
    server = servers[0]
    event["data"]["task"]["datasource_ids"] = ["source-1"]
    body = json.dumps(event).encode()
    webhook_url = f"http://127.0.0.1:{server.server_port}"
    try:
        response = httpx.post(webhook_url, content=body, headers=sign(body))
        assert response.status_code == 200
        assert calls == [
            ("GET", TASK_PATH, None),
            # transform() returns None (no change): nothing to save.
            ("GET", read_path, None),
            (
                "POST",
                TASK_PATH + "agent-result/",
                {"run_id": "run-1", "status": "complete"},
            ),
        ]
        response = httpx.post(webhook_url, content=body + b" ", headers=sign(body))
        assert response.status_code == 400
        test_body = json.dumps(connection_test_event()).encode()
        response = httpx.post(webhook_url, content=test_body, headers=sign(test_body))
        assert response.status_code == 204
        assert len(calls) == 3
        response = httpx.post(webhook_url, content=b"")
        assert response.status_code == 413
    finally:
        server.shutdown()
        worker.join(timeout=2)
        fake_api.shutdown()
        fake_api.server_close()
        api_thread.join(timeout=2)
