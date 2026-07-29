---
description: "Design synchronized Data Groups and Workbench layouts for factories, agriculture, retail, robotics, and spatial operations."
icon: camera
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Solution architects, program owners, project managers, quality leads, and downstream data consumers. **Outcome:** Create a stable multi-view unit of work whose grouping, layout, navigation, workflow state, and release output preserve context.
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
  A["Related views"]
  B["Grouping rule"]
  C["Layout slots"]
  D["Grouped Workbench"]
  E["Context-preserving release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define the real-world event or entity that binds the views
{% endstep %}
{% step %}
### 2. Choose a stable grouping key and required, optional, duplicate, and missing-view behavior
{% endstep %}
{% step %}
### 3. Estimate grouping and inspect complete, incomplete, ambiguous, and ungrouped examples
{% endstep %}
{% step %}
### 4. Create a layout with named slots, stable ordering, and one active editing panel
{% endstep %}
{% step %}
### 5. Attach grouped output to a pilot project and verify Grouped Workbench navigation
{% endstep %}
{% step %}
### 6. Calibrate cross-view identity, occlusion, disagreement, and source-of-truth policy
{% endstep %}
{% step %}
### 7. Validate that project tasks and releases preserve group membership and tile roles
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

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

Multiview is the default project annotation experience for all six data families. It is a persistent workspace containing the project header, work-item navigation, mode/layout selector, resizable panel grid, one active editor, and one or more passive inspection panels.

## Two modes

| Mode | What the panels show | Editing model | Default layout |
|---|---|---|---|
| **Current file** | Multiple views of the same datasource | One active editor; sibling panels mirror its changes in real time | 1×1 |
| **Multiple files** | Neighboring work items from the current queue/filter scope | One selected panel is editable; other items remain passive previews | 1×3 |

Layouts range from 1×1 to 4×4. Users can resize panel boundaries, fullscreen a panel, and switch modes from the Workbench header. Mode, layout, and panel sizes persist for the user.

## Active and passive panels

Only the active panel can mutate annotations. It receives the full native editor: tools, hotkeys, selection, object/event/entity editing, player or page controls, comments, classes, properties, history, and workflow actions.

Passive panels can show media, annotations, labels, pages, frames, waveforms, text, or medical projections. In Current file mode they receive the active panel’s live annotation changes, but they cannot originate edits, change the active selection, save, control playback, change a PDF page, edit text entities, or alter waveform regions.

When the user activates a passive panel:

1. Unitlab visually selects it immediately.
2. Any in-progress save in the outgoing panel is allowed to settle.
3. Unsaved changes are saved or safely snapshotted.
4. The outgoing panel becomes passive and pauses modality-specific playback.
5. The incoming native editor loads and restores its panel state.
6. The route updates only after the editor is ready.
7. If hydration fails, Unitlab restores the previous active panel instead of blanking the workspace.

## Current file flow

1. The user opens a work item from a dataset, Task Queue, Batch Queue detail, filtered grid, or direct link.
2. Unitlab creates multiple panel sessions for the same datasource without duplicating data or history.
3. One panel is active; the rest are read-only siblings.
4. Active edits are broadcast to siblings in real time.
5. The user can activate another panel to work from a different view, frame, page, or zoom state.
6. Saving refreshes the shared history and updates every sibling to the persisted result.

Current-file examples:

- **Image:** compare the same image at different zoom or inspection states.
- **Video:** inspect different frames of the same video while sharing annotations and downloaded frames.
- **Audio:** inspect different time regions while one waveform editor remains authoritative.
- **Text:** compare different windows of the same text while entity/relation changes remain synchronized.
- **Document:** compare different PDF pages without confusing page changes with work-item navigation.
- **Medical:** assign Axial, Sagittal, Coronal, and 3D views to separate slots with synchronized annotation state.

## Multiple files flow

1. The user selects **Multiple files** and a layout.
2. Unitlab fills the grid with the active item and neighboring items from the current visible set.
3. The visible set preserves queue, upload-session, archive, search, status, class, and assignment filters.
4. The user activates any ready panel.
5. If the item belongs to another data family, the correct editor loads within the same Workbench shell.
6. Previous/next navigation continues through the filtered work-item sequence.
7. Empty tail slots and inaccessible items appear as panel-level states rather than replacing the whole page with an error.

This mode supports mixed review—for example an image, video, PDF, and audio item in one 2×2 layout—while guaranteeing that only the selected panel is editable.

## Navigation hierarchy

Unitlab maintains three distinct navigation levels:

- **Top-center previous/next:** changes the project work item and can cross data families or move between loose items and Data Groups.
- **Panel activation:** changes which visible panel is editable without leaving the Workbench.
- **Within-item media navigation:** changes a video frame, audio time region, text window, medical slice/view, or PDF page inside the current work item.

Keeping these levels separate is essential for predictable UX. A PDF page change must never advance to another datasource, and a medical slice change must never appear as another project item.

## Grouped Workbench

A Data Group opens as one grouped Workbench whose layout is fixed by the Auto-Grouping builder. The header shows the group layout rather than the general mode/layout selector. Activating a tile never tears down the group route.

The project’s unified previous/next sequence treats each group as one work unit and excludes its member tiles from the loose-item sequence. Grouped saves remain attributable to the group.

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

![Grouped layouts preserve viewpoint context while keeping one panel authoritative for editing.](../.gitbook/assets/multiview-video-workbench.png)

*Grouped layouts preserve viewpoint context while keeping one panel authoritative for editing.*

