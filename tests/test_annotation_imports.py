import json
import uuid
from email import policy
from email.parser import BytesParser
from types import SimpleNamespace

import httpx
import pytest

from unitlab import (
    AnnotationImport,
    AnnotationImportError,
    ConflictError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    RequestTimeoutError,
    UnitlabClient,
    UnitlabError,
)
from unitlab.resources.projects import Project
from unitlab.types import UploadFailure, UploadResult

BASE = "/api/sdk/projects/p1/annotation-imports/"
PREVIEW = {
    "batch_id": "b1",
    "source_id": "s1",
    "token": "reviewed-token",
    "counts": {"create": 1},
    "media": [{"status": "matched"}],
    "classes": [],
    "annotations": [],
    "issues": [],
}
BENCHMARK_PREVIEW = {
    **PREVIEW,
    "benchmark": {"new": 1, "replace": 0, "groups": 0, "not_eligible": 0},
}


@pytest.fixture
def labels(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"images": [], "annotations": [], "categories": []}))
    return path


@pytest.fixture
def project_factory():
    clients = []

    def make(handler):
        client = UnitlabClient(api_key="key", api_url="http://testserver")
        client._api.client.close()
        client._api.client = httpx.Client(
            base_url="http://testserver",
            headers={"Authorization": "Api-Key key"},
            transport=httpx.MockTransport(handler),
        )
        clients.append(client)
        return Project("p1", "Project", {"pk": "p1"}, client)

    yield make
    for client in clients:
        client.close()


def multipart(request):
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
        + request.content
    )
    return {
        part.get_param("name", header="content-disposition"): part.get_payload(
            decode=True
        )
        for part in message.iter_parts()
    }


def test_s3_media_then_local_json_uses_preview_and_explicit_commit(
    project_factory, labels
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.headers["Authorization"] == "Api-Key key"
        assert "Company" not in request.headers
        if request.url.path.endswith("/cloud-storages/storage1/import/"):
            assert json.loads(request.content) == {"server_files": ["images/"]}
            return httpx.Response(
                202, json={"upload_session_id": "q1", "file_count": 1}
            )
        if request.url.path.endswith("/upload-sessions/q1/status/"):
            return httpx.Response(
                200, json={"total": 1, "completed": 1, "processing": 0, "failed": 0}
            )
        if request.url.path == BASE:
            fields = multipart(request)
            assert fields["annotation_file"] == labels.read_bytes()
            assert fields["source_name"] == b"detector-v1"
            assert json.loads(fields["options"]) == {}
            return httpx.Response(201, json=PREVIEW)
        if request.url.path == BASE + "b1/commit/":
            assert json.loads(request.content) == {
                "token": "reviewed-token",
                "decisions": {},
                "allow_partial": False,
            }
            return httpx.Response(200, json={"created": 1, "batch_id": "b1"})
        raise AssertionError(request.url)

    project = project_factory(handler)
    media = project.import_cloud("storage1", ["images/"])
    assert media.wait().failed == 0
    batch = project.annotation_imports.create(labels, source_name="detector-v1")
    assert isinstance(batch, AnnotationImport)
    assert batch.preview["counts"] == {"create": 1}
    assert len(calls) == 3  # Preview does not implicitly commit.
    assert batch.commit() == batch.commit()
    assert calls[-2:] == [BASE + "b1/commit/"] * 2


def test_video_upload_sends_explicit_frame_map(project_factory, labels, tmp_path):
    frame_map = tmp_path / "frames.json"
    frame_map.write_text('{"schema_version":"unitlab-frame-map/1","frames":[]}')

    def handler(request):
        fields = multipart(request)
        assert fields["frame_mapping_file"] == frame_map.read_bytes()
        assert fields["track_profile"] == b"attributes.track_id"
        assert fields["source_id"] == b"s1"
        assert "source_name" not in fields
        return httpx.Response(201, json=PREVIEW)

    project_factory(handler).annotation_imports.create(
        labels,
        source_id="s1",
        frame_mapping_file=frame_map,
        track_profile="attributes.track_id",
    )


def test_cloud_annotation_document_uses_json_request(project_factory):
    def handler(request):
        assert json.loads(request.content) == {
            "source_name": "model",
            "cloud_storage_id": "storage1",
            "annotation_key": "labels/predictions.json",
            "frame_mapping_key": "labels/frames.json",
            "options": {"stable_ids": True},
            "track_profile": "none",
        }
        return httpx.Response(201, json=PREVIEW)

    batch = project_factory(handler).annotation_imports.create(
        cloud_storage=SimpleNamespace(id="storage1"),
        annotation_key="labels/predictions.json",
        frame_mapping_key="labels/frames.json",
        source_name="model",
        options={"stable_ids": True},
    )
    assert batch.source_id == "s1"


def test_refresh_preserves_options_and_uses_only_new_reviewed_token(
    project_factory, labels
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == BASE:
            return httpx.Response(201, json=PREVIEW)
        if request.url.path.endswith("/preview/"):
            assert json.loads(request.content) == {
                "stable_ids": True,
                "media_mapping": {"road.jpg": "m1"},
            }
            return httpx.Response(200, json={**PREVIEW, "token": "new-token"})
        assert json.loads(request.content)["token"] == "new-token"
        return httpx.Response(200, json={"created": 1})

    options = {"stable_ids": True, "media_mapping": {"road.jpg": "m1"}}
    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model", options=options
    )
    options["media_mapping"]["road.jpg"] = "mutated"
    assert batch.refresh() is batch
    assert batch.commit()["created"] == 1
    assert calls == [BASE, BASE + "b1/preview/", BASE + "b1/commit/"]


def test_stale_preview_is_not_automatically_refreshed_or_committed(
    project_factory, labels
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == BASE:
            return httpx.Response(201, json=PREVIEW)
        return httpx.Response(
            409, json={"detail": "Preview changed.", "code": "CONFLICT"}
        )

    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model"
    )
    with pytest.raises(ConflictError):
        batch.commit()
    assert calls == [BASE, BASE + "b1/commit/"]
    assert batch.preview["token"] == "reviewed-token"


def test_uncertain_commit_can_be_retried_with_identical_request(
    project_factory, labels
):
    commits = []

    def handler(request):
        if request.url.path == BASE:
            return httpx.Response(201, json=PREVIEW)
        commits.append(json.loads(request.content))
        if len(commits) == 1:
            raise httpx.ReadTimeout("Response lost", request=request)
        return httpx.Response(200, json={"created": 1})

    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model"
    )
    decisions = {"a1": "keep"}
    with pytest.raises(RequestTimeoutError):
        batch.commit(decisions=decisions)
    assert batch.commit(decisions=decisions)["created"] == 1
    assert commits[0] == commits[1]


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"source_name": "model", "source_id": "s1"},
        {"source_name": "model", "cloud_storage": "storage1"},
        {
            "source_name": "model",
            "cloud_storage": "storage1",
            "annotation_key": "labels.json",
        },
        {"source_name": "model", "frame_mapping_key": "frames.json"},
        {"source_name": "model", "track_profile": "guess"},
    ],
)
def test_invalid_source_combinations_do_not_send_requests(
    project_factory, labels, extra
):
    def handler(request):
        raise AssertionError("Invalid input must not reach the server.")

    with pytest.raises(ValueError):
        project_factory(handler).annotation_imports.create(labels, **extra)


def test_file_size_limit_and_closed_streams_on_request_failure(
    project_factory, labels, monkeypatch
):
    project = project_factory(lambda request: httpx.Response(500))
    opened = []

    def post(endpoint, *, data, files, **kwargs):
        opened.extend(item[1] for item in files.values())
        raise RuntimeError("request failed")

    monkeypatch.setattr(project._client._api, "post", post)
    with pytest.raises(RuntimeError, match="request failed"):
        project.annotation_imports.create(labels, source_name="model")
    assert opened and all(stream.closed for stream in opened)
    monkeypatch.setattr("unitlab.resources.annotation_imports.MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="80 MiB"):
        project.annotation_imports.create(labels, source_name="model")
    assert len(opened) == 1


def test_geojson_export_is_uploaded_but_not_as_a_frame_map(
    project_factory, labels, tmp_path
):
    geojson = tmp_path / "release.geojson"
    geojson.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    def handler(request):
        parts = multipart(request)
        assert json.loads(parts["annotation_file"])["type"] == "FeatureCollection"
        assert "frame_mapping_file" not in parts
        return httpx.Response(201, json=PREVIEW)

    imports = project_factory(handler).annotation_imports
    assert imports.create(geojson, source_name="raster").id == "b1"
    with pytest.raises(ValueError, match="frame_mapping_file"):
        imports.create(labels, frame_mapping_file=geojson, source_name="raster")


def test_creatorless_key_commit_raises_permission_denied(project_factory, labels):
    def handler(request):
        if request.url.path == BASE:
            return httpx.Response(201, json=PREVIEW)
        return httpx.Response(
            403,
            json={
                "detail": "A user-created API key is required to commit.",
                "code": "permission_denied",
            },
        )

    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model"
    )
    with pytest.raises(PermissionDeniedError, match="user-created API key"):
        batch.commit()


def test_source_and_media_helpers_use_project_scoped_routes(project_factory):
    def handler(request):
        if request.url.path == BASE + "sources/":
            return httpx.Response(
                200, json={"sources": [{"id": "s1", "name": "model"}]}
            )
        assert request.url.path == BASE + "media/"
        assert request.url.params["search"] == "images/road.jpg"
        return httpx.Response(
            200, json={"media": [{"id": "m1", "name": "images/road.jpg"}]}
        )

    imports = project_factory(handler).annotation_imports
    assert imports.sources()[0]["id"] == "s1"
    assert imports.media("images/road.jpg")[0]["id"] == "m1"


def test_benchmark_flags_merge_into_options_and_survive_refresh(
    project_factory, labels
):
    sent = []
    report = {
        "created": 2,
        "benchmarks": {
            "created": 1,
            "replaced": 0,
            "approved": 1,
            "not_approved": [],
            "items": [],
        },
    }

    def handler(request):
        if request.url.path == BASE:
            sent.append(json.loads(multipart(request)["options"]))
            return httpx.Response(201, json=BENCHMARK_PREVIEW)
        if request.url.path.endswith("/preview/"):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=BENCHMARK_PREVIEW)
        return httpx.Response(200, json=report)

    batch = project_factory(handler).annotation_imports.create(
        labels,
        source_name="Benchmark uploads",
        options={"stable_ids": True, "benchmark": False},
        benchmark=True,
        approve_keys=True,
    )
    batch.refresh()
    assert batch.commit()["benchmarks"]["approved"] == 1
    expected = {"stable_ids": True, "benchmark": True, "approve_keys": True}
    assert sent == [expected, expected]


def test_benchmark_flags_are_not_sent_by_default(project_factory):
    def handler(request):
        assert json.loads(request.content)["options"] == {}
        return httpx.Response(201, json=PREVIEW)

    project_factory(handler).annotation_imports.create(
        cloud_storage="storage1",
        annotation_key="labels.json",
        source_name="model",
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"approve_keys": True},
        {"options": {"approve_keys": True}},
        {"approve_keys": True, "options": {"benchmark": False}},
    ],
)
def test_approve_keys_without_benchmark_sends_nothing(project_factory, labels, extra):
    def handler(request):
        raise AssertionError("Invalid input must not reach the server.")

    with pytest.raises(ValueError, match="approve_keys requires benchmark"):
        project_factory(handler).annotation_imports.create(
            labels, source_name="model", **extra
        )


@pytest.mark.parametrize(
    "extra", [{"benchmark": True}, {"options": {"benchmark": True}}]
)
def test_server_without_benchmark_support_is_refused_at_preview(
    project_factory, labels, extra
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(201, json=PREVIEW)

    with pytest.raises(AnnotationImportError, match="nothing was imported") as error:
        project_factory(handler).annotation_imports.create(
            labels, source_name="model", **extra
        )
    assert error.value.code == "benchmark_unsupported"
    assert error.value.batch_id == "b1"
    assert calls == [BASE]


def test_refresh_without_benchmark_block_blocks_commit(project_factory, labels):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == BASE:
            return httpx.Response(201, json=BENCHMARK_PREVIEW)
        return httpx.Response(200, json=PREVIEW)

    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model", benchmark=True
    )
    with pytest.raises(AnnotationImportError, match="does not support benchmark"):
        batch.refresh()
    with pytest.raises(AnnotationImportError, match="does not support benchmark"):
        batch.commit()
    assert calls == [BASE, BASE + "b1/preview/"]


def test_refresh_with_new_options_keeps_benchmark_flags(project_factory, labels):
    sent = []

    def handler(request):
        if request.url.path == BASE:
            return httpx.Response(201, json=BENCHMARK_PREVIEW)
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=BENCHMARK_PREVIEW)

    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model", benchmark=True, approve_keys=True
    )
    batch.refresh(options={"media_mapping": {"road.jpg": "m1"}})
    batch.refresh(options={"approve_keys": False})
    assert sent == [
        {"media_mapping": {"road.jpg": "m1"}, "benchmark": True, "approve_keys": True},
        {"approve_keys": False, "benchmark": True},
    ]
    assert batch._options == sent[-1]


def test_refresh_cannot_turn_off_benchmark(project_factory, labels):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(201, json=BENCHMARK_PREVIEW)

    batch = project_factory(handler).annotation_imports.create(
        labels, source_name="model", benchmark=True
    )
    with pytest.raises(ValueError, match="stays a benchmark import"):
        batch.refresh(options={"benchmark": False})
    assert calls == [BASE]
    assert batch._options == {"benchmark": True}


# --- Marking items as benchmarks (mark_benchmarks, upload(benchmark=True)) ---

MARK = "/api/sdk/projects/p1/benchmarks/"
IDS = [str(uuid.UUID(int=index + 1)) for index in range(205)]


def test_mark_benchmarks_sends_100_per_request_and_sums(project_factory):
    sent = []

    def handler(request):
        assert request.url.path == MARK
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(
            201,
            json={
                "created": len(body["datasource_ids"]) - 1,
                "existing": 1,
                "deferred": 2,
                "skipped_by_reason": {"not_ready": 0, "unsupported_type": 1},
                "first_created": None,
            },
        )

    counts = project_factory(handler).mark_benchmarks([*IDS, IDS[0]])
    assert [len(body["datasource_ids"]) for body in sent] == [100, 100, 5]
    assert [i for body in sent for i in body["datasource_ids"]] == IDS
    assert all(body["when_ready"] is True for body in sent)
    assert counts == {
        "created": 202,
        "existing": 3,
        "deferred": 6,
        "skipped_by_reason": {"not_ready": 0, "unsupported_type": 3},
    }


@pytest.mark.parametrize("ids", [[], IDS[0], ["not-an-id"]])
def test_mark_benchmarks_refuses_bad_ids_before_sending(project_factory, ids):
    def handler(request):
        raise AssertionError("Invalid input must not reach the server.")

    with pytest.raises(ValueError):
        project_factory(handler).mark_benchmarks(ids)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            404, text="<h1>Not Found</h1>", headers={"content-type": "text/html"}
        ),
        httpx.Response(405, json={"detail": 'Method "POST" not allowed.'}),
    ],
)
def test_mark_benchmarks_on_an_old_server_raises(project_factory, response):
    project = project_factory(lambda request: response)
    with pytest.raises(UnitlabError, match="cannot mark benchmarks yet") as error:
        project.mark_benchmarks(IDS[:1], when_ready=False)
    assert error.value.code == "benchmarks_unsupported"


def test_mark_benchmarks_keeps_the_route_own_not_found(project_factory):
    project = project_factory(
        lambda request: httpx.Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError, match="Not found") as error:
        project.mark_benchmarks(IDS[:1])
    assert error.value.code != "benchmarks_unsupported"


@pytest.mark.parametrize(
    ("generic_type", "uploader"),
    [
        (None, "unitlab.resources.projects._uploader.upload_project"),
        (
            "pointcloud",
            "unitlab.resources.projects._scene_uploader.upload_project_scenes",
        ),
    ],
)
def test_upload_with_benchmark_marks_only_uploaded_items(
    project_factory, monkeypatch, tmp_path, generic_type, uploader
):
    sent = []
    result = UploadResult(
        total=3,
        uploaded=2,
        failed=[UploadFailure(tmp_path / "bad.jpg", "refused")],
        responses=[{"datasource_id": IDS[0]}, {"datasource_id": IDS[1]}],
    )
    monkeypatch.setattr(uploader, lambda *args, **kwargs: (result, "queue-1"))

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(201, json={"created": 2, "existing": 0, "deferred": 1})

    project = project_factory(handler)
    plain = project.upload(tmp_path, generic_type=generic_type)
    batch = project.upload(tmp_path, generic_type=generic_type, benchmark=True)
    assert plain.benchmarks is None
    assert sent == [{"datasource_ids": IDS[:2], "when_ready": True}]
    assert batch.benchmarks == {
        "created": 2,
        "existing": 0,
        "deferred": 1,
        "skipped_by_reason": {},
        "error": None,
        "unmarked_ids": [],
    }


def fake_upload(monkeypatch, ids):
    result = UploadResult(
        total=len(ids),
        uploaded=len(ids),
        responses=[{"datasource_id": value} for value in ids],
    )
    monkeypatch.setattr(
        "unitlab.resources.projects._uploader.upload_project",
        lambda *args, **kwargs: (result, "queue-1"),
    )


def test_upload_keeps_its_batch_when_marking_fails_part_way(
    project_factory, monkeypatch, tmp_path
):
    fake_upload(monkeypatch, IDS)
    sent = []

    def handler(request):
        sent.append(json.loads(request.content)["datasource_ids"])
        if len(sent) == 2:
            return httpx.Response(500, json={"detail": "Server error."})
        return httpx.Response(201, json={"created": 100, "skipped_by_reason": {}})

    batch = project_factory(handler).upload(tmp_path, benchmark=True)
    assert len(sent) == 2
    assert batch.data_item_ids == IDS
    assert batch.benchmarks == {
        "created": 100,
        "existing": 0,
        "deferred": 0,
        "skipped_by_reason": {},
        "error": "Server error.",
        "unmarked_ids": IDS[100:],
    }


def test_upload_on_an_old_server_returns_the_batch_with_the_error(
    project_factory, monkeypatch, tmp_path
):
    fake_upload(monkeypatch, IDS[:2])
    project = project_factory(lambda request: httpx.Response(405, json={}))
    batch = project.upload(tmp_path, benchmark=True)
    assert batch.benchmarks["error"] == (
        "This Unitlab server cannot mark benchmarks yet."
    )
    assert batch.benchmarks["unmarked_ids"] == IDS[:2]
    assert batch.benchmarks["created"] == 0


def test_mark_benchmarks_still_raises_the_failing_request_error(project_factory):
    sent = []

    def handler(request):
        sent.append(request)
        if len(sent) == 2:
            return httpx.Response(500, json={"detail": "Server error."})
        return httpx.Response(201, json={"created": 100})

    with pytest.raises(NetworkError, match="Server error"):
        project_factory(handler).mark_benchmarks(IDS)
    assert len(sent) == 2
