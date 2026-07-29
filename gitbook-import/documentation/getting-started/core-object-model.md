---
description: "Understand how Unitlab resources relate before configuring projects or writing automation."
icon: diagram-project
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Solution architects, project owners, data engineers, and SDK integrators. **You will:** Choose the correct object for source organization, reusable membership, work execution, quality state, and downstream delivery.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Asset"]
  B["Data Group or loose item"]
  C["Dataset version"]
  D["Project Data Unit"]
  E["Workflow task"]
  F["Release"]
  A --> B
  B --> C
  C --> D
  D --> E
  E --> F
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Identify the durable source Assets and folders
{% endstep %}
{% step %}
### 2. Decide whether related resources must form a Data Group
{% endstep %}
{% step %}
### 3. Create a reusable dataset version when membership must be named and reproduced
{% endstep %}
{% step %}
### 4. Attach the correct source or version to a project
{% endstep %}
{% step %}
### 5. Operate Data Units through workflow tasks and queues
{% endstep %}
{% step %}
### 6. Create a release only after quality acceptance
{% endstep %}
{% endstepper %}

## Product behavior and controls

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

## Verify the result

- [ ] The visible result matches the project Instructions and active ontology.
- [ ] The workflow stage, assignee, and queue state are correct.
- [ ] A second user with the intended role can reproduce the result.
- [ ] Downstream dataset or release behavior remains correct.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| A folder is being used as a release | Separate organization, membership, work, and delivery. Use folders, dataset versions, project attachments, and releases for their distinct purposes. |
| Group members appear as separate work | Validate Auto-Grouping output and attach the grouped source rather than the ungrouped members. |
| Automation uses names as identifiers | Store stable resource IDs and use names only for display or operator selection. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.
