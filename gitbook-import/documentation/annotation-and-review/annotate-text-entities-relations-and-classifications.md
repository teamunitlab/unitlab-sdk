---
description: "Create structured text labels while preserving readable context and unambiguous span policy."
icon: align-left
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Text annotators, reviewers, ontology designers, and NLP teams. **You will:** Produce consistent spans, relations, and document-level classifications that downstream consumers can interpret.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Read context"]
  B["Select span"]
  C["Classify"]
  D["Relate"]
  E["Review"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Open the item and confirm whether the task requires entities, relations, Item Properties, comments, or source-text editing
{% endstep %}
{% step %}
### 2. Read enough context before selecting a span
{% endstep %}
{% step %}
### 3. Create the entity using the project’s token, punctuation, whitespace, and nesting policy
{% endstep %}
{% step %}
### 4. Create relations between the intended entity instances
{% endstep %}
{% step %}
### 5. Complete document-level or entity-level properties
{% endstep %}
{% step %}
### 6. Review ambiguous boundaries, overlapping entities, repeated mentions, and missing context
{% endstep %}
{% step %}
### 7. Save, validate, and submit
{% endstep %}
{% endstepper %}

## Product behavior and controls

The text workbench supports:

- entities;
- relations between entities;
- pan/navigation;
- comments;
- font-size and line-height controls;
- shortcuts;
- item properties and tags;
- normal workflow completion.

One uploaded text file remains one work item. Large text is delivered to the editor in character windows rather than being split into separate project tasks. Entity offsets and relations remain anchored to the full file. A project setting can allow annotators to edit the source text when the workflow requires correction as well as labeling.

## Entities, relations, and classifications

- **Entity:** a span with domain meaning, such as organization, medication, defect, or clause.
- **Relation:** an explicit connection between entities, such as `treats`, `caused_by`, `belongs_to`, or `answers`.
- **Item property:** a whole-document decision such as language, document type, sentiment, escalation state, or completeness.

In a document-and-audio layout, text entities and their relations can remain visible while annotators review temporal audio events below. Text structure can therefore be interpreted alongside another modality instead of being handled in a disconnected process.

## Text-quality design

Entity guidelines should define inclusion boundaries, punctuation, nested mentions, discontinuous concepts, pronouns, abbreviations, and uncertain spans. Relation guidelines should define direction, allowed source/target classes, and whether the connection must be explicit in the text or may be inferred from context.

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
