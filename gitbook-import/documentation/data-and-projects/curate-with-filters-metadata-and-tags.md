---
description: "Build precise, reviewable data cohorts with advanced conditions and durable business context."
icon: filter
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Data curators, reviewers, project managers, and ML engineers. **You will:** Find and explain an exact cohort before grouping, versioning, attachment, or quality review.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Question"]
  B["Conditions"]
  C["Visual inspection"]
  D["Metadata context"]
  E["Dataset version"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. State the question the cohort must answer
{% endstep %}
{% step %}
### 2. Choose Grid, List, or Embedding view for that question
{% endstep %}
{% step %}
### 3. Add type, source, date, size, dimension, metadata, tag, or status conditions
{% endstep %}
{% step %}
### 4. Review inclusions and exclusions on representative items
{% endstep %}
{% step %}
### 5. Apply or correct custom metadata and tags using the workspace convention
{% endstep %}
{% step %}
### 6. Save a personal filter only for repeat navigation
{% endstep %}
{% step %}
### 7. Publish durable cohort membership as a dataset version
{% endstep %}
{% endstepper %}

## Product behavior and controls

The **More Filters** sidebar is available from the Assets and Folders tabs and remains available inside folder detail. Its fixed sections are:

- **Asset Type:** Image, Video, Audio, Text, Medical, and Document;
- **Source:** Uploaded or Cloud storage;
- **Tags:** searchable tag selection;
- **Date:** asset creation date;
- **File Properties:** minimum/maximum size and minimum width/height.

The header badge counts active filter groups. The footer continuously reports the matching result count and displays **Updating…** while a new result set is loading. Added filters provide controls appropriate to their value: text operators, date or date-range inputs, boolean toggles, multiselect chips, color swatches, numeric range sliders, and searchable entity pickers for users, tags, folders, and datasets.

The complete additional-filter catalog is organized as follows:

| Category | Filter groups and fields |
|---|---|
| **Data** | File name, file type, extension, MIME type, asset ID; upload/created/modified/last-synced dates; width, height, resolution, aspect ratio, file size; video duration, frame count, FPS; medical modality, series count, study count, and slice count |
| **Metadata** | Folder, subfolder, collection, dataset membership, sequence membership, group membership; storage provider, bucket, import source, data source; uploaded by, created by, updated by; asset and system tags |
| **Embeddings** | Similar assets/images/frames; text-to-image and natural-language search; embedding cluster and cluster membership; diverse and representative samples; similarity and distance thresholds |
| **Image Features** | Sharpness, noise level, exposure; brightness, contrast, saturation, dominant colors; entropy, complexity, texture density, edge density; orientation, foreground coverage, and background coverage |
| **Video & Frames** | Frame number, timestamp, keyframes only; scene changes, shot boundaries, segments; frame tags, frame attributes, and frame quality |
| **Data Quality** | Exact and near duplicates; outliers and anomalies; blurry, low-resolution, corrupted, and incomplete assets; missing, invalid, and empty metadata |
| **Search** | Metadata search, tag search, natural-language query, and embedding search |

Filters that operate on stored asset fields and computed metrics narrow the results immediately. These include extension, MIME type, asset ID, uploaded/created/modified dates, creator, orientation, low resolution, blurry assets, dominant color, duration, frame count, FPS, series/slice count, and numeric image-curation metrics. Catalog entries carrying a **Preview** badge can be configured in the interface but do not yet narrow the result set.

On the Folders tab, an active asset filter keeps a folder only when its subtree contains at least one matching asset. Filters run before duplicate source identities are collapsed, so matching behavior remains stable across project clones of the same underlying data.

Typical curation flows include finding low-resolution uploads, isolating studies from one source bucket and date range, locating long videos, selecting a brightness or sharpness range, finding duplicate-heavy regions, and building a balanced sample from embedding clusters.

Folders preserve source organization rather than label truth. A folder such as `warehouse-camera-07` describes provenance; a decision such as `forklift_present` belongs in an ontology or annotation.

## Folder Explore, Collections, and frame granularity

Folder detail includes **Explore** and **Collections**:

- **Explore** is the normal list/grid/embedding file browser.
- **Collections** stores static, folder-scoped curated file sets.

Selecting files or child folders in Explore enables **Add to Collections** or **Remove from Collections**. A new collection can be created with the current selection, or the selection can be added to an existing collection. Collection actions include View in explorer, Add to dataset, and Download. Removing or deleting a collection never deletes its files.

For video folders, Explore can switch between **Video** and **Frames** granularity:

- **Video** shows one entry per source file and keeps the standard List/Grid/Embedding view switcher.
- **Frames** expands videos with extracted-frame metadata into a paginated frame-card sequence. The breadcrumb reports the frame count and the normal view switcher is disabled while frame browsing is active.
- Native videos without extracted frame metadata appear as one poster entry.
- Selection remains file-level: selecting any frame selects its parent video and highlights all visible sibling frames. Collection, dataset, download, and bulk actions therefore operate on the complete video rather than an arbitrary frame subset.

Inside a collection-scoped Explore view, search and advanced filters continue to apply. A dismissible collection chip identifies the active scope.

## Custom metadata and tags

Tags and custom metadata allow source facts to travel with assets. Appropriate metadata includes capture site, sensor, acquisition date, device version, customer partition, consent state, or study identifier. It should not silently encode ground truth that annotators are expected to determine from the data.

The SDK supports setting custom metadata during upload and updating it later, including explicitly setting it to `null`.

## Verify the result

- [ ] The visible result matches the project Instructions and active ontology.
- [ ] The workflow stage, assignee, and queue state are correct.
- [ ] A second user with the intended role can reproduce the result.
- [ ] Downstream dataset or release behavior remains correct.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| A saved filter is treated as a dataset | Saved filters are personal UI state. Create and publish a dataset version for durable, auditable membership. |
| Metadata conflicts with ontology values | Use metadata for source/business context, tags for operational categories, and ontology Item Properties for annotation output. |
| The cohort is unexpectedly small | Check is-any-of versus is-none-of logic, view state, lifecycle state, hidden folders, and stacked conditions. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.
