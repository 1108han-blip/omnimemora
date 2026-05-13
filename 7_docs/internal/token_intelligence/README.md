# Token Intelligence Lite Mainline

## Status

- Created: 2026-05-13
- Product line: OmniMemora Token Intelligence Lite
- Roadmap phase: Phase 8, next formal stage after Structured Compile MVP
- Current status: direction fixed in product constitution and roadmap; repo-only Token Intelligence core and candidate local proxy exist; no `18011`, GUI, cloud, or running configuration change yet.

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

## Product Target

Token Intelligence is not simple usage accounting.

It must explain:

- where tokens were spent,
- why they were spent,
- which parts were waste,
- how to optimize,
- which agents are most expensive,
- which prompts are least efficient,
- which contexts are repeated,
- which memory signals failed,
- which models have weak cost/performance,
- which workflows have the best or worst ROI.

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

Phase 8 answers: why should the user enable optimization, where will it help, and did it actually save money?

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

### TI-003 - Block-Level Spend Breakdown

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

### TI-004 - Waste Detectors

Detect high-value waste categories:

- duplicate context,
- long tool/log/diff/test output,
- retry waste,
- weak prompt ROI,
- failed or irrelevant memory injection,
- model/workflow mismatch.

Exit:

- every detector emits a compact reason and potential saving estimate.

### TI-005 - User Data Plane

Implement a small, bounded audit/user-pattern store only after schema and retention tests exist.

Exit:

- retention, delete, export, and disable controls are tested;
- user-pattern records are compact and approval-gated;
- audit records avoid raw payload storage by default.

### TI-006 - Potential Savings Report

Show what could be saved before enabling optimization.

Exit:

- report identifies the top saving opportunities by agent, model, prompt, workflow, and block type.

### TI-007 - Actual Savings Proof

Connect recommendations to structured compile and prove realized savings.

Exit:

- before/after records show recommended saving vs actual saving;
- failed or negative-saving optimizations are visible.

### TI-008 - Local MCP Companion

Expose local audit summaries to opted-in agents.

Exit:

- agents can query recent audit summaries and optimization recommendations;
- MCP is not the primary capture path and does not replace local proxy capture.

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
