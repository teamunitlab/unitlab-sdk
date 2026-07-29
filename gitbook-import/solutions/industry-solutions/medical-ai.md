---
description: "Coordinate DICOM planes, 3D context, reports, ontology policy, and specialist review for medical data programs."
icon: heart-pulse
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Clinical AI teams, specialist annotators, reviewers, medical data operations, security, and governance owners. **Outcome:** Operate a study-centered medical program with explicit clinical context, specialist authority, traceable policy, and controlled delivery.
{% endhint %}

## Decision to make

State the operational or model decision in one sentence. Then list the minimum evidence, temporal or spatial context, allowed uncertainty, and downstream representation required to make that decision consistently. Do not begin with a tool list; begin with the decision contract.

## Before you begin

- Approved access, handling, retention, and de-identification controls for the data sensitivity and regulatory context.
- A study-centered definition of required series, reports, derived images, and contextual resources.
- A specialist-owned ontology, Instructions, calibration set, and escalation route.
- A downstream format and validation protocol that preserves study and series context.

## Operating blueprint

~~~mermaid
flowchart LR
  A["Approved study"]
  B["Synchronized views"]
  C["Specialist labeling"]
  D["Clinical review"]
  E["Controlled release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define one study, encounter, procedure, or case as the unit of work
{% endstep %}
{% step %}
### 2. Group the permitted DICOM, NIfTI, NRRD, report, and contextual resources required for interpretation
{% endstep %}
{% step %}
### 3. Configure synchronized axial, sagittal, coronal, projection, 3D, and contextual-document panels
{% endstep %}
{% step %}
### 4. Encode findings, anatomy, geometry, properties, relationships, uncertainty, and study-level state in the ontology
{% endstep %}
{% step %}
### 5. Route primary labeling, specialist review, ambiguity, invalid data, and escalation through named stages
{% endstep %}
{% step %}
### 6. Calibrate view, window/level, boundary, measurement, negative-case, and disagreement policy
{% endstep %}
{% step %}
### 7. Audit cohort quality without exposing source data in operational logs
{% endstep %}
{% step %}
### 8. Create a release and validate study linkage, geometry, ontology values, exclusions, and downstream access controls
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

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

Medical is a resource family inside a typeless project. Medical resources open the native medical Workbench while remaining part of the same project, ontology, workflow, queue, and release system used by other modalities.

## Synchronized DICOM and 3D context

The medical workbench supports:

- axial view;
- sagittal view;
- coronal view;
- 3D view;
- synchronized annotations across views;
- window/level values visible per view;
- contextual document content beside medical imagery;
- multiview and multi-case layout switching.

The product story is not merely “four panes.” The key operational value is that an edit can remain connected across anatomical views, reducing the context switching required to reconcile separate representations of the same study.

## Medical ontology example

An example medical ontology can contain a `spine` mask class with structured properties such as:

- coverage: Cervical, Thoracic, Lumbar, Sacrum, Coccyx;
- a conditional Record property when Sacrum is selected;
- deeper text input when Normal is selected;
- Clinical Finding options including Normal, Degenerative changes, Compression fracture, Scoliosis, and Hardware present.

This shows how geometry, anatomy, and clinical meaning can be kept separate. A mask identifies the spatial region; properties capture structured findings; conditional branches request detail only when relevant.

## Medical formats and ingestion

The SDK supports mixed upload directories containing DICOM, NIfTI, and NRRD alongside common image and document formats. DICOM slices are grouped by `SeriesInstanceUID` into one user-facing medical volume. Internal source slices, pending rows, and failed rows do not appear as separate grid items, queue tasks, or navigation entries.

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

![Synchronized study views support specialist labeling and review without separating evidence from workflow state.](../.gitbook/assets/medical-workbench.png)

*Synchronized study views support specialist labeling and review without separating evidence from workflow state.*

![DICOM evidence and contextual documents can be presented together when the decision requires both.](../.gitbook/assets/medical-dicom-document.png)

*DICOM evidence and contextual documents can be presented together when the decision requires both.*

