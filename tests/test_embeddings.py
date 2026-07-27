import json
from types import SimpleNamespace

import httpx
from typer.testing import CliRunner

from unitlab import EmbeddingSpace, UnitlabClient
from unitlab.cli import app

SPACE_ID = "00000000-0000-0000-0000-000000000001"
ASSET_ID = "00000000-0000-0000-0000-000000000002"
PROJECT_ID = "00000000-0000-0000-0000-000000000003"


def test_embedding_space_sdk_contract():
    requests = []

    def handler(request):
        payload = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, payload))
        if request.url.path == "/api/sdk/embedding-spaces/":
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": SPACE_ID,
                                "name": "BiomedCLIP",
                                "dimensions": 2,
                                "model_name": "biomedclip-v1",
                                "ann_index_status": "ready",
                                "vector_search_supported": True,
                            }
                        ],
                        "next": None,
                    },
                )
            return httpx.Response(
                201,
                json={
                    "id": SPACE_ID,
                    "name": payload["name"],
                    "dimensions": payload["dimensions"],
                    "model_name": payload.get("model_name"),
                    "ann_index_status": "building",
                    "vector_search_supported": False,
                },
            )
        if request.url.path == f"/api/sdk/embedding-spaces/{SPACE_ID}/":
            if request.method == "DELETE":
                return httpx.Response(204)
            return httpx.Response(
                200,
                json={
                    "id": SPACE_ID,
                    "name": "BiomedCLIP",
                    "dimensions": 2,
                    "model_name": "biomedclip-v1",
                    "ann_index_status": "ready",
                    "vector_search_supported": True,
                },
            )
        if request.url.path.endswith("/vectors/"):
            return httpx.Response(
                200,
                json={
                    "space_id": SPACE_ID,
                    "submitted": len(payload["items"]),
                    "created": len(payload["items"]),
                    "updated": 0,
                },
            )
        if request.url.path.endswith("/search/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "asset_id": ASSET_ID,
                            "frame_index": 7,
                            "score": 0.9,
                            "file_name": "scan.mp4",
                        }
                    ],
                    "count": 1,
                },
            )
        raise AssertionError(request.url)

    client = UnitlabClient(api_key="key", api_url="http://testserver")
    client._api.client.close()
    client._api.client = httpx.Client(
        base_url="http://testserver",
        headers={"Authorization": "Api-Key key"},
        transport=httpx.MockTransport(handler),
    )

    listed = client.embedding_spaces.list()[0]
    assert isinstance(listed, EmbeddingSpace)
    assert listed.ann_index_status == "ready"
    assert listed.vector_search_supported is True
    created = client.embedding_spaces.create(
        "Medical",
        dimensions=2,
        model_name="biomedclip-v1",
    )
    assert created.id == SPACE_ID
    assert created.ann_index_status == "building"
    assert created.vector_search_supported is False
    space = client.embedding_spaces.get(SPACE_ID)
    asset = SimpleNamespace(id=ASSET_ID)
    assert space.upsert(asset, (0.1, 0.2), frame_index=7)["created"] == 1
    assert (
        space.upsert_many(
            [{"asset_id": asset, "vector": (0.3, 0.4), "frame_index": None}]
        )["submitted"]
        == 1
    )
    result = space.search(
        (0.5, 0.6),
        limit=5,
        project_id=SimpleNamespace(id=PROJECT_ID),
        level="frame",
    )
    assert result["results"][0]["asset_id"] == ASSET_ID
    space.delete()

    vector_payloads = [
        payload for method, path, payload in requests if path.endswith("/vectors/")
    ]
    assert vector_payloads == [
        {
            "items": [
                {
                    "asset_id": ASSET_ID,
                    "vector": [0.1, 0.2],
                    "frame_index": 7,
                }
            ]
        },
        {"items": [{"asset_id": ASSET_ID, "vector": [0.3, 0.4]}]},
    ]
    search_payload = next(
        payload for method, path, payload in requests if path.endswith("/search/")
    )
    assert search_payload == {
        "vector": [0.5, 0.6],
        "limit": 5,
        "project_id": PROJECT_ID,
        "level": "frame",
    }
    client.close()


def test_embedding_space_readiness_defaults_for_older_servers():
    space = EmbeddingSpace._from_raw(
        SimpleNamespace(),
        {
            "id": SPACE_ID,
            "name": "Legacy",
            "dimensions": 2,
            "model_name": None,
        },
    )

    assert space.ann_index_status is None
    assert space.vector_search_supported is True


def test_embeddings_cli_direct_and_jsonl_upload(monkeypatch, tmp_path):
    calls = []

    class Space:
        id = SPACE_ID

        def delete(self):
            calls.append(("delete",))

        def upsert(self, asset_id, vector, *, frame_index=None):
            calls.append(("upsert", asset_id, vector, frame_index))
            return {
                "space_id": self.id,
                "submitted": 1,
                "created": 1,
                "updated": 0,
            }

        def upsert_many(self, items):
            items = list(items)
            calls.append(("upsert_many", len(items)))
            return {
                "space_id": self.id,
                "submitted": len(items),
                "created": len(items),
                "updated": 0,
            }

        def search(self, vector, **options):
            calls.append(("search", vector, options))
            return {"results": [], "count": 0}

    space = Space()

    class Spaces:
        @staticmethod
        def list():
            return [
                {
                    "id": SPACE_ID,
                    "name": "Medical",
                    "dimensions": 2,
                    "ann_index_status": "ready",
                    "vector_search_supported": True,
                }
            ]

        @staticmethod
        def create(name, **options):
            calls.append(("create", name, options))
            return {
                "id": SPACE_ID,
                "name": name,
                "dimensions": options["dimensions"],
                "model_name": options["model_name"],
            }

        @staticmethod
        def get(space_id):
            assert space_id == SPACE_ID
            return space

    client = SimpleNamespace(embedding_spaces=Spaces())
    monkeypatch.setattr("unitlab.cli.get_client", lambda _api_key: client)
    vector_file = tmp_path / "vector.json"
    vector_file.write_text("[0.1, 0.2]")
    jsonl = tmp_path / "vectors.jsonl"
    jsonl.write_text(
        "\n".join(
            json.dumps({"asset_id": ASSET_ID, "vector": [0.1, 0.2]})
            for _ in range(1001)
        )
    )
    runner = CliRunner()

    help_result = runner.invoke(app, ["embeddings", "--help"])
    assert help_result.exit_code == 0
    for command in ("list", "create", "detail", "delete", "upsert", "upload", "search"):
        assert command in help_result.stdout

    listed = runner.invoke(app, ["embeddings", "list"])
    assert listed.exit_code == 0
    assert "ann_index_status=ready" in listed.stdout
    assert "vector_search_supported=True" in listed.stdout

    create = runner.invoke(
        app,
        [
            "embeddings",
            "create",
            "Medical",
            "--dimensions",
            "2",
            "--model-name",
            "biomedclip-v1",
        ],
    )
    assert create.exit_code == 0

    upsert = runner.invoke(
        app,
        [
            "embeddings",
            "upsert",
            SPACE_ID,
            ASSET_ID,
            "--vector-file",
            str(vector_file),
            "--frame-index",
            "7",
        ],
    )
    assert upsert.exit_code == 0

    upload = runner.invoke(
        app,
        ["embeddings", "upload", SPACE_ID, str(jsonl), "--json"],
    )
    assert upload.exit_code == 0
    assert json.loads(upload.stdout)["submitted"] == 1001
    assert json.loads(upload.stdout)["batches"] == 2

    search = runner.invoke(
        app,
        [
            "embeddings",
            "search",
            SPACE_ID,
            "--vector-file",
            str(vector_file),
            "--limit",
            "5",
            "--project",
            PROJECT_ID,
            "--level",
            "frame",
        ],
    )
    assert search.exit_code == 0

    deleted = runner.invoke(
        app,
        ["embeddings", "delete", SPACE_ID, "--yes"],
    )
    assert deleted.exit_code == 0
    assert ("upsert", ASSET_ID, [0.1, 0.2], 7) in calls
    assert ("upsert_many", 1000) in calls
    assert ("upsert_many", 1) in calls
    assert (
        "search",
        [0.1, 0.2],
        {"limit": 5, "project_id": PROJECT_ID, "level": "frame"},
    ) in calls
    assert ("delete",) in calls


def test_embeddings_cli_rejects_invalid_uploads_and_search_limit(monkeypatch, tmp_path):
    class Spaces:
        @staticmethod
        def get(_space_id):
            return SimpleNamespace(id=SPACE_ID, upsert_many=lambda _items: {})

    monkeypatch.setattr(
        "unitlab.cli.get_client",
        lambda _api_key: SimpleNamespace(embedding_spaces=Spaces()),
    )
    runner = CliRunner()
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    missing = tmp_path / "missing.jsonl"
    missing.write_text("{}\n")
    vector = tmp_path / "vector.json"
    vector.write_text("[0.1, 0.2]")

    empty_result = runner.invoke(
        app,
        ["embeddings", "upload", SPACE_ID, str(empty)],
    )
    assert empty_result.exit_code == 2
    assert "contains no embeddings" in empty_result.output

    missing_result = runner.invoke(
        app,
        ["embeddings", "upload", SPACE_ID, str(missing)],
    )
    assert missing_result.exit_code == 2
    assert "Line 1" in missing_result.output
    assert "asset_id, vector" in missing_result.output

    limit_result = runner.invoke(
        app,
        [
            "embeddings",
            "search",
            SPACE_ID,
            "--vector-file",
            str(vector),
            "--limit",
            "101",
        ],
    )
    assert limit_result.exit_code == 2
    assert "1<=x<=100" in limit_result.output
