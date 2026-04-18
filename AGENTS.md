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
