---
description: "Approve a Unitlab project for production volume with explicit governance and validation evidence."
icon: shield-check
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Program owners, security, quality, ML operations, and downstream data consumers. **You will:** Make an evidence-backed go/no-go decision before production scale or a material change.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Access review"]
  B["Data + policy review"]
  C["Workflow exercise"]
  D["Quality calibration"]
  E["Release approval"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Review workspace ownership, roles, and offboarding controls
{% endstep %}
{% step %}
### 2. Review source scope, grouping, lifecycle, invalid-data, and cloud-connection controls
{% endstep %}
{% step %}
### 3. Review Instructions, ontology version, edge cases, and schema-change ownership
{% endstep %}
{% step %}
### 4. Exercise every workflow path including rejection, failure, skip, invalid state, and escalation
{% endstep %}
{% step %}
### 5. Calibrate reviewers and inspect systematic errors across a cohort
{% endstep %}
{% step %}
### 6. Verify service identities, retries, logs, model versions, and failure routing
{% endstep %}
{% step %}
### 7. Validate one release and its downstream schema
{% endstep %}
{% step %}
### 8. Record approval, conditions, owners, and the next review trigger
{% endstep %}
{% endstepper %}

## Product behavior and controls

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

## Verify the result

- [ ] The visible result matches the project Instructions and active ontology.
- [ ] The workflow stage, assignee, and queue state are correct.
- [ ] A second user with the intended role can reproduce the result.
- [ ] Downstream dataset or release behavior remains correct.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| The expected action is unavailable | Check the active workflow stage, user role, selected item, and whether the required resource is Live or still processing. |
| The result appears incomplete | Inspect filters, source membership, Data Group membership, invalid state, and Batch Queue failures before repeating the operation. |
| A change affects existing work | Stop the rollout, identify affected items and versions, validate a recovery path on a sample, and document the change owner. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.
