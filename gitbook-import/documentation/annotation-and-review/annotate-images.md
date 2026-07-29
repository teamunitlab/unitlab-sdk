---
description: "Choose appropriate geometry, create and edit objects, complete attributes, and apply a consistent image-quality policy."
icon: image
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Image annotators, reviewers, ontology designers, and ML engineers. **You will:** Produce image labels whose geometry and semantics match the downstream model and export contract.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Policy"]
  B["Geometry"]
  C["Object"]
  D["Attributes"]
  E["Review"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Open the task and confirm the class, required annotation type, and boundary policy
{% endstep %}
{% step %}
### 2. Choose box, cuboid, brush, polygon, mask, skeleton, line, keypoint, or Item Property from the downstream need
{% endstep %}
{% step %}
### 3. Create the object and refine its geometry at the required zoom
{% endstep %}
{% step %}
### 4. Complete required properties, attributes, and relations
{% endstep %}
{% step %}
### 5. Resolve overlap with visibility, opacity, and object-ordering controls
{% endstep %}
{% step %}
### 6. Review difficult edges such as holes, shadows, truncation, reflection, and occlusion
{% endstep %}
{% step %}
### 7. Save, confirm validation state, and submit through the workflow
{% endstep %}
{% endstepper %}

## Product behavior and controls

The image workbench supports a broad geometry set:

- bounding box;
- cuboid;
- brush and eraser;
- polygon;
- mask-oriented Magic Touch;
- skeleton;
- line;
- keypoint;
- crosshair;
- comments.

Editing controls include pan, undo/redo, zoom/reset, image settings, shortcuts, selection, class reassignment, property/relation editing, deletion, and object stacking actions such as bring to front, bring forward, send backward, and send to back.

## Choose geometry from the model backward

- Use **bounding boxes** when coarse localization is sufficient and edge precision would not improve the model.
- Use **polygons or masks** when boundary shape, area, occlusion, or pixel-level separation matters.
- Use **cuboids** when a 3D-like image representation is required.
- Use **keypoints or skeletons** when the spatial arrangement of landmarks is the target.
- Use **lines/polylines** for elongated structures or paths.
- Use **item properties** for whole-image classification, captioning, or attributes that do not belong to one object.

In captioning workflows, the workbench presents item-level ontology properties instead of irrelevant spatial drawing tools. The ontology determines the work required for the item, so annotators see controls that match the labeling task.

Cuboid is available as a pseudo-3D eight-corner visual geometry in image, video, and document annotation, with shortcut **N**. UUEF preserves the cuboid geometry. COCO and YOLO do not have a native cuboid representation, so teams should choose UUEF when that geometry must remain lossless.

## Image quality is a policy problem

A technically valid polygon can still be wrong if annotators disagree about holes, shadows, truncation, reflections, or occluded boundaries. Production quality therefore requires:

- a geometry policy;
- hard examples in project instructions;
- an explicit treatment of ambiguity;
- reviewer calibration;
- release-level checks by class and source domain.

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

## Product view

![The image Workbench combines the active canvas, ontology tools, properties, item state, and workflow actions.](../.gitbook/assets/image-workbench.png)

*The image Workbench combines the active canvas, ontology tools, properties, item state, and workflow actions.*

