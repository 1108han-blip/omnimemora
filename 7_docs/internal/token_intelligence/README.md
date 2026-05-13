# DoloToken / Token Intelligence Lite Mainline

## Status

- Created: 2026-05-13
- External product name: DoloToken
- Internal product line: OmniMemora Token Intelligence Lite
- Roadmap phase: Phase 8, next formal stage after Structured Compile MVP
- Current status: DoloToken beta local package is published at `doloclaw.com` as a controlled-beta download; the local proxy remains a separate user-installed CLI/proxy and is not promoted into `18011` or desktop GUI.

## Repo Implementation Status

- 2026-05-13: added isolated adapter core under `5_connectors/adapter/application/token_intelligence/`.
- Covered core objects: OpenAI-compatible usage normalization, confidence/source labels, metadata-only SQLite audit ledger, and compact receipt generation.
- Default storage posture: request/response hashes plus compact sanitized metadata; no raw prompt, tool output, or full provider response body by default.
- Running boundary: not wired into `llm_proxy.py`, `18011`, desktop GUI, or cloud release package yet.
- Validation: `PYTHONPATH=. uvx --with httpx --with pydantic --with loguru pytest -q 5_connectors/adapter/tests/test_token_intelligence_core.py 5_connectors/adapter/tests/test_context_compiler_token_estimates.py` -> `5 passed`.
- 2026-05-13: TI-001A repo-only local proxy skeleton added with `/health`, `/version`, and non-streaming `/v1/chat/completions` pass-through on a candidate server; still not promoted into `18011` or desktop GUI.
- 2026-05-13: TI-001B repo-only config and CLI skeleton added. Config stores upstream API key environment-variable references, rejects raw-content modes, and validates before proxy startup; CLI packaging/distribution is still not started.
- 2026-05-13: TI-001C repo-only audit ledger integration added. The candidate proxy records metadata-only audit events after upstream responses, labels relay-reported usage, emits an audit id header, and fails open when audit persistence fails; receipt/summary HTTP APIs remain TI-001D.
- 2026-05-13: TI-001D repo-only receipt and summary API added. The candidate proxy exposes bounded `/audit/events/<audit_id>`, `/audit/events/<audit_id>/receipt`, and `/audit/summary` reads, and CLI receipt get/export prints metadata-only receipts; running promotion remains not started.
- 2026-05-13: TI-001E repo-only update metadata check added. The candidate proxy and CLI parse product-owned release metadata, report current/latest/minimum version and unsigned beta Gatekeeper notes, and do not auto-download or install packages.
- 2026-05-13: TI-001F repo-only local package builder added. It stages a checksum-verifiable local zip package under an operator-selected output directory, emits `SHA256SUMS.txt` and `latest.local.json`, and defaults to `/tmp` so build artifacts do not pollute the repo.
- 2026-05-13: TI-002 repo-only local estimate fallback added. When upstream omits `usage`, the candidate proxy records `local_estimated` usage with `compatible_estimate` confidence; provider/relay-reported usage remains preferred and is not overwritten.
- 2026-05-13: TI-003 repo-only block-level spend breakdown added. Audit events and receipts now include safe block summaries with block type, token estimate, item count, source, and confidence; raw block content is not stored.
- 2026-05-13: TI-004 repo-only waste detectors added for duplicate context, long tool results, and tool-result-heavy context. Receipts and summaries expose compact optimization opportunities with reason codes and potential saving estimates; no automatic optimization is performed.
- 2026-05-13: TI-005 repo-only data controls added. The candidate audit store supports single-event delete, bounded retention purge, metadata-only receipt export/read, and audit-disabled forwarding; user-pattern records remain unopened until a separate approval-gated design exists.
- 2026-05-13: TI-006 repo-only potential savings report added. The candidate proxy exposes `/audit/reports/potential-savings`, derived from bounded summary data, to show estimated savings opportunities without enabling automatic optimization.
- 2026-05-13: TI-007 repo-only actual savings proof calculator added. The candidate proxy exposes a stateless `/audit/reports/actual-savings/proof` endpoint that compares recommended, baseline, and actual tokens without modifying structured compile or storing proof rows.
- 2026-05-13: TI-008 repo-only local MCP companion added inside the candidate local proxy. `/mcp` exposes read-only `token_intelligence.summary` and `token_intelligence.potential_savings` tools for opted-in agents; it does not capture requests, write memory, or replace the primary proxy path.
- 2026-05-13: TI-009 repo-only usage reconciliation added. Audit events, receipts, and summaries now compare reported total tokens against local estimates and label normal, warning, unexplained, estimated-only, or not-applicable cases without treating deltas as fraud evidence.
- 2026-05-13: TI-010 repo-only CLI report surface added. `omni-token-audit report summary` and `omni-token-audit report potential-savings` read bounded local audit data and print metadata-only JSON without starting the proxy or scanning large history.
- 2026-05-13: TI-011 repo-only top requests report added. The candidate proxy and CLI expose bounded highest-token/highest-cost request summaries from local audit metadata, with source/confidence labels and no raw prompt output.
- 2026-05-13: TI-012 repo-only reported cost ingestion added. The candidate proxy records provider/relay-reported cost fields with pricing version when present, but does not infer cost from a local price table yet.
- 2026-05-13: TI-013 repo-only workflow ROI tags added. The candidate proxy can store explicit opt-in agent/project/workflow headers and summarize top token/cost consumers by those tags without inferring user profiles.
- 2026-05-13: TI-014 repo-only MCP top requests tool added. The local MCP companion can expose bounded top request summaries to opted-in agents without becoming a capture or memory-write path.
- 2026-05-13: TI-015 repo-only beta version alignment completed. CLI, local proxy, MCP server info, and local package builder now report `0.1.0-beta.1` consistently.
- 2026-05-13: TI-016 repo-only skill-like attach profile added. `doctor`, `attach`, and `detach` now create reversible local connection profiles for agents without mutating official agent configs.
- 2026-05-13: TI-017 repo-only managed launcher added. `attach --with-launcher` writes a reversible env file and launch wrapper so users can run compatible agents through Token Audit without editing agent configs.
- 2026-05-13: TI-018 repo-only harness snippet generator added. `snippets` prints copy-paste integration examples for common harnesses without editing files or storing API key values.
- 2026-05-13: TI-019 candidate package smoke passed. The local zip now preserves executable launcher permissions and has been unpacked and run through fake-upstream pass-through, receipt, reports, snippets, attach, and detach in a temp directory.
- 2026-05-13: Product decision recorded: Token Intelligence is token-flow accuracy first. Money/cost remains optional, source-labeled, and user-configurable; no official or relay price table is treated as the product anchor.
- 2026-05-13: TI-020 repo-only real-client attach smoke added. The candidate package is built, unpacked with system unzip, started as a subprocess, called through a normal OpenAI-compatible HTTP client, and then verified through receipt/summary/top-request CLI reads plus reversible detach.
- 2026-05-13: TI-021 repo-only beta package quickstart prepared. The package README now states local proxy purpose, config steps, compatible client base URL, optional attach helper, report commands, update check, checksum verification, private-source boundary, and unsigned Gatekeeper note.
- 2026-05-13: TI-022 repo-only cloud route candidate prepared. Current live `doloclaw.com` Token Intelligence paths were confirmed 404, then the Worker template gained candidate redirects for Token Intelligence package downloads and release metadata, with local route tests only and no cloud deployment.
- 2026-05-13: TI-023 repo-only local release layout added. The package builder now emits a local R2-preview directory with zip, `SHA256SUMS.txt`, `latest.json`, and versioned manifest, and tests verify SHA/metadata consistency before any upload.
- 2026-05-13: TI-024 repo-only dry-run publish plan added. The package builder can now print future R2 upload keys, content types, SHA values, and Worker routes with `mutates_cloud=false`, without creating Cloudflare tokens, uploading objects, or deploying the Worker.
- 2026-05-13: TI-025 repo-only release preflight gate added. The package builder now checks Worker template version alignment, Cloudflare auth visibility, target account/bucket/Worker resolution, upload file count, and manual publish readiness without uploading or deploying.
- 2026-05-13: TI-026 cloud release completed. Token Intelligence `0.1.0-beta.1` artifacts were uploaded to R2, the control-entry Worker was deployed, live `/download` now lists the Token Intelligence CLI beta, and remote package SHA/version were verified.
- 2026-05-13: Naming decision recorded. The external product name is DoloToken; Token Intelligence remains the internal module, engineering line, technical capability name, route namespace, and compatibility surface.
- 2026-05-13: TI-027 DoloToken brand-sync release completed. DoloToken `0.1.0-beta.2` artifacts were uploaded to R2, the control-entry Worker was redeployed, live `/download` now lists the DoloToken CLI beta, and remote package SHA/version were verified.
- 2026-05-13: Current-version product scope recorded. DoloToken can audit relay/middleman token usage and can become a unified token-flow meter for LLM requests that pass through it, but it must label provider-reported, relay-reported, local-estimated, and rough-estimated counts separately and must not claim local estimates as provider billing truth.
- 2026-05-13: TI-028 repo-only local report page added. The DoloToken proxy now serves a no-code browser report at `/report`, backed by existing metadata-only audit summary, top-request, and potential-savings APIs.

## Naming

DoloToken is the user-facing product name for Token Intelligence Lite.

Use externally:

- DoloToken
- DoloToken by OmniMemora
- DoloToken: local AI token audit and request receipts

Keep internally:

- `token_intelligence`
- Token Intelligence Lite
- `omni-token-audit`
- `/releases/token-intelligence/...`
- `/download/file/token-intelligence/...`

Reason:

- `Dolo` is tied to the operator-owned `doloclaw.com` brand asset.
- `Omni` is broad and commonly used, so it remains a platform/module association rather than the short external product name.
- `Token` directly signals token-flow accounting, which is the product foundation.
- Internal names remain stable to avoid unnecessary route, CLI, package, and test churn.

## Product Target

DoloToken is not simple usage accounting.

It must explain:

- where tokens were spent,
- why they were spent,
- which parts were waste,
- how to optimize,
- which agents are most expensive,
- which prompts are least efficient,
- which contexts are repeated,
- which memory signals failed,
- which models have weak token/performance or cost/performance when cost is reported,
- which workflows have the best or worst ROI.

Primary target: accurate token-flow accounting.

Money is a secondary convenience layer. Users can calculate money themselves from trusted token counts, or use a small optional calculator/profile when they want a local estimate. OmniMemora must not lock product truth to one official price table, one relay price table, one region, or one user group. Reported relay/provider cost can be recorded as evidence; locally inferred cost must remain labeled and optional.

## Current Version Scope

This version can be used to audit token usage through relays, middlemen, and OpenAI-compatible LLM clients when their requests are routed through DoloToken.

Product claim:

- DoloToken records and explains token flow for LLM requests that pass through the local proxy.
- Relay-reported or provider-reported `usage` remains the highest-confidence count for this version.
- When upstream usage is missing, DoloToken records a local estimate with an explicit estimate confidence label.
- DoloToken can compare reported usage against local estimates and mark normal, warning, unexplained, estimated-only, or not-applicable differences.
- DoloToken can unify local receipts, summaries, top requests, workflow tags, and optimization opportunities across compatible clients and relays.

Product boundary:

- DoloToken does not directly measure requests that do not pass through it.
- Local estimates must not be presented as provider billing truth.
- Difference analysis must be neutral. It can identify unexplained deltas and possible causes, but it must not accuse a relay or provider without independent evidence.
- Native Anthropic `/v1/messages`, OpenAI Responses API, streaming receipt semantics, provider tokenizer/count APIs, and richer multimodal/reasoning/cache normalization remain follow-up protocol adapters.
- Hidden provider-side context, server tools, reasoning tokens, cache rules, multimodal tokens, and relay pricing rules may limit local-only accuracy.

## Product Shape

Phase 8 should start as a lightweight local module and entrypoint:

```text
client / middleman request
        ↓
Omni Token Intelligence Lite local proxy
        ↓
original upstream or middleman API
```

The first product surface should not require:

- a paid cloud server,
- a heavy desktop-only installation path,
- a browser extension as the primary capture mechanism,
- a SaaS observability backend.

Cloud clarification:

- `doloclaw.com`, Cloudflare, and Railway remain available product resources.
- Phase 8 starts local because cloud storage size, traffic shape, privacy posture, and operating cost are not yet measured for Token Intelligence.
- Cloud-hosted Token Intelligence can be considered later, but only after local MVP value, retention requirements, and cost envelope are known.

Recommended packaging:

- shared core module inside OmniMemora,
- proprietary lightweight local proxy / CLI package for first adoption,
- optional local report page,
- optional local MCP companion for agent queries.

Local package candidate:

```text
python3 tools/token_intelligence/build_local_package.py --version 0.1.0-beta.1
```

Default output:

```text
/tmp/omnimemora-token-intelligence-build/
```

Generated candidate files:

- `omni-token-audit-<version>-local.zip`
- `SHA256SUMS.txt`
- `latest.local.json`

The package is unsigned beta material. It is not an automatic installer, does not self-update, and macOS users may need Privacy & Security / Gatekeeper manual approval.

Distribution requirements:

- Users download and run it locally; source code does not need to be open.
- The local CLI/proxy must support online version checks and product-pushed update notices through product-owned release metadata.
- Release downloads must be versioned and checksum-verifiable.
- During unsigned beta distribution, macOS users may need a manual Privacy & Security / Gatekeeper allow step. This is acceptable for beta, but must be stated plainly.
- Do not describe unsigned beta updates as signed silent updates.

Execution guide:

- [MVP Execution Guide](./MVP_EXECUTION_GUIDE.md)
- [TI-001 Local Proxy Engineering Plan](./TI001_LOCAL_PROXY_ENGINEERING_PLAN.md)

## Relationship To Phase 7

Phase 7 answers: can OmniMemora safely reduce tokens?

Phase 8 answers: why should the user enable optimization, where will it help, and did it actually save tokens?

Cost can be shown when reported by a provider/relay or calculated from a user-selected profile, but token-flow accuracy is the foundation.

Token Intelligence must connect back to concrete optimization paths:

- structured compile,
- prompt reduction,
- tool-result/log compression,
- duplicate-context removal,
- memory miss repair,
- model/workflow selection,
- User Pattern Lite.

If an insight cannot lead to token/cost saving or a clear user decision, it is not Phase 8 product value.

## Non-Goals

Token Intelligence Lite must not become:

- a generic usage dashboard,
- a cloud-first observability SaaS,
- a user profiling product,
- hidden behavior tracking,
- a large raw log warehouse,
- a replacement for provider billing truth,
- a broad agent orchestration layer.

The user-profile boundary is stage-specific: Phase 8 does workflow/token ROI and User Pattern Lite only. A future user-profile product may be valuable, but it must be opened as a separate explicit stage with user control, privacy, storage, disable, export, and delete design; it must not silently emerge from audit logs.

## User Data Boundary

User Pattern Lite is allowed only as a token-saving support layer.

Allowed:

- explicit stable preferences,
- project boundaries,
- repeated workflow constraints,
- repeated corrections,
- compact facts that reduce repeated prompts.

Forbidden:

- sensitive personal profiling,
- psychological, health, finance, relationship, location, or consumption inference,
- hidden inference from meter/proxy/trace/compile logs,
- automatic injection of low-confidence habits.

All user-facing pattern data must be visible, deletable, disableable, and bounded.

## Storage Boundary

A small SQLite user/audit database is allowed.

Rules:

- no raw prompt by default,
- no full tool output by default,
- no full provider response body by default,
- store hashes, counts, block classes, confidence labels, compact metadata, and optimization opportunities,
- provide retention, delete, export, and disable paths before normal release,
- keep request forwarding independent from noncritical persistence.

Large files are not allowed as a product strategy. If a file grows, split it into focused modules or hard-cap retention.

## First Capability Batches

### TI-001 - Local Proxy Audit Entry

Create the lightest local entrypoint for OpenAI-compatible and Anthropic-compatible requests.

Exit:

- user can point a client or middleman base URL at Omni Token Intelligence Lite;
- requests pass through without semantic rewrite;
- audit records are created without raw prompt storage by default.

### TI-002 - Provider-Aligned Counting

Status: repo implementation completed on 2026-05-13 for local estimate fallback; provider-specific tokenizer/count APIs remain future work.

Add confidence-labeled token counts.

Confidence classes:

- `official_usage`
- `official_count_api`
- `provider_tokenizer`
- `compatible_estimate`
- `rough_estimate`

Exit:

- every displayed count carries a confidence class;
- rough estimates cannot be presented as billing truth.
- cost estimates cannot drive token audit correctness; they are only optional interpretation on top of token counts.

Current behavior:

- reported OpenAI-compatible `usage` is stored as `provider_reported` or `relay_reported` with `official_usage` confidence;
- missing usage falls back to local payload/output estimation and is stored as `local_estimated` with `compatible_estimate` confidence;
- local estimates are shown as estimates only and must not be used as proof of provider billing truth.

### TI-003 - Block-Level Spend Breakdown

Status: repo implementation completed on 2026-05-13 for OpenAI-compatible request/response block classification.

Classify token spend by block.

Minimum block classes:

- system/developer instructions,
- current user intent,
- conversation history,
- tool schemas,
- tool calls,
- tool results,
- memory/context injection,
- provider output.

Exit:

- users can see what part of the request consumed tokens.

Current behavior:

- block summaries are stored in `blocks_json` and surfaced in audit event/receipt responses;
- `/audit/summary` aggregates `top_blocks` from bounded recent ledger rows;
- block rows contain only class names, token estimates, item counts, source, and confidence;
- raw message, tool result, prompt, and provider output text are excluded from block records.

### TI-004 - Waste Detectors

Status: repo implementation completed on 2026-05-13 for first safe local detectors; automatic optimization remains out of scope.

Detect high-value waste categories:

- duplicate context,
- long tool/log/diff/test output,
- retry waste,
- weak prompt ROI,
- failed or irrelevant memory injection,
- model/workflow mismatch.

Exit:

- every detector emits a compact reason and potential saving estimate.

Current behavior:

- `duplicate_context_v1` detects repeated message content and records only a reason/category plus estimated repeated tokens;
- `long_tool_result_v1` detects oversized tool/function result payloads and estimates compressible savings;
- `tool_result_share_v1` flags requests where tool results dominate the block-level token estimate;
- detector output is stored as `opportunities_json` and surfaced in receipts and bounded `/audit/summary`;
- opportunity records never contain raw prompt, raw repeated text, or raw tool output.

### TI-005 - User Data Plane

Status: repo implementation completed on 2026-05-13 for audit data controls only; user-pattern storage is not started.

Implement a small, bounded audit/user-pattern store only after schema and retention tests exist.

Exit:

- retention, delete, export, and disable controls are tested;
- user-pattern records are compact and approval-gated;
- audit records avoid raw payload storage by default.

Current behavior:

- `DELETE /audit/events/<audit_id>` deletes one audit event from the candidate local ledger;
- `POST /audit/retention/purge` deletes events older than a bounded day threshold;
- audit can be disabled in config so forwarding continues without creating audit rows;
- receipt read/export uses metadata-only hashes, usage, blocks, and opportunities;
- no user-pattern table or habit inference is active in TI-005.

### TI-006 - Potential Savings Report

Status: repo implementation completed on 2026-05-13 for candidate local audit data.

Show what could be saved before enabling optimization.

Exit:

- report identifies the top saving opportunities by agent, model, prompt, workflow, and block type.

Current behavior:

- `/audit/reports/potential-savings` reads bounded recent audit summary data;
- report includes `potential_saving_tokens`, `top_opportunities`, `top_blocks`, `top_models`, source, and confidence;
- advice is limited to explicit token-saving actions such as deduplication and tool-result compression;
- no automatic optimization, routing, model switching, or user-pattern inference is triggered.

### TI-007 - Actual Savings Proof

Status: repo implementation completed on 2026-05-13 as a stateless proof calculator; structured compile integration is not started.

Connect recommendations to structured compile and prove realized savings.

Exit:

- before/after records show recommended saving vs actual saving;
- failed or negative-saving optimizations are visible.

Current behavior:

- `/audit/reports/actual-savings/proof` accepts `recommended_saving_tokens`, `baseline_tokens`, and `actual_tokens`;
- output classifies `realized`, `partial`, `no_saving`, `negative_saving`, or `no_recommendation`;
- proof output includes realized saving, negative saving, realization ratio, source, and confidence;
- the endpoint is stateless and does not alter compile behavior or write audit rows.

### TI-008 - Local MCP Companion

Status: repo implementation completed on 2026-05-13 inside the candidate local proxy only; no `18011` MCP change or promotion started.

Expose local audit summaries to opted-in agents.

Exit:

- agents can query recent audit summaries and optimization recommendations;
- MCP is not the primary capture path and does not replace local proxy capture.

Current behavior:

- `GET /mcp` reports a candidate local HTTP JSON-RPC companion;
- `POST /mcp` supports `initialize`, `ping`, `tools/list`, and `tools/call`;
- tools are limited to `token_intelligence.summary` and `token_intelligence.potential_savings`;
- tool calls read bounded local audit summary/report data only;
- no request capture, memory write, compile routing, or `18011` MCP behavior is changed.

### TI-009 - Usage Reconciliation

Status: repo implementation completed on 2026-05-13 for OpenAI-compatible local-vs-reported usage comparison.

Compare provider or relay reported usage with local estimates.

Exit:

- reported usage remains preferred when present;
- local estimates are kept as confidence-labeled audit evidence;
- unexplained deltas are visible without making fraud claims.

Current behavior:

- audit events and receipts include `reconciliation`;
- `/audit/summary` aggregates reconciliation status counts;
- statuses are `normal`, `warning`, `unexplained_delta`, `estimated_only`, or `not_applicable`;
- reconciliation stores only numeric counts, status, source, and confidence;
- raw prompt, response, tool output, and hidden-context assumptions are not stored or inferred.

### TI-010 - CLI Report Surface

Status: repo implementation completed on 2026-05-13 for local metadata-only reports.

Expose the first report surface without requiring GUI, cloud, or running promotion.

Exit:

- local users can inspect recent audit summaries from CLI;
- potential savings are visible without starting the proxy;
- report commands remain bounded and metadata-only.

Current behavior:

- `omni-token-audit report summary --limit <n>` prints bounded audit summary JSON;
- `omni-token-audit report potential-savings --limit <n>` prints potential savings report JSON;
- optional `--db <path>` supports explicit local ledger selection for verification and support;
- report output uses the same summary/report builders as the candidate local proxy;
- raw prompt, response, and tool output are not printed.

### TI-011 - Top Requests Report Surface

Status: repo implementation completed on 2026-05-13 for local metadata-only top request reports.

Expose the first "where did tokens go" request list without GUI, cloud, or long history scans.

Exit:

- users can identify the highest-token and highest-cost recent requests;
- each request row remains a receipt pointer, not a raw prompt viewer;
- output stays bounded and metadata-only.

Current behavior:

- `/audit/reports/top-requests?limit=<n>` returns top recent requests by total tokens and by cost when cost exists;
- `omni-token-audit report top-requests --limit <n>` prints the same metadata-only report from a local ledger;
- rows include audit id, request id, provider/model, token counts, usage source/confidence, optional cost source/confidence, potential saving tokens, reconciliation status, status code, latency, and timestamp;
- the report reads at most 1000 recent ledger rows and does not scan large history;
- raw prompt, response, tool output, and full provider body are not printed.

### TI-012 - Reported Cost Ingestion

Status: repo implementation completed on 2026-05-13 for OpenAI-compatible provider/relay cost fields.

Record cost when the upstream already reports it, without introducing local price-table inference.

Exit:

- receipts preserve reported total cost with source and confidence labels;
- pricing version is recorded when the upstream supplies it;
- missing cost remains empty instead of being guessed.

Current behavior:

- OpenAI-compatible responses can provide cost in `usage.cost`, `usage.total_cost`, `usage.total_cost_usd`, `cost`, `total_cost`, or `total_cost_usd`;
- the candidate proxy records those values as `relay_reported` with `official_usage` confidence;
- `pricing_version` or `price_version` is copied when present;
- `/audit/summary` and `/audit/reports/top-requests` can surface cost totals/top-by-cost when cost exists;
- no local provider pricing table or billing-truth claim is active in TI-012;
- future price calculators must be opt-in profiles, not product anchors.

### TI-013 - Workflow ROI Tags

Status: repo implementation completed on 2026-05-13 for explicit metadata tags only.

Let users identify expensive agents and workflows without deriving a broad user profile.

Exit:

- agent, project, and workflow labels are explicit input metadata, not inferred from prompt content;
- summary/report surfaces can roll up token and cost by those labels;
- raw content remains outside the audit store.

Current behavior:

- the candidate proxy accepts `x-omni-agent-id`, `x-omni-project-id`, `x-omni-workflow-tag`, and `x-omni-workspace-tag`;
- tags are stored through the existing sanitized metadata path and capped to short strings;
- `/audit/summary` includes `top_agents`, `top_workflows`, and `top_projects`;
- `/audit/reports/top-requests` includes agent/project/workflow tags on request rows when present;
- `/audit/reports/potential-savings` carries the same top agent/workflow/project rollups;
- no hidden habit inference, user profiling, memory write, or automatic optimization is enabled.

### TI-014 - MCP Top Requests Tool

Status: repo implementation completed on 2026-05-13 inside the candidate local proxy only; no `18011` MCP change or promotion started.

Expose top request summaries to agents that explicitly connect to the local companion.

Exit:

- agents can query summary, potential savings, and top requests from the same read-only MCP surface;
- all MCP reads remain bounded and metadata-only;
- MCP remains optional and cannot capture traffic by itself.

Current behavior:

- `tools/list` includes `token_intelligence.top_requests`;
- `tools/call` for `token_intelligence.top_requests` returns the same bounded schema as `/audit/reports/top-requests`;
- the tool reads at most 1000 recent local ledger rows;
- no request capture, memory write, compile routing, profile inference, or `18011` MCP behavior is changed.

### TI-015 - Beta Version Alignment

Status: repo implementation completed on 2026-05-13 for the local Token Intelligence candidate package.

Keep package metadata, CLI output, proxy version, and MCP server info aligned.

Exit:

- the local package default version matches the candidate runtime version;
- update checks do not report a false update when metadata points to the same beta;
- version changes remain repo-only until a separate publish step is approved.

Current behavior:

- `omni-token-audit version` reports `0.1.0-beta.1`;
- `/version`, `/health`, and `/updates/check` use the same runtime version;
- MCP `initialize` reports `0.1.0-beta.1`;
- `tools/token_intelligence/build_local_package.py` defaults to `0.1.0-beta.1`;
- no cloud upload, desktop GUI promotion, or `18011` runtime replacement is performed by this alignment step.

### TI-016 - Skill-Like Attach Profile

Status: repo implementation completed on 2026-05-13 for local connection profiles only.

Make Token Audit feel closer to a skill install while keeping real request capture explicit and reversible.

Exit:

- users can run one command to generate an agent connection profile;
- users can inspect local readiness with a doctor command;
- detach removes the Token Audit profile without touching official agent config.

Current behavior:

- `omni-token-audit doctor` checks config validity, proxy health, upstream API key environment presence, attach directory, and supported targets;
- `omni-token-audit attach openclaw` writes an Omni-owned profile under `~/.omnimemora/token-intelligence/agents/openclaw.json`;
- `omni-token-audit attach claude-code --dry-run` prints the profile without writing it;
- `omni-token-audit detach <target>` removes the profile if it exists;
- profiles include `proxy_base_url`, `mcp_url`, upstream base URL, API key environment variable name, and recommended client headers;
- actual OpenClaw, Claude Code, or other agent configuration files are not mutated in TI-016;
- no API key value, raw prompt, response, tool output, memory write, or `18011` behavior is stored or changed.

### TI-017 - Managed Env Launcher

Status: repo implementation completed on 2026-05-13 for local launcher artifacts only.

Reduce attach friction without taking ownership of unknown agent config formats.

Exit:

- users can generate a wrapper that injects Token Audit connection environment variables;
- detach removes the wrapper and env file;
- official agent config files remain untouched.

Current behavior:

- `omni-token-audit attach openclaw --with-launcher` writes `openclaw.env` and `openclaw-launch.sh` next to the attach profile;
- the env file sets `OPENAI_BASE_URL`, `OPENAI_API_KEY` as a reference to the configured API key environment variable, `OMNI_TOKEN_AUDIT_AGENT_ID`, and `OMNI_TOKEN_AUDIT_MCP_URL`;
- the launcher sources the env file and executes the agent command passed by the user;
- `omni-token-audit detach openclaw` removes the profile, env file, and launcher if present;
- API key values are not written;
- no official OpenClaw, Claude Code, Codex, or provider config file is modified;
- this is not yet a protocol-specific Claude Code/Anthropic attach path.

### TI-018 - Harness Snippet Generator

Status: repo implementation completed on 2026-05-13 for copy-paste snippets only.

Support heterogeneous user harnesses without maintaining brittle auto-config writers.

Exit:

- users can request a copy-paste snippet for common integration styles;
- snippet output is generated from the local config;
- no harness config file is modified.

Current behavior:

- `omni-token-audit snippets --list` shows supported snippets;
- `omni-token-audit snippets generic-env` prints env exports for OpenAI-compatible harnesses;
- `omni-token-audit snippets openai-sdk-js` and `openai-sdk-python` print SDK examples;
- `omni-token-audit snippets litellm` prints LiteLLM-compatible env setup;
- `omni-token-audit snippets openclaw` recommends the managed launcher and provides manual env equivalents;
- snippets include the API key environment variable name, not the API key value;
- output is marked `mutates_files=false` and `stores_api_key_value=false`;
- no official harness config, `18011`, desktop GUI, or cloud setting is changed.

### TI-019 - Candidate Package Smoke Gate

Status: candidate package smoke completed on 2026-05-13; no running promotion performed.

Validate the downloadable local package path before any user-facing release step.

Exit:

- the zip preserves executable permission metadata for `omni-token-audit`;
- the package runs from an unpacked temp directory;
- fake upstream pass-through creates an audit receipt and reports;
- attach and detach launcher artifacts are reversible.

Current behavior:

- `tools/token_intelligence/build_local_package.py` writes Unix executable bits into the zip metadata;
- package smoke used `/usr/bin/unzip`, ran `omni-token-audit version`, `doctor`, `snippets`, `attach --with-launcher`, `proxy start`, `receipt get`, `report summary`, `report top-requests`, `report potential-savings`, and `detach`;
- smoke result: request forwarded to `/v1/chat/completions`, upstream authorization header present, response text `SMOKE_OK`, audit id present, receipt usage source `relay_reported`, cost captured when reported, top request readable, and secrets not present in outputs;
- launcher write/remove was verified: `launcher_exists_after_attach=true`, `launcher_removed_by_detach=true`;
- this gate validates the candidate package only; it does not promote Token Intelligence into `18011`, desktop GUI, cloud release, or official agent config mutation.

### TI-020 - Real Client Minimal Attach Smoke

Status: repo implementation completed on 2026-05-13 as a repeatable package-level test; no running promotion performed.

Validate the minimum user-style path after package smoke:

- user unpacks the local candidate package;
- user writes local config with upstream base URL and API key environment reference;
- user runs `omni-token-audit attach openclaw --with-launcher`;
- user starts `omni-token-audit proxy start`;
- a normal OpenAI-compatible client sends `POST /v1/chat/completions` to the local proxy;
- user reads `receipt`, `report summary`, and `report top-requests`;
- user runs `detach` and removes managed artifacts.

Current behavior:

- the test builds a fresh local package and unpacks it with system `unzip` so executable-bit behavior is part of the gate;
- the proxy runs from the unpacked package as a subprocess, not from imported repo modules;
- the upstream receives the configured upstream API key from the environment;
- the client response is pass-through and contains `x-omni-token-audit-id`;
- receipt records `relay_reported` token usage;
- summary/top-requests record `openclaw` and `coding` tags from request headers;
- detach removes the managed launcher and env/profile artifacts;
- the upstream API key value and request prompt text are absent from CLI outputs and config.

Boundaries:

- this is a candidate package/user-style smoke only;
- it does not mutate official OpenClaw, Claude Code, or other harness config files;
- it does not promote Token Intelligence into `18011`, desktop GUI, cloud release, or a signed updater path.

### TI-021 - Beta Package Quickstart And Release Metadata Prep

Status: repo implementation completed on 2026-05-13 for local package contents only; no cloud upload or Worker route change performed.

Prepare the downloadable package so a user can understand and verify the local beta path without source access.

Exit:

- package README explains what Token Intelligence Lite does and that source code is not included;
- README gives minimum config steps for `upstream.base_url` and `upstream.api_key_env`;
- README gives the OpenAI-compatible client base URL `http://127.0.0.1:18081/v1`;
- README lists `doctor`, `proxy start`, optional `attach/detach`, report commands, and `update check`;
- README tells users to verify `SHA256SUMS.txt` before replacing the package;
- README states unsigned beta Gatekeeper behavior and does not imply signed silent updates;
- builder test verifies the README text and executable-bit package metadata.

Boundaries:

- no cloud publication is performed in TI-021;
- no `doloclaw.com/download` page or Worker route is changed in this batch;
- no automatic installer, self-replacement, or signed updater claim is added;
- price/cost calculation remains optional and does not affect token-flow audit truth.

### TI-022 - Cloud Download Route Preflight

Status: repo implementation completed on 2026-05-13 for Worker template candidate routes only; no cloud upload or Worker deployment performed.

Prepare the cloud route shape needed before Token Intelligence can appear on `doloclaw.com/download`.

Observed live cloud state before candidate change:

- `https://doloclaw.com/releases/token-intelligence/latest.json` returned 404.
- `https://doloclaw.com/download/file/token-intelligence/omni-token-audit-0.1.0-beta.1-local.zip` returned 404.
- `https://doloclaw.com/download` displayed the desktop beta17 download page only.

Candidate route behavior:

- `/download/file/token-intelligence/omni-token-audit-0.1.0-beta.1-local.zip` redirects to `https://assets.doloclaw.com/omnimemora/token-intelligence/0.1.0-beta.1/omni-token-audit-0.1.0-beta.1-local.zip`;
- `/releases/token-intelligence/latest.json` redirects to `https://assets.doloclaw.com/omnimemora/token-intelligence/0.1.0-beta.1/latest.json`;
- `/download` lists "DoloToken CLI (local token audit beta)" and links the DoloToken release manifest;
- unknown Token Intelligence package names return 404;
- local Node-based Worker route test verifies the behavior after placeholder substitution.

Boundaries:

- this does not upload package artifacts to R2;
- this does not deploy the Worker to Cloudflare;
- this does not alter desktop beta17 download behavior;
- this does not promote Token Intelligence into `18011` or the desktop GUI.

### TI-023 - Local Release Layout And Metadata Consistency

Status: repo implementation completed on 2026-05-13 for local release preview only; no cloud upload or Worker deployment performed.

Generate the exact local file layout expected by the TI-022 Worker routes before touching R2.

Output layout:

```text
<output-dir>/
  omni-token-audit-<version>-local.zip
  SHA256SUMS.txt
  latest.local.json
  release/omnimemora/token-intelligence/<version>/
    omni-token-audit-<version>-local.zip
    SHA256SUMS.txt
    latest.json
    <version>.json
```

Current behavior:

- `tools/token_intelligence/build_local_package.py` now returns `release_dir` in its JSON output;
- the release preview directory mirrors the future R2 prefix `omnimemora/token-intelligence/<version>/`;
- `latest.json` and `<version>.json` contain the same product-owned metadata;
- the manifest download URL points to `/download/file/token-intelligence/omni-token-audit-<version>-local.zip`;
- `SHA256SUMS.txt` and manifest SHA match the actual zip bytes;
- validation built `0.1.0-beta.1` locally and confirmed `sha_matches=true` and `version_manifest_matches=true`.

Boundaries:

- this does not upload artifacts to R2;
- this does not deploy the Worker to Cloudflare;
- this does not update the live `doloclaw.com/download` page;
- generated release preview artifacts stay outside the repo by default and are cleaned after validation.

### TI-024 - Dry-Run Publish Plan

Status: repo implementation completed on 2026-05-13 for local dry-run output only; no cloud token, upload, or Worker deploy performed.

Make the eventual cloud publish step inspectable before any mutation.

Command:

```text
python3 tools/token_intelligence/build_local_package.py --version 0.1.0-beta.1 --dry-run-publish-plan
```

Current behavior:

- output includes `publish_plan.dry_run=true`;
- output includes `publish_plan.mutates_cloud=false`;
- output lists future R2 keys under `omnimemora/token-intelligence/<version>/`;
- each upload item includes local path, R2 key, content type, byte size, and SHA256;
- output names the Worker route paths expected by TI-022;
- output names `OMNIMEMORA_RELEASE_BUCKET` and `OMNIMEMORA_CONTROL_ENTRY_WORKER` as env-controlled release surfaces without reading credentials.

Validated `0.1.0-beta.1` dry-run plan:

- R2 prefix: `omnimemora/token-intelligence/0.1.0-beta.1/`;
- upload items: package zip, `SHA256SUMS.txt`, `latest.json`, `0.1.0-beta.1.json`;
- Worker routes: `/download/file/token-intelligence/omni-token-audit-0.1.0-beta.1-local.zip`, `/releases/token-intelligence/latest.json`, `/releases/token-intelligence/0.1.0-beta.1.json`;
- example package SHA from the validation run: `9b75990f441552d0b2a029c9a6feacd749284d050e98a18367ed8d3d512acab1`.

Boundaries:

- this does not create Cloudflare API tokens;
- this does not upload artifacts to R2;
- this does not deploy the Worker;
- this does not update live `doloclaw.com` routes;
- the output is a candidate plan, not evidence of cloud availability.

### TI-025 - Release Preflight Gate

Status: repo implementation completed on 2026-05-13 for local preflight output only; no cloud token, upload, or Worker deploy performed.

Make the last pre-publication gate explicit before running any real Cloudflare/R2 mutation.

Command:

```text
python3 tools/token_intelligence/build_local_package.py --version 0.1.0-beta.1 --preflight-release-gate
```

Current behavior:

- output includes `preflight.dry_run=true`;
- output includes `preflight.mutates_cloud=false`;
- output verifies Worker template `TOKEN_INTELLIGENCE_VERSION` matches the package version;
- output checks Cloudflare auth env visibility without printing secret values;
- output resolves target account, release bucket, and Worker name from env or current release defaults;
- output checks that the release preview contains 4 upload files;
- output returns `ready_for_manual_publish` only when credentials, target config, Worker version, and release files are all ready;
- output still includes the TI-024 `publish_plan`.

Validated local preflight on 2026-05-13:

- credentials_ready: `true`;
- target_config_ready: `true`;
- worker_version_matches: `true`;
- required_files_present: `true`;
- ready_for_manual_publish: `true`;
- target account/bucket/Worker resolved to the current release defaults when env overrides were absent.

Validated live pre-publication state:

- `https://doloclaw.com/releases/token-intelligence/latest.json` returned 404;
- `https://doloclaw.com/download/file/token-intelligence/omni-token-audit-0.1.0-beta.1-local.zip` returned 404;
- `https://doloclaw.com/download` returned 200 and still displayed the Desktop beta17 page only.

Boundaries:

- this does not create Cloudflare API tokens;
- this does not upload artifacts to R2;
- this does not deploy the Worker;
- this does not update live `doloclaw.com` routes;
- live-route checks are recorded separately from local preflight and are not treated as candidate code being active.

### TI-026 - Cloud Release

Status: cloud running release completed on 2026-05-13 for Token Intelligence `0.1.0-beta.1`.

Release action:

- built local release preview with `--preflight-release-gate`;
- uploaded 4 R2 objects under `omnimemora/token-intelligence/0.1.0-beta.1/`;
- deployed Worker `omnimemora-control-entry` with desktop version placeholder kept at `1.0.0-beta.17`;
- preserved existing desktop beta17 release paths.

Uploaded objects:

- `omnimemora/token-intelligence/0.1.0-beta.1/0.1.0-beta.1.json`
- `omnimemora/token-intelligence/0.1.0-beta.1/SHA256SUMS.txt`
- `omnimemora/token-intelligence/0.1.0-beta.1/latest.json`
- `omnimemora/token-intelligence/0.1.0-beta.1/omni-token-audit-0.1.0-beta.1-local.zip`

Release SHA:

```text
c8607db3dd30e101cb0a74d0a6ef0a6be39ea5a04e8af2719cb8d701d2810875  omni-token-audit-0.1.0-beta.1-local.zip
```

Running verification:

- `https://doloclaw.com/releases/token-intelligence/latest.json` resolves to product `omnimemora-token-intelligence`, version `0.1.0-beta.1`;
- `https://doloclaw.com/releases/token-intelligence/0.1.0-beta.1.json` resolves with the same version metadata;
- `https://doloclaw.com/download/file/token-intelligence/omni-token-audit-0.1.0-beta.1-local.zip` redirects to the Token Intelligence R2 object;
- downloaded remote zip SHA matched the release SHA above;
- unpacked remote zip ran `omni-token-audit version` and returned `0.1.0-beta.1`;
- unpacked remote zip ran `omni-token-audit snippets --list` and returned the supported snippet list;
- `https://doloclaw.com/download` displays "DoloToken CLI (local token audit beta)" and the DoloToken release manifest link after the next Worker deployment;
- `https://doloclaw.com/releases/latest.json` still reports desktop `1.0.0-beta.17` and `beta_one_click_download_verify_open_dmg`;
- `https://doloclaw.com/download/file/darwin-arm64` still redirects to the desktop beta17 DMG;
- `https://doloclaw.com/health` remains healthy and reports `release_posture=proprietary-controlled-beta`;
- `http://127.0.0.1:18011/health` remains healthy;
- `http://127.0.0.1:18011/metrics/core_capabilities` remains responsive.

Download stats check:

- `/api/download/stats?days=1` returned 200 and counted `token-intelligence/omni-token-audit-0.1.0-beta.1-local.zip`.
- A broader `/api/download/stats` query timed out once at 10 seconds during validation, so stats should not be treated as the release-critical proof path.

Operational note:

- The first R2 upload attempt hit `Unauthorized` on the first object, consistent with temporary token propagation timing seen in earlier release tooling. Retrying with the existing propagation wait/backoff strategy succeeded.

Boundaries:

- no `18011` promotion was performed;
- no desktop app package was rebuilt;
- no source code was published;
- Token Intelligence remains unsigned controlled-beta local CLI/proxy material;
- price/cost calculation remains optional and does not affect token-flow audit truth.

### TI-027 - DoloToken Brand Sync Release

Status: cloud running release completed on 2026-05-13 for DoloToken `0.1.0-beta.2`.

Release action:

- bumped the local proxy, CLI, MCP companion, package builder, tests, and Worker route version to `0.1.0-beta.2`;
- built local release preview with `--preflight-release-gate`;
- uploaded 4 R2 objects under `omnimemora/token-intelligence/0.1.0-beta.2/`;
- deployed Worker `omnimemora-control-entry` with desktop version placeholder kept at `1.0.0-beta.17`;
- preserved existing desktop beta17 release paths.

Uploaded objects:

- `omnimemora/token-intelligence/0.1.0-beta.2/0.1.0-beta.2.json`
- `omnimemora/token-intelligence/0.1.0-beta.2/SHA256SUMS.txt`
- `omnimemora/token-intelligence/0.1.0-beta.2/latest.json`
- `omnimemora/token-intelligence/0.1.0-beta.2/omni-token-audit-0.1.0-beta.2-local.zip`

Release SHA:

```text
5e98f18367187af7a3c0cc079b38696c85f422b8f89938db55f096a920d4e989  omni-token-audit-0.1.0-beta.2-local.zip
```

Running verification:

- `https://doloclaw.com/releases/token-intelligence/latest.json` resolves to product `omnimemora-token-intelligence`, version `0.1.0-beta.2`;
- `https://doloclaw.com/releases/token-intelligence/0.1.0-beta.2.json` resolves with the same version metadata;
- `https://doloclaw.com/download/file/token-intelligence/omni-token-audit-0.1.0-beta.2-local.zip` redirects to the DoloToken R2 object;
- downloaded remote zip SHA matched the release SHA above;
- unpacked remote zip ran `omni-token-audit version` and returned `0.1.0-beta.2`;
- unpacked remote zip ran `omni-token-audit snippets --list` and returned the supported snippet list;
- `https://doloclaw.com/download?verify=beta2` displays "DoloToken CLI (local token audit beta)" and the DoloToken release manifest link;
- `https://doloclaw.com/releases/latest.json` still reports desktop `1.0.0-beta.17` and `beta_one_click_download_verify_open_dmg`;
- `https://doloclaw.com/download/file/darwin-arm64` still redirects to the desktop beta17 DMG;
- `https://doloclaw.com/health` remains healthy and reports `release_posture=proprietary-controlled-beta`;
- `http://127.0.0.1:18011/health` remains healthy;
- `http://127.0.0.1:18011/metrics/core_capabilities` remains responsive.

Update capability boundary:

- DoloToken already supports product-owned update metadata checks through `https://doloclaw.com/releases/token-intelligence/latest.json`;
- the cloud side can push update notices, minimum supported version, and force-update flags by publishing a new versioned package and updating the latest manifest;
- the current beta CLI does not silently self-replace or install updates;
- frequent beta updates are operationally supported through versioned packages, checksum manifests, and the Worker download route, but users still manually replace the local package until a dedicated updater or launcher-managed installer is added.

Boundaries:

- no `18011` promotion was performed;
- no desktop app package was rebuilt;
- no source code was published;
- DoloToken remains unsigned controlled-beta local CLI/proxy material;
- price/cost calculation remains optional and does not affect token-flow audit truth.

### TI-028 - Local Browser Report Page

Status: repo implementation completed on 2026-05-13 for the DoloToken local proxy.

Goal:

- let non-technical relay users see agent, model, request, and token usage without CLI commands;
- keep all data local and metadata-only;
- reuse the existing local audit APIs instead of adding a cloud service, desktop GUI dependency, or new storage model.

User surface:

- `GET /report`
- `GET /`

The page reads:

- `/health`
- `/audit/summary?limit=1000`
- `/audit/reports/top-requests?limit=50`
- `/audit/reports/potential-savings?limit=1000`

Boundary:

- local-only browser page served by the DoloToken proxy;
- no external assets, CDN, cloud calls, cookies, or raw prompt display;
- no write actions, deletion controls, or retention changes in this batch;
- no `18011`, desktop GUI, OpenClaw config, or official agent config mutation;
- `/report` is a user-readable view over existing audit metadata, not a new product truth source.

Exit:

- users can open `http://127.0.0.1:18081/report` after starting the proxy;
- page shows request count, total/input/output/reasoning tokens, top agents, top models, top requests, and optimization signals;
- existing CLI reports remain available for users who want JSON output.

## Validation Requirements

Repo reality:

- schema tests for no raw payload by default;
- retention/delete/export tests;
- confidence-label tests;
- block-classification tests;
- detector tests with small fixtures;
- no large fixture files.

Running reality:

- local proxy pass-through succeeds;
- `/health`, `/metrics/core_capabilities`, `/metrics/summary`, and `/compile/status` remain responsive when applicable;
- audit persistence failure does not block upstream request forwarding;
- user can disable audit/pattern features.

## Success Criteria

Phase 8 succeeds when a user can answer:

- what spent my tokens,
- why was it expensive,
- what can I do to reduce it,
- what Omni optimization can safely execute,
- how much did it actually save.
