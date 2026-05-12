# Structured Compile Mainline

## Status

- Created: 2026-05-13
- Product line: OmniMemora structured context compilation
- Current status: SC-021 repo candidate adds a local Tool Plane search entry so AI tool traffic can enter OmniMemora before agent reuse
- Supersedes phase6 as the active engineering line for compile capability work.

## Product Target

OmniMemora compile should become a protocol-aware structured context compiler, not only a memory-context injector.

The compiler must reduce real token/cost usage while preserving the provider message graph needed by agent clients such as Claude Code and OpenClaw.

## Current Baseline

- Product framework exists: desktop control/display surface, `18011` ingress, `8765` memory plane, adapter routing, meter/read-model, promotion workflow, and validation records.
- Current compile implementation is a narrow memory-context compile path: it can rebuild upstream payloads from OmniMemora `packed_context` plus the current user-visible query.
- That narrow path is suitable only for simple request shapes where replacing the original message graph is safe.
- It is not validated for agent tool continuations that contain `tool_use`, `tool_result`, assistant continuation state, or provider-required tool/result ordering.
- The 2026-05-13 safety fix makes tool-context requests bypass the narrow compiler until protocol-aware compilation exists.

## Constitution

- Structured context compilation is the highest-value product layer for the next engineering line.
- Product file count may grow when the growth creates focused compiler modules and directly serves token/cost saving on real requests.
- Single-file growth is not acceptable as the default path.
- Runtime workflow blocking is not acceptable: upstream-critical paths must not depend on LLM summarization, cloud policy fetch, historical file scans, or slow persistence.
- The first compiler must be deterministic and local-first.
- Protocol preservation is a local invariant, not a cloud/local strategy option.
- Strategy policy may control rollout, compression budgets, and agent scope after the compiler exists.

## External Research and Reuse Map

This line should borrow methods, not adopt a full external framework.

| Source family | Useful idea | OmniMemora use | Boundary |
| --- | --- | --- | --- |
| ACON / agent context optimization | Learn from full-context-success vs compressed-context-failure cases | Later failure corpus and rule refinement | Not in v1 upstream-critical path |
| Context-as-a-Tool / SWE-agent context work | Keep recent agent interaction high fidelity; compress older observations | Preserve recent tool graph, compress old tool results | Do not replace provider protocol |
| ACE / evolving context papers | Avoid context collapse and repeated-summary drift | Prefer extractive, auditable compression first | No repeated abstractive summaries in v1 |
| Perception Compressor style dynamic allocation | Different fields get different compression budgets | Protect protocol fields, compress long observations more | Budgeting cannot override validation |
| LLMLingua / LongLLMLingua | Token-importance compression for text blocks | Optional later text-block compressor behind deterministic fallback | Not a whole-payload compiler |
| Distill MCP / code-context tools | AST/log/diff/search-output compaction patterns | Borrow extractors for code, logs, stack traces, search results | MCP source compression is not transparent ingress compile |

2026-05-13 decision: do not call external compression libraries or model compressors in product work. External projects remain design references only. OmniMemora may keep internal offline evaluation scaffolding, but no external compressor adapter, model download, network dependency, or third-party compression runtime may enter the product path.

## Architecture Target

Candidate package:

`5_connectors/adapter/application/context_compiler/`

Candidate modules:

- `ir.py` - provider payload internal representation.
- `anthropic_tool_graph.py` - Anthropic tool graph parsing and validation.
- `anthropic_tool_schema.py` - provided Anthropic tool schema checks.
- `classifiers.py` - classify blocks as protected, recent, old, compressible, or memory.
- `compressors.py` - deterministic text block compression.
- `compiler.py` - protect, classify, compress, rebuild, and fallback orchestration.
- `validators.py` - provider schema and graph-preservation checks.
- `metrics.py` - compile-specific token delta and reason fields.
- `research_adapters.py` - offline compressor comparison interface.

Existing files should remain thin:

- `llm_proxy.py` keeps ingress and upstream forwarding.
- `compile_orchestrator.py` chooses compile path and records metadata.
- `gateway_compile.py` remains the compatibility path for current memory-context compile until migrated or retired.

## Compile IR Model

The compiler should parse the request into blocks before making compression decisions.

Minimum block types:

- `system_policy` - provider/system/developer instruction blocks.
- `current_user_intent` - most recent user-visible request.
- `assistant_state` - assistant continuation text and tool-use declarations.
- `tool_call` - tool name, id, and arguments.
- `tool_result_recent` - recent result paired with a required tool id.
- `tool_result_old` - older result that may be compressed.
- `retrieved_context` - search/read/file/log output embedded in tool results.
- `conversation_history` - older natural-language turns.
- `omni_memory_context` - product memory context selected by OmniMemora.

Protection rules:

- Never drop role ordering.
- Never rewrite `tool_use.id` or `tool_result.tool_use_id`.
- Never separate a tool result from the tool call it answers.
- Never compress the latest unresolved tool result in v1.
- Never remove current user intent.
- Never allow compression output to violate provider schema.

## Staged Roadmap

### SC-000 - Close Current Safety Baseline

Goal: freeze the current safety repair before opening new implementation.

Required:

- Record the 2026-05-13 baseline and safety fix.
- Keep tool-context passthrough active for Claude Code/OpenClaw.
- Confirm existing adapter tests pass.
- Do not mix structured compiler implementation into this closeout.

### SC-001 - Protocol Fixture and IR Skeleton

Goal: create the smallest protocol-aware compiler surface without changing running behavior.

Status: implemented in repo reality on 2026-05-13. No orchestrator or running-path integration.

Implementation:

- Add `context_compiler/ir.py`.
- Add `context_compiler/anthropic_tool_graph.py`.
- Parse Anthropic payloads into IR blocks.
- Validate valid and invalid tool graphs.
- Return analysis only; no payload rewrite.

Tests:

- Valid `tool_use/tool_result` pairing.
- Missing result id.
- Mismatched result id.
- Multiple tool calls.
- Text-only payload still parses.

Exit:

- No running behavior change: satisfied by design; modules are not imported by `llm_proxy.py`, `compile_orchestrator.py`, or `gateway_compile.py`.
- File boundaries proven: `ir.py` and `anthropic_tool_graph.py` exist under `context_compiler/`.
- Tests passed: `test_context_compiler_anthropic_tool_graph.py` covers valid pair, missing id, mismatched id, multiple tool calls, and text-only payload.

### SC-002 - Deterministic Tool-Result Compression

Goal: compress only old or oversized tool-result text while preserving graph structure.

Status: implemented in repo reality on 2026-05-13. The compiler is deterministic, local-only, and does not call an LLM.

Implementation:

- Add deterministic extractive compressors.
- Preserve recent tool graph uncompressed.
- Compress old search/file/log blocks by keeping:
  - file path or source id
  - command/tool name
  - matched lines or key snippets
  - error code and stack frame when present
  - explicit omission marker with original size
- Rebuild Anthropic-valid payload.
- Validate rebuilt payload before returning it.
- Fallback to passthrough on any uncertainty.

Compression policy:

- No LLM summarization.
- No external dependency required.
- Target modest compression first, not extreme ratios.

Tests:

- Long search result compresses.
- Recent result is protected.
- Tool ids and ordering are unchanged.
- Invalid rebuilt graph falls back.
- Token estimate decreases for eligible fixtures.

Exit:

- Repo fixture shows positive token saving without graph damage: satisfied by `test_context_compiler_structured_compile.py`.

### SC-003 - Orchestrator Integration Behind Flag

Goal: integrate structured compiler without changing default product behavior broadly.

Status: implemented in repo reality on 2026-05-13 for Anthropic-compatible Claude Code/OpenClaw tool-context requests.

Implementation:

- Add a feature flag or local config gate.
- First enable for Anthropic-compatible Claude Code/OpenClaw tool-context requests only.
- `compile_orchestrator.py` chooses:
  - structured compiler for eligible tool graphs when enabled.
  - current memory-context compile for safe simple requests.
  - passthrough for unsupported or uncertain requests.
- Meter fields distinguish:
  - `structured_compile_success`
  - `structured_compile_passthrough`
  - `memory_context_compile_success`
  - `compile_skipped`

Tests:

- Existing memory-context compile tests still pass.
- Tool-context requests no longer call the narrow memory compiler.
- Structured compiler success records token delta.
- Structured compiler fallback records reason and preserves payload.

Exit:

- Default behavior remains safe: unsupported/uncertain tool graphs fall back to passthrough.
- Enabling the flag affects only the named Anthropic tool path: enforced by `OMNIMEMORA_STRUCTURED_COMPILE_AGENTS` and Anthropic protocol checks.
- Structured compile success is counted as token saving by gateway meter persistence.

### SC-004 - Running Validation on Real Agent Requests

Goal: prove product value on real Claude Code/OpenClaw traffic.

Status: running reality validated on 2026-05-13 for direct Anthropic-compatible product ingress. Real external agent CLI driving was not used for this validation; the request exercised the same `18011` Anthropic path with `agent_id=claude_code`.

Procedure:

- Promote adapter through `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`.
- Verify `http://127.0.0.1:18011/health`.
- Verify `/metrics/summary` and `/metrics/core_capabilities` remain fast enough for product validation.
- Run real Claude Code/OpenClaw tool-loop prompts.
- Capture request ids and compare:
  - passthrough baseline token size
  - structured compiled token size
  - upstream status
  - whether the agent answers instead of repeating the same search
  - pre-upstream local processing time

Exit:

- At least one tool-loop request saves tokens and preserves agent continuation: satisfied for request `25cf17ffdd32`, trace `sc004-structured-compile-20260513-0420-tools`.
- No evidence of upstream-critical blocking regression: `/health` stayed healthy and compile evidence shows deterministic structured compile before upstream success.

Evidence:

- Promotion log: `tools/verification/logs/promotion_20260513_041942.log`
- Promotion result: `final_status=running_reality_promoted`, `repo_revision=f78c406`, adapter pid changed from `89069` to `4932`.
- Endpoint timings after promotion:
  - `/health`: `0.002503s` before direct request; `0.002596s` after direct request.
  - `/metrics/summary`: `0.215501s` before direct request; `0.211036s` after direct request.
  - `/metrics/core_capabilities`: `0.199998s` before direct request; `0.198119s` after direct request.
- Direct product request:
  - path: `/llm/v1/messages`
  - agent: `claude_code`
  - request_id: `25cf17ffdd32`
  - upstream status: `200`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract`
  - original_token_estimate: `4031`
  - compiled_token_estimate: `723`
  - compression_ratio: `0.8206400396923841`

Provider compatibility note:

- The first synthetic direct request omitted the top-level Anthropic `tools` schema and was rejected by the MiniMax Anthropic-compatible upstream, even though the structured compiler preserved the tool graph.
- The successful direct request included the `tools` schema.
- Structured compile must preserve provided tool schemas and must not invent missing provider tool definitions.

### SC-005 - Optional Text-Block Compressor Research Adapter

Goal: evaluate whether LLMLingua-like compression improves deterministic extraction.

Status: implemented in repo reality on 2026-05-13 as an offline adapter interface. No external model, network dependency, or product hot-path import was added.

Boundary:

- Offline or non-critical path first.
- No model download or network dependency in product hot path.
- Must be behind a separate compressor interface.
- Must compare against deterministic extractive baseline.

Implementation:

- `TextBlockCompressorAdapter` protocol defines the comparison surface.
- `DeterministicBaselineAdapter` wraps the current extractive compressor.
- `compare_text_block_compressors` reports char/token estimates and compression ratio for offline candidates.

Exit:

- Offline adapter interface exists and deterministic baseline comparison is covered by tests.
- Future non-deterministic or model-based candidates remain research-only until they improve token saving without quality or latency regression.

### SC-006 - Failure Corpus and Rule Refinement

Goal: use ACON-style failure analysis without building a training system.

Status: running reality validated on 2026-05-13 for deterministic tool-schema validation. No failure corpus retention was added.

Implementation:

- Store minimal anonymized failure cases only when operator explicitly enables collection.
- Compare full-context success vs structured-compiled failure.
- Add deterministic rules or fixtures from observed failures.
- Validate provided Anthropic `tools` schemas against `tool_use.name` before rewriting payloads.

Boundary:

- No silent retention expansion.
- No raw user memory mutation.
- No background training.
- No schema synthesis: absent `tools` remains a provider/client responsibility, while present-but-inconsistent schemas force passthrough.

Running evidence:

- Promotion log: `tools/verification/logs/promotion_20260513_042953.log`
- Promotion result: `final_status=running_reality_promoted`, `repo_revision=eb62295`, adapter pid changed from `4932` to `9230`.
- Endpoint timings after promotion, before direct request:
  - `/health`: `0.018554s`
  - `/metrics/summary`: `0.023332s`
  - `/metrics/core_capabilities`: `0.229316s`
- Direct product request with top-level `tools` schema:
  - path: `/llm/v1/messages`
  - agent: `claude_code`
  - request_id: `c42e8c2ded6f`
  - trace: `sc006-tool-schema-20260513-0430`
  - upstream status: `200`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract`
  - original_token_estimate: `2697`
  - compiled_token_estimate: `732`
  - compression_ratio: `0.728587319243604`
- Endpoint timings after direct request:
  - `/health`: `0.014336s`
  - `/metrics/summary`: `0.00914s`
  - `/metrics/core_capabilities`: `0.231321s`

### SC-007 - Warning-Clean Product Upgrade

Goal: remove validation warnings from the structured compile support path and promote the fixed adapter to running reality.

Status: running reality validated on 2026-05-13.

Implementation:

- Fixed `resolve_internal_base_url_sync` so calls from an existing event loop no longer create an unawaited coroutine.
- Switched backend config extraction to Pydantic v2 `model_dump()` when available.
- Added the missing `os` import for `BackendConfig` default environment lookup.
- Kept the fix subtractive in behavior: no new background task, no log-retention expansion, and no user-memory mutation.

Repo validation:

- Targeted warning-as-error check: `30 passed`
- Adapter and structured compile regression check with warning-as-error: `76 passed`
- `py_compile`: passed for touched adapter modules.
- `git diff --check`: passed.

Running evidence:

- Promotion log: `tools/verification/logs/promotion_20260513_043502.log`
- Promotion result: `final_status=running_reality_promoted`, `repo_revision=ce9b0c7`, adapter pid changed from `9230` to `12078`.
- Promotion marker: `/Users/sc/.omnimemora/service/current/.omnimemora_promotion_state.json` records `repo_revision=ce9b0c7` and `primary_breakpoint=none`.
- Runtime fingerprint: `/debug/runtime_fingerprint` reports adapter pid `12078`, service version `2.2.0`, and code source under `/Users/sc/.omnimemora/service/current`.
- Endpoint timings after promotion, before direct request:
  - `/health`: `0.013476s`
  - `/metrics/summary`: `0.022075s`
  - `/metrics/core_capabilities`: `0.21849s`
- Direct product request after promotion:
  - path: `/llm/v1/messages`
  - agent: `claude_code`
  - request_id: `509a42f424db`
  - trace: `sync-warning-fix-structured-compile-20260513-0435`
  - upstream status: `200`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract`
  - original_token_estimate: `2507`
  - compiled_token_estimate: `726`
  - compression_ratio: `0.710410849621061`
- Endpoint timings after direct request:
  - `/health`: `0.012028s`
  - `/metrics/summary`: `0.005268s`
  - `/metrics/core_capabilities`: `0.223232s`

### SC-008 - Current Product Surface Regression

Goal: broaden validation after the warning-clean adapter promotion without reopening historical DLP/RES/archive governance tracks.

Status: repo reality validated on 2026-05-13. No running behavior change was introduced.

Scope:

- Included current product paths: access plan, agent control and identity, agent metrics, routing state, structured compile, gateway compile, internal transport, live-flow read model, LLM proxy ingress, diagnostics surface, metrics summary-first, recommendation policy version manager, request evidence skill metadata/suggestions, runtime backend bridge, runtime bridge fallback, Track B status, and usage surface.
- Excluded historical governance-heavy DLP/RES/archive cleanup tests from this product-upgrade gate.

Fix:

- Updated `test_diagnostics_surface_smoke.py` to match the current summary-first implementation: `/metrics/summary` delegates directly to `metrics_service.compute_metrics_summary`.

Evidence:

- Current product surface regression: `204 passed`.
- Warning policy for this run elevated `RuntimeWarning` and `PydanticDeprecatedSince20` to errors.
- Residual warnings were limited to FastAPI `on_event` deprecation messages in `main.py`; they were not changed in this batch because replacing startup/shutdown lifecycle handling is a separate behavior-risking migration.

### SC-009 - Adapter Lifespan Migration

Goal: remove FastAPI `on_event` deprecation warnings from the current product adapter while preserving startup/shutdown behavior.

Status: running reality validated on 2026-05-13.

Implementation:

- Replaced `@app.on_event("startup")` and `@app.on_event("shutdown")` registration with a FastAPI `lifespan` context manager.
- Kept the existing `_startup_data_lifecycle_scheduler` and `_shutdown_data_lifecycle_scheduler` function bodies unchanged.
- Added no new background task, no new retention behavior, and no user-memory mutation.

Repo validation:

- `test_main_assembly_smoke.py` with `DeprecationWarning` elevated to error: `7 passed`.
- Current product surface regression with `RuntimeWarning`, `PydanticDeprecatedSince20`, and `DeprecationWarning` elevated to errors: `204 passed`.
- `py_compile`: passed for `5_connectors/adapter/main.py`.
- `git diff --check`: passed.

Running evidence:

- Promotion log: `tools/verification/logs/promotion_20260513_044137.log`
- Promotion result: `final_status=running_reality_promoted`, `repo_revision=5ac3bb1`, adapter pid changed from `12078` to `16053`.
- Promotion marker: `/Users/sc/.omnimemora/service/current/.omnimemora_promotion_state.json` records `repo_revision=5ac3bb1` and `primary_breakpoint=none`.
- Endpoint timings after promotion, before direct request:
  - `/health`: `0.013889s`
  - `/metrics/summary`: `0.025103s`
  - `/metrics/core_capabilities`: `0.192821s`
  - `/debug/runtime_fingerprint`: `0.044616s`, pid `16053`, version `2.2.0`
- Direct product request after promotion:
  - path: `/llm/v1/messages`
  - agent: `claude_code`
  - request_id: `b4faa3a23120`
  - trace: `lifespan-upgrade-structured-compile-20260513-0442`
  - upstream status: `200`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract`
  - original_token_estimate: `2261`
  - compiled_token_estimate: `720`
  - compression_ratio: `0.6815568332596196`

### SC-010 - Real Compile Distribution Telemetry

Goal: make structured compile coverage measurable on real traffic before expanding compressor scope.

Status: repo reality validated on 2026-05-13. No running promotion was performed in this batch.

Implementation:

- Extend compile telemetry summaries without adding a new hot-path persistence system.
- Count all compile statuses, including:
  - `structured_compile_success`
  - `structured_compile_passthrough`
  - `compile_success`
  - `compile_skipped`
  - `compile_failed`
- Track request share per status, estimated compile-token savings, and structured compile success/passthrough share.
- Keep reads bounded to recent compile events; do not scan historical logs.
- Preserve 7-day internal log retention.
- Expose the new fields through the existing `/compile/status` diagnostic surface.

Exit:

- `/compile/status` exposes enough distribution data to answer: "how often do real requests actually save tokens?" Satisfied in repo reality.
- Existing `compile_success`, `compile_skipped`, and `compile_failed` fields remain backward compatible. Satisfied by preserving the old fields and adding separate structured fields.
- No new background task, no new raw payload retention, and no user-memory mutation. Satisfied by reusing bounded compile event summaries.

Repo validation:

- `test_compile_store_distribution_summary.py`, `test_llm_proxy_compile_event_persistence.py`, and `test_context_compiler_structured_compile.py`: `9 passed`.
- `test_main_assembly_smoke.py` and `test_compile_orchestrator_enforcement_trace.py`: `9 passed`, with pre-existing `datetime.utcnow()` deprecation warnings only.
- `py_compile`: passed for `compile_store.py`, `status_api.py`, and the new distribution test.
- `git diff --check`: passed.

### SC-011 - Provider Token Estimate Upgrade

Goal: reduce the gap between current char/3 estimates and provider-visible token accounting.

Status: repo reality validated on 2026-05-13. No running promotion was performed in this batch.

Implementation:

- Added a tokenizer interface under `context_compiler/metrics.py`.
- Uses local `tiktoken` when available for the requested model.
- Fallback is deterministic `mixed_script_heuristic_v1`, which accounts for CJK-heavy text more closely than a single char divisor.
- Structured compile results and compile events now record `token_estimator_name` and `token_estimator_confidence`.

Boundary:

- No network call in token estimation.
- No provider-specific routing decision based only on estimated tokens.

Repo validation:

- `test_context_compiler_token_estimates.py`, `test_context_compiler_structured_compile.py`, and `test_llm_proxy_compile_event_persistence.py`: `10 passed`.
- `py_compile`: passed for `metrics.py`, `compiler.py`, `gateway_compile.py`, and `llm_proxy.py`.

### SC-012 - Compressor Type Expansion

Goal: improve real savings by using specialized deterministic compressors for common agent tool outputs.

Status: repo reality validated on 2026-05-13. No running promotion was performed in this batch.

Priority types:

- search results: implemented by `search_result` classifier.
- file reads: implemented by `file_read` classifier.
- logs and stack traces: implemented by `log` classifier.
- diffs: implemented by `diff` classifier.
- test output: implemented by `test_output` classifier, with failure lines prioritized over long pass lists.

Boundary:

- Compress only payload blocks classified as old or oversized tool results.
- Preserve latest tool result and all provider protocol fields.
- Fallback to passthrough on classifier uncertainty.

Repo validation:

- `test_context_compiler_compressors.py`, `test_context_compiler_structured_compile.py`, and `test_context_compiler_research_adapters.py`: `13 passed`.
- `py_compile`: passed for `compressors.py` and the compressor tests.

### SC-013 - Minimal Failure Samples

Goal: learn from full-context-success vs compiled-context-failure cases without retaining raw user content.

Status: repo reality validated on 2026-05-13. No running promotion was performed in this batch.

Implementation:

- Added `context_compiler/failure_samples.py`.
- Store only anonymized minimal fields when explicitly enabled by `OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLES`.
- Stored fields: compile status, reason, issue codes, protocol, agent family, token estimates, estimator metadata, changed block count, and timestamp.
- No raw user prompt, raw tool output, raw memory content, provider response body, or full request messages.

Boundary:

- Disabled by default.
- 7-day retention cap applies.

Repo validation:

- `test_context_compiler_failure_samples.py` and `test_gateway_compile_skill_suggestions.py`: `8 passed`.
- `py_compile`: passed for `failure_samples.py`, `gateway_compile.py`, and the failure sample tests.

### SC-014 - Offline Candidate Compression Evaluation

Goal: evaluate LLMLingua-like or other model-based compressors without slowing upstream-critical requests.

Status: repo reality validated on 2026-05-13. No running promotion was performed in this batch.

Implementation:

- Extended the existing offline adapter interface from SC-005.
- Added `TextBlockCorpusCase` and `evaluate_text_block_corpus` to summarize candidate performance over curated anonymized text blocks.
- Corpus summaries report case count, changed count, estimated saved tokens, and compression ratio.
- Promote only deterministic or proven-low-latency improvements into SC-012-style compressors.

Boundary:

- No model download, model inference, or network dependency in the hot path.
- Candidate results are research evidence, not product savings claims.

### SC-015 - Running Value Gate

Goal: prove the repo-validated structured compiler works in the current running product before adding more compile behavior.

Status: running reality recorded on 2026-05-13.

Implementation:

- Promote adapter to running reality through `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`.
- Verify `18011 /health`, `/metrics/core_capabilities`, and `/compile/status`.
- Run direct Anthropic-compatible tool-loop requests through `18011` with provider-valid tool schemas.
- Record request ids, compile statuses, token estimates, compile distribution, upstream status, and endpoint timings.

Exit:

- Running adapter is on the expected repo revision.
- At least one structured compile request returns upstream success and positive token saving.
- `/compile/status` shows structured compile distribution fields from SC-010.
- No evidence of upstream-critical local blocking regression.

Evidence:

- Initial promotion attempt with the default service directory failed as designed:
  - command: `./tools/promotion/promotion.sh adapter`
  - log: `tools/verification/logs/promotion_20260513_054621.log`
  - result: `promotion_failed`
  - primary breakpoint: `code_source_mismatch`
  - cause: launchd was serving the beta16 app path `/Users/sc/.omnimemora/app/current`, while the default promotion target expected `/Users/sc/.omnimemora/service/current`.
- Corrected promotion used the current app directory:
  - command: `OMNIMEMORA_SERVICE_DIR=/Users/sc/.omnimemora/app ./tools/promotion/promotion.sh adapter`
  - log: `tools/verification/logs/promotion_20260513_054646.log`
  - result: `running_reality_promoted`
  - repo revision: `1300365`
  - marker: `/Users/sc/.omnimemora/app/current/.omnimemora_promotion_state.json`
  - adapter pid after promotion: `49558`
  - runtime fingerprint code source: `/Users/sc/.omnimemora/app/current/5_connectors/adapter/...`
- Direct Claude Code shaped request through `/llm/v1/messages` returned upstream `200` in `2.571518s`, but it is not counted as a structured compile proof because running route state recorded `compile_skipped` with `compile_path=agent_route_disabled`.
- Running OpenClaw traffic in the 10-minute window after the value gate showed:
  - proxied requests: `4`
  - `structured_compile_success`: `4`
  - structured success share: `1.0`
  - estimated saved tokens: `1550`
  - estimated savings ratio: `0.0115`
  - representative request ids with upstream `200`: `e3eae3da0441`, `c82803fc97ee`, `c2f0e13a40f9`, `76367a75ec33`
- Endpoint timings sampled during the gate:
  - `/health`: `0.086409s`
  - `/metrics/core_capabilities`: `0.729977s`
  - `/compile/status`: `0.109176s`

Conclusion:

- SC-015 proves current running OpenClaw structured compile can return upstream success with positive deterministic token saving.
- SC-015 does not prove Claude Code structured compile in running reality because the direct Claude Code request was route-disabled in that running configuration.

### SC-016 - Golden Fixture Corpus

Goal: create a stable internal fixture corpus for compiler changes.

Status: repo reality validated on 2026-05-13.

Implementation:

- Add anonymized fixtures for search result, file read, log, diff, and test output.
- Each fixture declares required retention markers and expected output type.
- Fixture tests validate token reduction, required marker preservation, latest-result protection, and provider graph validity.

Boundary:

- No raw user request content.
- No external compressor dependency.

Implementation:

- Added anonymized in-test golden fixtures for `search_result`, `file_read`, `log`, `diff`, and `test_output`.
- Each fixture declares required markers, expected output type, max chars, and a provider-valid tool graph.
- Fixture coverage validates token reduction, required marker retention, graph preservation, latest-result protection, and top-level tool schema preservation.

Repo validation:

- `test_context_compiler_compressors.py`, `test_context_compiler_structured_compile.py`, and `test_context_compiler_research_adapters.py`: `16 passed`.

### SC-017 - Typed Compressor v2

Goal: improve deterministic typed compressors using the golden fixture corpus.

Status: repo reality validated on 2026-05-13.

Implementation:

- Add per-type retention priorities where current v1 rules are too generic.
- Keep failure mode as passthrough or no-gain, not forced compression.
- Preserve latest tool result and provider protocol invariants.

Boundary:

- No LLM summarization.
- No whole-payload compression.

Implementation:

- Changed typed retention order from generic head-first retention to type-priority-first retention.
- `search_result` and `log` outputs now sample matching lines across head, middle, and tail instead of taking only the first matching lines.
- `log` output prioritizes severe lines such as `ERROR`, `WARN`, `timeout`, and `denied`.
- `diff` output samples diff-matched lines across the file instead of over-retaining early hunks.
- Failure behavior remains no-gain/passthrough; latest tool result and provider protocol fields remain protected.

Repo validation:

- Structured compiler targeted tests: `16 passed`.
- Gateway/compile-event/failure-sample regressions: `12 passed`.
- `py_compile`: passed for touched compressor, research adapter, and tests.
- `git diff --check`: passed.

### SC-018 - Internal Offline Compression Evaluation

Goal: evaluate OmniMemora's own deterministic compressors over the golden corpus without external libraries.

Status: repo reality validated on 2026-05-13.

Implementation:

- Extend offline corpus summaries to include per-label results.
- Compare internal deterministic compressor variants only.
- Use results to decide whether a rule should be promoted into SC-017-style production compressors.

Boundary:

- No external compression library.
- No model inference or model download.
- No network dependency.

Implementation:

- Extended offline corpus summaries with per-label case results.
- Per-label summaries include changed flag, reason, output type, token estimates, saved token estimate, and compression ratio.
- The evaluation still runs only over internal deterministic adapters.

Repo validation:

- `test_context_compiler_research_adapters.py`: passed with per-label case summary assertions.
- No product hot-path import of an external compressor or model dependency was added.

### SC-019 - Promotion Decision and Product Closeout

Goal: decide whether SC-015 through SC-018 are ready for product promotion, GUI/cloud packaging, or another repo-only iteration.

Status: running reality promoted and closed on 2026-05-13.

Implementation:

- Summarize running value gate, fixture corpus coverage, typed compressor behavior, and internal offline evaluation.
- Decide one of:
  - promote and package,
  - keep repo-only and iterate,
  - pause expansion due to insufficient real token-saving evidence.
- Record file-count, background-logic, retention, and endpoint-speed impact.

Exit:

- Worktree is clean.
- Product decision is recorded without mixing repo reality and running reality.

Repo validation:

- `test_context_compiler_research_adapters.py`: passed with corpus summary coverage.
- `py_compile`: passed for `research_adapters.py`.

Decision:

- Promote the adapter running surface for local controlled-beta validation.
- Do not package a new desktop GUI or cloud download bundle in SC-019 because this batch changed adapter structured compile logic and tests only; no desktop GUI code changed.
- Keep Claude Code running-route validation separate because the SC-015 direct Claude Code request was route-disabled. OpenClaw is the validated running target for this closeout.

Promotion evidence:

- First SC-019 promotion attempt:
  - command: `OMNIMEMORA_SERVICE_DIR=/Users/sc/.omnimemora/app ./tools/promotion/promotion.sh adapter`
  - log: `tools/verification/logs/promotion_20260513_055318.log`
  - result: `promotion_failed`
  - primary breakpoint: `api_unreachable`
  - follow-up finding: the adapter became healthy immediately after the script check window, so this was treated as a restart readiness race and not as a code failure.
- Successful SC-019 promotion:
  - command: `OMNIMEMORA_SERVICE_DIR=/Users/sc/.omnimemora/app ./tools/promotion/promotion.sh adapter`
  - log: `tools/verification/logs/promotion_20260513_055342.log`
  - result: `running_reality_promoted`
  - repo revision: `629b6bf`
  - adapter pid changed from `53103` to `54311`
  - marker: `/Users/sc/.omnimemora/app/current/.omnimemora_promotion_state.json`
  - primary breakpoint: `none`

Running validation:

- Endpoint timings after successful promotion:
  - `/health`: `0.004919s` before direct request; `0.327292s` after direct request.
  - `/metrics/summary?tenant=all`: `0.005813s` after direct request, degraded by design with `summary_unavailable_no_historical_scan`.
  - `/metrics/core_capabilities?tenant=all`: `0.333600s` before direct request; `0.318298s` after direct request.
  - `/compile/status?window_minutes=10`: `0.333380s` before direct request; `0.334919s` after direct request.
- Direct OpenClaw product request:
  - path: `/llm/v1/messages`
  - agent: `openclaw`
  - trace: `sc019-openclaw-structured-compile`
  - request_id: `b17ba5735944`
  - upstream response id: `0652d49c0deb2c68e8fe57d649636420`
  - upstream status: `200`
  - elapsed time: `15.711414s`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract_search_result`
  - original_token_estimate: `2341`
  - compiled_token_estimate: `594`
  - compression_ratio: `0.746262281076463`
  - selected_memory_count: `0`
  - token_estimator_name: `tiktoken`
  - token_estimator_confidence: `high`
- `/compile/status?window_minutes=10` after direct request:
  - `openclaw.proxied_requests`: `2`
  - `openclaw.structured_compile_success`: `2`
  - `openclaw.structured_compile.success_share`: `1.0`
  - `openclaw.compile_token_savings.saved_token_estimate`: `3494`
  - `openclaw.compile_token_savings.savings_ratio`: `0.7463`

Product impact:

- File count stayed flat in the implementation batch; the golden corpus was added to an existing test file.
- Resident background logic stayed flat; no new scheduler, watcher, or background compression worker was added.
- Runtime hot path remains deterministic parse/compress/validate only; no model inference, model download, external compressor library, network dependency, or cloud policy fetch was added.
- Internal log retention remains governed by the existing 7-day cap; this batch did not add new retention paths.
- Product compile behavior remains protocol-aware and local-first for the validated OpenClaw Anthropic-compatible tool path.

### SC-020 - Beta17 Post-Release Value Gate

Goal: verify beta17 running value after release, close the Claude Code route gap, and decide whether the next action should be more compiler work or coverage/telemetry.

Status: running reality recorded on 2026-05-13.

Scope:

- Running instance: local beta17 install under `/Users/sc/.omnimemora/app/current`, adapter on `18011`, runtime on `8765`.
- Release surface: beta17 was already published and verified before this gate.
- No compiler code change, no external compressor, no model inference, no new background task.

Findings:

- OpenClaw was already routing through structured compile after beta17.
- Claude Code was installed and detected but had `routing_enabled=false`, `route_truth=off`, and prior `compile_path=agent_route_disabled`.
- The direct cause of the previous Claude Code validation gap was running route configuration, not structured compiler failure.
- Product control API enable action changed running config from `claude_code=off` to `claude_code=force_if_possible` in `/Users/sc/.omnimemora/app/current/5_connectors/adapter/config/agent_modes.json`.

Claude Code validation:

- Enable action:
  - path: `POST /agents/control/enable`
  - body: `{"family_id":"claude_code"}`
  - result: `routing_enabled=true`, `route_truth=effective`
- Direct product request:
  - path: `/llm/v1/messages`
  - agent: `claude_code`
  - trace: `sc020-claude-route-verify`
  - request_id: `4f89619eced0`
  - upstream response id: `0652d84655614bac004000cec878d3f5`
  - upstream status: `200`
  - elapsed time: `11.340619s`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract_search_result`
  - original_token_estimate: `2826`
  - compiled_token_estimate: `634`
  - compression_ratio: `0.775654635527247`
  - selected_memory_count: `0`
  - token_estimator_name: `tiktoken`
  - token_estimator_confidence: `high`

30-minute running distribution after the Claude route check:

- `claude_code`:
  - proxied requests: `3`
  - `structured_compile_success`: `2`
  - `compile_skipped`: `1` from the pre-enable route-disabled check
  - `structured_compile.success_share`: `0.6667`
  - saved token estimate: `4384`
  - savings ratio: `0.7757`
- `openclaw`:
  - proxied requests: `11`
  - `compile_success`: `2`
  - `structured_compile_success`: `4`
  - `structured_compile_passthrough`: `5`
  - saved token estimate: `6682`
  - savings ratio across all compile events: `0.0621`

Health and error scan:

- `18011 /health`: HTTP `200`, `status=healthy`.
- Recent 30-minute logs:
  - `compile_events`: `14` events, `0` failed statuses, `0` error fields.
  - `proxy_events`: `16` events, `0` failed statuses, `0` error fields.
  - `trace_events`: `132` events, `0` failed statuses, `0` error fields.
- `/agents/control` after enable:
  - `claude_code`: `routing_enabled=true`, `route_truth=effective`, `traffic_truth=real_request_observed`.
  - `openclaw`: `routing_enabled=true`, `route_truth=effective`, `traffic_truth=real_request_observed`.

Decision:

- SC-020 closes the Claude Code running validation gap for this local beta17 install.
- Do not expand compressor logic in the next step until real post-release traffic shows whether passthrough coverage or compressor quality is the bottleneck.
- If the product wants Claude Code route enabled by default for newly downloaded packages, that is a separate release decision because beta17 cloud artifacts were already published with the prior default config.

### SC-021 - Local Tool Plane Search Entry

Goal: start the long-term product path where OmniMemora weakly integrates with agent clients while controlling as much LLM and AI tool traffic as possible.

Status: repo candidate implemented on 2026-05-13. No OpenClaw or Claude Code running configuration was changed in this batch.

Product decision:

- Direct agent-to-CLI tool calls are acceptable only as temporary fallbacks.
- The target shape is agent -> OmniMemora `18011` tool endpoint -> local provider backend -> structured, capped tool result -> next LLM turn through OmniMemora.
- Search is the first Tool Plane capability because failed or slow search currently wastes agent-loop time and can inflate later LLM context.
- Image, video, voice, and vision tool traffic remain out of scope until search proves latency and token-saving value.

Implementation:

- Added `POST /tools/search`.
- Default provider is local `mmx search query --q <query> --output json`.
- The endpoint uses bounded query size, bounded result size, command timeout, no shell interpolation, and response-only retention.
- The endpoint does not write raw search results to product logs, does not mutate user memory, and does not add a scheduler or background worker.
- Unsupported providers fail closed instead of silently bypassing OmniMemora.

Boundary:

- Existing LLM ingress paths are unchanged.
- Existing structured compile behavior is unchanged.
- Existing OpenClaw configuration is unchanged; adapting OpenClaw `web_search` to call OmniMemora is a later running-integration batch.
- Brave or other fallback search providers are not implemented in this repo candidate.

Exit:

- Repo tests prove route registration, mmx command construction, bounded output, unsupported provider rejection, and bounded backend failure detail.
- Running reality is not claimed until the adapter is promoted and OpenClaw is configured to call the OmniMemora search endpoint.

## Success Criteria

Repo reality:

- Deterministic fixtures prove valid passthrough, valid compression, invalid graph fallback, and no memory-context-only regression.
- Tests cover Anthropic `tool_use/tool_result` ordering and ID preservation.
- Existing memory-context compile tests still pass.
- Single-file growth is controlled; new code lands in focused modules.

Running reality:

- Adapter promotion follows `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`.
- `http://127.0.0.1:18011/health` remains healthy.
- `/metrics/summary` and `/metrics/core_capabilities` remain fast enough for current product validation.
- Claude Code/OpenClaw tool-loop requests receive upstream responses.
- Successful structured compile requests show positive token saving without breaking tool continuation.
- Upstream-critical local processing does not add blocking work beyond deterministic parse/compress/validate.

## Phase6 Pointer

Phase6 remains the historical governance and promotion index. Structured compile work continues here and should not be treated as a Phase6 tail item.
