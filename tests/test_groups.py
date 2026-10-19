import json

import httpx
import pytest
from test_client import client_with_handler

from unitlab import TileSpec
from unitlab.exceptions import ConflictError, UnitlabError
from unitlab.resources import groups as groups_module
from unitlab.resources.assets import Folder

GROUP = {
    "pk": "g1",
    "name": "Session 1",
    "revision": 0,
    "tiles": [{"tile_id": "front", "metadata": {}}],
    "settings": {"multi_layer": False},
    "custom_metadata": {},
    "source_kind": "manual",
    "config_id": None,
}


def test_create_group_sends_tiles():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(201, json=GROUP)

    client = client_with_handler(handler)
    group = client.data_groups.create(
        "f1",
        "Session 1",
        [
            TileSpec("front", asset="a1", required=True),
            TileSpec("notes", asset="a2", read_only=True),
            {
                "tile_id": "imu",
                "asset_id": "a3",
                "alignment": {"align_to_tile_id": "front", "mode": "frame"},
            },
        ],
        custom_metadata={"weather": "rain"},
    )
    method, path, body = seen[0]
    assert (method, path) == ("POST", "/api/sdk/data-assets/folders/f1/groups/")
    assert body["tiles"][0] == {
        "tile_id": "front",
        "title": "front",
        "asset_id": "a1",
        "required": True,
        "read_only": False,
    }
    assert body["tiles"][1]["read_only"] is True
    assert body["tiles"][2]["alignment"]["mode"] == "frame"
    assert body["custom_metadata"] == {"weather": "rain"}
    assert group.id == "g1"
    assert group.source_kind == "manual"


def test_update_group_sends_revision_and_tile_changes():
    seen = []

    def handler(request):
        seen.append((request.method, json.loads(request.content)))
        return httpx.Response(200, json={**GROUP, "revision": 1, "name": "Renamed"})

    client = client_with_handler(handler)
    group = groups_module.DataGroup._from_raw(client, GROUP)
    group.update(
        name="Renamed",
        add_tiles=[TileSpec("side", asset="a9")],
        update_tiles=[{"tile_id": "front", "read_only": True}],
        remove_tiles=["old"],
    )
    method, body = seen[0]
    assert method == "PATCH"
    assert body["expected_revision"] == 0
    assert body["tiles"]["delete"] == ["old"]
    assert [tile["tile_id"] for tile in body["tiles"]["upsert"]] == ["side", "front"]
    assert group.revision == 1
    assert group.name == "Renamed"


def test_update_conflict_is_raised():
    def handler(request):
        return httpx.Response(
            409, json={"detail": "This group was changed.", "code": "revision_conflict"}
        )

    client = client_with_handler(handler)
    group = groups_module.DataGroup._from_raw(client, GROUP)
    with pytest.raises(ConflictError):
        group.update(name="x")


def test_large_auto_group_waits_for_the_background_job(monkeypatch):
    monkeypatch.setattr(groups_module.time, "sleep", lambda _seconds: None)
    statuses = iter(["running", "succeeded"])

    def handler(request):
        if request.url.path.endswith("/auto-groups/"):
            return httpx.Response(
                202,
                json={
                    "mode": "async",
                    "job_id": "j1",
                    "status": "pending",
                    "created_count": 0,
                    "grouped_folder_id": "gf",
                    "valid": True,
                    "estimated_valid_groups": 2000,
                },
            )
        assert request.url.path == "/api/sdk/data-assets/auto-grouping-jobs/j1/"
        return httpx.Response(
            200,
            json={
                "job_id": "j1",
                "status": next(statuses),
                "progress": {"groups_total": 2000, "groups_done": 2000},
                "error": "",
                "grouped_folder_id": "gf",
            },
        )

    client = client_with_handler(handler)
    folder = Folder._from_raw(client, {"pk": "f1", "name": "big"})
    result = folder.auto_group({"grouping_keys": ["k"], "tiles": []})
    assert result.job_id == "j1"
    assert result.grouped_folder_id == "gf"


def test_failed_background_job_raises():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "job_id": "j1",
                "status": "failed",
                "error": "folder gone",
                "progress": {},
            },
        )

    client = client_with_handler(handler)
    job = client.data_groups.job("j1")
    with pytest.raises(UnitlabError) as raised:
        job.wait()
    assert raised.value.code == "grouping_failed"


def test_rerun_posts_dry_run():
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(
            200, json={"would_create_count": 1, "would_fill_count": 2}
        )

    client = client_with_handler(handler)
    result = client.data_groups.rerun("c1", dry_run=True)
    assert seen == [
        ("/api/sdk/data-assets/auto-grouping-configs/c1/rerun/", {"dry_run": True})
    ]
    assert result["would_fill_count"] == 2
