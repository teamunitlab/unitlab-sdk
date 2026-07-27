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
                "download_formats": "COCO, JSONL",
                "is_public": True,
            },
        )

    client = client_with_handler(handler)
    release = client.releases.get("r1")
    assert release.id == "r1"
    assert release.data_item_count == 3
    assert release.data_type == ""
    assert release.download_formats == ["COCO", "JSONL"]
    assert release.is_public

    monkeypatch.setattr(
        "unitlab.resources.releases._downloader.download_annotation",
        lambda api, release_id, split: f"{release_id}-{split}.zip",
    )
    assert release.download("train") == "r1-train.zip"
    client.close()


def test_multimodal_release_uses_all_available_types():
    def handler(request):
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
    assert client.get_workflow_task("t1").available_actions == ["complete", "assign"]
    task.submit()
    assert task.stage_id == "review"
    assert task.stage_type == "review"
    assert task.name == "cat.png"
    assert task.data_type == "image"
    assert task.task_status == "new"
    assert task.available_actions == ["approve", "reject"]
    assert task.move_targets == [{"stage_id": "complete", "allowed": True}]
    client.close()


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
