---
description: "Learn the current workspace navigation and the responsibility of each Unitlab product area."
icon: compass
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** All Unitlab users and technical evaluators. **You will:** Navigate Unitlab with a clear understanding of which area owns each stage of the data-production lifecycle.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Workspace"]
  B["Data Space"]
  C["Project"]
  D["Workbench + review"]
  E["Release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Open the workspace and confirm the active workspace identity
{% endstep %}
{% step %}
### 2. Locate Annotation, Data Space, AI Suite, Releases, and Workspace Settings
{% endstep %}
{% step %}
### 3. Map each team responsibility to its product area
{% endstep %}
{% step %}
### 4. Open a representative project and follow its Datasets, Queues, Workflows, Ontologies, Instructions, Issues, Releases, and Settings navigation
{% endstep %}
{% step %}
### 5. Document the operating path for the team
{% endstep %}
{% endstepper %}

## Product behavior and controls

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

## Verify the result

- [ ] Every role knows its default starting area.
- [ ] The team distinguishes durable data from project work and released outputs.
- [ ] Users can identify the current workspace and project before changing state.
- [ ] The operating path is documented for annotators, reviewers, project managers, and administrators.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| The expected action is unavailable | Check the active workflow stage, user role, selected item, and whether the required resource is Live or still processing. |
| The result appears incomplete | Inspect filters, source membership, Data Group membership, invalid state, and Batch Queue failures before repeating the operation. |
| A change affects existing work | Stop the rollout, identify affected items and versions, validate a recovery path on a sample, and document the change owner. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.
