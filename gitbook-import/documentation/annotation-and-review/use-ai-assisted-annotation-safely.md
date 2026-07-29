---
description: "Apply Magic Touch, Detect all objects, Find Similar, tracking, interpolation, captioning, batch automation, and Model stages inside human-controlled quality gates."
icon: wand-magic-sparkles
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Annotators, reviewers, project managers, ML engineers, and quality leads. **You will:** Select the smallest useful assist, validate its proposal, correct it, and keep accountability in the workflow.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Policy"]
  B["Assist"]
  C["Proposal"]
  D["Human correction"]
  E["Workflow review"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Define the ontology class, geometry, output, and acceptance policy
{% endstep %}
{% step %}
### 2. Choose the assist that matches the task: boundary, repeated objects, similarity, temporal propagation, captioning, or batch work
{% endstep %}
{% step %}
### 3. Run the assist on one representative item or small cohort
{% endstep %}
{% step %}
### 4. Inspect class, geometry, attributes, relations, identity, temporal state, and Item Properties
{% endstep %}
{% step %}
### 5. Correct every proposal in the native editor
{% endstep %}
{% step %}
### 6. Submit through the configured human or model workflow stage
{% endstep %}
{% step %}
### 7. Record systematic errors by source domain, class, model version, and operation
{% endstep %}
{% step %}
### 8. Expand volume only after corrected output is stable
{% endstep %}
{% endstepper %}

## Product behavior and controls

Unitlab combines local assistance inside the workbench with Model stages inside workflows. Assisted results remain proposals until they are reviewed and accepted through the annotation and quality process.

## Magic Touch

Magic Touch is available in image and video toolbars as an interactive mask-oriented tool. When no compatible class is selected, it opens a Create Class dialog configured for a Mask class, with name, color, and numeric hotkey fields.

The correct production loop is:

1. Select the target mask class.
2. Guide the proposal on a representative object.
3. Inspect boundaries, holes, thin structures, and occlusion.
4. Correct with manual tools.
5. Review the final mask under the same policy as a fully manual label.

## Detect all objects

A class-aware auto-labeling panel contains:

- current class;
- prompt textbox;
- prompt initially populated from the class name;
- reset prompt to class name;
- Detect all objects.

Detect all objects provides prompt-based, class-aware detection within the current image or video frame.

Detect all objects is available on images and individual video frames. It uses shortcut **S**, opens a **Create annotations** popup with a SAM 3 badge, and requires an active class with bounding-box, polygon, mask, or cuboid geometry. The prompt defaults to the class name and accepts up to 300 characters. Each call is scoped to the current image or current frame, can return up to a configured maximum number of candidates, and consumes one AI-inference quota unit when successful.

Annotators review proposed objects before accepting them. Prompt changes can alter the candidate distribution even when the ontology class name remains the same, so teams can standardize prompts in their labeling instructions.

## Find Similar

Find Similar is a contextual header action, not a drawing tool. It becomes available when the selected object is a box, polygon, or mask. It searches the current image or current video frame, exposes a confidence threshold, removes strong overlaps with existing annotations, and holds new predictions for review before commitment. It does not search across the full dataset and does not consume AI-inference quota.

Find Similar can return multiple candidates at the selected confidence threshold, with **Clear** and **Accept all** actions available. Seed quality, visual repetition, clutter, scale, and threshold affect the result, so operators review each candidate set in context before acceptance.

## Auto-Tracking and interpolation

Auto-Tracking predicts later frames with machine learning; interpolation fills geometry between keyframes. Both results remain visible on the timeline for human review and correction.

## Magic Crop

Magic Crop runs model-assisted labeling inside a user-selected crop region. It is useful when the relevant objects occupy one part of a larger surface and whole-image detection would create unnecessary proposals. Each call uses AI-inference quota and still requires review before acceptance.

## AI captioning

AI-assisted captioning can propose text for the current item. The proposal should be reviewed against the item-property or captioning ontology rather than treated as an automatically accepted description.

## Batch auto-annotation

Unitlab supports batch auto-annotation for model-assisted labeling. Batch jobs apply model assistance across a selected data scope, while human review remains part of the annotation and workflow process.

## Model stages

A Model stage can be placed between human stages in a workflow. Model output can move forward to annotation or review, while rejected outcomes return through the configured correction route. Inference behavior follows the connected model’s input, output, and class mapping configuration.

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

![Find Similar returns model-assisted candidates that remain subject to operator verification and project policy.](../.gitbook/assets/find-similar-results.png)

*Find Similar returns model-assisted candidates that remain subject to operator verification and project policy.*

