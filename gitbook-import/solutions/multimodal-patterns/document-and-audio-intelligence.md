---
description: "Pair audio, transcripts, PDFs, entities, relations, regions, and structured context for customer, compliance, and research workflows."
icon: file-waveform
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Solution architects, program owners, project managers, quality leads, and downstream data consumers. **Outcome:** Produce linked temporal, textual, relational, and document evidence without confusing page, item, and project navigation.
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
  A["Case package"]
  B["Audio + text + document"]
  C["Linked annotation"]
  D["Specialist review"]
  E["Validated release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define the conversation, case, session, document package, or research unit
{% endstep %}
{% step %}
### 2. Group permitted audio, transcript, PDF, images, and structured context by stable case identity
{% endstep %}
{% step %}
### 3. Configure waveform or spectrogram, text, document, and context panels with one active editor
{% endstep %}
{% step %}
### 4. Encode temporal regions, entities, relations, classifications, document regions, and Item Properties
{% endstep %}
{% step %}
### 5. Write alignment, overlap, redaction, silence, uncertainty, and evidence-linking policy
{% endstep %}
{% step %}
### 6. Route sensitive or ambiguous cases to named specialist review
{% endstep %}
{% step %}
### 7. Validate timestamps, page identity, text spans, relations, regions, group membership, and downstream schema
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

**Problem:** A written record contains entities and relations, while audio contains speakers, motion, noise, or transcription evidence.

**Unitlab pattern:**

1. Group the text/document and audio as one case.
2. Place them in a joint layout.
3. Annotate text entities and relations.
4. Mark audio event ranges or review a transcript.
5. Use item-level properties for case outcome or escalation status.
6. Validate completeness across both modalities before release.

This workflow preserves the relationship between written structure and temporal audio evidence within one task.

The audio workspace provides:

- waveform and timeline;
- temporal event segments;
- play/pause;
- rewind and forward by 10 seconds;
- current time and duration;
- volume and mute;
- zoom;
- playback speed;
- event/class selection;
- comments;
- item properties;
- tags;
- workflow completion actions.

The audio workbench combines waveform and spectrogram context with temporal event regions. Audio can also be aligned with document text or video inside the same grouped task.

## Common audio tasks

- **Clip classification:** describe the whole recording.
- **Temporal event detection:** mark the start and end of a sound, speaker, motion, noise, or other event.
- **Segmentation:** partition a recording into meaningful regions.
- **Transcription-oriented work:** produce or review speech text.

An external audio model can return an Event result and may optionally provide a speech-recognition transcript.

## Boundary quality

Audio disagreement often comes from boundary policy rather than class identity. Teams should define whether an event begins at the first acoustic evidence, the first intelligible phoneme, or a fixed context margin; how overlap is handled; whether silence is labeled; and how background noise interacts with foreground speech.


## 11. Text annotation

The text workbench supports:

- entities;
- relations between entities;
- pan/navigation;
- comments;
- font-size and line-height controls;
- shortcuts;
- item properties and tags;
- normal workflow completion.

One uploaded text file remains one work item. Large text is delivered to the editor in character windows rather than being split into separate project tasks. Entity offsets and relations remain anchored to the full file. A project setting can allow annotators to edit the source text when the workflow requires correction as well as labeling.

## Entities, relations, and classifications

- **Entity:** a span with domain meaning, such as organization, medication, defect, or clause.
- **Relation:** an explicit connection between entities, such as `treats`, `caused_by`, `belongs_to`, or `answers`.
- **Item property:** a whole-document decision such as language, document type, sentiment, escalation state, or completeness.

In a document-and-audio layout, text entities and their relations can remain visible while annotators review temporal audio events below. Text structure can therefore be interpreted alongside another modality instead of being handled in a disconnected process.

## Text-quality design

Entity guidelines should define inclusion boundaries, punctuation, nested mentions, discontinuous concepts, pronouns, abbreviations, and uncertain spans. Relation guidelines should define direction, allowed source/target classes, and whether the connection must be explicit in the text or may be inferred from context.


## 12. Documents and multimodal layouts

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

![Waveform, spectrogram, transcript, and document evidence can be coordinated around one case-level decision.](../.gitbook/assets/audio-workbench.png)

*Waveform, spectrogram, transcript, and document evidence can be coordinated around one case-level decision.*

