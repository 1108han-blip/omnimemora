# Supervisor Skills

This directory is the canonical source for supervisor workspace skills.

## Rule

- Put editable skill source here: `supervisor/skills/<skill-name>/SKILL.md`
- Keep references, templates, examples, and cases under the same skill directory
- Do not maintain duplicate editable copies under `supervisor/.skills/`
- Do not rely on container image rebuilds for skill updates

## Why

OpenClaw loads workspace skills from `workspaceDir/skills` and gives them higher precedence than bundled or managed skills. For this workspace, that means:

- Preferred path: `supervisor/skills/...`
- Avoid split-brain maintenance between `skills/` and `.skills/`

## Current Skill

- `video-prompt-engineering`

## Packaging Note

- `video-prompt-engineering.skill` is treated as a packaged artifact, not the primary editable source
- Edit the directory under `supervisor/skills/` first
- Repackage only if your downstream workflow explicitly requires a `.skill` archive
