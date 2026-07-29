---
description: "Adapt Unitlab’s current product capabilities to manufacturing, agriculture, medical, customer-interaction, and construction-safety programs."
icon: route
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Solution architects, program owners, technical evaluators, and customer teams. **You will:** Translate a domain problem into source structure, grouping, ontology, workflow, quality, model, and release decisions.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Domain unit"]
  B["Context layout"]
  C["Ontology"]
  D["Workflow + quality"]
  E["Release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Define the real-world unit that must remain together
{% endstep %}
{% step %}
### 2. Choose source ingestion, metadata, grouping, and custom layout
{% endstep %}
{% step %}
### 3. Define ontology classes, geometry, properties, Item Properties, and edge cases
{% endstep %}
{% step %}
### 4. Define human, model, review, escalation, and completion stages
{% endstep %}
{% step %}
### 5. Run a representative calibration cohort
{% endstep %}
{% step %}
### 6. Measure systematic errors and correct policy or configuration
{% endstep %}
{% step %}
### 7. Create and validate a domain-appropriate release
{% endstep %}
{% endstepper %}

## Product behavior and controls

## Pattern A: multiview factory inspection

**Problem:** The same item appears in four camera views. Treating each recording as an independent task can create inconsistent identity and defect decisions.

**Unitlab pattern:**

1. Ingest the four camera files with consistent identifiers.
2. Use auto-grouping to create one Data Group per inspected item.
3. Arrange four video tiles in a custom layout.
4. Define object classes and defect properties in the ontology.
5. Use tracking or interpolation within each view.
6. Route uncertain cases to a specialist-configured Review stage.
7. Publish a release that preserves the grouped case.

This workflow keeps the four views connected from curation through release, so annotators can make one case-level decision with all relevant visual context available.

## Pattern B: agriculture and repeated objects

**Problem:** A frame contains many similar cherries, and the same scene is captured from two angles.

**Unitlab pattern:**

1. Group the two camera views.
2. Annotate one trusted seed object.
3. Run Find Similar.
4. Adjust the confidence threshold and inspect candidates.
5. Accept only valid suggestions.
6. Continue tracking across frames if the data is video.

This workflow combines multiview context with seed-based assistance, reducing repetitive drawing while keeping acceptance under annotator control.

## Pattern C: medical study with contextual documentation

**Problem:** A finding must be understood across axial, sagittal, coronal, and 3D views, while a clinical document provides case context.

**Unitlab pattern:**

1. Upload or import the medical study and document.
2. Preserve study identity through grouping.
3. Use a custom layout with synchronized medical views and the document.
4. Annotate anatomy with geometry.
5. Record findings through conditional ontology properties.
6. Route the task through specialist review.
7. Export a controlled release after de-identification and governance checks.

This workflow keeps medical volumes and contextual documents together, allowing the specialist to review the case across synchronized views before release.

## Pattern D: customer interaction across text and audio

**Problem:** A written record contains entities and relations, while audio contains speakers, motion, noise, or transcription evidence.

**Unitlab pattern:**

1. Group the text/document and audio as one case.
2. Place them in a joint layout.
3. Annotate text entities and relations.
4. Mark audio event ranges or review a transcript.
5. Use item-level properties for case outcome or escalation status.
6. Validate completeness across both modalities before release.

This workflow preserves the relationship between written structure and temporal audio evidence within one task.

## Pattern E: model-assisted construction safety review

**Problem:** Many people must be tracked over time and classified by helmet status.

**Unitlab pattern:**

1. Use a Person class with a dynamic Helmet status property.
2. Seed or import initial detections.
3. Use Auto-Tracking across later frames.
4. Correct identity drift and status changes at keyframes.
5. Route to review; rejected tracks return to annotation.
6. Measure accepted tracks after rework, not raw predictions.

This workflow combines persistent tracks with properties that can change over time, allowing reviewers to distinguish identity errors from attribute changes.

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
