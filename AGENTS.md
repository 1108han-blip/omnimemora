# AGENTS.md

## Session Startup Rule (Mandatory)

Before any implementation or reporting work in this repo:

1. Identify the active product line from the latest current milestone, release, or cloud-local sync docs.
2. Treat `7_docs/internal/phase6/plan/README.md` as the current historical index and post-phase6 governance entry unless a newer current milestone doc explicitly supersedes it.
3. Read only the working-principles / SOP docs relevant to the current product line. For current local/runtime promotion work, use `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`.
4. Do not read archived phase folders by default. Only open historical phase documents when the operator explicitly asks for that historical workstream or the current milestone directly references it.
5. If experiment data is explicitly in scope, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_all.ps1 -RunLabel "session-start" -Tenant all -Salt "<secret-salt>"
```

## Current Product State Rule (Mandatory)

OmniMemora is currently a proprietary controlled-beta local-first product, not an archived experiment workspace.

- Product goal: MVP first; token saving first; no complexity expansion.
- Product surface split:
  - `5173` = user control and display surface
  - `18011` = product ingress after explicit user opt-in
  - `8765` = internal memory plane
- Distribution path: `https://doloclaw.com/download`.
- Current release posture: closed beta / controlled beta; source stays private.
- Any product downloaded to a user's local machine must have app-level automatic update management before normal downloadable release.
- Manual desktop app replacement is not acceptable as a steady-state product update mechanism.
- Cloud policy candidates remain candidate-only and must not silently replace local active policy.

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

## Cloud Platform Stewardship Rule (Mandatory)

Codex is authorized to manage OmniMemora cloud resources on the operator's behalf when credentials are available.

Default operating model:

- Treat Cloudflare, Railway, GitHub, and future cloud services as shared platform resources that may host multiple projects.
- Keep every project isolated by name, DNS hostname, route, Worker/Pages project, Railway project/service, bucket prefix, environment variable namespace, and documentation record.
- Do not let OmniMemora changes mutate unrelated project resources such as separate product domains, subdomains, Workers, Pages, Vercel projects, Railway projects, buckets, or email routes.
- When platform resources are shared, inspect and label the target project before mutation.

Same-project iteration rule:

- New OmniMemora cloud iterations should replace the previous OmniMemora iteration instead of accumulating parallel legacy surfaces.
- Legacy OmniMemora resources that conflict with the current product identity should be deleted, disabled, or explicitly retired after replacement continuity is verified.
- Do not keep old OmniMemora projects, routes, DNS records, variables, or workers as informal fallbacks unless a current record names the reason, owner, and retirement condition.
- Small-project bias: if cloud state is tangled, prefer a clean rebuild over hours of incremental repair, provided user-facing continuity and data safety are checked first.

Codex execution authority:

- Codex should plan and execute cloud architecture, project isolation, DNS/routes, security configuration, deployment checks, runtime audits, and user-data handling checks without asking the operator to design the website or cloud structure.
- Ask the operator only for product/business decisions that cannot be inferred safely, destructive actions involving user-facing data, billing/account ownership changes, or credentials not already available.
- Reports must be in plain Chinese by default and distinguish repository reality, cloud platform reality, running reality, and user-data impact.

## One-Line Operator Command

```powershell
make data-governance
```
