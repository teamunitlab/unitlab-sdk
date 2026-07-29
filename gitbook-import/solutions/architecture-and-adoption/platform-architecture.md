---
description: "Map Unitlab data, project, human, model, automation, quality, and delivery layers into an enterprise system."
icon: building-shield
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Enterprise architects, security, data engineering, ML operations, solution architects, and platform owners. **Outcome:** Define system boundaries, identities, data movement, state transitions, processing monitors, and reproducible delivery contracts.
{% endhint %}

## Decision to make

State the operational or model decision in one sentence. Then list the minimum evidence, temporal or spatial context, allowed uncertainty, and downstream representation required to make that decision consistently. Do not begin with a tool list; begin with the decision contract.

## Before you begin

- A named business or model decision that the data program must support.
- Representative normal, difficult, ambiguous, invalid, and failure examples.
- Named owners for source data, labeling policy, annotation operations, review, and downstream acceptance.
- A downstream consumer that can validate one sample release.

## Operating blueprint

~~~mermaid
flowchart LR
  A["Source systems"]
  B["Durable Data Space"]
  C["Project operations"]
  D["Automation + quality"]
  E["Release consumers"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Map source systems, local upload paths, cloud connections, and durable Asset ownership
{% endstep %}
{% step %}
### 2. Define how folders, metadata, tags, filters, Data Groups, embeddings, and dataset versions represent reusable data
{% endstep %}
{% step %}
### 3. Define project boundaries for Instructions, ontology, workflow, queues, annotation, review, issues, and statistics
{% endstep %}
{% step %}
### 4. Map human identities, service identities, roles, project assignment, model endpoints, and secret ownership
{% endstep %}
{% step %}
### 5. Separate accepted requests from Batch Queue or release processing completion and monitoring
{% endstep %}
{% step %}
### 6. Define release formats, source inclusion, splits, stable references, and downstream consumers
{% endstep %}
{% step %}
### 7. Document audit records, retention, support boundaries, recovery ownership, and change-control triggers
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

Unitlab connects four operating layers:

1. **Data Space** — ingest, connect, organize, filter, group, explore, and version raw or curated data.
2. **Annotation** — annotate images, video, audio, text, medical data, documents, and grouped multimodal cases.
3. **Quality operations** — define ontologies, route tasks through workflows, assign people, review outcomes, manage issues, and preserve instructions.
4. **AI and automation** — use interactive labeling assistance, tracking, model stages, external AI models, API keys, a Python SDK, and a CLI.

The platform is best understood as a lifecycle:

```text
Raw files or cloud data
        ↓
Assets and folders
        ↓
Curation, filtering, embeddings, and multimodal grouping
        ↓
Versioned dataset
        ↓
Project + ontology + workflow
        ↓
Model assistance + human annotation + review
        ↓
Versioned release with annotations, files, metadata, and splits
        ↓
Training, evaluation, traceability, or another controlled project
```

This operating model matters because most training-data failures are not drawing-tool failures. They come from ambiguous label definitions, missing context, weak assignment rules, unreviewed model output, accidental dataset changes, and an inability to reproduce the exact data used by a model. Unitlab provides product surfaces for each part of that operating problem.

## Workspace navigation

The Unitlab workspace is organized into:

- **Annotation:** Projects, Workflows, Ontologies
- **Data Space:** Assets, Datasets, Releases
- **AI Suite:** My AI Models, Public AI Models
- **Workspace operations:** Documentation/Instructions, Members, Settings, cloud storage, roles, and API keys

Each area uses the same core concepts—projects, data, ontologies, workflows, queues, review, and releases—so teams can standardize how training data moves from source to production-ready output.


## 2. The Unitlab object model

Several platform terms sound similar but serve different purposes. Keeping them distinct makes product explanations much clearer.

| Object | Purpose | What changes over time |
|---|---|---|
| **Asset** | A source file or data item stored in or connected to Data Space | Metadata, tags, folder placement, and curation state |
| **Folder** | A source-oriented container for assets; it can also represent a cloud-backed location | Contents, synchronization state, subfolders, and grouping |
| **Data Group** | A related set of files treated as one multimodal or multiview unit | Group membership and tile layout |
| **Dataset** | A curated working collection assembled from folders or individual assets | Unpublished changes and explicit published versions |
| **Project** | The operational environment where data is annotated and reviewed | Attached sources, ontology copy, tasks, annotations, and status |
| **Ontology** | The reusable schema defining objects, properties, classifications, events, entities, and relations | Working edits, Live versions, nested logic, and project-specific history |
| **Workflow** | The routing graph for Project, Annotate, Review, Model, Archive, and Complete stages | Stage topology, assignments, and accepted/rejected paths |
| **Task** | A workflow unit assigned to a person or made available to a queue | Assignee, priority, state, review decision, and timeline |
| **Batch Queue** | A processing batch for uploaded or imported project data | Processing, completion, and failure counts |
| **Release** | A versioned annotation snapshot prepared for downstream use | Version, split, export, annotation package, and associated files |
| **AI model** | A public or private model connected to annotation or workflow operations | Endpoint/configuration, validation, class mapping, and running state |

## Data Units in the SDK

The SDK makes one additional distinction:

- A loose file becomes a `datasource` Data Unit.
- A Data Group becomes one `group` Data Unit whose `items` contain its tile summaries.
- Group member files are not duplicated as separate top-level project units.

This is an important design detail for multimodal cases. A four-camera inspection, a DICOM study with related views, or a video–document–audio case can remain one unit of work rather than four unrelated tasks.

## Authentication

API-key management includes create, masked display, reveal, copy, enable/disable, and delete controls.

The Unitlab Python SDK accepts an API key and optional API URL directly, through environment variables, or through CLI configuration. Version 3.0.0 requires Python 3.10 or newer.

## SDK resource coverage

| Resource | Supported automation |
|---|---|
| Projects | list, get, create, update, soft-delete, data units, sources, upload, cloud import, attach/detach, Batch Queues |
| Assets | upload, folders/subfolders, list items, custom metadata, cloud folders, sync, grouping |
| Datasets | list, get, create, add sources, unpublished changes, publish versions, list versioned items |
| Embeddings | create spaces, list/get/delete, upsert asset or frame vectors, vector search |
| Ontologies | list/filter, get, create, build structures, save |
| Workflows | list stages/tasks, claim, assign, release, prioritize, submit, approve, reject, skip, move, timeline, bulk operations |
| Cloud storage | list safe metadata, get, browse prefixes |
| Releases | create, list/get, split-aware annotation download, file download |

## Important automation details

- Project deletion is recoverable at first; permanent cleanup happens later rather than disappearing immediately from every system record.
- Project uploads and cloud imports return Batch Queue handles that can be polled or waited on.
- Partial upload failures remain visible even when processing has finished.
- Dataset attachment can be previewed before commitment.
- Exact dataset versions can be attached to prevent silent drift.
- Video attachments may require FPS.
- Data Groups can be created from filename templates.
- Embeddings can be attached to a whole asset or a specific video frame.
- Workflow rejection can include both a reason and a comment.
- Release annotations and source files can be downloaded separately.

| Area | Unitlab capabilities |
|---|---|
| Image annotation | Bounding boxes, cuboids, polygons, masks, brush and eraser, keypoints, skeletons, lines, properties, relations, Magic Touch, Detect all objects, Find Similar, and Magic Crop |
| Video annotation | Frame and timeline navigation, persistent tracks, single- and multi-object Auto-Tracking, full bidirectional/forward/backward tracking, object and mask interpolation, dynamic class properties, and dynamic Item Properties |
| Audio annotation | Waveform and spectrogram views, temporal events, segmentation, transcription-oriented workflows, and playback controls |
| Text annotation | Entities, relations, whole-item properties, configurable text windows, and source-text editing |
| PDF annotation | Native multipage navigation, selectable PDF text, copied text values, bounding boxes from text or embedded image regions, page-aware history, and UUEF export |
| Medical annotation | Grouped DICOM volumes, synchronized axial/sagittal/coronal and 3D views, clinical ontologies, and DICOM, NIfTI, and NRRD ingestion |
| Multiview Workbench | Current File and Multiple Files modes, 1×1 through 4×4 grids, grouped custom layouts, resizable panels, and family-aware tools per tile |
| Multimodal data | Data Groups, filename-based auto-grouping, custom layouts, mixed datasets, mixed releases, and grouped project work items |
| AI assistance | Magic Touch, Detect all objects, Find Similar, Magic Crop, AI captioning, Auto-Tracking, interpolation, batch auto-annotation, and workflow Model stages |
| Ontologies | Classes, class attributes, typed class properties, Item Properties, relations, annotation-side schema creation, required/dynamic fields, validation, unlimited conditional depth, Logic Map, Live switching, snapshots, and version history |
| Workflows | Project, Annotate, Review, Model, Archive, and Complete stages; approve/reject routes; specialist review; assignment; self-assignment; manager override; and task lifecycle controls |
| Queues | Stage-based Task Queues, upload-oriented Batch Queues, assignment filters, priorities, claiming, submission, approval, rejection, and rework |
| Quality operations | Cohort filters, Grid/List/Embedding inspection, annotation-aware Display View controls, project instructions, item-level comments, owned issues, human review, notifications, project statistics, and member statistics |
| Data curation | Assets, folders, cloud folders, collections, activity history, metadata, advanced filters, Video/Frames browsing, filename-based auto-grouping, custom multimodal layouts, embeddings, natural-language search, duplicate detection, and outlier detection |
| Datasets | Working drafts, immutable published versions, version history, restore, duplicate, exact-version project attachment, detachment, and restoration |
| Releases | Versioned annotation snapshots, public/private visibility, read-only viewing, cloning, train/validation/test splits, UUEF, Standard Bundle, family-specific formats, and stable tokenized URLs |
| AI models | Public and private model catalogs, external-model registration, validation, input/output mapping, class mapping, and workflow integration |
| Accounts and workspaces | Email or Google authentication, email verification, password recovery, TOTP two-factor authentication, onboarding, workspace switching, settings, and quotas |
| Enterprise access | Members, invitations, built-in and custom roles, granular permissions, and API-key management |
| Automation | Python SDK and CLI access across projects, assets, datasets, ontologies, workflows, queues, embeddings, cloud storage, and releases |


## 25. Core product value

## One operating model across modalities

Image, video, audio, text, medical, PDF, and grouped multimodal cases share projects, ontologies, workflows, queues, review, and release concepts. Teams can standardize governance once and apply it across different forms of training data.

## Context-preserving annotation

Unitlab does more than accept multiple file formats. It groups related files into one work item and lets teams control how those sources appear together. Supported patterns include two- and four-camera views, synchronized medical views, document with audio, and video with PDF and audio.

## Reusable domain knowledge

Ontologies turn domain rules into reusable annotation structures. They support spatial objects, classifications, events, entities, relations, required properties, dynamic video properties, validation rules, and unlimited conditional nesting. Live versions, snapshots, history, Logic Map, and deleted-item restoration keep those structures manageable over time.

## Human and model work in one workflow

Project, Annotate, Review, Model, Archive, and Complete stages form forward and correction routes. Teams can add a second Review stage for specialist evaluation, configure eligible participants, and return rejected work to the appropriate annotation stage. Model output remains part of the same assignment, review, and release process as human-created annotations.

## Reproducible data handoffs

Datasets separate working changes from immutable published versions. Projects attach exact versions, and releases package annotation snapshots, source context, metadata, and data splits for downstream use. A model experiment can therefore reference the precise data, ontology, and release used to produce it.

## Integration with existing data operations

Cloud storage connections, public and private AI models, API keys, the Python SDK, the CLI, custom metadata, embeddings, and vector search allow Unitlab to fit into an existing AI data workflow while preserving the platform’s project, review, and release controls.

## Validation gates

- [ ] The unit of work preserves every modality and viewpoint required for the decision.
- [ ] Instructions, ontology, workflow, roles, and review criteria express one consistent policy.
- [ ] Normal, hard, ambiguous, invalid, rejected, and failed cases have an explicit route and owner.
- [ ] AI-assisted output is reviewed under the same semantic and workflow controls as manual work.
- [ ] A named release is reproducible and accepted by the downstream consumer.

## Risks and controls

| Risk | Control |
|---|---|
| Context is split across unrelated tasks | Use Data Groups and a custom layout; validate incomplete and ambiguous group behavior before attachment. |
| Operators invent different policies | Align Instructions, ontology validation, calibration examples, and reviewer decisions before scale. |
| Throughput hides systematic error | Inspect cohorts, issue categories, rejection patterns, and model failures rather than relying on aggregate completion. |
| A configuration change alters active work | Pilot the change on a controlled sample, record impact, and validate downstream schema before rollout. |
| Delivery cannot be reproduced | Pin dataset versions and retain ontology, workflow, model, format, split, exclusion, and validation records with the release. |

## Production evidence

Retain the workspace and project IDs; source scope; Data Group rule and layout version; dataset version; Instructions owner; ontology version; workflow stages and routes; role assignments; model and endpoint versions; calibration cohort; quality findings; unresolved exceptions; release ID and format; downstream validation result; approval owner; and the date or event that triggers the next review. Never place credentials, signed download URLs, cloud secrets, or regulated source data in this record.

## Product view

![Durable source data is separated from project-scoped work and versioned delivery.](../.gitbook/assets/assets-library.png)

*Durable source data is separated from project-scoped work and versioned delivery.*

![Workflow configuration defines controlled state transitions across human and model stages.](../.gitbook/assets/workflow-canvas.png)

*Workflow configuration defines controlled state transitions across human and model stages.*

![Release detail closes the architecture with a reproducible downstream contract.](../.gitbook/assets/release-detail.png)

*Release detail closes the architecture with a reproducible downstream contract.*

