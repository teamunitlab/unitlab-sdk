import json
import zipfile

import httpx
import pytest
from test_client import client_with_handler

from unitlab import Project, Release
from unitlab.exceptions import (
    AnnotationValidationError,
    RevisionConflictError,
    UnsupportedByServerError,
)

ITEM = "/api/sdk/projects/p1/items/d1/annotations/"


def _project(handler):
    client = client_with_handler(handler)
    return client, Project("p1", "Project", {"pk": "p1"}, client)


def test_get_annotations_follows_every_page():
    pages = {
        "0": {
            "datasource_id": "d1",
            "project_id": "p1",
            "data_type": "img",
            "revision": "h1:3",
            "item_properties": {"4": "rain"},
            "tags": [],
            "objects": [{"type": "bbox", "id": "a"}],
            "next_offset": 1,
        },
        "1": {"revision": "h1:3", "objects": [{"type": "bbox", "id": "b"}]},
    }

    def handler(request):
        assert request.url.path == ITEM
        return httpx.Response(200, json=pages[request.url.params.get("offset", "0")])

    _client, project = _project(handler)
    item = project.get_annotations("d1")
    assert [obj["id"] for obj in item.objects] == ["a", "b"]
    assert item.revision == "h1:3"
    assert item.item_properties == {"4": "rain"}


def test_keyframes_of_a_track_join_across_pages():
    pages = {
        "0": {
            "revision": "h1:1",
            "objects": [{"type": "bboxes", "id": "t1"}],
            "keyframes": {"bboxes": {"t1": {"0": "a", "1": "b"}}},
            "next_frame": 2,
        },
        "2": {
            "revision": "h1:1",
            "objects": [{"type": "bboxes", "id": "t1"}],
            "keyframes": {"bboxes": {"t1": {"2": "c"}, "t2": {"2": "d"}}},
        },
    }

    def handler(request):
        return httpx.Response(200, json=pages[request.url.params["frame_start"]])

    _client, project = _project(handler)
    item = project.get_annotations("d1", frame_start=0)
    assert item.keyframes == {
        "bboxes": {"t1": {"0": "a", "1": "b", "2": "c"}, "t2": {"2": "d"}}
    }
    assert [obj["id"] for obj in item.objects] == ["t1"]


def test_save_moves_the_revision_on():
    bodies = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"datasource_id": "d1", "revision": "h1:3", "objects": []}
            )
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"revision": "h2:4", "created": 1})

    _client, project = _project(handler)
    item = project.get_annotations("d1")
    item.save(upsert=[{"type": "bbox", "class": 1}])
    item.save(delete=["a"])
    assert bodies[0]["expected_revision"] == "h1:3"
    assert bodies[1]["expected_revision"] == "h2:4"
    assert "dry_run" not in bodies[0]


@pytest.mark.parametrize(
    ("status", "code", "error"),
    [
        (409, "revision_conflict", RevisionConflictError),
        (400, "annotation_invalid", AnnotationValidationError),
        (501, "unsupported", UnsupportedByServerError),
    ],
)
def test_save_errors_map_to_their_types(status, code, error):
    def handler(request):
        return httpx.Response(status, json={"detail": "no", "code": code})

    _client, project = _project(handler)
    with pytest.raises(error):
        project.save_annotations("d1", expected_revision="h1:1", delete=["a"])


def test_project_groups_layer_round_trip():
    seen = []
    group = {
        "id": "g1",
        "name": "Session",
        "tiles": [{"tile_id": "front", "datasource_id": "d1"}],
        "settings": {"multi_layer": False},
        "layer_revision": None,
        "readiness": {"is_ready": False},
    }

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/sdk/projects/p1/groups/":
            return httpx.Response(200, json={"results": [group], "next": None})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "group_id": "g1",
                    "revision": "l1:1",
                    "version": 1,
                    "properties": {"7": "rain"},
                    "links": [],
                    "problems": [],
                },
            )
        body = json.loads(request.content)
        assert body == {
            "expected_revision": "l1:1",
            "properties": {"7": "snow"},
            "links": [],
        }
        return httpx.Response(200, json={"revision": "l2:2", "version": 2})

    _client, project = _project(handler)
    [found] = project.groups.list()
    assert found.tile("front")["datasource_id"] == "d1"
    layer = found.layer()
    result = found.save_layer(layer=layer, properties={"7": "snow"})
    assert result["revision"] == "l2:2"
    assert found.layer_revision == "l2:2"
    assert ("PUT", "/api/sdk/projects/p1/groups/g1/layer/") in seen


def test_import_layer_reads_a_path(tmp_path):
    document = {"version": "1.0", "kind": "data_group", "group": {"id": "g1"}}
    path = tmp_path / "group.json"
    path.write_text(json.dumps(document))

    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/sdk/projects/p1/data-groups/layer-import/"
        assert body == {"document": document, "dry_run": True}
        return httpx.Response(200, json={"group_id": "g1", "dry_run": True})

    _client, project = _project(handler)
    assert project.groups.import_layer(str(path))["group_id"] == "g1"


def test_release_reads_group_documents(tmp_path):
    archive = tmp_path / "uuef.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("front.jpg.json", "{}")
        bundle.writestr("groups/r1.json", json.dumps({"kind": "data_group"}))
    assert Release.read_groups(archive) == [{"kind": "data_group"}]
    assert Release.read_groups(tmp_path / "missing.txt") == []


def test_capabilities_default_to_empty_on_old_servers():
    def handler(request):
        return httpx.Response(404, json={"detail": "Not found."})

    client = client_with_handler(handler)
    assert client.capabilities() == {}
