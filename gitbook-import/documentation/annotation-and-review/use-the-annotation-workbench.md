---
description: "Open assigned work, understand the shared shell, create labels, complete required values, save history, and submit through the active stage."
icon: pen-to-square
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Annotators, reviewers, project managers, and training leads. **You will:** Complete one work item without losing data identity, ontology context, save state, or workflow ownership.
{% endhint %}

## Before you begin

- An active project workflow and a task available to the user’s role.
- A Live project ontology and current Instructions.
- A supported Data Unit that has completed processing.
- A decision about Current file, Multiple files, or grouped Workbench context.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Task Queue"]
  B["Instructions + ontology"]
  C["Native editor"]
  D["Save + validate"]
  E["Stage action"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Open the Task Queue or project cohort and confirm the item identity and stage
{% endstep %}
{% step %}
### 2. Read Instructions and inspect issue or comment context
{% endstep %}
{% step %}
### 3. Confirm the active class, annotation type, Item Properties, and required values
{% endstep %}
{% step %}
### 4. Create or edit annotations with the native modality toolbar
{% endstep %}
{% step %}
### 5. Use View Settings, visibility controls, shortcuts, and object ordering for accurate inspection
{% endstep %}
{% step %}
### 6. Save and confirm history, validation, and invalid state
{% endstep %}
{% step %}
### 7. Use the explicit Workbench stage action to submit, approve, reject, skip, archive, or complete
{% endstep %}
{% step %}
### 8. Confirm the next item and queue state
{% endstep %}
{% endstepper %}

## Product behavior and controls

Across modalities, Unitlab keeps a recognizable operating model:

- top-center previous/next work-item navigation;
- active class or annotation type;
- Multiview mode and layout controls;
- object/class or event/entity inspection;
- item properties;
- object properties and relations;
- comments;
- tags;
- appearance and visibility controls;
- save and version-history controls;
- workflow actions appropriate to the active stage;
- project instructions and issue context.

The active native editor supplies the modality-specific toolbar, timeline, player, page controls, and inspector content. The surrounding Workbench stays stable when navigation crosses data families.

## Annotation keyboard shortcuts

Press **H** inside the active annotation panel to open the context-aware **Annotation Shortcuts** dialog. It groups the shortcuts available for the current data family into Annotation Tools, Actions, and Views. Only the active Workbench panel receives shortcuts; passive Multiview panels remain read-only.

## Common actions and view controls

| Shortcut | Action | UX behavior |
|---|---|---|
| **H** | Show shortcuts | Opens the shortcut dialog for the active modality |
| **Ctrl/Cmd + Z** | Undo | Reverses the last annotation edit |
| **Ctrl/Cmd + Y** or **Ctrl/Cmd + Shift + Z** | Redo | Reapplies the last reversed edit |
| **Delete/Backspace** | Delete selected | Removes the currently selected annotation |
| **Ctrl/Cmd + C** | Copy | Copies the selected annotation; native text copy takes priority when text is selected |
| **Ctrl/Cmd + X** | Cut | Cuts the selected annotation; native text editing takes priority in text fields |
| **Ctrl/Cmd + V** | Paste | Pastes the copied annotation into the active annotation context |
| **1–9** | Select class | Activates the project class assigned to that numeric hotkey |
| **+ / − / 0** | Zoom in / zoom out / reset | Changes or resets the active viewer zoom |
| **Shift + H** | Home | Returns from the annotation workspace to the project/home context |
| **R / K** | Review / reject in compatible legacy contexts | Workflow-managed items use the explicit stage actions in the Workbench header, which guard these status shortcuts |

## Visual annotation tools

| Shortcut | Tool | Available context |
|---|---|---|
| **V** | Pan/select/reposition | Image, video, medical, document; also Pan mode in text |
| **B** | Bounding Box | Image, video, medical, document |
| **N** | Cuboid | Image, video, document |
| **F** | Brush | Image, video, medical, document |
| **E** | Eraser | Image, video, medical, document |
| **P** | Polygon | Image, video, medical, document |
| **L** | Polyline | Image, video, document |
| **J** | Skeleton | Image, video, document |
| **U** | Keypoint | Image, video, document |
| **A** | Add polygon point | Adds a point while editing polygon geometry |
| **M** | Magic Touch | Image, video, medical, document; **Shift + Click** removes from the assisted mask |
| **S** | Detect all objects | Image and video for an active box, polygon, mask, or cuboid class |
| **T** | Toggle crosshair | Image, video, medical, document |
| **C** | Comment | Adds an annotation comment |
| **D** | Select PDF Text | Document only; selects, copies, or converts embedded PDF text into annotations |
| **[ / ]** | Decrease/increase brush size | Image, video, medical, document |
| **Esc** | Finish the active drawing operation | Completes the current segmentation/drawing interaction and returns to a stable editing state |

## Object ordering

| Shortcut | Action |
|---|---|
| **W** | Bring selected annotation to front |
| **O** | Bring selected annotation one level forward |
| **I** | Send selected annotation one level backward |
| **Q** | Send selected annotation to back |

These ordering commands apply to overlapping canvas annotations. The same actions appear in the object right-click menu and become unavailable when the selected object is already at the relevant edge of the stack.

## Navigation and playback

| Context | Shortcut | Action |
|---|---|---|
| Image, audio, text | **← / →** | Previous/next work item |
| Document | **← / →** | Previous/next PDF page |
| Document | **Shift + ← / Shift + →** | Previous/next PDF document |
| Video, medical | **← / →** | Previous/next frame or slice |
| Video, medical | **Shift + ← / Shift + →** | Previous/next video or medical work item |
| Video, medical, audio | **Space** | Play/pause |
| Audio | **↑ / ↓** | Volume up/down |
| Audio | **Alt + → / Alt + ←** | Increase/decrease playback speed |
| Audio | **L** | Toggle loop |
| Audio | **P** | Toggle autoplay |
| Audio | **S** | Toggle spectrogram |
| Audio | **T** | Toggle timeline |
| Audio | **Ctrl/Cmd + O / Ctrl/Cmd + I** | Zoom waveform in/out |
| Text | **T / R / C** | Entity mode / Relation mode / Comment tool |

Shortcut meanings are modality-aware. For example, **T** is Crosshair on a visual canvas, Entity mode in text, and Timeline visibility in audio; **R** is the Relation tool in text and a review action only in compatible non-workflow contexts.

## Annotation View Settings

The View Settings panel controls how the active editor looks and responds without changing the source file. Available sections adapt to the resource family and Workbench mode.

| Section | Controls | Effect |
|---|---|---|
| **Canvas / Rendering** | Pixel Perfect | Preserves one-to-one pixel rendering for supported standalone image views; hidden where it does not apply, including medical and multi-panel layouts |
| **Annotation Display** | Display object names; Show properties & attributes; object-label font size; selected-object opacity; object-edge opacity | Controls labels and visual emphasis without changing saved geometry |
| **Annotation Tools** | Handle size; primitive keypoint sensitivity; show polyshape angles; ruler around cursor | Adjusts editing precision, control-point size, angle visibility, and local measurement guidance |
| **Auto zoom** | Auto zoom on timeline click; auto zoom on object-list click | Centers and enlarges the selected annotation when the corresponding navigation action is used |
| **Image Adjustments** | Color Map; Invert Image; Brightness; Contrast; Image Saturation | Changes the inspection view only; source-image properties remain unchanged |
| **Video** | Default annotation length; Jump frames | Sets the initial temporal span for a new annotation and the number of frames used by jump navigation |
| **Hounsfield unit presets** | Built-in preset selection; custom preset name; Save W/L; delete custom preset | Applies and stores medical window/level presets |
| **3D Viewer Settings** | Threshold; Opacity | Controls the medical 3D rendering |
| **Projection (MIP)** | Single slice, MIP (max), MinIP (min), Average; slab thickness | Controls multi-slice projection when a medical volume is available |
| **Windows Levels** | VOI LUT mode; histogram; window-width/level range; reset; **Tab + ←/→** for width and **Tab + ↑/↓** for level | Controls the displayed intensity range for medical-image inspection |

Settings persist as annotation-view preferences. They alter rendering, navigation, or editing ergonomics; they do not rewrite the uploaded media.

## Work-item status

Item status is derived from the item’s current workflow stage, not maintained as an unrelated manual field. User-facing status buckets include:

- New;
- In annotation;
- In Review;
- AI Review where applicable;
- Processing;
- Complete;
- Archived;
- Error.

Task-level status can further show Reopened, Skipped, Pending, Dispatched, Running, Paused, Succeeded, or Failed. An **Invalid** sub-state appears when the latest saved history fails required-property or value validation. Validation is non-blocking: the save succeeds, the item is marked for correction, and the workflow can route it appropriately.

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

![Project Instructions keep labeling policy available in the same operating context as assigned annotation work.](../.gitbook/assets/project-instructions.png)

*Project Instructions keep labeling policy available in the same operating context as assigned annotation work.*

