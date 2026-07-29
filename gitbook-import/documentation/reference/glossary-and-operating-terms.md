---
description: "Use consistent Unitlab terminology across product, operational, security, and integration teams."
icon: book
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** All Unitlab users. **You will:** Use one vocabulary when designing, operating, troubleshooting, and auditing Unitlab programs.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.



## Procedure

{% stepper %}
{% step %}
### 1. Identify the term in the current product context
{% endstep %}
{% step %}
### 2. Distinguish source, membership, work, workflow, and delivery objects
{% endstep %}
{% step %}
### 3. Use stable IDs and explicit versions in technical records
{% endstep %}
{% step %}
### 4. Correct ambiguous language in Instructions, tickets, integrations, and handoffs
{% endstep %}
{% endstepper %}

## Product behavior and controls

| Term | Operating meaning |
|---|---|
| Asset | Durable source resource managed in Data Space. |
| Folder | Source organization and navigation boundary; not a dataset version or release. |
| Data Group | Related resources treated as one context-preserving work unit. |
| Data Unit | A loose datasource or group exposed to project work and automation. |
| Dataset | Reusable membership definition whose published versions freeze exact source membership. |
| Project | Operational boundary for Instructions, data attachments, ontology, workflow, queues, annotation, review, issues, statistics, settings, and releases. |
| Workbench | Shared annotation shell that loads the native editor for the active resource family. |
| Ontology | Versioned semantic contract for classes, annotation types, properties, relations, Item Properties, and validation. |
| Workflow | Stage graph that determines item state and valid human or model actions. |
| Task Queue | Operational list of individual workflow tasks. |
| Batch Queue | Processing and operational context for a grouped set of work. |
| Invalid | Non-blocking saved state indicating required-property or value validation failure. |
| Release | Frozen downstream delivery with explicit version, content, format, splits, and settings. |
| UUEF | Unitlab export representation for preserving platform-native annotation structures. |

## Verify the result

- [ ] Team documentation uses the defined product terms.
- [ ] Folders, dataset versions, project attachments, Data Units, tasks, and releases are not treated as interchangeable.
- [ ] Technical records include stable IDs and versions where relevant.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| The expected action is unavailable | Check the active workflow stage, user role, selected item, and whether the required resource is Live or still processing. |
| The result appears incomplete | Inspect filters, source membership, Data Group membership, invalid state, and Batch Queue failures before repeating the operation. |
| A change affects existing work | Stop the rollout, identify affected items and versions, validate a recovery path on a sample, and document the change owner. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.
