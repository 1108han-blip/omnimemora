# Case Log

Record each generation attempt as a structured case entry. The purpose is to capture what was tried, what failed, and what should change next.

## Entry Template

Use the following Markdown structure for each case:

````markdown
## YYYY-MM-DD | [video theme] | [node]

**Generation Mode**: text-to-video / image-to-video
**Model**: Seedream / Seedance / Kling / other
**Duration**: 1-10s
**Reference Asset**: none / image / prior frame / other
**Rating**: ⭐1-5

**Prompt**
```text
[positive prompt]
```

**Negative Prompt**
```text
[negative prompt]
```

**Continuity Notes**
- [what had to stay consistent]

**Observed Result**
- [what worked]
- [what broke]

**Failure Mode**
- [identity drift / lighting jump / motion jitter / composition collapse / other]

**Next Iteration**
- [exact change to apply next time]
````

## Usage Rules

- Add one entry per node run, not just one entry per whole project
- If multiple iterations were tried on the same node, log each iteration separately
- Write failure modes concretely; avoid comments like "not ideal" without saying why
- When a pattern repeats, summarize it back into `models.md` or `templates.md`

## Rating Guide

- ⭐5: Fully usable, no changes needed
- ⭐4: Usable with minor polish
- ⭐3: Partially usable, needs meaningful revision
- ⭐2: Barely usable, obvious drift or artifacts
- ⭐1: Failed run, should not be reused

## Suggested Failure Tags

- `identity_drift`
- `lighting_jump`
- `palette_shift`
- `motion_jitter`
- `anatomy_error`
- `transition_break`
- `composition_clutter`
- `detail_loss`
- `text_render_error`

## Index

- [Opening Cases](#opening-cases)
- [Push Cases](#push-cases)
- [Close-up Cases](#close-up-cases)
- [Transition Cases](#transition-cases)
- [Ending Cases](#ending-cases)

## Opening Cases


## Push Cases


## Close-up Cases


## Transition Cases


## Ending Cases
