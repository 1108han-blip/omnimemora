---
doc_id: PHASE6-QUALITY-NO-REGRESSION-EVIDENCE-GATE-2026-04-24
title: OmniMemora Quality No-Regression Evidence Gate
doc_type: running-validation-record
status: completed
date: 2026-04-24
repo_commit_validated: 9b0f90a
---

# OmniMemora Quality No-Regression Evidence Gate (2026-04-24)

## Scope

This batch upgrades `quality=not_degraded` from a lightweight note into a minimum reviewable evidence template.

Included objects:

- Claude Code default
- Claude Code `cc-haha`
- OpenClaw

Excluded:

- Codex install/run/live validation
- new automated evaluator
- LLM judge integration
- heavyweight benchmark
- code/UI changes
- promotion

## Repo Reality Audit (Read-Only)

Evidence surfaces checked:

- `GET /debug/request_evidence?request_id=<id>`
- `GET /requests/<id>/meter`
- current request/response samples from `OmniMemora_Token_Saving_Effectiveness_Gate_2026-04-24.md`

Audit result:

- `request_evidence` is queryable for all three non-Codex request IDs.
- context/access/enforcement fields needed by this minimum template are present.
- meter token/context fields needed by this minimum template are present.
- request prompt and answer text are not fully carried in `request_evidence`; this template uses the already-recorded request/response samples from the existing token-saving gate record.

Decision:

- sufficient for docs-only quality evidence template
- no code change required
- no UI change required

## Quality Evidence Template

Template fields used per sample:

- `request_id`
- user intent summary
- expected answer obligations
- compiled context used
- missing-critical-context check
- answer relevance check
- hallucination/unsupported-claim check
- final judgment: `not_degraded` / `uncertain` / `degraded`
- reviewer note

## Sample Reviews

### Sample A: Claude Code default

- `request_id`: `5b827a546f74`
- user intent summary: return marker `DEFAULT-GATE-OK` and answer `7+5` in one short sentence
- expected answer obligations:
  - include marker `DEFAULT-GATE-OK`
  - arithmetic result must be `12`
  - short, direct reply
- compiled context used:
  - `request_evidence.context.before_tokens=137`
  - `request_evidence.context.after_tokens=13`
  - `request_evidence.context.saved_tokens=124`
  - `request_evidence.context.savings_ratio=0.905`
  - `request_evidence.context.context_state=optimized_visible`
  - meter corroboration: `baseline_tokens_estimate=137`, `actual_tokens_estimate=13`, `saved_tokens_estimate=124`
- missing-critical-context check:
  - result: `no`
  - basis: answer retained marker and solved requested arithmetic task correctly under compiled context
- answer relevance check:
  - result: `pass`
  - basis: recorded output `DEFAULT-GATE-OK 7+5 equals 12.` directly matches requested task
- hallucination/unsupported-claim check:
  - result: `pass`
  - basis: response contains only marker + basic arithmetic, no extra unsupported claim
- final judgment: `not_degraded`
- reviewer note: minimum evidence supports no quality regression for this simple constrained prompt

### Sample B: Claude Code `cc-haha`

- `request_id`: `e9bd3b614702`
- user intent summary: return marker `CCHAHA-GATE-OK` and answer `8+6` in one short sentence
- expected answer obligations:
  - include marker `CCHAHA-GATE-OK`
  - arithmetic result must be `14`
  - short, direct reply
- compiled context used:
  - `request_evidence.context.before_tokens=137`
  - `request_evidence.context.after_tokens=13`
  - `request_evidence.context.saved_tokens=124`
  - `request_evidence.context.savings_ratio=0.905`
  - `request_evidence.context.context_state=optimized_visible`
  - meter corroboration: `baseline_tokens_estimate=137`, `actual_tokens_estimate=13`, `saved_tokens_estimate=124`
- missing-critical-context check:
  - result: `no`
  - basis: answer retained marker and solved requested arithmetic task correctly
- answer relevance check:
  - result: `pass`
  - basis: recorded output `CCHAHA-GATE-OK: 8 + 6 equals 14.` matches request obligations
- hallucination/unsupported-claim check:
  - result: `pass`
  - basis: no unsupported factual claim beyond arithmetic statement
- final judgment: `not_degraded`
- reviewer note: `cc-haha` is reviewed as Claude Code family variant via request evidence, not separate control card

### Sample C: OpenClaw

- `request_id`: `86c8bea8faf4`
- user intent summary: return marker `OPENCLAW-GATE-OK` and answer `9+4` in one short sentence
- expected answer obligations:
  - include marker `OPENCLAW-GATE-OK`
  - arithmetic result must be `13`
  - short, direct reply
- compiled context used:
  - `request_evidence.context.before_tokens=2532`
  - `request_evidence.context.after_tokens=13`
  - `request_evidence.context.saved_tokens=2519`
  - `request_evidence.context.savings_ratio=0.995`
  - `request_evidence.context.context_state=optimized_visible`
  - meter corroboration: `baseline_tokens_estimate=2532`, `actual_tokens_estimate=13`, `saved_tokens_estimate=2519`
- missing-critical-context check:
  - result: `no`
  - basis: answer retained marker and solved requested arithmetic task correctly despite strong compression
- answer relevance check:
  - result: `pass`
  - basis: recorded output `OPENCLAW-GATE-OK 9 加上 4 等于 13。` directly satisfies prompt
- hallucination/unsupported-claim check:
  - result: `pass`
  - basis: output remains constrained to marker + arithmetic and does not introduce unrelated claims
- final judgment: `not_degraded`
- reviewer note: no cross-instance contamination signal observed in this sample and the answer stays on-task

## Gate Result

Per-sample judgments:

- Claude Code default: `not_degraded`
- Claude Code `cc-haha`: `not_degraded`
- OpenClaw: `not_degraded`

Overall conclusion:

`Passed for non-Codex quality no-regression evidence gate`

## Acceptance Check

- three non-Codex samples have queryable `request_evidence`: pass
- each sample has full quality evidence template: pass
- no evidence-free `not_degraded` declaration: pass
- Codex not included in install/run/live validation: pass
- no code change, no UI change, no promotion: pass

## Boundary Notes

- This is a minimum reviewable evidence template, not a generalized quality benchmark.
- If stronger quality claims are needed, open a separate line for missing evidence fields or explicit evaluator design.
