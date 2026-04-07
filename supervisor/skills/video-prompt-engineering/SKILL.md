---
name: video-prompt-engineering
description: Craft structured prompts for short-form video generation across a node-based pipeline. Use when generating video content, writing prompts for text-to-video or image-to-video models, building a short video automation pipeline, or optimizing prompts for Seedance, Seedream, Kling, or similar video AI models. Triggers on: "视频提示词", "video prompt", "seedance", "seedream", "kling", "视频生成", "短视频自动化", "视频节点", "镜头描述", "按节点走".
---

# Video Prompt Engineering

## Overview

Transform a video concept into a stable, node-based prompt package for short-form generation. The default pipeline is:

**Opening -> Push -> Close-up -> Transition -> Ending**

The skill must produce a reusable output package instead of ad hoc prompt text. Each node should include:

- `node`
- `goal`
- `generation_mode`
- `recommended_model`
- `duration`
- `prompt`
- `negative_prompt`
- `continuity_notes`
- `reference_requirements`

If the user explicitly asks for fewer or more shots, adapt the node count while preserving the same output schema.

## Input Contract

Accept any of the following user inputs:

- A topic only
- A short script or storyboard
- A visual style request
- A reference image requirement
- A target model preference

Normalize user input into this internal structure before writing prompts:

```yaml
theme:
script_or_story:
visual_style:
subject:
setting:
mood:
target_duration:
aspect_ratio:
language:
has_reference_image:
reference_constraints:
model_preference:
delivery_goal:
```

## Defaulting Rules

If the user leaves fields unspecified, use these defaults:

- `target_duration`: short-form, 5 nodes, about 10-15 seconds total
- `aspect_ratio`: `9:16` for short-video use unless the user asks otherwise
- `language`: English prompt text by default; use Chinese if the target model or user request clearly benefits from it
- `has_reference_image`: `false` unless the user provides or requests one
- `delivery_goal`: visually coherent social short, not dialogue-heavy narrative
- `style`: preserve the user's explicit style first; otherwise prefer cinematic, physically plausible, concise prompts

Do not invent detailed story beats that contradict the user's theme. Fill only the minimum missing context needed to complete the pipeline.

## Output Contract

When invoked with requests like "帮我写一个 [主题] 的视频提示词，按节点走", always return the following sections in order:

### 1. Brief

Summarize the concept in 1-2 sentences.

### 2. Global Continuity

Output one continuity block covering:

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

### 3. Node Plan

Provide one row per node:

| Node | Goal | Generation Mode | Recommended Model | Duration |
|------|------|-----------------|-------------------|----------|

### 4. Prompt Package

For each node, output:

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

## Workflow Decision Tree

```text
用户输入: 视频主题 / 脚本 / 描述 / 参考图
         |
         v
    分析核心约束
    - 目标时长?
    - 风格要求?
    - 是否有参考图?
    - 是否指定模型?
         |
         v
    是否存在参考图或明确要求保留已有画面?
         |
    否 -> 优先 text-to-video
    是 -> 优先 image-to-video
         |
         v
    构建 continuity state
    - 主体一致性
    - 场景一致性
    - 光线/色调一致性
    - 运镜/节奏一致性
         |
         v
    按节点输出提示词包
    (Opening -> Push -> Close-up -> Transition -> Ending)
```

## Node Definitions

| Node | Purpose | Prompt Focus | Model Preference |
|------|---------|--------------|------------------|
| Opening | 建立第一印象，吸引注意 | 场景描述 + 氛围词 + 镜头运动 | Seedream 优先，强调场景质感 |
| Push | 推进叙事，引导视线 | 主体动作 + 前景 + 运动方向 | Seedance 优先，强调连续动作 |
| Close-up | 突出情绪和细节 | 局部主体 + 材质/表情 + 光线 | Seedream 优先，强调细节质感 |
| Transition | 连接镜头，降低跳变 | 形状匹配 + 运动关系 + 时长 | Seedance 优先，强调衔接控制 |
| Ending | 收束叙事，形成记忆点 | 构图 + 留白 + 结尾动作 | Seedream 优先，强调构图与氛围 |

If the user explicitly targets long-form or a single long take, consider Kling for selected nodes or the whole sequence. See `references/models.md`.

## Generating Prompts by Node

### Opening

**Goal**: 建立场景、氛围、视觉基调

**Prompt Formula**:

```text
[subject] in [setting], [mood], [camera movement], [lighting], [style], [continuity anchor]
```

**Notes**:

- Prioritize scene clarity over action density
- Lock the continuity anchor early, such as wardrobe, object shape, or palette
- Prefer broader framing and stable movement language

### Push

**Goal**: 推进叙事，引导视线

**Prompt Formula**:

```text
[subject action], [foreground layer], [movement direction], [camera push], [tempo], [continuity anchor]
```

**Notes**:

- Use one dominant action, not several competing actions
- Add a foreground element only if it helps depth or framing
- Reassert the subject and lighting from the continuity block

### Close-up

**Goal**: 捕捉情绪、细节、质感

**Prompt Formula**:

```text
[detail subject], [material or expression detail], [light direction], [lens or framing], [emotion], [continuity anchor]
```

**Notes**:

- Use specific local detail, such as hands, eyes, object texture, steam, dust, fabric, metal
- Keep the camera language consistent with earlier nodes
- Prefer physically plausible detail cues over abstract adjectives

### Transition

**Goal**: 自然连接两个镜头

**Prompt Formula**:

```text
[end element of current shot] transforms into [start element of next shot], [transition method], [duration], [continuity anchor]
```

**Notes**:

- Prefer shape match, directional motion match, or lighting match over generic dissolve
- Avoid crossfade for fast motion unless the effect is intentionally dreamy
- Explicitly name both sides of the transition

### Ending

**Goal**: 留下印象，收束叙事

**Prompt Formula**:

```text
[subject] at [ending setting], [composition], [ending mood], [final motion or hold], [continuity anchor]
```

**Notes**:

- Composition matters more than action density
- Leave visual breathing room
- End with a hold, fade, or clean movement resolution

## Negative Prompts

Use concise negative prompts unless a specific model benefits from a longer exclusion list.

**General**:

```text
blurry, low quality, distorted, stutter, jitter, watermark, logo
```

**When people are present**:

```text
bad anatomy, distorted face, extra fingers, asymmetrical eyes, unnatural pose
```

**When motion is critical**:

```text
frame inconsistency, jittery motion, motion tearing, ghosting
```

## Model Guidance

Detailed notes live in `references/models.md`.

Important: model selection advice in this skill is heuristic, not contractual. Treat it as working guidance based on internal usage patterns and update it when your toolchain, provider, or model version changes.

Choose models in this order:

1. Obey the user's explicitly requested model if reasonable.
2. If scene atmosphere or fine detail is dominant, prefer Seedream.
3. If motion continuity or shot connection is dominant, prefer Seedance.
4. If long-take structure or Chinese-first prompting is dominant, consider Kling.

## Prompt Templates

Full templates and continuity-aware prompt fields live in `references/templates.md`.

## End-to-End Example

For a complete invocation and response example, see `references/examples.md`.

## Case Logging

Log results in `references/cases.md` after generation. Each entry should capture:

- node
- model
- generation mode
- prompt
- negative prompt
- rating
- observed failure mode
- next iteration plan

The goal is not just archiving prompts, but building a reusable failure-and-fix dataset for future runs.
