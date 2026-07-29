---
description: "Curate synchronized driving, robotics, and temporal scene data across cameras, motion, identities, and rare scenarios."
icon: car
layout:
  width: wide
---

{% hint style="info" %}
**Who this blueprint is for:** Autonomous-driving, robotics, perception, mapping, safety, and data-engineering teams. **Outcome:** Create synchronized temporal datasets with defensible identity, event, rare-scenario, and release policy.
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
  A["Synchronized episode"]
  B["Scenario curation"]
  C["Temporal labeling"]
  D["Safety review"]
  E["Group-safe release"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Implementation

{% stepper %}
{% step %}
### 1. Define the drive, scene, maneuver, event window, or robot episode as the unit of work
{% endstep %}
{% step %}
### 2. Preserve synchronized camera and permitted contextual resources with stable capture and calibration metadata
{% endstep %}
{% step %}
### 3. Use filters and embeddings to build representative and rare-event cohorts without leaking split membership
{% endstep %}
{% step %}
### 4. Define geometry, identity, temporal presence, occlusion, truncation, re-entry, scene cuts, and dynamic-state policy
{% endstep %}
{% step %}
### 5. Configure multiview video layouts, tracking, interpolation, Item Properties, and review stages
{% endstep %}
{% step %}
### 6. Calibrate on dense scenes, small objects, motion blur, lighting transitions, sensor gaps, and topology change
{% endstep %}
{% step %}
### 7. Inspect error by scenario, geography, weather, lighting, device, class, motion, and model version
{% endstep %}
{% step %}
### 8. Release group-safe splits and validate tracks, temporal properties, source references, and exclusions downstream
{% endstep %}
{% endstepper %}

## Current Unitlab capabilities

Video uses the spatial annotation toolset plus time:

- frame counter and frame-by-frame navigation;
- playback;
- object track rows;
- timeline zoom from 1× to 10×;
- loop control;
- keyframes;
- track-level review;
- synchronized multiview video layouts.

Common video workflows include:

- construction and mining scenes with person tracks and a dynamic `Helmet status` property;
- agriculture with two synchronized camera angles;
- factory inspection with four camera angles;
- self-driving data with many vehicle and person tracks;
- a construction sequence in which annotations propagate across frames.

## Auto-Tracking

Auto-Tracking uses machine learning to predict an object across frames. The user starts with one or more annotated objects, chooses a tracking direction, runs tracking, then reviews the propagated results and keyframes on the timeline.

Use Auto-Tracking when motion is continuous enough for model proposals to reduce repeated drawing. Review after occlusion, re-entry, camera cuts, scale changes, blur, and interactions between similar objects.

## Full, forward, and backward tracking

Right-clicking a supported object opens **Auto track** with three directional actions:

| Action | Range | Typical use |
|---|---|---|
| **Track full annotation** | Runs in both directions from the selected frame across the annotation’s available temporal range | The seed object is created in the middle of a sequence and the complete track is required |
| **Track forward** | Runs from the selected frame toward later frames | The first reliable appearance of the object is known, or only future motion needs propagation |
| **Track backward** | Runs from the selected frame toward earlier frames | The clearest object appearance occurs later and earlier frames need to be recovered |

Direction availability follows the current position. **Track backward** is unavailable at the first frame, and **Track forward** is unavailable when no later frame remains. Full tracking provides bidirectional propagation from a single reliable seed.

The same commands are available from a selected timeline segment. While a track is running, the segment menu changes from **Tracking** to **Stop Tracking**, allowing the user to end an active tracking operation.

## Multi-object tracking

Unitlab can track several objects in one operation:

1. The annotator holds **Command** on macOS or **Ctrl** on Windows/Linux and right-clicks objects to build a multi-selection.
2. The context menu reports the number of selected objects.
3. The annotator chooses **Auto track**.
4. The annotator selects **Track full annotation**, **Track forward**, or **Track backward**.
5. Unitlab submits the selected supported tracks together and writes each result back to its own object track.
6. The annotator reviews every result on the timeline and corrects individual tracks where identities diverge.

The multi-object menu also provides group actions such as bring all to front, send all to back, duplicate all, and delete all. Group tracking preserves separate object identities; it does not merge the selected objects into one annotation.

## Interpolation

The live control describes Interpolation as “Tween between keyframes.” It is deterministic propagation between manually defined states and is appropriate when an annotator can place reliable keyframes around smooth motion.

## Auto-Tracking versus interpolation

| Question | Auto-Tracking | Interpolation |
|---|---|---|
| Source of intermediate labels | Model predictions | Geometry between keyframes |
| Best fit | Complex but trackable motion | Smooth movement between known states |
| Main risk | Identity drift or confident false proposals | Missing non-linear motion or shape change |
| Review focus | Track identity, occlusion, re-entry, false positives | Keyframe placement and motion between keys |

## Dynamic properties

Class properties can be marked **Dynamic** in video and medical annotation. This enables temporal labeling across frames: a dynamic property stores frame-aware values instead of one value for the complete object track. For example, a person can remain the same tracked instance while `Helmet status` changes from `Not visible` to `Present` and later to `Absent`.

Dynamic class-property flow:

1. Create or edit the property and enable **Dynamic**.
2. Select the annotated object at the frame where the value becomes known or changes.
3. Set the single-choice, multi-choice, or text value in the object inspector.
4. Unitlab creates a property keyframe for that object and displays the property as a child row beneath the object track.
5. Move to a later frame and change the value to create another temporal state.
6. Expand the object row on the timeline to inspect the property ranges and their transition points.

A non-dynamic class property applies to the object without a frame-by-frame value history. Dynamic properties are used when the object identity remains stable but its state changes across the sequence.

## Dynamic Item Properties

Item Properties describe the complete datasource rather than one annotation object. They can also be marked **Dynamic** for video and medical work, enabling temporal labeling across frames for whole-scene or whole-frame state—for example `Weather`, `Camera state`, `Scene`, `Traffic density`, `Procedure phase`, or `Overall quality`.

Dynamic Item Property flow:

1. Open **Item properties** at the top of the Objects inspector.
2. Add or select an Item Property whose **Dynamic** setting is enabled.
3. Set the value at the current frame. The first value creates an item-property range from that frame across the available sequence.
4. Move to another frame and set a different value. Unitlab creates a new keyframe and divides the timeline into value ranges.
5. Expand nested Item Properties to inspect conditional child values beneath the parent range.
6. Select a range on the timeline to jump to it, inspect its label/color, and adjust the temporal boundaries when required.

Static Item Properties appear as one full-item range. Dynamic Item Properties appear as independent timeline rows and are not attached to one object track. Class properties and Item Properties can both use nested conditional logic; their timeline placement distinguishes object state from item-level scene state.

## Timeline UX and user flow

The video and medical timeline is the temporal control center for geometry, object state, and item-level state.

**Timeline structure**

- The header shows the editable current-frame number, total frames, previous/play/next controls, the Tracking settings menu, timeline zoom from 1× to 10×, and loop control.
- The left column lists tracks by class and geometry. Bounding boxes, cuboids, polygons, masks/brushes, skeletons, points, polylines, instances, Item Properties, and dynamic annotation properties can have timeline rows.
- Parent object and Item Property rows can be expanded to reveal nested dynamic-property rows.
- Colored bars show active ranges. Diamond markers show keyframes. Explicit interpolation spans are connected visually between their source keyframes.
- The vertical playhead and numbered badge identify the active frame.

**Navigation and selection**

1. Enter a frame number, use previous/play/next, press **←/→**, click the timeline, or drag the numbered playhead to move through the sequence.
2. Click a track label or bar to select the corresponding annotation. The canvas and object inspector synchronize to that selection.
3. Enable **Auto zoom on timeline click** in View Settings to center the selected annotation automatically.
4. Use the 1×–10× timeline zoom and horizontal scrolling to inspect dense keyframes; vertical scrolling keeps the track-label column synchronized with the rows.

**Range editing and contextual actions**

- Drag a segment’s left or right handle to change where the annotation or property range begins or ends.
- Right-click a geometry segment to start/stop Tracking, hide/show the segment, delete it, or access mask interpolation when applicable.
- Hidden ranges remain part of the annotation history but are not rendered in their hidden interval.
- Selecting an object on the canvas selects its timeline row; selecting its timeline row selects the object on the canvas.
- Read-only release and passive Multiview panels show timeline context without exposing mutation actions.

**Tracking settings**

The **Tracking** menu contains two independent switches:

- **Auto-Tracking — Predict later frames with ML:** new supported annotations can immediately start model-assisted propagation.
- **Interpolation — Tween between keyframes:** geometry is generated between manually defined keyframes.

These settings can be used separately. Auto-Tracking follows visual evidence; interpolation follows the geometry defined at its surrounding keyframes.

## Mask interpolation

Video mask interpolation is distinct from general object interpolation. The user places or edits segmentation keyframes, then uses the **Interpolate mask** timeline action to materialize intermediate masks between them. Generated in-between masks remain reviewable. This is most useful for smooth boundary motion and still needs correction around occlusion, topology changes, rapid deformation, and scene cuts.

When a mask segment contains at least two manually created keyframes, its context menu exposes **Interpolate mask**. After intermediate masks are materialized, **Clear interpolation** removes the generated in-between frames while preserving the source keyframes.

The embedding view projects embeddable assets into a visual space and supports drag or crop-style region selection. Users can select a cluster and review its associated thumbnails before adding, excluding, or organizing the selected assets.

Useful curation patterns include:

- locating dense duplicate or near-duplicate regions;
- sampling from visually distinct clusters;
- finding outliers and rare conditions;
- comparing source domains;
- building a more diverse pilot dataset;
- selecting negative examples near a target class.

The two-dimensional plot is a navigation aid, not a guarantee that every nearby point is semantically identical. Operators should inspect the actual assets before turning a region into a dataset.

## Custom embedding spaces and vector search

The SDK can create named embedding spaces with a specified dimensionality and optional model name, upload vectors for an asset or a video frame, bulk-upsert vectors, search by a query vector, and optionally scope the search to a project or level.

This allows teams to use Unitlab’s curation interface while retaining control over the embedding model and vector space used for similarity operations.

## Search, duplicates, outliers, and UMAP

Unitlab includes visual similarity search, natural-language CLIP-style search, duplicate detection, outlier detection, quality-inconsistency checks, and UMAP visualization. These embedding and visual exploration experiences are available for image and video data.

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

![Frame-aware video operations support object identity, temporal properties, review, and correction across a scene.](../.gitbook/assets/video-workbench.png)

*Frame-aware video operations support object identity, temporal properties, review, and correction across a scene.*

