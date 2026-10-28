<p align="center">
    <br>
        <img src="https://unitlab-storage.s3.us-east-2.amazonaws.com/Logo.png" width="400"/>
    <br>
<p>

<p align="center">
    <a href="https://pypi.org/project/unitlab/">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/unitlab">
    </a>
    <a href="https://pypi.org/project/unitlab/">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/unitlab">
    </a>
    <a href="https://github.com/teamunitlab/unitlab-sdk">
        <img alt="Downloads" src="https://img.shields.io/pypi/dm/unitlab">
    </a>
    <a href="https://github.com/teamunitlab/unitlab-sdk/blob/main/LICENSE.md">
        <img alt="License" src="https://img.shields.io/pypi/l/unitlab">
    </a>
</p>

[Unitlab.ai](https://unitlab.ai/) is an AI-driven data annotation platform that automates the collection of raw data, facilitating collaboration with human annotators to produce highly accurate labels for your machine learning models. With our service, you can optimize work efficiency, improve data quality, and reduce costs.

![](https://unitlab-storage.s3.us-east-2.amazonaws.com/unitlab.png)

# Unitlab Python SDK

Native Python and CLI access to Unitlab projects, Ontologies, Assets, datasets,
published versions, Batch Queues, Releases, cloud storage, and multimodal Data
Groups and Workflow Tasks.

## Install

```bash
pip install --upgrade unitlab
```

Python 3.10 or newer is required.

## Authenticate

Create an API key in Workspace settings, then use environment variables:

```bash
export UNITLAB_API_KEY="YOUR_API_KEY"
export UNITLAB_API_URL="https://api.unitlab.ai"  # optional
```

Or configure the CLI once:

```bash
unitlab configure --api-key YOUR_API_KEY
unitlab configure --api-url https://api.unitlab.ai
```

You can also pass both values directly:

```python
from unitlab import UnitlabClient

client = UnitlabClient(
    api_key="YOUR_API_KEY",
    api_url="https://api.unitlab.ai",
)
```


### 1. Upload multimodal data to a project

```python
from unitlab import UnitlabClient

client = UnitlabClient()
project = client.projects.create("Medical review")
batch = project.upload("./multimodal-data")
status = batch.wait()

print(batch.uploaded, batch.batch_queue_id)
```

The directory may mix images, video, audio, text, PDFs, DICOM, NIfTI, and NRRD.
One call creates one Batch Queue. Call `batch.wait()` when the next operation
depends on server-side processing. Lidar scenes are uploaded with
`generic_type="pointcloud"`; see [Lidar scenes](#lidar-scenes).

### 2. Curate in Assets, publish a dataset, and attach it

```python
from unitlab import UnitlabClient

client = UnitlabClient()
project = client.projects.create("Quality review")

uploaded = client.assets.upload(
    "./multimodal-data",
    folder="Raw data",
    tags=["incoming"],
)

dataset = client.datasets.create(
    "Review set",
    folder_ids=[uploaded.folder_id],
)
version = dataset.publish_version("Initial snapshot")

attached = client.attach_dataset(
    project,
    dataset,
    version=version.version_number,
)

print(attached.created_count)
```

Datasets are version-first. Editing a dataset creates Unpublished changes;
`publish_version()` freezes a version, and projects attach that published snapshot.
A folder given to `create()` or `add_sources()` is followed: files added to it
later join the draft, files moved out or trashed leave it, and each file keeps
its sub-folder path. `remove_assets()` takes files out of the draft only; a
followed folder does not bring them back until they are added again with
`add_sources()`. Published versions never change.

### 3. Import existing cloud data

```python
from unitlab import UnitlabClient

client = UnitlabClient()
project = client.projects.create("Cloud review")
storage = next(
    item for item in client.cloud_storages.list() if item.name == "Production data"
)

batch = project.import_cloud(
    storage,
    ["incoming/study-001/"],
)
status = batch.wait()

print(batch.batch_queue_id)
```

Directory paths end in `/`. Cloud credentials are never returned through the
SDK; list and browse responses expose only safe storage metadata.

## Resource handles

Namespace entrypoints return typed resource handles:

```python
project = client.projects.get("PROJECT_ID")
projects = client.projects.list()
dataset = client.datasets.get("DATASET_ID")
datasets = client.datasets.list()
folder = client.assets.folder("FOLDER_ID")
folders = client.assets.folders()
```

### Ontologies

```python
from unitlab import OntologyStructure, RadioAttribute, Shape

structure = OntologyStructure()
cat = structure.add_object("Cat", Shape.BOUNDING_BOX)
colour = cat.add_attribute(RadioAttribute, "Colour", required=True)
colour.add_option("Black")
colour.add_option("White")

ontology = client.ontologies.create("Cat labels", structure=structure)
project = client.projects.create(
    "Cat review",
    ontology_hash=ontology.id,
)
```

Use `client.ontologies.get()`, `client.ontologies.list()`, and
`ontology.save()` for the rest of the Ontology lifecycle. Project attachment
copies the Workspace Ontology so Unitlab can preserve project-specific version
history.

### Projects and Batch Queues

```python
projects = client.projects.list()
project = client.projects.get("PROJECT_ID")
project = client.projects.create("Road scenes")

batch = project.upload("./data", fps=2.0)
tiled_batch = project.upload("./maps")

status = batch.status()
status = batch.wait(timeout=1800)

queues = project.batch_queues()
queue = project.batch_queue(batch.batch_queue_id)
items = queue.data()
status = queue.wait()
```

`ProcessingStatus` exposes `total`, `completed`, `processing`, and `failed`.
Completion means `processing == 0`; a completed Batch Queue may still report
individual failures.

GeoTIFF and whole-slide files are detected automatically. Large tiled files
upload directly to storage in bounded parts. Tiled processing can take hours,
so use a longer timeout such as `batch.wait(timeout=25200)` when the next
operation depends on the generated COG/DZI derivative.

Video, medical (NIfTI, NRRD, DICOM), audio and PDF files larger than 64 MiB
also upload directly to storage, up to 500 MiB each; smaller ones keep the
ordinary upload. A large medical file becomes one volume on its own and is not
grouped with other files of the batch into a series.

DICOM files named without a usable extension (`IM00001`, or a UID) are found by
their content when a folder is uploaded and are sent as medical; nothing needs
to be renamed.

### Lidar scenes

A lidar scene is one item whatever it is made of. It is uploaded only when the
type is named; without it `.pcd`, `.ply`, `.bin` and scene `.zip` files are
skipped. The workspace needs lidar scenes enabled.

```python
from unitlab import detect_scenes

# Look first: what would be uploaded, nothing is sent.
for scene in detect_scenes("./recordings").scenes:
    print(scene.name, scene.frame_count, scene.point_sensors, scene.cameras)

batch = project.upload("./recordings", generic_type="pointcloud")
batch.wait()

for item_id in batch.data_item_ids:
    status = project.scene_status(item_id)
    print(status.status, status.frame_count, status.error)

project.retry_scene(item_id)  # a failed scene, about a minute after it failed
```

What `source` may be:

- One file: a `.pcd`, `.ply` or `.bin` cloud, or a `.zip` that contains such
  frames or a `scene.json`. Any other `.zip` is refused.
- A folder with a `scene.json`, or with the point clouds of one sensor
  (`drive_01/lidar/000.pcd`, ...). Image folders whose file names match the
  frames become its cameras (`drive_01/cam_front/000.jpg`).
- A folder with one subfolder per sensor that share file names. This is read as
  one scene with several sensors; pass `split_sensor_folders=True` when each
  folder is a recording of its own.
- A folder that holds several such scenes: each one is uploaded as its own
  item. Scene files left over in the folder are one scene each.
- A nuScenes dataset (the folder with `samples/` and `v1.0-*/`): one scene per
  recording, key frames only, with the calibration taken from its tables.

Other files in the folder are not uploaded by this call; upload the folder once
more without the type for ordinary media. A scene is limited to 20 GiB and
1,000 frames, and one data unit is used per frame.

`batch.wait()` covers scenes like any other upload. A failed scene is not in
`project.data_units()`; find it in the Batch Queue (`queue.data()`) and ask
`project.scene_status(item_id)` for the reason.

Scenes go into Assets the same way, and the existing Asset methods apply:

```python
result = client.assets.upload(
    "./recordings", generic_type="pointcloud", folder="Lidar"
)
asset = result.assets[0]
status = asset.wait()          # status.frame_count, status.error
asset.retry()                  # a failed scene
asset = client.assets.asset("ASSET_ID")  # a handle by ID, for status and retry
```

`release.download_files()` writes a scene that was uploaded as a folder under
`<item file name>/` with the paths it was uploaded with.

### Data Units and project lifecycle

```python
project.update(name="Road review v2", description="Second collection")

units = project.data_units(data_type="image", status="annotate")
unit = client.get_data_unit(project.id, units[0].id)

for unit in units:
    print(unit.kind, unit.name, unit.status)
```

A loose file is one `datasource` Data Unit. A Data Group is one `group` Data
Unit whose `items` contain its tile summaries; member files are not duplicated
in the top-level list. `project.delete()` soft-deletes the Project and schedules
the existing backend cleanup.

### Assets and folders

```python
folders = client.assets.folders()
folder = client.assets.create_folder("Raw data")
children = folder.children()
every_folder = client.assets.all_folders()
items = folder.list_items()

result = client.assets.upload("./images", folder_id=folder.id, tags=["train"])
asset = result.assets[0]

tiled = client.assets.upload(
    "./slides",
    folder_id=folder.id,
)
tiled.assets[0].wait()

cloud_folder = client.assets.create_cloud_folder(
    "Incoming",
    "CLOUD_STORAGE_ID",
    prefix="incoming/",
)
cloud_folder.sync_cloud()  # Tiled files are registered as processing Assets.
```

`sync_cloud()` returns `registered`, `folders`, `skipped`, `skipped_in_trash`
and `missing`. Files you put in library Trash are not added back by a sync.
Files the bucket no longer lists stay in the library but are left out of
dataset drafts, new versions and attach until a later sync finds them again.

### Datasets and published versions

```python
dataset = client.datasets.create(
    "Training set",
    folder_ids=["FOLDER_ID"],
)

dataset.add_sources(asset_ids=["ASSET_ID"])
dataset.remove_assets(["OTHER_ASSET_ID"])  # Draft only, like the web app.
changes = dataset.unpublished_changes()
version = dataset.publish_version("Added edge cases")
versions = dataset.versions()
items = dataset.list_items(version=version.version_number)
```

In folder and Dataset item lists, `file_name` is the stored name, the one
releases use; match files by it. `uploaded_name` is the name shown in the web
app. They differ for files uploaded to a project (`a91f...3c.jpg` and
`cat.jpg`) and are the same for files uploaded to the library.

### Workflow Tasks

```python
workflow = project.workflow
annotate = workflow.get_stage(name="Annotate")

for task in annotate.get_tasks():
    task.assign("USER_ID")
    task.submit()
```

Review Tasks provide `approve()` and `reject()`. Managers can use `move()` for
a direct stage override and `get_timeline()` to inspect Task history.

### Agent webhooks (no task polling)

An Agent stage tells your HTTPS webhook which tasks are ready: one event per
task, sent as soon as it enters the stage. The webhook carries IDs only; your service reads and saves annotations with a workspace API
key, then reports the run. A successful webhook response acknowledges delivery;
only `complete_agent` advances the task through the stage's single outgoing edge.

```python
from unitlab import AgentWebhook, UnitlabClient

client = UnitlabClient()  # workspace API key


def handle(body: bytes, headers, secret: str) -> int:
    """Return the HTTP status to answer the webhook with."""
    # body: original request bytes; headers: incoming HTTP headers.
    # secret: the signing secret configured in the Agent stage. A stage saved
    # without one sends unsigned events: use AgentWebhook.parse(body) instead.
    event = AgentWebhook.verify(body, headers, secret)
    if event.is_test:  # "Test connection": acknowledge only
        return 204
    ref = event.task
    task = client.get_workflow_task(ref.task_id)
    for item in task.get_annotations():  # one item, or one per Data Group panel
        # item.document: the item's UUEF; your_model returns a new one, or None
        # when it changes nothing (a save always writes a new version).
        document = your_model(item.document, item.source_url)
        if document is not None:
            task.save_annotations(item, document)  # replaces the item whole
    task.complete_agent(ref.run_id)
    # On model failure: task.fail_agent(ref.run_id, "A useful processing error")
    return 200
```

The payload is a [CloudEvents 1.0](https://cloudevents.io/) structured JSON event
(`Content-Type: application/cloudevents+json`,
`type: ai.unitlab.agent.task.ready.v1`) whose `data` is:

```json
{
  "project_id": "PROJECT_ID",
  "workflow_id": "WORKFLOW_ID",
  "stage_id": "STAGE_ID",
  "task": {"task_id": "TASK_ID", "run_id": "RUN_ID", "datasource_ids": ["DATASOURCE_ID"]}
}
```

Each event carries exactly one task (there is no batching).
`AgentWebhook.verify` (or `parse`) returns `id`, `project_id`, `workflow_id`, `stage_id` and
`task`, an `AgentTaskRef(task_id, run_id, datasource_ids)`. Any missing
or wrongly typed field, or a `task` that is not one object, raises `ValueError`.

The stage's **Test connection** button sends the same envelope (signed only
when the stage has a secret) with
`type: ai.unitlab.agent.test.v1` and `data: {"test": true, "project_id", "workflow_id",
"stage_id", "task": null}`, where the IDs may be `null` for an unsaved workflow.
For it `event.is_test` is `True` and `event.task` is `None`: answer `2xx` and do
nothing else.

Signatures use [Standard Webhooks](https://www.standardwebhooks.com/):
`webhook-id`, `webhook-timestamp`, and `webhook-signature`. The secret is
optional; a stage without one sends no `webhook-signature`.
Verification uses HMAC-SHA256 over `id.timestamp.raw_body`, accepts `v1,BASE64`
signatures and a 300-second clock tolerance, and supports plain configured secrets
or `whsec_` base64 keys. Pass the original body bytes; parsing and re-encoding JSON
changes the signed content. Keep your receiver clock synchronized.

`get_annotations()` returns one `TaskAnnotation` per item with `datasource_id`,
`generic_type`, `revision`, `source_url` (a signed media URL; empty or `None` for an item without a file),
`format` and `document`: the item's UUEF, the same per-item JSON a UUEF release
exports. Its JSON Schema is `uuef.schema.json`, at the root of every UUEF
release export (`client.releases.create(project, export_type="UUEF")`). A
large document arrives as a signed link that the SDK downloads, so `document`
is always one whole dict. Hidden objects are included with `visible: false`.
Tracks (video, medical) list their stored keyframes only;
`get_annotations(only_keyframes=False)` lists every frame a track is visible
on. Both save back safely: a save keeps only frames marked `keyframe: true`.

`save_annotations(item, document)` replaces the item with `document` and
returns the new revision. It is a whole overwrite: objects missing from the
document are deleted, and a save made by someone else since your read is
overwritten (no revision check, no `ConflictError`). Keep the `id` of every
object you keep. Every object in the saved version is credited to the API
key's creator, so skip the save when your model changed nothing. Afterwards
`item.revision` and `item.document` hold what was saved. A save is the
Agent's answer, so it works only while the task is in an Agent stage: once a
manager moved the task out, it is refused (`ValidationError`, 400) and nothing
is saved, like a late `complete_agent`. Reads work in any stage. Two other
answer formats are accepted, each also
replacing the item whole:

```python
# Geospatial and pathology items: an RFC 7946 FeatureCollection (lon/lat, raster CRS units or pixels).
task.save_annotations(item, feature_collection, format="geojson")
# Image items: the custom-model reply JSON ("bboxes", "polygons", "brush", ...).
task.save_annotations(item, model_reply, format="model")
```

A format the item's type does not take is refused (`ValidationError`, 400) and
nothing is saved. One bad shape never refuses the whole document: a
self-crossing outline is repaired, a shape past the media's edge is clipped, a
shape that cannot be stored (no area) is skipped, and the rest is saved.

After a `geojson` or `model` save `item.document` is `None`:
read again to see the UUEF the server built. A document over 64 MiB is sent to
a signed upload link first; the SDK does this for you.

Lidar scenes (`generic_type == "pointcloud"`) are not UUEF yet: their `format`
is `"native"`, `document` is `None` and `result` holds the editor's
track-first result, `{"tracks": {"cuboids3d": {"<track id>": {"ranges":
[[0, 21]], "value": 7, "keyframes": {"0": {...}, "20": {...}}}}},
"item_properties": {...}}`, stitched from its pages. Save the complete new
result with `save_annotations(item, result)`: only changed tracks are sent
(nothing when unchanged), in parts within the server's limits, each an
ordinary save carrying the previous part's revision. A stale revision raises
`ConflictError` with `code == "revision_conflict"`; parts sent before it stay
saved: read again and save again. A track larger than one save takes raises
`ValueError` before anything is sent. Leave `segments3d` tracks as you read
them (their points live in label arrays).

The raw HTTP calls, all with `Authorization: Api-Key <key>`:

| Call | Body |
| --- | --- |
| `GET /api/sdk/workflow-tasks/{task_id}/annotations/?only_keyframes=true` | a row has `document`, or `document_url` (GET it without the API key) |
| `PUT /api/sdk/workflow-tasks/{task_id}/annotations/` | `{"datasource_id", "format", "document"}` or `{"datasource_id", "format", "document_upload_id"}` |
| `POST /api/sdk/workflow-tasks/{task_id}/annotations/uploads/` | `{"datasource_id", "format", "size"}`; then PUT the JSON to the returned `upload_url` without the API key, `Content-Type: application/json` |
| `PUT /api/sdk/workflow-tasks/{task_id}/annotations/` (lidar) | `{"datasource_id", "revision", "result"}` |
| `GET /api/sdk/workflow-tasks/{task_id}/annotations/pages/` (lidar) | query: the item's `pages.params` plus `cursor` |
| `POST /api/sdk/workflow-tasks/{task_id}/agent-result/` | `{"run_id", "status": "complete"}` or `{"run_id", "status": "failed", "error"}` |

Delivery can repeat. Deduplicate processing by `run_id`. A run not completed
within 7 days (fixed, not a stage setting) fails, as does one reported with
`fail_agent` (its `error` is cut to the 4,000 characters the server takes); the
task stays in the stage until a manager clicks Retry, which starts a new run
with a new `run_id` and refuses results for the old one. Production receivers
should acknowledge with `2xx` only after durable enqueueing, then process
asynchronously. Never log signing secrets, API keys, full payloads, or signed
media URLs.

For a local smoke test, give the stage a signing secret (the sample verifies
signatures) and run [the receiver](examples/agent_webhook.py) with it as
`UNITLAB_AGENT_WEBHOOK_SECRET`, plus `UNITLAB_API_KEY` and, for a non-default
API, `UNITLAB_API_URL` in its environment:

```bash
python examples/agent_webhook.py
cloudflared tunnel --url http://127.0.0.1:8091
```

Run the tunnel command in a second terminal and put its HTTPS address in the Agent
stage. The sample's `transform()` returns `None`, so it saves nothing and only
completes the run; replace it with your model.

### Attach data

```python
preview = project.attach_preview(dataset_ids=[dataset.id])

result = project.attach(dataset_ids=[dataset.id])

# Attach an exact version instead of latest:
result = project.attach(
    dataset_versions=[
        {"dataset_id": dataset.id, "version_number": 2},
    ]
)

for source in project.attached_sources():
    print(source.name, source.detach_preview())
    # source.detach() removes only the Project copy and keeps annotations.
```

Video attachment may require `fps=`. Call `attach_preview()` when you need
counts before committing; `attach()` validates the same rule and raises an
actionable `ValidationError` if FPS is missing.

A dataset in `dataset_ids` that has no published version yet is listed in
`preview.unpublished_datasets` and left out of `attach()`; the result names it
in `skipped_datasets`. Pass `publish_unpublished=True` to publish such datasets
as v1 and attach them (`published_datasets`). If nothing else is selected, the
attach is refused and names the dataset.

Files in library Trash, and cloud files the last sync of their folder did not
find in the bucket, are left out of an attach and of a new version;
`preview.skipped_files` and `result.skipped_files` count them as
`{"in_trash": n, "missing_in_bucket": n}`. One attach into a Project runs at a
time: a second one meanwhile raises `ConflictError` and attaches nothing.

### Cloud storage

```python
storages = client.cloud_storages.list()
storage = storages[0]

for entry in storage.browse(prefix="incoming/"):
    print(entry.name, entry.type, entry.size)

batch = project.import_cloud(
    storage,
    ["incoming/file.png", "incoming/study/"],
)
status = batch.wait()
```

### Import annotation JSON

Media can come from S3 while the annotation JSON stays on your computer:

```python
project = client.projects.get("PROJECT_ID")
media = project.import_cloud("CLOUD_STORAGE_ID", ["images/"])
status = media.wait()
if status.failed:
    raise RuntimeError("Some media failed processing; inspect the Batch Queue.")

batch = project.annotation_imports.create(
    "./predictions.json",
    source_name="my-model",  # Reuse this namespace for the same prediction source.
)
print(batch.preview["counts"], batch.preview["issues"])
# Inspect the preview before saving labels. Approval is a separate review step.
report = batch.commit()
print(report)
```

Supported inputs are COCO JSON, Unitlab exports (UUEF item JSON, Audio JSON and
GeoJSON, as `.json` or `.geojson`), `unitlab-image/1` and `unitlab-video/1`. They
cover image, video, medical, document, audio, time series, text, HTML, geospatial
and pathology items. A UUEF file holds one item: import each file as its own batch.
Each JSON file is limited to 80 MiB. The backend matches original media paths/IDs,
with a unique-filename fallback; ambiguous names require an explicit mapping.
YOLO text/ZIP files and other tools' project files are not accepted by this importer.

For COCO video, pass `frame_mapping_file="./frames.json"` in
`unitlab-frame-map/1` format. Use `track_profile="attributes.track_id"` only for
COCO exports with that explicit track-ID convention. Import video media at its
original frame rate; annotations for frames omitted by sampling are rejected.

`project.annotation_imports.sources()` lists saved prediction sources, and
`project.annotation_imports.media(search="road.jpg")` finds media IDs for mappings.
Pass `source_id=` instead of `source_name=` to reuse a source by ID. Set
`options={"stable_ids": True}` only when your exporter keeps annotation IDs stable
between prediction runs. Otherwise the default protects existing objects from
unconfirmed ID reuse.

After processing completes or you supply mappings, call `batch.refresh()` to
rebuild the preview. `batch.refresh(options={...})` replaces all import options;
omitting `options` preserves them. Supported options are `stable_ids`,
`media_mapping`, `class_mapping`, `object_mapping`, and `review_mapping`.

`batch.commit()` preserves conflicts and human deletions by default. To resolve
a specific preview annotation, pass `decisions={annotation_key: "keep"}` (or
`"incoming"` / `"skip"`). Invalid records prevent the whole commit unless you
explicitly choose `allow_partial=True`. The report includes created, updated,
kept, unchanged and skipped counts when applicable. A stale preview raises
`ConflictError`; inspect a refreshed preview before committing again. If a
commit response is lost, repeat the same batch's `commit()` with the same
decisions; the server returns the saved report without duplicating labels.

For annotations already in connected storage, omit the local file and pass
`cloud_storage=storage`, `annotation_key="labels/predictions.json"`, and optionally
`frame_mapping_key="labels/frames.json"`. Keys are relative to that connection's
prefix. Media and annotations must resolve within the API key's workspace and
the selected project.

This requires a backend with the `/api/sdk/projects/{id}/annotation-imports/`
routes and the annotation-import database migration installed. Commit requires
a user-created API key so saved labels have an audit author. Legacy keys without
a creator can preview but receive `PermissionDeniedError` when committing.

### Data Groups

Let Unitlab suggest a filename pattern:

```python
folder = client.assets.folder("FOLDER_ID")
grouped = folder.auto_group()
```

Or compile a literal filename template:

```python
from unitlab import tiles_from_template

config = tiles_from_template(
    "{patient_id}_{view}",
    tile_values={
        "view": ["L_CC", "R_CC", "L_MLO", "R_MLO"],
    },
)

estimate = folder.estimate_grouping(config)
grouped = folder.auto_group(config)
```

For folders above 5,000 files or estimates above 1,000 groups, `auto_group()`
raises an actionable `ValidationError`. Split the source into smaller folders
and retry; the SDK does not return a job that will never run.

### Releases

Releases are exported annotation snapshots. They are separate from Assets
datasets.

```python
release = client.releases.create(
    project,
    export_type="UUEF",
    split_ratios={"train": 80, "test": 20},
)

releases = client.releases.list()
release = client.releases.get(release.id)

annotation_path = release.download(split="train", dest="./release-annotations")
files_folder = release.download_files(dest="./release-files")
```

`client.releases.create()` waits until the Release is ready. To return immediately
and wait later:

```python
release = client.releases.create(project, wait=False)
release.wait(timeout=7200)  # Wait before downloading.
```

Check progress with `release.refresh()`, then read `release.status` and
`release.progress`. Lists show ready Releases; use `client.releases.get(release_id)`
to check one still being prepared.

Release item download tokens are persistent Unitlab URLs. For files stored in
customer cloud storage, the URL redirects to a signed target URL; only that target
URL is temporary.

## CLI quick reference

```bash
# Projects and Batch Queues
unitlab project create "Medical review" --ontology ONTOLOGY_ID
unitlab project list
unitlab project detail PROJECT_ID
unitlab project update PROJECT_ID --name "Medical review v2"
unitlab project data-units PROJECT_ID --data-type image
unitlab project data-unit PROJECT_ID DATA_UNIT_ID
unitlab project sources PROJECT_ID
unitlab project detach-source PROJECT_ID SOURCE_LINK_ID --preview
unitlab project upload PROJECT_ID --source ./data
unitlab project upload PROJECT_ID --source ./maps
unitlab project upload PROJECT_ID --source ./recordings --type pointcloud --dry-run
unitlab project upload PROJECT_ID --source ./recordings --type pointcloud
unitlab project upload PROJECT_ID --source ./rig --type pointcloud \
  --split-sensor-folders
unitlab project scene-status PROJECT_ID ITEM_ID
unitlab project scene-retry PROJECT_ID ITEM_ID
unitlab batch-queue list PROJECT_ID
unitlab batch-queue detail PROJECT_ID BATCH_QUEUE_ID
unitlab batch-queue status PROJECT_ID BATCH_QUEUE_ID
unitlab batch-queue data PROJECT_ID BATCH_QUEUE_ID
unitlab batch-queue wait PROJECT_ID BATCH_QUEUE_ID --timeout 1800

# Cloud import and attach
unitlab project import-cloud PROJECT_ID CLOUD_STORAGE_ID incoming/study/
unitlab project attach PROJECT_ID --dataset DATASET_ID
unitlab project attach PROJECT_ID --dataset DATASET_ID --preview
unitlab project attach PROJECT_ID --dataset-version DATASET_ID:2
unitlab project attach PROJECT_ID --dataset DATASET_ID --publish-unpublished

# Assets
unitlab assets upload ./data --folder "Raw data" --tag incoming
unitlab assets upload ./slides --folder "Slides"
unitlab assets upload ./recordings --folder "Lidar" --type pointcloud
unitlab assets status ASSET_ID
unitlab assets retry ASSET_ID

# Folders
unitlab folders create "Raw data"
unitlab folders create "Incoming" \
  --cloud-storage CLOUD_STORAGE_ID --prefix incoming/
unitlab folders list
unitlab folders list --parent PARENT_FOLDER_ID
unitlab folders detail FOLDER_ID
unitlab assets upload ./data --folder-id FOLDER_ID
unitlab folders sync-cloud FOLDER_ID

# Data Groups
unitlab assets group FOLDER_ID --config grouping.json
unitlab assets group FOLDER_ID --config grouping.json --preview
unitlab assets group FOLDER_ID --preview
unitlab assets group FOLDER_ID \
  --template '{patient_id}_{view}' \
  --tile-values view=L_CC,R_CC,L_MLO,R_MLO

# Datasets
unitlab dataset list
unitlab dataset create "Training set" --folder FOLDER_ID
unitlab dataset detail DATASET_ID
unitlab dataset add-sources DATASET_ID --asset ASSET_ID
unitlab dataset remove-assets DATASET_ID --asset ASSET_ID
unitlab dataset unpublished-changes DATASET_ID
unitlab dataset publish DATASET_ID --title "Initial snapshot"
unitlab dataset versions DATASET_ID

# Releases (create returns immediately; add --wait to wait until ready)
unitlab release create PROJECT_ID --format UUEF --splits train=100
unitlab release wait RELEASE_ID --timeout 7200
unitlab release list
unitlab release detail RELEASE_ID
unitlab release download RELEASE_ID --split-type train --dest ./release-annotations

# Ontologies
unitlab ontology list
unitlab ontology list --title-like Medical --created-after 2026-01-01
unitlab ontology create "Medical labels" --structure ontology.json
unitlab ontology update ONTOLOGY_ID --title "Medical labels v2"

# Cloud storage
unitlab cloud list
unitlab cloud browse CLOUD_STORAGE_ID --prefix incoming/
```

Run `unitlab COMMAND --help` for every option.

## License

[MIT](LICENSE.md)
