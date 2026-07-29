---
description: "Navigate native PDFs, select text, create regions from text or images, and preserve document context across pages and files."
icon: file-pdf
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Document annotators, reviewers, project managers, and information-extraction teams. **You will:** Create page-aware text and region annotations without confusing page navigation with project-item navigation.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Open document"]
  B["Navigate page"]
  C["Select text or image"]
  D["Create annotation"]
  E["Review"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Open the PDF task and confirm the document identity, page count, and required annotation types
{% endstep %}
{% step %}
### 2. Navigate pages with document controls and reserve shifted navigation for changing documents
{% endstep %}
{% step %}
### 3. Select and copy native PDF text when the text layer is available
{% endstep %}
{% step %}
### 4. Convert selected text or an embedded image into the intended bounding region
{% endstep %}
{% step %}
### 5. Complete entity, relation, classification, or Item Property values
{% endstep %}
{% step %}
### 6. Use Multiview when another page, document, image, or medical study provides required context
{% endstep %}
{% step %}
### 7. Review page identity, region alignment, text content, and current document limits before submission
{% endstep %}
{% endstepper %}

## Product behavior and controls

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
