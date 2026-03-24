# Video Generation Models

This file provides working model-selection guidance for the skill. It is not a source of hard product guarantees.

## Scope and Freshness

- Last reviewed: 2026-03-24
- Basis: internal prompt-engineering usage patterns and operator heuristics
- Do not treat duration, resolution, text quality, or feature behavior here as contractual limits
- When exact platform limits matter, confirm them in the active provider UI or official documentation before production use

## Seedream

### Best Fit

- Atmosphere-heavy openings
- Texture-rich close-ups
- Composition-led ending shots
- Scenes where surface detail matters more than complex motion

### Typical Strengths

- Strong scene mood and visual polish
- Good control through camera and lighting language
- Better fit for detail-oriented prompts than action-dense prompts

### Common Risks

- Motion-heavy prompts may become unstable
- Large action changes can weaken shot coherence
- Multi-shot subject continuity still needs explicit carry-over fields

### Prompt Guidance

- Put subject, setting, and mood first
- Use one camera movement, not several
- Specify light direction and one primary texture cue
- End with style or finish descriptors rather than stacking many adjectives

## Seedance

### Best Fit

- Push or progression shots
- Transition nodes
- Motion-led narrative beats
- Cases where temporal continuity matters more than texture richness

### Typical Strengths

- Better motion continuity than purely atmosphere-first prompting
- More suitable for directional movement and shot connection
- Useful when the shot logic depends on action progression

### Common Risks

- Fine texture and micro-detail may be weaker than in detail-first models
- Style can drift if the prompt mixes too many visual directions
- Character consistency still needs explicit continuity anchors

### Prompt Guidance

- Lead with a single dominant action
- Name the movement direction and tempo
- Reassert subject identity, wardrobe, and lighting
- Use transition prompts that explicitly mention both the source and destination frame logic

## Kling

### Best Fit

- Longer-shot sequences
- Chinese-first prompting workflows
- Cinematic movement when the user wants a longer take instead of rapid cutting

### Typical Strengths

- Better fit for long-take thinking than short-node-only workflows
- Stronger benefit from explicit cinematic language
- Often useful when the user wants one coherent main shot instead of many fragments

### Common Risks

- Requires more precise prompt writing
- Detail may soften in complex distant scenes
- Long outputs still need a clear shot plan to avoid drift

### Prompt Guidance

- Be explicit with camera language
- State the movement path, not just the mood
- Prefer clear Chinese shot descriptions if that matches your workflow
- Keep the prompt logically ordered: subject -> environment -> motion -> light -> finish

## Selection Matrix

| Need | Preferred Model | Why |
|------|-----------------|-----|
| Big atmosphere, strong first frame | Seedream | Better fit for mood, composition, and texture |
| Smooth action progression | Seedance | Better fit for motion continuity |
| Transition between shots | Seedance | Better fit for directional or shape-based carry-over |
| Detail-centric close-up | Seedream | Better fit for fine surface cues |
| Long take or Chinese-first cinematic prompt | Kling | Better fit for longer-shot planning |

## Decision Rule

```text
If the user explicitly names a model, follow that unless it clearly conflicts with the task.

Otherwise:
- atmosphere/detail dominant -> Seedream
- motion/transition dominant -> Seedance
- long-take/cinematic Chinese workflow -> Kling
```

## What to Update Over Time

Refresh this file whenever one of these changes:

- A provider changes exposed model versions
- A model gains or loses image-reference support
- A model materially improves or regresses in motion stability
- Your logged cases show a repeated success or failure pattern
