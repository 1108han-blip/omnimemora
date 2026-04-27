# SFE-006: Real Token Saving A/B Gate

## Goal

Prove that OmniMemora-compiled prompts are **actually shorter** than original prompts
when sent to the same model, and that the compiled output **quality is not worse**.

This is a real A/B test, not a dashboard metric.

## Method

For each of N real tasks:

```
Task Prompt → [A] Send ORIGINAL to model      → record tokens + output
            → [B] OmniMemora COMPILE → model → record tokens + output

Compare A vs B:
  - B input tokens < A input tokens?
  - B output quality ≥ A output quality?
```

## Gate Criteria

A task **passes** only if ALL hold:

| Criterion | Requirement |
|-----------|-------------|
| Compile | `compile_status == "compile_success"` |
| Token save | `compiled_input_tokens < original_input_tokens` (strict) |
| Quality | Output meets quality criteria (see below) |

**Gate threshold**: at least 9/10 *eligible* (compile_success) tasks must pass.

- Tasks with `compile_skipped` or `compile_failed` are excluded from denominator.
- If fewer than 10 tasks are eligible, all eligible tasks must pass.

## Running

### 1. Prerequisites

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-...

# Optional: override model
export OMNIMEMORA_ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Optional: override agent_id (which memory scope to use)
export SFE006_AGENT_ID=claude_code
```

### 2. Prepare tasks

Edit [sfe006_tasks.json](sfe006_tasks.json) with real tasks from your use cases.

Each task needs:
- `id`, `description`
- `messages` (array of role/content objects)
- `quality_check` with `must_contain`, `must_not_contain`, `min_length`

### 3. Run

```bash
cd OmniMemora
python -m pytest 5_connectors/adapter/__tests__/test_sfe006_real_token_saving_ab_gate.py -v

# Debug: run single task
SFE006_TASK_INDEX=0 python -m pytest 5_connectors/adapter/__tests__/test_sfe006_real_token_saving_ab_gate.py -v -s

# Custom task file
SFE006_TASK_FILE=path/to/my_tasks.json python -m pytest ...
```

## Output Interpretation

```
======================================================================
SFE-006 GATE SUMMARY
======================================================================
  Total tasks:   10
  Eligible:      8 (compile_success only)
  Passed:        7/8
  Gate threshold: 9/10 (or 100% if < 9 eligible)
======================================================================
  Detailed results:
  ✅ [compile_success    ] task-001: PASS: saved 142 tokens (12.3%), quality OK
  ✅ [compile_success    ] task-002: PASS: saved 89 tokens (8.1%), quality OK
  ...
  ❌ [compile_success    ] task-005: FAIL: no_token_save(1240>=1240); quality_fail: ...
======================================================================

  Eligible:   7/8
  Required:    ≥8
  Gate:        ❌ FAILED
```

## If the Gate Passes

OmniMemora can legitimately claim: *"compiled prompts are shorter AND quality is preserved."*

Next steps:
- Enable token saving claims in UI (5173)
- Expand task coverage to more task types

## If the Gate Fails

OmniMemora must NOT claim real token savings.

Action items:
- Review failed tasks: which task types lose quality?
- Adjust compile strategy (packing rules, memory selection)
- Only enable for task types that pass
- Keep meter visible but labeled "observed" not "saved"

## Token Counting

- **Anthropic models**: `len(text) / 3.8` chars/token (conservative estimate)
- **OpenAI models**: `tiktoken` cl100k_base

Conservative estimation is intentional: overestimating compiled tokens makes
passing the gate *harder*, so a passed gate is more meaningful.

## Quality Evaluation

Quality check is task-specific (defined in `quality_check`):

- `must_contain`: all substrings must appear in compiled output
- `must_not_contain`: no substring should appear
- `min_length`: output must be at least N characters

If no quality check is defined, the test only checks for API errors.
