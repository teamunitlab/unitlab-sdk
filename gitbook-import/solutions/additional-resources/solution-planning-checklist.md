---
description: "Translate a new use case into explicit Unitlab decisions, owners, controls, acceptance evidence, and downstream validation."
icon: list-check
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Solution architects, program owners, project managers, quality leads, and downstream data consumers. **Outcome:** Leave solution design with no hidden decisions about context, semantics, ownership, failure behavior, or delivery.
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
  A["Outcome"]
  B["Evidence model"]
  C["Semantic + operating contract"]
  D["Pilot evidence"]
  E["Approval"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Write the outcome and accountable owner
{% endstep %}
{% step %}
### 2. Define the unit of work and required evidence
{% endstep %}
{% step %}
### 3. Map durable source data, metadata, grouping, reusable membership, and project attachment
{% endstep %}
{% step %}
### 4. Design the semantic contract and edge-case policy
{% endstep %}
{% step %}
### 5. Design normal, rejection, invalid, failure, skip, and escalation routes
{% endstep %}
{% step %}
### 6. Define human and model responsibilities and service identity controls
{% endstep %}
{% step %}
### 7. Define quality evidence and downstream release acceptance
{% endstep %}
{% step %}
### 8. Approve the pilot scope, exit criteria, production conditions, and next review trigger
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

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

## Planning decision record

| Area | Decision to record |
|---|---|
| Outcome | Business or model decision, consumer, acceptance metric, accountable owner |
| Unit of work | Real-world entity, event, study, case, scene, document package, or time window |
| Evidence | Required modalities, viewpoints, context, metadata, and missing-evidence behavior |
| Data contract | Source systems, folder convention, grouping key, dataset-version policy, split integrity |
| Semantic contract | Instructions owner, ontology classes, geometry, properties, relations, Item Properties, ambiguity policy |
| Operating contract | Workflow stages, queues, assignments, review sample, rejection, skip, invalid, failure, escalation |
| Model contract | Model version, endpoint, secret owner, mapping, proposal scope, failure path, human gate |
| Delivery contract | Release format, source inclusion, splits, exclusions, URLs or tokens, downstream validation |
| Governance | Roles, service identities, audit fields, retention, change approval, review trigger |

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

![Instructions make inclusion, exclusion, ambiguity, invalid-data, and acceptance policy operational for the team.](../.gitbook/assets/project-instructions.png)

*Instructions make inclusion, exclusion, ambiguity, invalid-data, and acceptance policy operational for the team.*

