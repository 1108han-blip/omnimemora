# End-to-End Examples

This file shows what the skill should output when triggered in a real conversation.

## Example 1

**User request**

```text
帮我写一个“雨夜茶馆”主题的视频提示词，按节点走，做成 9:16 短视频，整体偏电影感。
```

**Expected response shape**

### 1. Brief

A cinematic short set in a rain-soaked teahouse at night. The sequence moves from atmosphere, to human presence, to tactile detail, then resolves in a quiet final frame.

### 2. Global Continuity

```yaml
subject_identity: solitary tea master in dark linen clothing
wardrobe_or_surface_details: dark indigo robe, wooden tea tray, porcelain cup, warm steam
setting: old teahouse interior by a rain-streaked window at night
lighting: warm tungsten interior light with cool blue rain light from window side
color_palette: amber, deep brown, muted blue
camera_language: slow cinematic movement, stable framing, shallow depth of field on details
motion_tempo: calm and measured
aspect_ratio: 9:16
overall_style: cinematic, tactile, moody, photoreal
continuity_risks:
  - warm/cool light balance drifting between shots
  - robe color shifting away from dark indigo
  - cup and tea tray design changing between nodes
```

### 3. Node Plan

| Node | Goal | Generation Mode | Recommended Model | Duration |
|------|------|-----------------|-------------------|----------|
| Opening | Establish the rainy teahouse atmosphere | text-to-video | Seedream | 3s |
| Push | Move attention toward the tea master | text-to-video | Seedance | 2.5s |
| Close-up | Show tactile tea detail and emotion | text-to-video | Seedream | 2s |
| Transition | Bridge steam and window rain visually | text-to-video | Seedance | 1.5s |
| Ending | Leave a quiet final impression | text-to-video | Seedream | 2.5s |

### 4. Prompt Package

```yaml
- node: Opening
  goal: Establish the world, subject, and tone
  generation_mode: text-to-video
  recommended_model: Seedream
  duration: 3s
  prompt: >
    A solitary tea master in a dark indigo robe stands inside an old teahouse at night,
    rain streaking across the wooden window, warm tungsten light inside and cool blue rain light
    outside, slow tracking shot, cinematic, tactile wood texture, preserve the dark robe,
    porcelain cup, amber-and-blue palette
  negative_prompt: >
    blurry, low quality, distorted, stutter, jitter, watermark, logo
  continuity_notes:
    - Preserve robe color as dark indigo
    - Preserve warm interior light and cool exterior rain light contrast
    - Preserve porcelain cup and wooden tea tray design
  reference_requirements:
    - None
  handoff_notes:
    - End with the tea master raising one hand toward the tea tray

- node: Push
  goal: Advance the action and guide attention inward
  generation_mode: text-to-video
  recommended_model: Seedance
  duration: 2.5s
  prompt: >
    The tea master reaches toward the steaming porcelain cup, rain-blurred window in the background,
    hanging beads soft in the foreground, camera slowly pushes in, calm measured tempo,
    preserve the same robe, tea tray, warm-and-cool lighting logic
  negative_prompt: >
    blurry, jittery motion, frame inconsistency, distorted anatomy, watermark
  continuity_notes:
    - Keep the same subject identity and sleeve silhouette
    - Maintain slow camera language and consistent light direction
  reference_requirements:
    - Previous frame optional if continuity is sensitive
  handoff_notes:
    - End on the hand, cup rim, and rising steam for Close-up

- node: Close-up
  goal: Highlight tactile detail and emotional focus
  generation_mode: text-to-video
  recommended_model: Seedream
  duration: 2s
  prompt: >
    Close-up of the tea master's hand holding a thin porcelain cup, steam rising in warm light,
    tiny droplets of condensation, shallow depth of field, 85mm lens feel, contemplative mood,
    preserve the amber highlights, indigo sleeve edge, and porcelain texture
  negative_prompt: >
    blurry, distorted hand, bad anatomy, extra fingers, oversmoothed texture, watermark
  continuity_notes:
    - Keep cup shape identical to Opening
    - Keep steam warm and directional against cool window ambience
  reference_requirements:
    - Prior node frame recommended for hand and cup continuity
  handoff_notes:
    - Let steam fill frame to motivate the transition

- node: Transition
  goal: Bridge steam and rain into the final image
  generation_mode: text-to-video
  recommended_model: Seedance
  duration: 1.5s
  prompt: >
    Rising tea steam transforms into rain mist on the night window, shape-matched transition,
    soft directional motion upward into diagonal rain streaks, 1.5 seconds,
    preserve the same warm amber highlights and cool blue shadows
  negative_prompt: >
    abrupt cut feel, jitter, frame inconsistency, broken geometry, watermark
  continuity_notes:
    - Match the steam shape to the rain texture
    - Maintain palette and light logic without abrupt contrast jump
  reference_requirements:
    - Prior and next keyframes helpful but not required
  handoff_notes:
    - Land on a still composition with the window and cup in frame

- node: Ending
  goal: Resolve the sequence with a quiet final impression
  generation_mode: text-to-video
  recommended_model: Seedream
  duration: 2.5s
  prompt: >
    The porcelain tea cup rests on the wooden tray beside the rain-lit window,
    the tea master now softly out of focus in the background, balanced vertical composition,
    quiet reflective mood, hold still before a gentle fade, preserve the amber interior glow,
    muted blue rain light, and uncluttered cinematic frame
  negative_prompt: >
    cluttered composition, jitter, distorted details, abrupt motion, watermark
  continuity_notes:
    - Keep cup, tray, and window design consistent with earlier nodes
    - Resolve movement into a still hold
  reference_requirements:
    - Prior frame optional for exact prop continuity
  handoff_notes:
    - End on a clean 0.5s hold
```

## Example 2

**User request**

```text
帮我写一个“竹林旅人”的视频提示词，按节点走，我有一张参考图，要保持人物和场景一致。
```

**Expected adjustment**

- Switch the default generation mode to `image-to-video`
- In every node, make `reference_requirements` explicit
- In every prompt, state exactly what must remain unchanged from the reference
- Tighten continuity notes around face, clothing, lighting, and composition anchors
