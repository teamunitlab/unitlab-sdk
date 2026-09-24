import json
from inspect import signature

import httpx
import pytest

import unitlab
from unitlab import (
    ChecklistAttribute,
    CloudEntry,
    OntologyStructure,
    RadioAttribute,
    Shape,
    UnitlabClient,
    tiles_from_template,
)
from unitlab.resources.assets import Asset, AssetsNamespace, Folder
from unitlab.resources.datasets import Dataset, DatasetsNamespace, DatasetVersion
from unitlab.resources.ontologies import Ontology
from unitlab.resources.projects import DataUnit, Project, ProjectsNamespace
from unitlab.resources.releases import ReleasesNamespace
from unitlab.resources.workflow import WorkflowTask
from unitlab.types import AttachPreview, AttachResult


def client_with_handler(handler):
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    client._api.client.close()
    client._api.client = httpx.Client(
        base_url="http://testserver",
        headers={"Authorization": "Api-Key key"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_duplicate_public_methods_are_removed():
    removed = (
        (
            UnitlabClient,
            (
                "wait_for_batch_queue",
                "upload_to_assets",
                "create_with_api_key",
                "get_project",
                "list_projects",
                "create_project",
                "get_ontology",
                "get_ontologies",
                "create_ontology",
                "get_dataset",
                "get_datasets",
                "create_dataset",
                "get_storage_folder",
                "list_storage_folders",
                "get_cloud_integrations",
                "project",
                "project_upload_info",
                "project_upload_data",
                "dataset_download",
                "dataset_download_files",
                "upload_to_project",
                "import_cloud",
                "create_storage_folder",
                "find_storage_folders",
                "__enter__",
                "__exit__",
            ),
        ),
        (ProjectsNamespace, ("list_raw",)),
        (ReleasesNamespace, ("list_raw",)),
        (
            Project,
            (
                "project_hash",
                "title",
                "created_at",
                "creator_email",
                "upload_requirements",
                "refresh",
                "refetch_data",
                "get_data_unit",
                "add_datasets",
                "create_release",
            ),
        ),
        (DataUnit, ("refresh",)),
        (
            Folder,
            (
                "uuid",
                "parent_uuid",
                "refresh",
                "refetch_data",
                "list_subfolders",
                "upload",
            ),
        ),
        (Asset, ("uuid", "name")),
        (Dataset, ("dataset_hash", "title", "refresh", "refetch_data")),
        (Ontology, ("ontology_hash", "refresh", "refetch_data")),
        (WorkflowTask, ("refresh", "perform")),
    )
    for owner, names in removed:
        assert all(not hasattr(owner, name) for name in names)
    assert "__call__" not in ProjectsNamespace.__dict__
    assert "__call__" not in DatasetsNamespace.__dict__
    for name in unitlab.__all__:
        exported = getattr(unitlab, name)
        if isinstance(exported, type):
            assert all(
                not hasattr(exported, method)
                for method in ("from_raw", "from_queue", "from_detail", "fetch")
            )
    assert hasattr(AssetsNamespace, "upload")
    for method in (Project.upload, Project.import_cloud):
        assert {"wait", "timeout", "on_progress"}.isdisjoint(
            signature(method).parameters
        )
    assert {"wait", "timeout", "on_progress"}.isdisjoint(
        signature(UnitlabClient.attach_dataset).parameters
    )
    assert "show_progress" not in signature(Project.upload).parameters
    assert "show_progress" not in signature(AssetsNamespace.upload).parameters
    assert "asset_ids" not in signature(Project.attach).parameters
    assert "asset_ids" not in signature(Project.attach_preview).parameters
    assert "splits" not in signature(Dataset.publish_version).parameters
    assert list(signature(tiles_from_template).parameters) == [
        "template",
        "tile_values",
    ]
    assert "uid" not in signature(OntologyStructure.add_object).parameters
    assert "uid" not in signature(OntologyStructure.add_classification).parameters
    assert "project_data_id" not in DataUnit.__dataclass_fields__
    assert "is_cloud" not in Folder.__dataclass_fields__
    assert "splits" not in DatasetVersion.__dataclass_fields__
    assert all(
        not hasattr(Shape, name) for name in ("SEGMENTATION", "CUBOID_2D", "AUDIO")
    )


def test_resource_namespace_returns_typed_handles():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/api/sdk/projects/":
            return httpx.Response(200, json=[{"pk": "p1", "name": "Project"}])
        raise AssertionError(request.url)

    client = client_with_handler(handler)
    projects = client.projects.list()
    assert projects[0].id == "p1"
    assert projects[0].name == "Project"

    assert seen == ["/api/sdk/projects/"]
    client.close()


def test_unique_convenience_delegates_without_duplicate_requests(monkeypatch):
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    assert client.cloud_storages is not None
    project = Project("p1", "Project", {"pk": "p1"}, client)
    attach_result = AttachResult(1, 1, ["pd1"], None, 1, {})
    monkeypatch.setattr(project, "attach", lambda **kwargs: attach_result)
    assert client.attach_dataset(project, "d1") is attach_result
    client.close()


def test_resource_properties_and_unique_conveniences(monkeypatch):
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    project = Project(
        "p1",
        "Project",
        {"pk": "p1"},
        client,
        created="today",
        creator="owner@example.com",
    )
    dataset = Dataset("d1", "Dataset", "", None, False, {"pk": "d1"}, client)
    folder = Folder("f1", "Folder", None, None, "", {"pk": "f1"}, client)
    asset = Asset("a1", "image.png", "image", "f1", {"pk": "a1"}, client)

    monkeypatch.setattr(client.assets, "create_folder", lambda *a, **k: folder)
    monkeypatch.setattr(client.assets, "folders", lambda *a, **k: [folder])

    assert project.id == "p1"
    assert project.name == "Project"
    assert project.created == "today"
    assert project.creator == "owner@example.com"
    assert dataset.id == "d1"
    assert dataset.name == "Dataset"
    assert folder.id == "f1"
    assert folder.parent_id is None
    assert asset.id == "a1"
    assert asset.file_name == "image.png"
    assert folder.children() == [folder]
    assert folder.create_subfolder("Child") is folder

    client.close()


def test_ontology_builder_and_client_contract():
    requests = []

    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert payload["data_type"] == "image"
        if request.method == "POST":
            serialized = request.content.decode()
            assert '"shape":"bounding_box"' in serialized
            assert '"type":"radio"' in serialized
            assert "featureNodeHash" not in serialized
        return httpx.Response(
            200,
            json={
                "ontology_hash": "o1",
                "title": "Cats",
                "description": "",
                "data_type": "image",
                "created_at": "today",
                "last_edited_at": "today",
                "project_id": None,
                "structure": structure.to_dict(),
            },
        )

    structure = OntologyStructure()
    cat = structure.add_object("Cat", Shape.BOUNDING_BOX)
    colour = cat.add_attribute(RadioAttribute, "Colour", required=True)
    assert "value" not in signature(colour.add_option).parameters
    black = colour.add_option("Black")
    black.add_nested_attribute(RadioAttribute, "Shade").add_option("Dark")
    scene = structure.add_classification()
    scene_type = scene.add_attribute(ChecklistAttribute, "Scene")
    scene_type.add_option("Indoor")

    client = client_with_handler(handler)
    ontology = client.ontologies.create(
        "Cats",
        structure=structure,
        data_type="multimodal",
    )
    assert isinstance(ontology, Ontology)
    assert ontology.id == "o1"
    assert ontology.data_type == "image"
    assert ontology.structure.objects[0].title == "Cat"
    ontology.title = "Cats v2"
    ontology.save()
    assert [request.method for request in requests] == ["POST", "PUT"]
    client.close()


@pytest.mark.parametrize("shape_value", ("interval", "instant"))
def test_timeseries_ontology_shapes_round_trip(shape_value):
    shape = Shape(shape_value)
    structure = OntologyStructure()

    created = structure.add_object("Chart event", shape)
    restored = OntologyStructure.from_dict(structure.to_dict()).objects[0]

    assert created.shape is shape
    assert restored.shape is shape


def test_release_detail_parses_and_downloads(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/sdk/releases/r1/"
        return httpx.Response(
            200,
            json={
                "pk": "r1",
                "name": "Snapshot",
                "version": "1.0",
                "number_of_data": 3,
                "generic_type": None,
                "is_public": True,
            },
        )

    client = client_with_handler(handler)
    release = client.releases.get("r1")
    assert release.id == "r1"
    assert release.data_item_count == 3
    assert release.data_type == ""
    assert not hasattr(release, "download_formats")
    assert release.is_public

    monkeypatch.setattr(
        "unitlab.resources.releases._downloader.download_annotation",
        lambda api, release_id, split, dest: f"{dest}/{release_id}-{split}.zip",
    )
    assert release.download("train", dest="exports") == "exports/r1-train.zip"
    client.close()


def test_multimodal_release_uses_all_available_types():
    def handler(request):
        assert set(request.extensions["timeout"].values()) == {600.0}
        payload = json.loads(request.content)
        assert "generic_types" not in payload
        return httpx.Response(
            201,
            json={
                "pk": "r1",
                "name": "Snapshot",
                "version": "1.0",
                "number_of_data": 3,
                "generic_type": None,
            },
        )

    client = client_with_handler(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)

    release = client.releases.create(project, data_types=["multimodal"])
    assert release.data_type == ""

    with pytest.raises(ValueError, match="concrete data types"):
        client.releases.create(
            project,
            bundle_formats={"multimodal": "UUEF"},
        )
    client.close()


RELEASE_ROW = {"pk": "r1", "name": "Snapshot", "version": "0.3", "generic_type": None}
PENDING_RELEASE = {
    **RELEASE_ROW,
    "number_of_data": None,
    "status": "pending",
    "progress": 0,
    "status_error": None,
}
READY_RELEASE = {
    **PENDING_RELEASE,
    "number_of_data": 3,
    "status": "ready",
    "progress": 100,
}
# /status/ answers in the ProcessingStatus shape; processing == 0 ends the poll.
EXPORTING = {"status": "processing", "total": 100, "completed": 40, "processing": 1}
COMPLETED = {"status": "completed", "total": 100, "completed": 100, "processing": 0}
CREATE_RELEASE = ("POST", "/api/sdk/projects/p1/releases/")
RELEASE_STATUS = ("GET", "/api/sdk/releases/r1/status/")
RELEASE_DETAIL = ("GET", "/api/sdk/releases/r1/")


def release_client(responses, calls):
    """Answer requests from a queue so each test pins the exact call order."""
    queue = list(responses)

    def handler(request):
        calls.append((request.method, request.url.path))
        status_code, body = queue.pop(0)
        return httpx.Response(status_code, json=body)

    client = client_with_handler(handler)
    return client, Project("p1", "Project", {"pk": "p1"}, client)


def test_release_create_waits_until_the_async_release_is_ready(monkeypatch):
    monkeypatch.setattr("unitlab._waiter.time.sleep", lambda _delay: None)
    calls = []
    client, project = release_client(
        [
            (202, PENDING_RELEASE),
            (200, EXPORTING),
            (200, COMPLETED),
            (200, READY_RELEASE),
        ],
        calls,
    )

    release = client.releases.create(project)

    assert calls == [CREATE_RELEASE, RELEASE_STATUS, RELEASE_STATUS, RELEASE_DETAIL]
    assert release.status == "ready"
    assert release.progress == 100
    assert release.data_item_count == 3
    client.close()


def test_release_create_without_wait_returns_the_pending_release():
    calls = []
    client, project = release_client([(202, PENDING_RELEASE)], calls)

    release = client.releases.create(project, wait=False)

    assert calls == [CREATE_RELEASE]
    assert release.status == "pending"
    assert release.progress == 0
    assert release.data_item_count == 0
    client.close()


def test_release_wait_raises_when_the_release_failed(monkeypatch):
    monkeypatch.setattr("unitlab._waiter.time.sleep", lambda _delay: None)
    calls = []
    failed = {"status": "failed", "total": 100, "completed": 40, "processing": 0}
    client, project = release_client(
        [
            (202, PENDING_RELEASE),
            (200, {**failed, "failed": 1}),
            (200, {**PENDING_RELEASE, "status": "failed", "status_error": "Disk full"}),
        ],
        calls,
    )

    with pytest.raises(unitlab.UnitlabError, match="Disk full") as exc:
        client.releases.create(project)

    assert exc.value.code == "release_failed"
    assert calls == [CREATE_RELEASE, RELEASE_STATUS, RELEASE_DETAIL]
    client.close()


def test_release_create_never_polls_a_backend_without_release_status():
    # A synchronous (pre-async) backend answers 201 with no status field and
    # has no /status/ route, so polling it would 404 a finished release.
    calls = []
    legacy = {**RELEASE_ROW, "number_of_data": 3}
    client, project = release_client([(201, legacy)], calls)

    release = client.releases.create(project)

    assert calls == [CREATE_RELEASE]
    assert release.status is None
    assert release.data_item_count == 3
    client.close()


def test_release_conflicts_propagate_as_conflict_error():
    conflict = {"detail": "Release 0.3 is still being prepared (40%)."}
    client, project = release_client(
        [
            (409, {**conflict, "code": "release_in_progress", "release_id": "r1"}),
            (409, {**conflict, "code": "release_not_ready"}),
        ],
        [],
    )

    with pytest.raises(unitlab.ConflictError) as duplicate:
        client.releases.create(project)
    assert duplicate.value.code == "release_in_progress"

    pending = unitlab.Release._from_raw(client, PENDING_RELEASE)
    with pytest.raises(unitlab.ConflictError, match="still being prepared") as early:
        pending.download("train")
    assert early.value.code == "release_not_ready"
    client.close()


def test_data_units_project_lifecycle_sources_and_release_creation():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/api/sdk/projects/p1/" and request.method == "PATCH":
            return httpx.Response(
                200,
                json={"pk": "p1", "name": "Renamed", "description": "Notes"},
            )
        if path == "/api/sdk/projects/p1/data-units/":
            assert request.url.params["data_type"] == "image"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "u1",
                            "kind": "datasource",
                            "name": "cat.png",
                            "data_type": "img",
                            "status": "annotate",
                            "priority": 3,
                            "thumbnail_url": "https://signed.example/cat.webp",
                            "metadata": {},
                            "items": [],
                        },
                        {
                            "id": "g1",
                            "kind": "group",
                            "name": "Study",
                            "data_types": ["medical"],
                            "items": [
                                {
                                    "tile_id": "front",
                                    "data_type": "medical",
                                    "thumbnail_url": "https://signed.example/front.webp",
                                }
                            ],
                        },
                    ],
                    "next": None,
                },
            )
        if path == "/api/sdk/projects/p1/attached-sources/":
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Dataset v1",
                        "source_link_id": "s1",
                        "source_dataset_id": "d1",
                        "source_dataset_version_number": 1,
                    }
                ],
            )
        if path.endswith("/s1/detach-preview/"):
            return httpx.Response(200, json={"asset_count": 2})
        if path.endswith("/s1/detach/"):
            return httpx.Response(200, json={"detached": True})
        if path == "/api/sdk/projects/p1/releases/":
            payload = json.loads(request.content)
            assert payload["export_type"] == "COCO"
            assert payload["split_ratios"] == {"train": 100}
            assert payload["generic_types"] == ["img"]
            assert payload["bundle_formats"] == {"img": "UUEF"}
            return httpx.Response(
                201,
                json={
                    "pk": "r1",
                    "name": "Renamed",
                    "version": "1.0",
                    "number_of_data": 2,
                    "generic_type": "img",
                },
            )
        if path == "/api/sdk/projects/p1/" and request.method == "DELETE":
            return httpx.Response(204)
        raise AssertionError(request.url)

    client = client_with_handler(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)
    project.update(name="Renamed", description="Notes")
    assert project.name == "Renamed"
    assert project.description == "Notes"

    units = project.data_units(data_type="image")
    assert units[0].name == "cat.png"
    assert units[0].data_type == "image"
    assert units[0].thumbnail_url == "https://signed.example/cat.webp"
    assert units[1].kind == "group"
    assert units[1].data_type == ""
    assert units[1].data_types == ["medical"]
    assert units[1].thumbnail_url is None
    assert units[1].items[0]["thumbnail_url"] == ("https://signed.example/front.webp")

    source = project.attached_sources()[0]
    assert source.dataset_id == "d1"
    assert source.detach_preview() == {"asset_count": 2}
    assert source.detach() == {"detached": True}

    release = client.releases.create(
        project,
        export_type="COCO",
        data_types=["image"],
        bundle_formats={"image": "UUEF"},
    )
    assert release.id == "r1"
    project.delete()
    assert ("DELETE", "/api/sdk/projects/p1/") in calls
    client.close()


def test_data_group_parsing_accepts_payloads_without_singular_data_type():
    client = UnitlabClient(api_key="key", api_url="http://testserver")
    unit = DataUnit._from_raw(
        client,
        "p1",
        {
            "id": "g1",
            "kind": "group",
            "name": "Legacy group",
            "data_types": ["img", "video"],
            "items": [{"tile_id": "front"}],
        },
    )

    assert unit.thumbnail_url is None
    assert unit.data_type == ""
    assert unit.data_types == ["image", "video"]
    assert unit.items == [{"tile_id": "front"}]
    client.close()


def test_dict_results_use_public_product_names():
    def handler(request):
        if request.url.path == "/api/sdk/datasets/d1/sources/":
            return httpx.Response(
                200,
                json={
                    "added": 1,
                    "draft_changes": {"has_changes": True, "added": 1},
                },
            )
        raise AssertionError(request.url)

    client = client_with_handler(handler)
    dataset = Dataset("d1", "Data", "", None, False, {"pk": "d1"}, client)
    result = dataset.add_sources(asset_ids=["a1"])
    assert result == {
        "added": 1,
        "unpublished_changes": {"has_changes": True, "added": 1},
    }
    assert dataset.has_unpublished_changes
    client.close()


def test_folder_dataset_and_workflow_items():
    def task_state(stage_id="annotate", priority=0):
        return {
            "uuid": "t1",
            "project_id": "p1",
            "datasource_id": "data1",
            "data_group_id": None,
            "current_stage": {
                "id": stage_id,
                "type": "annotate" if stage_id == "annotate" else "review",
            },
            "previous_stage": None,
            "status": stage_id,
            "assigned_to_id": None,
            "priority": priority,
        }

    def handler(request):
        path = request.url.path
        if path == "/api/sdk/data-assets/folders/f1/items/":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "pk": "a1",
                            "file_name": "cat.png",
                            "generic_type": "img",
                            "folder_id": "f1",
                        }
                    ],
                    "next": None,
                },
            )
        if path == "/api/sdk/datasets/d1/items/":
            version = request.url.params.get("version")
            return httpx.Response(
                200,
                json={
                    "version_number": int(version) if version else None,
                    "results": [
                        {
                            "pk": "di1" if version else "a1",
                            "file_name": "cat.png",
                            "generic_type": "img",
                            "folder_path": "/cats/",
                            "split": "train" if version else "",
                        }
                    ],
                    "next": None,
                },
            )
        if path == "/api/sdk/projects/p1/workflow/stages/":
            return httpx.Response(
                200,
                json={
                    "stages": [
                        {
                            "id": "annotate",
                            "uuid": "s1",
                            "name": "Annotate",
                            "type": "annotate",
                            "task_count": 1,
                        }
                    ]
                },
            )
        if path == "/api/sdk/projects/p1/workflow/stages/annotate/tasks/":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "item_id": "t1",
                            "stage_id": "annotate",
                            "stage_type": "annotate",
                            "status": "annotate",
                            "task_status": "new",
                            "priority": 0,
                            "name": "cat.png",
                            "datasource_id": "data1",
                            "generic_type": "img",
                        }
                    ],
                    "next": None,
                },
            )
        if path == "/api/sdk/workflow-tasks/t1/":
            return httpx.Response(
                200,
                json={
                    "task": task_state(),
                    "queue": {"name": "cat.png", "task_status": "new"},
                    "available_actions": ["complete", "assign"],
                    "move_targets": [],
                },
            )
        if path == "/api/sdk/workflow-tasks/t1/actions/":
            payload = json.loads(request.content)
            assert payload["action"] == "complete"
            assert payload["expected_stage_id"] == "annotate"
            assert payload["idempotency_key"]
            return httpx.Response(
                200,
                json={
                    "task": task_state("review"),
                    "queue": {
                        "name": "cat.png",
                        "task_status": "new",
                        "generic_type": "img",
                    },
                    "available_actions": ["approve", "reject"],
                    "move_targets": [{"stage_id": "complete", "allowed": True}],
                },
            )
        if path == "/api/sdk/workflow-tasks/t1/model-result/":
            payload = json.loads(request.content)
            assert payload["run_id"] == "11111111-1111-1111-1111-111111111111"
            if payload["status"] == "complete":
                assert len(payload["results"]) == 2
                assert payload["results"][0]["type"] == "FeatureCollection"
                assert payload["model_version"] == "geo-v1"
            else:
                assert payload["error"] == "provider failed"
            return httpx.Response(
                200,
                json={
                    "task": task_state(),
                    "queue": {"name": "cat.png", "task_status": payload["status"]},
                    "available_actions": [],
                    "move_targets": [],
                },
            )
        raise AssertionError(request.url)

    client = client_with_handler(handler)
    folder = Folder("f1", "Folder", None, None, "", {"pk": "f1"}, client)
    assert folder.list_items()[0].file_name == "cat.png"

    dataset = Dataset("d1", "Dataset", "", 1, False, {"pk": "d1"}, client)
    draft_item = dataset.list_items()[0]
    assert draft_item.file_name == "cat.png"
    assert draft_item.version_number is None
    item = dataset.list_items(version=1)[0]
    assert item.file_name == "cat.png"
    assert item.version_number == 1
    assert item.data_type == "image"

    project = Project("p1", "Project", {"pk": "p1"}, client)
    stage = project.workflow.get_stage(stage_type="annotate")
    task = stage.get_tasks()[0]
    assert task.name == "cat.png"
    assert task.task_kind == "item_state"
    assert task.parent_item_id is None
    assert task.assignment_id is None
    assert task.consensus_summary is None
    assert client.get_workflow_task("t1").available_actions == ["complete", "assign"]
    task.complete_model_run(
        "11111111-1111-1111-1111-111111111111",
        [
            {"type": "FeatureCollection", "features": []},
            {"type": "FeatureCollection", "features": []},
        ],
        model_version="geo-v1",
    )
    task.fail_model_run("11111111-1111-1111-1111-111111111111", "provider failed")
    task.submit()
    assert task.stage_id == "review"
    assert task.stage_type == "review"
    assert task.name == "cat.png"
    assert task.data_type == "image"
    assert task.task_status == "new"
    assert task.available_actions == ["approve", "reject"]
    assert task.move_targets == [{"stage_id": "complete", "allowed": True}]
    client.close()


@pytest.mark.parametrize(
    ("queue", "datasource_id", "assigned_to_id"),
    [
        (
            {"datasource_id": "private-branch", "assigned_to_id": "voter"},
            "private-branch",
            "voter",
        ),
        (
            {"datasource_id": "private-branch", "assigned_to_id": None},
            "private-branch",
            None,
        ),
        ({}, "parent-data", "parent-owner"),
    ],
)
def test_workflow_task_refresh_uses_queue_resource_identity(
    queue, datasource_id, assigned_to_id
):
    def handler(request):
        assert request.url.path in {
            "/api/sdk/workflow-tasks/vote-1/",
            "/api/sdk/workflow-tasks/vote-1/assign/",
        }
        return httpx.Response(
            200,
            json={
                "task": {
                    "uuid": "parent-task",
                    "task_id": "vote-1",
                    "task_kind": "consensus_branch",
                    "assignment_id": "vote-1",
                    "parent_item_id": "parent-task",
                    "datasource_id": "parent-data",
                    "assigned_to_id": "parent-owner",
                },
                "queue": queue,
            },
        )

    client = client_with_handler(handler)
    task = client.get_workflow_task("vote-1")
    for refreshed in (task, task.assign("voter")):
        assert refreshed.id == "vote-1"
        assert refreshed.assignment_id == "vote-1"
        assert refreshed.parent_item_id == "parent-task"
        assert refreshed.datasource_id == datasource_id
        assert refreshed.assigned_to_id == assigned_to_id
    client.close()


def test_consensus_workflow_task_routes_with_branch_identity_and_refreshes_fields():
    mutation_count = 0

    def detail_envelope(*, task_status="new", summary_location="top"):
        task = {
            "uuid": "branch-task-1",
            "project_id": "p1",
            "datasource_id": "data1",
            "current_stage": {"id": "consensus", "type": "review"},
            "status": "consensus",
            "assigned_to_id": "annotator-1",
            "priority": 0,
            "task_kind": "consensus_branch",
            "parent_item_id": "parent-item-1",
            "assignment_id": "assignment-1",
        }
        summary = {"agreement": 0.75, "task_status": task_status}
        if summary_location == "task":
            task["consensus_summary"] = summary
        return {
            "task": task,
            "queue": {
                "name": "cat.png",
                "task_status": task_status,
                "generic_type": "img",
            },
            "consensus_summary": summary if summary_location == "top" else None,
        }

    def handler(request):
        nonlocal mutation_count
        path = request.url.path
        if path == "/api/sdk/projects/p1/workflow/stages/":
            return httpx.Response(
                200,
                json={
                    "stages": [
                        {
                            "id": "consensus",
                            "uuid": "stage-1",
                            "name": "Consensus",
                            "type": "review",
                            "task_count": 1,
                        }
                    ]
                },
            )
        if path == "/api/sdk/projects/p1/workflow/stages/consensus/tasks/":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "task_id": "branch-task-1",
                            "item_id": "parent-item-1",
                            "parent_item_id": "parent-item-1",
                            "assignment_id": "assignment-1",
                            "task_kind": "consensus_branch",
                            "consensus_summary": {"agreement": 0.5},
                            "stage_id": "consensus",
                            "stage_type": "review",
                            "status": "consensus",
                            "task_status": "new",
                            "priority": 0,
                        }
                    ],
                    "next": None,
                },
            )
        if path == "/api/sdk/workflow-tasks/branch-task-1/consensus-comparison/":
            return httpx.Response(200, json={"components": [{"kind": "annotation"}]})
        if path == "/api/sdk/workflow-tasks/branch-task-1/consensus-selections/":
            payload = json.loads(request.content)
            assert payload["source_assignment_id"] == "assignment-source-2"
            assert payload["component_kind"] == "annotation"
            assert payload["component_locator"] == {"object_id": "obj-1"}
            assert payload["operation"] == "replace"
            assert payload["panel_id"] == "panel-1"
            assert payload["replacement_locator"] == {"object_id": "obj-old"}
            assert payload["expected_stage_id"] == "consensus"
            assert payload["idempotency_key"]
            return httpx.Response(200, json=detail_envelope(task_status="selected"))
        if path in {
            "/api/sdk/workflow-tasks/branch-task-1/claim/",
            "/api/sdk/workflow-tasks/branch-task-1/assign/",
            "/api/sdk/workflow-tasks/branch-task-1/release/",
            "/api/sdk/workflow-tasks/branch-task-1/actions/",
        }:
            if path.endswith("/actions/"):
                payload = json.loads(request.content)
                assert payload["action"] == "complete"
                assert payload["expected_stage_id"] == "consensus"
            mutation_count += 1
            return httpx.Response(
                200,
                json=detail_envelope(
                    task_status=f"refreshed-{mutation_count}",
                    summary_location="task" if mutation_count == 2 else "top",
                ),
            )
        raise AssertionError(request.url)

    client = client_with_handler(handler)
    project = Project("p1", "Project", {"pk": "p1"}, client)
    task = project.workflow.get_stage(stage_id="consensus").get_tasks()[0]

    assert task.id == "branch-task-1"
    assert task.parent_item_id == "parent-item-1"
    assert task.assignment_id == "assignment-1"
    assert task.task_kind == "consensus_branch"
    assert task.consensus_summary == {"agreement": 0.5}
    assert task.get_consensus_comparison() == {"components": [{"kind": "annotation"}]}

    task.copy_consensus_component(
        source_assignment_id="assignment-source-2",
        component_kind="annotation",
        component_locator={"object_id": "obj-1"},
        operation="replace",
        panel_id="panel-1",
        replacement_locator={"object_id": "obj-old"},
    )
    assert task.task_status == "selected"
    mutations = (
        task.claim,
        lambda: task.assign("annotator-2"),
        task.release,
        task.submit,
    )
    for mutation in mutations:
        mutation()
        assert task.id == "branch-task-1"
        assert task.parent_item_id == "parent-item-1"
        assert task.assignment_id == "assignment-1"
        assert task.task_kind == "consensus_branch"
        assert task.consensus_summary == {
            "agreement": 0.75,
            "task_status": task.task_status,
        }
    client.close()


@pytest.mark.parametrize("operation", ["remove", "merge"])
def test_copy_consensus_component_rejects_unknown_operations(operation):
    task = WorkflowTask(
        id="task-1",
        project_id="p1",
        stage_id="review",
        stage_type="review",
        status="review",
        task_status="new",
        priority=0,
        raw={},
        _client=object(),
    )

    with pytest.raises(ValueError, match="operation"):
        task.copy_consensus_component(
            source_assignment_id="assignment-1",
            component_kind="annotation",
            component_locator={"object_id": "obj-1"},
            operation=operation,
        )


def test_consensus_task_detail_and_mutation_accept_task_id_without_uuid():
    def detail_envelope(task_status):
        return {
            "task": {
                "task_id": "branch-task-1",
                "project_id": "p1",
                "current_stage": {"id": "consensus", "type": "review"},
                "status": "consensus",
                "priority": 0,
                "task_kind": "consensus_branch",
                "parent_item_id": "parent-item-1",
                "assignment_id": "assignment-1",
            },
            "queue": {"task_status": task_status},
            "consensus_summary": {"agreement": 0.75},
        }

    def handler(request):
        if request.url.path == "/api/sdk/workflow-tasks/branch-task-1/":
            return httpx.Response(200, json=detail_envelope("new"))
        if request.url.path == "/api/sdk/workflow-tasks/branch-task-1/claim/":
            return httpx.Response(200, json=detail_envelope("claimed"))
        raise AssertionError(request.url)

    client = client_with_handler(handler)
    task = client.get_workflow_task("branch-task-1")
    assert task.id == "branch-task-1"
    task.claim()
    assert task.id == "branch-task-1"
    assert task.task_status == "claimed"
    client.close()


def test_consensus_queue_parser_accepts_alias_without_overriding_canonical_summary():
    queue_row = {
        "task_id": "branch-task-1",
        "item_id": "parent-item-1",
        "stage_id": "consensus",
        "stage_type": "review",
        "status": "consensus",
        "task_status": "new",
        "priority": 0,
        "task_kind": "consensus_branch",
    }
    canonical_summary = {"agreement": 0.9}
    alias_summary = {"agreement": 0.4}

    canonical_task = WorkflowTask._from_queue(
        object(),
        "p1",
        {
            **queue_row,
            "consensus_summary": canonical_summary,
            "consensus": alias_summary,
        },
    )
    alias_task = WorkflowTask._from_queue(
        object(),
        "p1",
        {**queue_row, "consensus": alias_summary},
    )

    assert canonical_task.consensus_summary == canonical_summary
    assert alias_task.consensus_summary == alias_summary


def test_folder_navigation_supports_children_and_all():
    def handler(request):
        params = request.url.params
        if params.get("parent_id") == "root":
            rows = [{"pk": "child", "name": "Child", "parent_id": "root"}]
        elif params.get("all") == "1":
            rows = [
                {"pk": "root", "name": "Root"},
                {"pk": "child", "name": "Child", "parent_id": "root"},
            ]
        else:
            rows = [{"pk": "root", "name": "Root"}]
        return httpx.Response(200, json={"results": rows, "next": None})

    client = client_with_handler(handler)
    root = client.assets.folders()[0]
    assert [folder.id for folder in root.children()] == ["child"]
    assert [folder.id for folder in client.assets.all_folders()] == ["root", "child"]
    client.close()


def test_cloud_entry_uses_readable_types():
    assert CloudEntry._from_raw({"name": "image.png", "type": "REG"}).type == "file"
    assert CloudEntry._from_raw({"name": "incoming/", "type": "DIR"}).type == "folder"


def test_attach_results_cover_preview_and_commit_outcomes():
    preview = AttachPreview._from_raw(
        {
            "requires_fps": True,
            "resolved_unique_asset_count": 4,
            "already_attached_count": 1,
            "will_publish_project_version": True,
            "dataset_version_count": 2,
            "video_count": 1,
            "processing_video_count": 1,
        }
    )
    assert preview.resolved_asset_count == 4
    assert preview.will_publish_version

    result = AttachResult._from_raw(
        {
            "created_count": 3,
            "unassigned_count": 2,
            "created_project_data_ids": ["project-data-1"],
            "created_datasource_ids": ["data-unit-1"],
            "upload_session_id": "queue-1",
            "already_attached_count": 1,
            "resolved_unique_asset_count": 4,
            "link_ids": ["attachment-1"],
            "created_project_group_ids": ["group-1"],
        }
    )
    assert result.data_item_ids == ["data-unit-1"]
    assert result.batch_queue_id == "queue-1"
    assert result.resolved_asset_count == 4
    assert result.attachment_ids == ["attachment-1"]
    assert result.data_group_ids == ["group-1"]
