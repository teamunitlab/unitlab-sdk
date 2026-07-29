---
description: "Use embeddings, model proposals, issues, review outcomes, and releases to build targeted feedback cohorts."
icon: arrows-rotate
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Solution architects, program owners, project managers, quality leads, and downstream data consumers. **Outcome:** Turn model behavior into a versioned, human-verified data cohort and a reproducible delivery for the next training or evaluation cycle.
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
  A["Model finding"]
  B["Targeted curation"]
  C["Human verification"]
  D["Versioned release"]
  E["Train/evaluate"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define the model version, source domain, target failure, and acceptance metric
{% endstep %}
{% step %}
### 2. Use metadata, filters, embeddings, duplicates, outliers, issues, and review outcomes to assemble candidates
{% endstep %}
{% step %}
### 3. Human-verify the candidate cohort and publish exact membership as a dataset version
{% endstep %}
{% step %}
### 4. Attach the version to a project with the required ontology, workflow, model stage, and review policy
{% endstep %}
{% step %}
### 5. Measure proposals, corrections, failures, and disagreements by cohort and class
{% endstep %}
{% step %}
### 6. Create a release with explicit format, splits, exclusions, and provenance
{% endstep %}
{% step %}
### 7. Validate the release in training or evaluation and feed the next finding back into curation
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

The embedding view projects embeddable assets into a visual space and supports drag or crop-style region selection. Users can select a cluster and review its associated thumbnails before adding, excluding, or organizing the selected assets.

Useful curation patterns include:

- locating dense duplicate or near-duplicate regions;
- sampling from visually distinct clusters;
- finding outliers and rare conditions;
- comparing source domains;
- building a more diverse pilot dataset;
- selecting negative examples near a target class.

The two-dimensional plot is a navigation aid, not a guarantee that every nearby point is semantically identical. Operators should inspect the actual assets before turning a region into a dataset.

## Custom embedding spaces and vector search

The SDK can create named embedding spaces with a specified dimensionality and optional model name, upload vectors for an asset or a video frame, bulk-upsert vectors, search by a query vector, and optionally scope the search to a project or level.

This allows teams to use Unitlab’s curation interface while retaining control over the embedding model and vector space used for similarity operations.

## Search, duplicates, outliers, and UMAP

Unitlab includes visual similarity search, natural-language CLIP-style search, duplicate detection, outlier detection, quality-inconsistency checks, and UMAP visualization. These embedding and visual exploration experiences are available for image and video data.

## Public and private catalogs

Unitlab separates **My AI Models** from **Public AI Models**. Private model states include Running, Stopped, and Integration unfinished.

Model use cases include:

- object/person detection;
- open-vocabulary detection;
- image and video segmentation;
- polygon detection;
- human pose/skeleton detection;
- cuboid or other visual geometry;
- OCR and document OCR;
- speech-to-text and speech recognition;
- audio segmentation;
- general multimodal models.

## External-model integration wizard

The wizard follows:

1. Registration
2. Validation
3. Integration
4. Confirmation

Supported model input types are Image, Video, Audio, Text, and Medical.

Visual result types include bounding box, polygon, mask, skeleton, line, point, and cuboid. Audio can return an Event and optional speech-recognition transcript. Text can return an Entity.

Configuration includes:

- model name and description;
- endpoint;
- request headers and parameters;
- required source-data parameter;
- OCR-output option;
- validation;
- tags;
- class creation or mapping;
- integer class mapping;
- update or delete integration.

The default request structure includes a source-data URL. Credentials and request headers are managed as part of the private model integration.

## Integration discipline

Before a model is added to production, define:

- input contract and supported media;
- response schema and coordinate system;
- ontology mapping;
- timeout, retry, and failure behavior;
- authentication and secret rotation;
- confidence interpretation;
- abstention behavior;
- validation data;
- human correction route;
- traceability fields needed in the release.


## 21. Releases and downstream delivery

## What a release contains

A release is a versioned annotation snapshot with:

- visibility such as Private or Public;
- modality;
- version number;
- creation date;
- item counts;
- data preview;
- annotation preview;
- Clone Release;
- Overview, Data, and Settings tabs;
- item type, data ID, preview, ground truth, and metadata.

A release can contain video, document, and audio items together. Metadata is represented as structured content: video metadata can include frame, video, and audio facts, while document metadata includes PDF and page information.

## Release creation flow

Releases are created from a project’s Releases page:

1. The user opens the export dialog.
2. The user chooses the source scope: the full project or one/more Batch Queues.
3. The user selects one or more data families inside that scope.
4. Unitlab previews releasable counts, annotation/review progress, format compatibility, and recommended format.
5. The user chooses an export format or per-family Standard Bundle formats.
6. The user selects a license when required.
7. The user enters nonnegative integer train, validation, and test percentages that sum to 100.
8. The user optionally enables stable tokenized item URLs.
9. Unitlab creates the versioned release.

Invalid latest histories are excluded from ordinary releasable counts. Cloud-storage-sourced releases are forced private.

## Release areas and read-only viewing

Data Space contains **My Releases** and **Public Releases**, toggled from the page header. A release detail contains Overview, Data, and—on private workspace releases—Settings.

Opening a release item uses a separate read-only annotation viewer for Image, Video, Audio, Text, Medical, or Document. It reuses the familiar modality surface but disables mutation. This lets teams inspect exactly what a release contains without accidentally changing the project history that produced it.

Making a release public requires license selection. Release deletion is permission- and subscription-gated. If the latest release version is deleted, the previous version becomes latest.

## Export formats

Working converters include:

| Data family | Supported formats |
|---|---|
| Image | COCO, YOLOv8, YOLOv5, UUEF |
| Video | COCO, YOLOv8, YOLOv5, UUEF |
| Medical | COCO, YOLOv8, YOLOv5, UUEF |
| Document/PDF | UUEF only |
| Text | JSONL, UUEF |
| Audio | Audio JSON, RTTM, UUEF |

Native single-family formats apply to one compatible family. A release containing more than one family must use **UUEF** or **Standard Bundle**.

- **UUEF** is the universal full-fidelity format. It preserves properties, attributes, relations, item properties, tags, page/frame context, and the richer annotation graph.
- **Standard Bundle** creates one ZIP containing a native output per selected family plus a manifest describing the release, source scope, selected types, split ratios, written files, and omitted empty combinations.

Default Standard Bundle choices are COCO for image/video/medical, JSONL for text, and Audio JSON for audio. Document data uses UUEF.

## SDK export behavior

The SDK can:

- create a release from a project;
- specify `export_type="UUEF"`;
- define split ratios such as 80% train and 20% test;
- list and retrieve releases;
- download annotations for a selected split;
- download associated files to a destination folder.

The SDK supports UUEF creation and split-aware annotation and file downloads. The complete release format matrix is shown above.

## Cloning and reproducibility

Clone Release supports controlled branching. The user can clone with annotations or as datasource-only content, choose the new project name, and continue from the new project’s Data page. Unitlab creates a completed Batch Queue for cloned rows so queue and data views remain consistent.

A team can preserve a known release, create a new branch for correction or experimentation, and avoid rewriting the historical data associated with an earlier model run.

Private release Data pages also provide a new-version and augmentation flow for creating a derived version while preserving the original release.

## Stable release item URLs

When enabled during release creation, Unitlab can issue tokenized, stable item URLs—including frame-specific video/medical URLs—that redirect to fresh storage links. A release being public does not automatically make every underlying item URL anonymous; tokenized access must be explicitly enabled.

A model experiment should record at least:

- release ID and version;
- dataset source versions;
- ontology version;
- split policy;
- model and prompt/configuration version;
- known exclusions;
- evaluation result.

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

![Embedding evidence helps teams assemble targeted feedback cohorts for a defined model failure mode.](../.gitbook/assets/embedding-view.png)

*Embedding evidence helps teams assemble targeted feedback cohorts for a defined model failure mode.*

