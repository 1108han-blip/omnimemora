# Prompt Templates

Use these templates to produce continuity-aware prompt packages instead of isolated prompt lines.

## Global Continuity Block

Always define this block before writing node prompts:

```yaml
subject_identity:
wardrobe_or_surface_details:
setting:
lighting:
color_palette:
camera_language:
motion_tempo:
aspect_ratio:
overall_style:
continuity_risks:
```

Recommended continuity anchors:

- Character identity markers: age range, silhouette, hair, clothing, props
- Scene anchors: architecture, weather, time of day, landmark objects
- Visual anchors: key light direction, palette, lens feel, texture style
- Motion anchors: calm, deliberate, energetic, drifting, handheld, locked-off

## Node Output Template

Use this exact structure for every node:

```yaml
node:
goal:
generation_mode:
recommended_model:
duration:
prompt:
negative_prompt:
continuity_notes:
reference_requirements:
handoff_notes:
```

## Full Node Templates

### Opening

```yaml
node: Opening
goal: Establish the world, subject, and visual tone
generation_mode: text-to-video or image-to-video
recommended_model:
duration:
prompt: >
  [subject] in [setting], [mood], [camera movement], [lighting], [style],
  preserve [continuity anchor]
negative_prompt: >
  blurry, distorted, stutter, watermark, logo
continuity_notes:
  - Preserve subject silhouette and wardrobe
  - Preserve lighting direction and palette
reference_requirements:
  - None or reference image for scene/style lock
handoff_notes:
  - Establish the anchor object, palette, or costume to carry into Push
```

### Push

```yaml
node: Push
goal: Advance the action and direct viewer attention
generation_mode: text-to-video or image-to-video
recommended_model:
duration:
prompt: >
  [subject action], [foreground layer], [movement direction], camera pushes in,
  [tempo], preserve [continuity anchor]
negative_prompt: >
  blurry, jittery motion, frame inconsistency, distorted anatomy, watermark
continuity_notes:
  - Keep the same subject identity, costume, and environment
  - Maintain camera language from Opening
reference_requirements:
  - Previous frame or reference image when continuity is critical
handoff_notes:
  - End on a detail that can motivate Close-up
```

### Close-up

```yaml
node: Close-up
goal: Highlight emotion, texture, or a decisive detail
generation_mode: text-to-video or image-to-video
recommended_model:
duration:
prompt: >
  close-up of [detail subject], [detail description], [light direction],
  [lens or framing], [emotion], preserve [continuity anchor]
negative_prompt: >
  blurry, distorted face, bad anatomy, extra fingers, oversmoothed texture, watermark
continuity_notes:
  - Keep lighting direction identical unless the story intentionally shifts
  - Keep texture and palette aligned with earlier nodes
reference_requirements:
  - Prior node frame recommended for face, hand, or object consistency
handoff_notes:
  - Pick a shape, movement, or light cue that can transition into the next node
```

### Transition

```yaml
node: Transition
goal: Bridge the previous and next shots without visual discontinuity
generation_mode: text-to-video or image-to-video
recommended_model:
duration:
prompt: >
  [current ending element] transforms into [next opening element],
  [transition method], [duration], preserve [continuity anchor]
negative_prompt: >
  abrupt cut feel, jitter, frame inconsistency, broken geometry, watermark
continuity_notes:
  - Match shape, movement direction, or lighting across both shots
  - Keep transition logic physically or visually motivated
reference_requirements:
  - Previous and next keyframes if available
handoff_notes:
  - Land cleanly on the opening frame of Ending
```

### Ending

```yaml
node: Ending
goal: Resolve the sequence with a clear final impression
generation_mode: text-to-video or image-to-video
recommended_model:
duration:
prompt: >
  [subject] at [ending setting], [composition], [ending mood],
  [final motion or hold], preserve [continuity anchor]
negative_prompt: >
  cluttered composition, jitter, distorted details, abrupt motion, watermark
continuity_notes:
  - Keep final palette and subject design consistent with the opening
  - Resolve the motion tempo instead of escalating it
reference_requirements:
  - Prior node frame optional, useful for precise final composition
handoff_notes:
  - End on a clean hold, fade, or minimal final motion
```

## Image-Reference Variants

Use these additions when the user provides a reference image or asks to preserve a prior visual:

- `same subject identity as reference`
- `same wardrobe and color palette as reference`
- `same environment layout and lighting logic as reference`
- `preserve the composition language of the reference while changing only [action/detail/time]`

Avoid vague carry-over instructions such as only `same as previous`. Be explicit about what must remain unchanged.

## Negative Prompt Packs

### General Pack

```text
blurry, low quality, distorted, stutter, jitter, watermark, logo
```

### Character Pack

```text
bad anatomy, distorted face, extra fingers, asymmetrical eyes, unnatural pose
```

### Motion Pack

```text
frame inconsistency, motion tearing, ghosting, jittery motion, unstable camera
```

## Style Vocabulary

### Mood

`ethereal`, `mystical`, `serene`, `dramatic`, `contemplative`, `dreamy`, `noir`, `warm`, `cold`

### Camera Motion

`tracking shot`, `dolly in`, `pull-back`, `pan left`, `pan right`, `tilt up`, `crane shot`, `handheld`, `steady cam`, `aerial`

### Lighting

`golden hour`, `backlit`, `volumetric light`, `soft diffused light`, `hard shadows`, `neon glow`, `rim lighting`

### Quality and Finish

`cinematic`, `photorealistic`, `hyperrealistic`, `fine texture detail`, `soft film grain`, `clean composition`

### Emotion

`contemplative`, `nostalgic`, `tense`, `serene`, `melancholic`, `joyful`, `mysterious`

## Useful Phrases

- `preserve subject continuity`
- `maintain the same lighting logic`
- `match the previous shot's palette`
- `resolve motion into a still hold`
- `shape-matched transition`
- `maintaining continuity`
- `shallow depth of field`
