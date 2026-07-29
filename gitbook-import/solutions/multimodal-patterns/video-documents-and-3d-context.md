---
description: "Combine temporal evidence with manuals, reports, medical or spatial context, and 3D representations."
icon: cube
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Solution architects, program owners, project managers, quality leads, and downstream data consumers. **Outcome:** Keep temporal evidence, reference material, and spatial context synchronized around one traceable decision.
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
  A["Event package"]
  B["Temporal + reference context"]
  C["Authoritative edit"]
  D["Cross-context review"]
  E["Structured release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define the event, inspection, case, procedure, or equipment instance
{% endstep %}
{% step %}
### 2. Assign each grouped member a role such as primary video, manual, report, audio note, scan, or 3D context
{% endstep %}
{% step %}
### 3. Design one authoritative active editor and passive evidence panels with stable placement
{% endstep %}
{% step %}
### 4. Encode object, temporal, document, scene, and item-level semantics in one ontology contract
{% endstep %}
{% step %}
### 5. Write navigation, synchronization, source-of-truth, conflict, and missing-context policy
{% endstep %}
{% step %}
### 6. Calibrate annotators on context switches, frame/page boundaries, scene cuts, and evidence disagreement
{% endstep %}
{% step %}
### 7. Validate that release output preserves member identity, roles, annotations, and required source references
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

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

## Native PDF annotation

Document currently means PDF. One uploaded PDF remains one file and one work item; pages are internal surfaces inside that item. Assignment, workflow status, comments, review, history, and release remain document-level concepts rather than being duplicated per page.

The document editor intentionally uses the familiar Image Annotation UX:

- the same top app bar and work-item navigation;
- the same left visual-annotation toolbar;
- the same pan, select, draw, transform, zoom, undo, and redo behavior;
- the same right-side Objects, Classes, and Comment inspector;
- the same class assignment, properties, tags, relations, visibility, review, save, and history flows;
- visual markups including bounding box, cuboid, polygon, mask/semantic segmentation, skeleton, line, and point.

Document-specific controls appear only where required:

- a bottom-center page footer for multi-page navigation;
- **Select PDF Text** mode;
- document loading copy;
- page-aware annotations.

Top-center previous/next changes the project work item. The footer changes the page inside the current PDF. These actions are intentionally separate.

## Open and annotate a PDF

1. The user uploads a PDF through the normal mixed-data upload flow.
2. Unitlab detects the Document family and generates a first-page thumbnail.
3. The PDF appears in the project grid and relevant queues as one document item.
4. Opening it loads the PDF in the Workbench.
5. The active page is rendered as the visual annotation surface.
6. The user creates normal visual annotations with the standard tools.
7. Each saved object records its page number.
8. The object list shows annotations for the active page while off-page annotations remain preserved in the full document history.

## Page navigation

1. The user selects another page from the bottom footer.
2. The PDF file and work-item identity stay unchanged.
3. Unitlab loads the new page raster, selectable text layer, and embedded image regions.
4. The canvas shows only annotations belonging to that page.
5. Saving merges active-page changes back into the complete multi-page result without deleting annotations from other pages.

Adjacent pages may be prepared in advance, and a cached lower-resolution page can appear while a sharper render is prepared. Annotation geometry remains aligned to the document page rather than the temporary screen resolution.

## Select and copy native PDF text

1. The user activates **Select PDF Text**.
2. Browser-native text selection becomes available over the active page.
3. The user highlights embedded PDF text and copies it normally.
4. Leaving text-selection mode returns pointer control to normal annotation, transformation, and pan tools.

## Create a bounding box from selected text

1. The user highlights native PDF text.
2. Unitlab converts the selected text rectangles into page coordinates.
3. A normal editable bounding box is created.
4. Optional anchor metadata can preserve the selected text, source type, page, and rectangles.
5. The object continues through the standard class, property, save, review, history, and export lifecycle.

## Create a bounding box from an embedded PDF image

In Select PDF Text mode, Unitlab can identify embedded image regions exposed by the PDF and let the user create a normal bounding box from a selected region. This is embedded-image-region detection, not a promise of semantic figure recognition.

## Current document limits

The native selection layer does not semantically detect tables, equations, vector diagrams, or generic figures. Those tasks use document-understanding models or manual annotation rather than layout heuristics. Native and scanned PDFs can require different handling for OCR alignment, rotations, reading order, and very large page sets.

## The value of multimodal layout

The product’s stronger document story is contextual. A field incident may include a video, a report PDF, and audio; a medical case may include images and a clinical form; a support interaction may include text and speech. Grouping these sources into one task lets an annotator reason about the case rather than annotate unrelated files.


## 13. Medical data annotation

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

![A contextual layout can combine temporal, document, and spatial evidence without losing member identity.](../.gitbook/assets/medical-dicom-document.png)

*A contextual layout can combine temporal, document, and spatial evidence without losing member identity.*

