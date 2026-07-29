---
description: "Authenticate safely and automate current Unitlab resources with stable identifiers, processing waits, explicit errors, and reproducible output handling."
icon: terminal
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Developers, data engineers, ML operations, and platform engineers. **You will:** Choose the correct automation surface and operate Unitlab resources without bypassing workflow, permissions, or audit controls.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Identity"]
  B["Resource operation"]
  C["Processing monitor"]
  D["State verification"]
  E["Audit record"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Create a least-privilege API key and store it in an approved secret manager
{% endstep %}
{% step %}
### 2. Choose Python SDK, CLI JSON output, or direct HTTP based on the runtime
{% endstep %}
{% step %}
### 3. Use stable resource IDs and explicit dataset versions
{% endstep %}
{% step %}
### 4. Separate request acceptance from Batch Queue or release processing completion
{% endstep %}
{% step %}
### 5. Handle authentication, validation, permission, subscription, not-found, request-timeout, and processing-timeout errors distinctly
{% endstep %}
{% step %}
### 6. Inspect remote state before retrying a mutation
{% endstep %}
{% step %}
### 7. Record correlation IDs, resource IDs, counts, versions, duration, and redacted errors
{% endstep %}
{% step %}
### 8. Validate the same downstream result as the interactive product path
{% endstep %}
{% endstepper %}

## Product behavior and controls

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
