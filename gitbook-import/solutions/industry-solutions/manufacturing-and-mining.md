---
description: "Design context-preserving inspection, PPE, equipment, defect, event, and operational-state programs."
icon: industry
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Manufacturing, mining, construction, safety, quality, and computer-vision program teams. **Outcome:** Operate a multiview safety or inspection program whose identities, state changes, review decisions, and releases remain reproducible.
{% endhint %}

## Decision to make

State the operational or model decision in one sentence. Then list the minimum evidence, temporal or spatial context, allowed uncertainty, and downstream representation required to make that decision consistently. Do not begin with a tool list; begin with the decision contract.

## Before you begin

- A site- and task-specific definition of hazards, defects, equipment states, and allowed ambiguity.
- Synchronized or near-synchronized representative views from normal, crowded, low-light, occluded, and high-risk conditions.
- Named safety or quality authority for ontology policy and specialist escalation.
- A downstream inspection, training, monitoring, or audit consumer.

## Operating blueprint

~~~mermaid
flowchart LR
  A["Site evidence"]
  B["Multiview group"]
  C["Object + state labeling"]
  D["Safety/quality review"]
  E["Verified release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define one inspection, event window, equipment instance, or work-zone episode as the unit of work
{% endstep %}
{% step %}
### 2. Group camera views and contextual files by stable site, equipment, event, and time identifiers
{% endstep %}
{% step %}
### 3. Design a layout with one authoritative editor and passive contextual views
{% endstep %}
{% step %}
### 4. Model people, PPE, equipment, zones, defects, relations, and dynamic state in the ontology
{% endstep %}
{% step %}
### 5. Route model proposals, human annotation, safety review, rework, and completion through explicit stages
{% endstep %}
{% step %}
### 6. Calibrate on occlusion, glare, dust, crowding, partial PPE, scene cuts, and identity re-entry
{% endstep %}
{% step %}
### 7. Inspect systematic errors by site, shift, device, class, condition, and model version
{% endstep %}
{% step %}
### 8. Release a versioned cohort and validate geometry, tracks, properties, group context, and exclusions downstream
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

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

**Problem:** Many people must be tracked over time and classified by helmet status.

**Unitlab pattern:**

1. Use a Person class with a dynamic Helmet status property.
2. Seed or import initial detections.
3. Use Auto-Tracking across later frames.
4. Correct identity drift and status changes at keyframes.
5. Route to review; rejected tracks return to annotation.
6. Measure accepted tracks after rework, not raw predictions.

This workflow combines persistent tracks with properties that can change over time, allowing reviewers to distinguish identity errors from attribute changes.

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

![A multiview work unit keeps inspection evidence aligned around the same asset, event, or operating condition.](../.gitbook/assets/multiview-video-workbench.png)

*A multiview work unit keeps inspection evidence aligned around the same asset, event, or operating condition.*

