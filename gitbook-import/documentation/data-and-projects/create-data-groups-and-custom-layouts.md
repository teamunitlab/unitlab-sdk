---
description: "Group related views or modalities into one context-preserving work unit and stable Workbench layout."
icon: objects-group
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Solution architects, data curators, and project managers. **You will:** Turn repeatable filenames or metadata into Data Groups that annotators navigate as one unit.
{% endhint %}

## Before you begin

- A folder whose members have consistent identifiers or metadata.
- A layout plan with named required and optional slots.
- Representative complete, incomplete, duplicate, and ambiguous groups.
- A release consumer that can preserve or interpret group context.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Source folder"]
  B["Grouping rule"]
  C["Estimate"]
  D["Create groups"]
  E["Grouped Workbench"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Open the source folder and request a grouping suggestion
{% endstep %}
{% step %}
### 2. Choose the grouping key and define the layout slots
{% endstep %}
{% step %}
### 3. Estimate complete, incomplete, ambiguous, and ungrouped outcomes
{% endstep %}
{% step %}
### 4. Preview representative groups and correct the rule
{% endstep %}
{% step %}
### 5. Create groups into the grouped output folder
{% endstep %}
{% step %}
### 6. Attach the grouped source to a pilot project
{% endstep %}
{% step %}
### 7. Open the Grouped Workbench and verify tile order, active editor behavior, navigation, workflow state, and release output
{% endstep %}
{% endstepper %}

## Product behavior and controls

Unitlab can automatically group related files into multiview or multimodal units using filename patterns. The current UI shows a four-step wizard:

1. **Configure**
2. **Rules**
3. **Layout**
4. **Review**

Available layout options are:

- **Grid** — related files arranged as a balanced grid;
- **List** — a primary tile with remaining files listed below;
- **Custom** — a draggable, resizable workspace for specialized arrangements.

A custom layout can place video, document, and audio tiles in one workspace. Layout determines what information an annotator can compare without leaving the task.

The SDK can:

- suggest a filename grouping pattern;
- estimate the outcome before creating groups;
- create groups from an explicit configuration;
- compile a literal filename template such as `{patient_id}_{view}`;
- map expected tile values such as `L_CC`, `R_CC`, `L_MLO`, and `R_MLO`.

## Auto-Grouping user flow

1. The user opens **Add auto-groups** from Assets or a folder.
2. **Configure:** choose the source folder. Unitlab analyzes filenames and can propose grouping keys, group-name template, and tiles; **Auto-detect** reruns the suggestion.
3. **Rules:** define the minimum matched tiles, required tiles, and incomplete-group handling. A live estimate shows valid, skipped, and conflicting examples. The user cannot continue without at least one valid estimated group.
4. **Layout:** arrange a panel per tile using Grid, List, or Custom/free-form placement. Panels can be dragged, resized, nudged, enlarged, or minimized. Overlap is highlighted and blocks continuation. An optional JSON view edits the same layout.
5. **Review:** inspect the final rules and static layout preview.
6. **Create:** Unitlab creates a new sibling `<source>_grouped` folder and leaves the source folder unchanged.

Every grouping run is non-destructive and creates a new grouped folder, even when the same configuration is run again. The saved percentage-based layout becomes the single layout used by preview, published dataset version, attached project group, and grouped Workbench.

For folders above 5,000 files or estimates above 1,000 groups, Unitlab starts an asynchronous grouping job and reports that it has begun. The SDK applies a stricter guard and may advise splitting the source before retrying.

## From Custom Layout to multimodal annotation

The layout is part of the Data Group, not a temporary preference inside the annotation screen. It moves with the group through the complete data lifecycle:

```text
Source files
    ↓ Auto-group by filename rules
Data Group + saved tile layout
    ↓ Add to dataset and publish
Immutable dataset version with grouped tiles
    ↓ Attach to project
One grouped project work item
    ↓ Open in Workbench
Multimodal annotation in the saved layout
    ↓ Release
Grouped annotation context preserved in UUEF
```

Each configured tile retains its own data family and native viewer. A single layout can therefore combine video playback, PDF pages, audio waveforms, images, or medical views while the surrounding project supplies one ontology, workflow state, assignee, comment history, and review route for the grouped case.

The grouped Workbench follows the saved Grid, List, or Custom arrangement. Annotators activate one tile at a time for editing; the other tiles remain visible as read-only context. Previous/next navigation treats the complete group as one work item, and group members do not appear again as unrelated loose tasks.

Custom-layout UX is designed to prevent invalid arrangements before creation:

- each expected tile has one panel;
- panels can be dragged, resized, nudged, enlarged, or minimized;
- panel coordinates and dimensions are percentage-based so the layout scales with the Workbench;
- overlap is highlighted and blocks continuation;
- the visual editor and optional JSON view edit the same layout;
- Review shows the final rules and a static layout preview before groups are created.

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
