"""Lidar's native read/save helpers behind ``WorkflowTask``.

Contract: nbackend docs/workflow-agent.md and docs/workflow-agent-save-spec.md.
Every other family reads and saves one UUEF document whole (tests/test_agents.py);
a lidar scene keeps ``stitch`` (keyframe pages into one result) and ``snapshot``
+ ``plan_parts`` (a new complete result into the ``track_delta`` PUT bodies).
"""

import copy
import json
import math

import pytest

from unitlab._task_annotations import (
    DEFAULT_LIMITS,
    item_limits,
    plan_parts,
    snapshot,
    stitch,
)

# boxes2d listed first so only the sort can put cuboids before them.
LIDAR = {
    "mode": "track_delta",
    "keys": ["boxes2d", "cuboids3d", "segments3d"],
    "read_only_keys": ["segments3d"],
}
BIG = {"objects": 5000, "bytes": 32 * 1024 * 1024}


def plan(before, after, limits=BIG):
    return plan_parts(snapshot(before, LIDAR), after, LIDAR, limits)


def size(obj):
    return len(json.dumps(obj, separators=(",", ":")).encode())


def track(**fields):
    return {"ranges": [[0, 9]], "value": 1, "keyframes": {"0": {"x": 0}}, **fields}


def frames(count):
    return {str(n): {"x": n} for n in range(count)}


def lidar(**tracks):
    return {
        "tracks": {key: dict(rows) for key, rows in tracks.items()},
        "item_properties": {},
        "data_tags": [],
    }


def cuboids(*names):
    return lidar(cuboids3d={name: track() for name in names})


# --- stitch ---


def pager(pages):
    asked = []

    def fetch(path, params):
        asked.append((path, dict(params)))
        return pages[params.get("cursor")]

    return fetch, asked


def test_stitch_merges_keyframe_pages_into_tracks():
    fetch, asked = pager(
        {
            None: {
                "keyframes": {"cuboids3d": {"t1": {"0": "g0"}, "t2": {"3": "g3"}}},
                "next_cursor": "500",
            },
            "500": {"keyframes": {"cuboids3d": {"t1": {"600": "g600"}}}},
        }
    )
    light = {
        "tracks": {
            "cuboids3d": {
                "t1": {"ranges": [[0, 600]], "value": 1, "keyframes": {}},
                "t2": {"ranges": [[0, 3]], "value": 2, "keyframes": {}},
            }
        },
        "item_properties": {},
    }
    pages = {"path": "/pages/", "params": {"version": 4}}
    result = stitch(light, pages, fetch)
    assert result["tracks"]["cuboids3d"] == {
        "t1": {
            "ranges": [[0, 600]],
            "value": 1,
            "keyframes": {"0": "g0", "600": "g600"},
        },
        "t2": {"ranges": [[0, 3]], "value": 2, "keyframes": {"3": "g3"}},
    }
    assert asked == [
        ("/pages/", {"version": 4}),
        ("/pages/", {"version": 4, "cursor": "500"}),
    ]
    assert pages["params"] == {"version": 4}


def test_stitch_without_pages_fetches_nothing():
    def fetch(path, params):
        raise AssertionError("no page to fetch")

    light = cuboids("car")
    assert stitch(copy.deepcopy(light), None, fetch) == light


# --- snapshot + plan_parts: the diff ---


def test_an_unchanged_result_plans_nothing():
    result = lidar(cuboids3d={"car": track()}, segments3d={"road": track()})
    assert plan(result, copy.deepcopy(result)) == []


def test_new_changed_and_deleted_tracks_in_one_part():
    before = lidar(cuboids3d={"a": track(), "b": track()}, boxes2d={"c": track()})
    after = lidar(cuboids3d={"a": track(value=2), "n": track()})
    assert plan(before, after) == [
        {
            "save_mode": "track_delta",
            "deleted_tracks": {"boxes2d": ["c"], "cuboids3d": ["b"]},
            "upserted_tracks": {"cuboids3d": {"a": track(value=2), "n": track()}},
        }
    ]


def test_item_fields_change_alone():
    before = cuboids("car")
    after = copy.deepcopy(before)
    after["item_properties"] = {"k": 2}
    del after["data_tags"]
    assert plan(before, after) == [
        {"save_mode": "track_delta", "data_tags": [], "item_properties": {"k": 2}}
    ]


@pytest.mark.parametrize(
    "change",
    [
        lambda result: result["tracks"]["segments3d"]["road"].update(value=9),
        lambda result: result["tracks"]["segments3d"].pop("road"),
        lambda result: result["tracks"]["segments3d"].update(new=track()),
    ],
)
def test_a_read_only_key_is_refused(change):
    before = lidar(cuboids3d={"car": track()}, segments3d={"road": track()})
    after = copy.deepcopy(before)
    change(after)
    with pytest.raises(ValueError, match="segments3d"):
        plan(before, after)


@pytest.mark.parametrize("name", ["timeline", "meta"])
def test_another_top_level_key_is_refused(name):
    before = {**lidar(), name: {"t": 1}}
    after = copy.deepcopy(before)
    after[name] = {"changed": True}
    with pytest.raises(ValueError, match=repr(name)):
        plan(before, after)


def test_a_track_key_that_is_not_a_mapping_is_refused():
    with pytest.raises(ValueError, match="must map ids to tracks"):
        plan(lidar(), {"tracks": {"cuboids3d": [track()]}})


# --- plan_parts: splitting ---


def test_split_by_track_count_deletes_first_item_fields_last():
    before = {**cuboids("a", "b", "c"), "item_properties": {"k": 1}}
    after = {
        **lidar(cuboids3d={"a": track(value=2), "d": track(), "e": track()}),
        "item_properties": {"k": 2},
    }
    assert plan(before, after, limits={"objects": 2, "bytes": BIG["bytes"]}) == [
        {"save_mode": "track_delta", "deleted_tracks": {"cuboids3d": ["b", "c"]}},
        {
            "save_mode": "track_delta",
            "upserted_tracks": {"cuboids3d": {"a": track(value=2), "d": track()}},
        },
        {
            "save_mode": "track_delta",
            "upserted_tracks": {"cuboids3d": {"e": track()}},
            "item_properties": {"k": 2},
        },
    ]


def test_split_by_bytes_keeps_ten_percent_headroom():
    tracks = {name: track(pad="x" * 100) for name in "abcd"}
    one = size(tracks["a"])
    before = cuboids("old")
    after = lidar(cuboids3d=tracks)
    # Exactly two tracks' bytes: 90% of it holds only one per part.
    parts = plan(before, after, limits={"objects": 5000, "bytes": 2 * one})
    assert [
        list(part.get("upserted_tracks", {}).get("cuboids3d", {})) for part in parts
    ] == [["a"], ["b"], ["c"], ["d"]]
    # Deletes weigh nothing and lead.
    assert parts[0]["deleted_tracks"] == {"cuboids3d": ["old"]}
    # Room for two and a half tracks at 90%: two per part.
    limit = math.ceil(2.5 * one / 0.9)
    parts = plan(before, after, limits={"objects": 5000, "bytes": limit})
    assert [sorted(part["upserted_tracks"]["cuboids3d"]) for part in parts] == [
        ["a", "b"],
        ["c", "d"],
    ]
    assert all(size(part["upserted_tracks"]) <= limit for part in parts)


def test_tracks_referring_to_others_go_last():
    before = cuboids("old")
    box = track(linked_track_id="car")
    linked = track(relations=[{"target": "car"}])
    after = lidar(boxes2d={"box": box}, cuboids3d={"linked": linked, "car": track()})
    parts = plan(before, after, {"objects": 1, "bytes": BIG["bytes"]})
    assert parts == [
        {"save_mode": "track_delta", "deleted_tracks": {"cuboids3d": ["old"]}},
        {
            "save_mode": "track_delta",
            "upserted_tracks": {"cuboids3d": {"car": track()}},
        },
        {"save_mode": "track_delta", "upserted_tracks": {"boxes2d": {"box": box}}},
        {
            "save_mode": "track_delta",
            "upserted_tracks": {"cuboids3d": {"linked": linked}},
        },
    ]


def test_missing_limits_fall_back_to_the_server_defaults():
    after = lidar(cuboids3d={f"t{n}": track() for n in range(6000)})
    parts = plan(lidar(), after, limits={})
    assert [len(part["upserted_tracks"]["cuboids3d"]) for part in parts] == [5000, 1000]


def test_an_id_moved_to_another_key_is_deleted_in_an_earlier_part():
    # The server refuses one save that deletes and upserts the same id.
    after = lidar(cuboids3d={}, boxes2d={"a": track(x=1)})
    assert plan(cuboids("a"), after) == [
        {"save_mode": "track_delta", "deleted_tracks": {"cuboids3d": ["a"]}},
        {
            "save_mode": "track_delta",
            "upserted_tracks": {"boxes2d": {"a": track(x=1)}},
        },
    ]


# --- plan_parts: keyframes per part ---


def test_split_by_keyframes_counts_upserted_tracks_only():
    before = lidar(cuboids3d={"old": track(keyframes=frames(4))})
    after = lidar(
        cuboids3d={
            name: track(keyframes=frames(count))
            for name, count in [("a", 3), ("b", 2), ("c", 2), ("d", 1), ("e", 5)]
        }
    )
    parts = plan(before, after, {**BIG, "keyframes": 5})
    # A delete carries no keyframes; a part may hold exactly the cap.
    assert parts[0]["deleted_tracks"] == {"cuboids3d": ["old"]}
    assert [list(part["upserted_tracks"]["cuboids3d"]) for part in parts] == [
        ["a", "b"],
        ["c", "d"],
        ["e"],
    ]


def test_one_track_over_the_keyframe_cap_is_refused_before_any_part():
    after = lidar(cuboids3d={"car": track(), "long": track(keyframes=frames(6))})
    with pytest.raises(ValueError, match=r"'long' in cuboids3d has 6 keyframes.* 5,"):
        plan(lidar(), after, {**BIG, "keyframes": 5})


@pytest.mark.parametrize("limits", [{**BIG, "keyframes": None}, BIG])
def test_a_null_or_missing_keyframe_cap_means_no_keyframe_limit(limits):
    after = lidar(
        cuboids3d={name: track(keyframes=frames(15000)) for name in ("a", "b")}
    )
    [part] = plan(lidar(), after, limits)
    assert list(part["upserted_tracks"]["cuboids3d"]) == ["a", "b"]


def test_row_limits_take_precedence_over_the_read_limits():
    row = {"objects": 2000, "bytes": BIG["bytes"], "keyframes": 20000}
    assert item_limits({**LIDAR, "limits": row}, BIG) == row
    assert item_limits(LIDAR, BIG) == BIG
    assert item_limits({**LIDAR, "limits": None}, BIG) == BIG
    assert item_limits(LIDAR, None) == DEFAULT_LIMITS
    assert DEFAULT_LIMITS["keyframes"] is None


def test_one_track_over_the_byte_cap_is_refused_before_sending():
    big = track(note="x" * 2000)
    with pytest.raises(ValueError, match="huge"):
        plan(lidar(), lidar(cuboids3d={"huge": big}), {"objects": 5000, "bytes": 1000})
