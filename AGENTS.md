# AGENTS.md

## Session Startup Rule (Mandatory)

Before any implementation or reporting work in this repo:

1. Identify the active phase from the latest project handoff / current milestone docs.
2. Read the working-principles and SOP docs for that active phase.
3. Do **not** hardcode Phase 3 startup reads when the project has moved to a newer phase.
4. If experiment data is involved, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_all.ps1 -RunLabel "session-start" -Tenant all -Salt "<secret-salt>"
```

### Phase 3 Compatibility Note

Use the following only when you are explicitly operating on Phase 3 experiment flows:

- `7_docs/internal/phase3/WORKING_PRINCIPLES_README.md`
- `7_docs/internal/phase3/EXPERIMENT_DATA_GOVERNANCE_SOP.md`

## Data Handling Rule

- Never edit raw meter files manually.
- Always archive and checksum-verify before publishing metrics.
- Use anonymized exports for external reports and paper artifacts.

## Product Path Rule (Mandatory)

- Codex must actively use OmniMemora product interfaces for validation and usage generation.
- Default adapter/API endpoint is `http://127.0.0.1:18011` unless operator explicitly overrides.
- Do not treat legacy endpoints (for example `:8000`) as product truth for current-stage checks.
- Do not bypass product behavior by writing meter files directly or simulating usage outside product API calls.

## MVP Constitution Rule (Mandatory)

Fixed target:

`MVP first; token saving first; no complexity expansion`.

OmniMemora MVP exists only to prove:

- real user requests save tokens.
- real user requests save cost.
- the product stays stable, ultra-low-latency, and does not slow the user down.

Non-MVP expansion is forbidden by default:

- do not continue DLP/RES governance work unless it directly improves token saving, cost saving, speed, or product shrinkage.
- do not expand archive, quarantine, restore, approval, gate, readiness, proposal, or traceability tracks.
- do not preserve long-term evidence for its own sake.
- do not build automatic cleanup chains when a simple retention limit, truncation, deletion, or split is enough.
- do not add UI, reports, dashboards, or diagnostics that cannot prove token-saving value.

Internal data rules:

- internal logs are not assets.
- evidence, trace, proxy, compile, maintenance, and temporary compile artifacts are not user value.
- retain internal logs for at most 7 days by default.
- delete what can be deleted; split or hard-cap any large file that cannot be deleted.
- do not touch user-facing memory under this rule.

Engineering admission rules:

- new engineering must directly make the product save more tokens, save more cost, run faster, or get smaller.
- new code must replace old code, not stack complexity on top of it.
- default internal interface targets are p50 <10ms, p95 <30ms, max <100ms.
- default read paths must not scan historical files or read frozen governance artifacts.
- if token saving, cost saving, speed, or shrinkage cannot be shown, the work stops.

## Shrink-First Product Rule (Mandatory)

Fixed target:

`OmniMemora gets smaller, faster, and simpler; no complexity expansion without direct token-saving value`.

- Freeze complex governance expansion by default:
  - do not continue RES automatic cleanup, approval, gate, proposal, or scale-up tracks.
  - do not add new DLP/RES state machines or report files.
  - do not add UI explanation layers unless they directly improve token-saving value.
- Prefer short retention:
  - internal logs are retained for at most 7 days by default.
  - trace/proxy/compile/maintenance files are temporary debugging artifacts, not product assets.
  - discard internal artifacts after the retention window unless a narrower operator decision says otherwise.
  - do not touch user-facing memory under this rule.
- Engineering changes must be subtractive:
  - new code must replace old code, not merely stack on top of it.
  - new files are disallowed by default unless the same change deletes or deprecates more old files.
  - ordinary read paths must not scan historical files.
  - default targets are fewer files, less resident logic, and fewer background tasks.
- Product value is judged only by:
  - real token saving.
  - real cost saving.
  - stable operation without slowing the product.
  - if these cannot be shown, the work should stop.
- Every change must report:
  - whether file count decreased or stayed flat.
  - whether resident background logic decreased or stayed flat.
  - whether `/health`, `/metrics/summary`, and `/metrics/core_capabilities` remain fast when runtime validation is in scope.
  - whether log retention remains capped at 7 days.
- Do not use broad governance tests or auditability language as proof of current product progress.

## Workspace Governance Rule (Mandatory)

- Codex must actively monitor branch and worktree health while executing phased work.
- Before expanding implementation scope, Codex must check whether the workspace is still in a safe range.
- Default thresholds:
  - `<= 8` uncommitted files: normal progress allowed
  - `9-12`: tighten scope; avoid opportunistic expansion
  - `13-15`: warning zone; prioritize batching, records, and cleanup
  - `> 15`: do not expand implementation by default
  - `> 20`: pause implementation; only do governance, batching, validation alignment, or documentation
- Codex must pause earlier when high-risk files are involved, including ingress, runtime, control API, routing state, environment mutation, or deployment paths.
- Codex must distinguish and label:
  - repository reality
  - candidate reality
  - running reality
- Codex must not mix code-reading conclusions with running-instance behavior in one validation claim.
- Codex must not advance to the next gate unless the validation target is explicitly named and the conclusion scope is recorded.
- When suitable, Codex should proactively use lower-cost subagents for bounded low-risk work such as document cleanup, inventories, checklist backfill, and contract comparison, while keeping main-thread control over gate decisions and workspace risk.

## One-Line Operator Command

```powershell
make data-governance
```
