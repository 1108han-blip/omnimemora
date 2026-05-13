# Structured Compile Mainline

## Status

- Created: 2026-05-13
- Product line: OmniMemora structured context compilation
- Current status: SC-027 document-content preservation implemented in repo reality as the current beta18 compile fix
- Supersedes phase6 as the active engineering line for compile capability work.

## Product Target

OmniMemora compile should become a protocol-aware structured context compiler, not only a memory-context injector.

The compiler must reduce real token/cost usage while preserving the provider message graph needed by agent clients such as Claude Code and OpenClaw.

Long-term traffic-control principle: OmniMemora should remain weakly intrusive at the client layer while making the local `18011` product ingress the preferred control point for LLM traffic, AI tool traffic, tool-result shaping, token/cost accounting, and later structured compilation. Direct client-to-provider or client-to-CLI paths are temporary fallbacks, not the target product shape.

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

### SC-022 - Tool Plane Running Promotion

Goal: promote the repo candidate from SC-021 into the current local running adapter and prove the search endpoint is healthy without changing OpenClaw behavior yet.

Status: running reality promoted and validated on 2026-05-13.

Required:

- Promote adapter through `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`.
- Verify `18011 /health`.
- Verify `POST /tools/search` with a low-risk query and bounded timeout.
- Verify `/metrics/core_capabilities` and `/compile/status` remain responsive.
- Keep the conclusion scoped to running OmniMemora adapter capability only.

Boundary:

- Do not change OpenClaw configuration in SC-022.
- Do not start `5173`.
- Do not claim OpenClaw `web_search` is routed through OmniMemora until a separate integration batch proves it.

Evidence:

- Promotion log for initial SC-022 candidate:
  - `tools/verification/logs/promotion_20260513_065304.log`
  - repo revision: `8e6a12f`
  - result: `running_reality_promoted`
  - adapter pid changed from `64144` to `74856`
- First running `/tools/search` check returned `503` with `mmx_cli_not_found`.
  - Cause: launchd adapter environment did not include the interactive shell path where `mmx` is installed.
  - Fix: repo commit `4ad2479` resolves `mmx` from explicit env, PATH, or common local install paths.
- Second running `/tools/search` check returned `502` with `env: node: No such file or directory`.
  - Cause: the `mmx` executable uses `#!/usr/bin/env node`, and launchd adapter PATH did not include the local Node binary path.
  - Fix: repo commit `3868f55` adds bounded tool-subprocess PATH defaults for common Node/mmx locations.
- Final promotion log:
  - `tools/verification/logs/promotion_20260513_065502.log`
  - repo revision: `3868f55`
  - result: `running_reality_promoted`
  - adapter pid changed from `76745` to `78316`
- Final running validation:
  - `POST /tools/search`: HTTP `200`, response time `2.039187s`
  - provider: `mmx`
  - backend: `mmx_cli`
  - output format: `json`
  - returned content was capped to `1200` chars and marked `truncated=true`
  - OmniMemora endpoint-reported backend elapsed time: `1717.066ms`
  - `/metrics/core_capabilities?tenant=all`: HTTP `200`, `0.300633s`
  - `/compile/status?window_minutes=10`: HTTP `200`, `0.297529s`

Conclusion:

- OmniMemora running adapter now exposes a working local Tool Plane search endpoint.
- SC-022 did not change OpenClaw configuration; OpenClaw routing is covered by SC-023.

### SC-023 - OpenClaw Search Routing Integration Plan

Goal: decide the smallest weak-intrusion way to make OpenClaw `web_search` call OmniMemora `/tools/search` instead of a direct external provider or direct CLI fallback.

Status: implemented and running-local validated on 2026-05-13.

Preferred path:

- Use an OpenClaw-supported provider/plugin/config hook if one exists.
- If no supported hook exists, keep the current direct fallback and record the missing product integration boundary.
- Do not patch OpenClaw internals blindly from OmniMemora.

Exit:

- Record the exact OpenClaw config surface or plugin surface to change.
- Only proceed to running mutation after the config surface is clear and reversible.

Implementation:

- Added a standalone local OpenClaw plugin candidate:
  - `5_connectors/omni-tool-plane-openclaw-plugin/`
  - plugin id: `omnimemora-tool-plane`
  - web search provider id: `omnimemora`
  - provider behavior: OpenClaw `web_search` -> OmniMemora `POST /tools/search` -> local `mmx` backend.
- The plugin is separate from the existing `omnimemora-memory` plugin so search routing does not trigger memory auto-recall or auto-capture behavior.
- The plugin has no external npm dependency and no credential requirement.

Repo validation:

- `node --test 5_connectors/omni-tool-plane-openclaw-plugin/index.test.mjs`: `3 passed`.
- `node --test` validates provider registration, successful OmniMemora response normalization, and bounded failed-response payloads.

Running OpenClaw configuration:

- Installed with:
  - `openclaw plugins install --link /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/omni-tool-plane-openclaw-plugin`
- OpenClaw wrote config backups under `~/.openclaw/openclaw.json.bak`.
- `openclaw plugins inspect omnimemora-tool-plane --json` reported:
  - `enabled=true`
  - `status=loaded`
  - `webSearchProviderIds=["omnimemora"]`
  - source path under this repo's `5_connectors/omni-tool-plane-openclaw-plugin/index.mjs`
- OpenClaw config was patched to:
  - `tools.web.search.provider=omnimemora`
  - `tools.web.search.timeoutSeconds=12`
  - `plugins.entries.omnimemora-tool-plane.config.webSearch.baseUrl=http://127.0.0.1:18011`
  - `plugins.entries.omnimemora-tool-plane.config.webSearch.timeoutSeconds=12`
  - `plugins.entries.omnimemora-tool-plane.config.webSearch.maxChars=6000`
- `openclaw config validate`: passed.
- Gateway log showed config hot reload applied for `plugins.entries.omnimemora-tool-plane.config`, `tools.web.search.provider`, and `tools.web.search.timeoutSeconds`.

Running validation:

- Command:
  - `openclaw infer web search --provider omnimemora --query 'MiniMax AI official website' --limit 2 --json`
- Result:
  - `ok=true`
  - `capability=web.search`
  - `provider=omnimemora`
  - `upstreamProvider=mmx`
  - `count=2`
  - provider-reported `tookMs=1161`
  - returned structured result entries with title, url, description, published, and siteName.

Full agent-turn validation:

- Command:
  - `openclaw agent --agent main --message "验证 OmniMemora Tool Plane：请必须调用 web_search 搜索 'MiniMax AI official website'，然后只用一句中文说明官网域名是什么。不要执行 shell、不要使用浏览器。" --thinking off --json --timeout 120`
- Result:
  - OpenClaw run id: `4fe32259-1bfe-44b9-8946-c7ed93ba2f73`
  - OpenClaw session id: `28499d9e-81aa-4896-a845-ae495d47314a`
  - command status: `ok`
  - command duration: `35897ms`
  - OpenClaw `toolSummary`: one call to `web_search`, zero failures
  - OpenClaw tool result provider: `omnimemora`
  - OpenClaw tool result upstream provider: `mmx`
  - OpenClaw tool result `tookMs`: `3166`
  - final assistant text: `MiniMax 官网域名为 **chat.minimax.io**。`
  - final stop reason: `stop`
  - trajectory status: `success`, `timedOut=false`, `timedOutDuringToolExecution=false`
- OmniMemora LLM ingress records for the same turn:
  - `23820fba86e3`: OpenClaw first Anthropic-compatible request, upstream `200`, final `200`
  - `e44f4b2c0c26`: OpenClaw post-tool Anthropic-compatible request, upstream `200`, final `200`
  - `/compile/status?window_minutes=10`: OpenClaw `structured_compile_success=4`, `success_share=1.0`
- Endpoint health after validation:
  - `POST /tools/search` direct check with trace `sc023-final-health-check`: HTTP `200`, provider `mmx`, backend `mmx_cli`, response time `1.130922s`
  - `/metrics/core_capabilities?tenant=all`: HTTP `200`, response time `0.363399s`
  - `/compile/status?window_minutes=10`: HTTP `200`, response time `0.371622s`

Boundary:

- This proves the OpenClaw web-search capability can route through OmniMemora.
- The full agent-turn sample proves one forced-search OpenClaw agent turn can choose `web_search`, route through OmniMemora, and complete inside the 45-second agent deadline.
- It does not yet prove unforced daily prompts always choose `web_search` or that all longer search tasks complete inside the deadline.
- The installed plugin is linked to the repo path, so moving or deleting the repo path would break the OpenClaw plugin until packaged or installed as a copied plugin.

### Daily Evaluation Taxonomy

Goal: keep routine OpenClaw/Claude Code evaluation durable and comparable across sessions instead of relying on operator or agent chat memory.

When a user-visible agent turn appears missing, delayed, or recovered by a later "continue" request, classify the sample before assigning product responsibility:

- `tool_result_recovered_by_session`: a prior run wrote the relevant tool result into the same client session, the final assistant turn timed out or was aborted, and a later continuation succeeded because the client resent the session transcript. This is a positive structured-compile preservation sample when OmniMemora did not break the tool graph.
- `tool_result_broken_after_compile`: the relevant tool result existed before OmniMemora compile, but the compiled payload prevented the model from continuing correctly. Investigate `tool_use` id preservation, `tool_result.tool_use_id`, role ordering, recent-result protection, and content truncation rules.
- `ui_missing_but_session_success`: the client session file or trajectory recorded a successful assistant response, but the UI did not show it. Treat this as client display/sync behavior unless separate evidence shows OmniMemora returned an error.

2026-05-13 OpenClaw reference sample:

- User sent `continue` after the previous AI-video-platform request had already produced an `mmx` search tool result but timed out before final assistant output.
- OpenClaw resent the same session transcript; OmniMemora recorded request `34ee1d8f22e1` with `structured_compile_success`, `packed_memory_count=0`, and no `/tools/search` call for the continuation turn.
- MiniMax returned `200`, OpenClaw wrote an assistant response with `stopReason=stop`, and the trajectory recorded `finalStatus=success`.
- Classification: `tool_result_recovered_by_session`, not Omni memory recall and not OpenClaw `memory_search` success.

### SC-024 - User Pattern Layer Direction Gate

Goal: decide whether OmniMemora should add a user-controlled long-term preference and workflow-pattern layer after the structured compile MVP, without turning internal evaluation logs into hidden behavior tracking.

Status: direction gate opened on 2026-05-13. No product behavior, database schema, GUI, or running configuration change in this record.

Product interpretation:

- Treat high-value user habit data as user-controlled context assets, not surveillance or behavioral telemetry.
- The product value is continuity and token saving: users should repeat fewer stable constraints, project facts, and collaboration preferences across agents.
- The AI OS direction is a local context broker that can serve multiple opted-in agents through `:18011`, not a background profile collector.
- This layer must remain subordinate to the structured compile goal: only inject compact, relevant, protocol-safe context when it improves the current request.

Research inputs to preserve:

- Mem0: structured persistent memory can outperform full-context history while reducing latency and token cost.
- MemMachine: keep ground-truth conversational episodes separate from derived profile memory to reduce lossy extraction risk.
- MemX: local-first, explainable retrieval with low-confidence rejection is a better fit than aggressive recall for preference data.
- Letta and Supermemory: cross-agent continuity is the product direction to study, but OmniMemora should not adopt external hosted memory behavior or hidden telemetry defaults.

Allowed candidate categories:

- `preference`: explicit stable user preferences, such as response language, tone, or collaboration style.
- `workflow`: repeated operator process constraints, such as baseline-first changes or separate repo/running reality.
- `project_fact`: stable product or workspace facts that prevent repeated prompt overhead.
- `correction`: repeated negative feedback that should prevent the agent from taking the same wrong path again.

Hard boundaries:

- Do not build a separate user-habit database in the first candidate phase.
- Do not infer sensitive identity, health, finance, personal relationship, or location habits from request metadata.
- Do not use meter, proxy, trace, compile, or tool logs as a hidden profile source.
- Do not auto-inject unapproved or low-confidence habits into upstream prompts.
- Do not add external memory, compression, or profiling services.
- Do not make upstream-critical compile paths depend on model-based habit extraction.

First implementation shape, if approved later:

- Reuse the existing `memory.db` memory record path with stricter metadata instead of adding a new database.
- Store candidates as normal memories with metadata fields such as `category`, `source_event_id`, `confidence`, `approval_status`, `expires_at`, and `derived_from`.
- Default new candidates to `candidate` or `needs_review`; only `approved` or explicitly safe project facts may enter compile.
- Keep extraction off the upstream-critical path; run it after the request, in bounded local background work, or through an explicit operator action.
- Preserve the source pointer needed to explain why a candidate exists, but avoid storing raw prompt/tool content beyond normal memory policy.

Evaluation gate before code:

- Show that selected patterns reduce repeated prompt tokens on real requests.
- Show that compile injection stays smaller than the repeated text it replaces.
- Show that false personalization is rejected or remains unapproved.
- Show that `/health`, `/metrics/summary`, `/metrics/core_capabilities`, and `/compile/status` remain fast when running validation is in scope.
- Keep file count flat or justify any added file by replacing old code or preventing single-file growth.

Exit:

- A later SC-025 candidate may implement only candidate extraction and storage metadata.
- GUI review, automatic approval, new database tables, and cross-device/cloud sync remain out of scope until real token-saving value is proven.

### SC-025 - Token Audit and User Pattern Lite Data Plan

Goal: prepare Token Audit Mode as a near-term product focus while allowing a bounded user database for token-saving value, not broad user profiling.

Status: direction record opened on 2026-05-13. No product behavior, schema, GUI, or running configuration change in this record.

Decision:

- Do not build user profiling.
- Do allow `User Pattern Lite` when records are compact, user-visible, and used to reduce repeated prompt tokens.
- Do allow a small user database if it supports token saving, provider-aligned token audit, and user control.
- Do not create large files or make upstream-critical paths depend on slow persistence.
- Token Audit Mode must include user data management from the start: view, delete/expire, confidence labels, and raw-payload avoidance by default.

Plan:

- See [Token Audit and User Pattern Lite Data Plan](./token_audit_user_data_plan.md).

### SC-026 - OpenClaw 45-Second Deadline Profile

Goal: reduce OpenClaw long-content failures caused by a fixed 45-second harness deadline without adding a task platform or extra LLM calls.

Status: repo reality implemented on 2026-05-13. The current beta17 app runtime under `/Users/sc/.omnimemora/app/current` has been synced and validated, but the app-target promotion script still recorded `promotion_failed` because its API gate checked during the adapter restart window. SC-027 supersedes the part of this record that allowed OpenClaw to compress the latest oversized `tool_result`.

Implementation:

- Added an OpenClaw-only structured compile deadline profile for long Anthropic tool-context requests.
- The profile triggers only when `agent_id=openclaw`, structured compile is enabled, the payload is Anthropic tool context, and the full payload token estimate crosses the long-context threshold.
- Default profile values:
  - client deadline: `45s`
  - compile budget marker: `2500ms`
  - long-context threshold: `8000` estimated tokens
  - OpenClaw tool-result target: `700` chars
- Original SC-026 behavior allowed the profile to deterministically compress the latest oversized `tool_result`; SC-027 changes the current policy so OpenClaw also protects the latest tool result by default.
- No LLM summarization, cloud fetch, historical scan, memory search, or extra provider call is added to the upstream-critical path.
- Compile events now persist deadline fields such as `deadline_profile`, `structured_compile_latency_ms`, `deadline_budget_exceeded`, and `protect_latest_tool_result`.

Boundary:

- This does not promise all OpenClaw 45-second failures can be fixed.
- It targets failures where long tool results or large repeated context consume the client deadline before final answer assembly.
- It keeps protocol graph fields intact: `tool_use.id`, `tool_result.tool_use_id`, roles, ordering, and provided tool schemas remain provider-valid.
- It is not a general heartbeat, multi-step task protocol, or UI progress system.

Repo validation:

- `/usr/bin/python3 -m pytest 5_connectors/adapter/tests/test_context_compiler_structured_compile.py 5_connectors/adapter/tests/test_gateway_compile_skill_suggestions.py 5_connectors/adapter/tests/test_llm_proxy_compile_event_persistence.py`: `16 passed`.
- `/usr/bin/python3 -m pytest 5_connectors/adapter/tests/test_llm_proxy_agent_detection.py 5_connectors/adapter/tests/test_llm_proxy_auto_memory_write.py 5_connectors/adapter/tests/test_gateway_compile_internal_memory_status.py 5_connectors/adapter/tests/test_compile_store_distribution_summary.py`: `17 passed`.
- `/usr/bin/python3 -m py_compile 5_connectors/adapter/application/context_compiler/compiler.py 5_connectors/adapter/application/gateway_compile.py 5_connectors/adapter/config.py 5_connectors/adapter/ingress/llm_proxy.py`: passed.
- `git diff --check`: passed.

Running validation:

- A default-target adapter promotion wrote the candidate to `/Users/sc/.omnimemora/service/current`, but failed `code_source` validation because the current beta17 LaunchAgent runs from `/Users/sc/.omnimemora/app/current`.
  - Log: `tools/verification/logs/promotion_20260513_141556.log`
  - Result: `promotion_failed`
- The app-target promotion command synced the candidate into the actual running path:
  - `OMNIMEMORA_SERVICE_DIR=/Users/sc/.omnimemora/app tools/promotion/promotion.sh adapter`
  - Log: `tools/verification/logs/promotion_20260513_141746.log`
  - Result: `promotion_failed`
  - Failure scope: API reality gate reported `api_unreachable` during restart validation.
- Independent post-restart running checks:
  - `/debug/runtime_fingerprint` reported PID `81581` and code source under `/Users/sc/.omnimemora/app/current/5_connectors/adapter/main.py`.
  - SHA-256 matched between repo reality and app runtime for `gateway_compile.py`, `context_compiler/compiler.py`, `config.py`, and `llm_proxy.py`.
  - `/health`: HTTP `200`; repeated checks included `0.004738s` and `0.004788s` after the restart settled.
  - `/metrics/summary`: HTTP `200`; repeated checks included `0.003345s`, `0.006008s`, and `0.018665s`.
  - `/metrics/core_capabilities`: HTTP `200`, but not within the default internal `<100ms` target in this sample; repeated checks ranged from `0.195818s` to `0.718751s`.
- Direct product ingress validation:
  - A real `POST http://127.0.0.1:18011/llm/v1/messages` request with `agent_id=openclaw` and a long Anthropic `tool_result` executed the structured compile path.
  - Upstream returned HTTP `500` for the artificial tool payload, but the gateway response explicitly reported `Gateway compile succeeded, upstream returned HTTP 500`.
  - Latest compile event for request `15ad55912435`:
    - `compile_status=structured_compile_success`
    - `deadline_profile=openclaw_45s_long_tool_context`
    - `deadline_profile_applied=true`
    - `original_token_estimate=70120`
    - `compiled_token_estimate=241`
    - `structured_compile_latency_ms=312`
    - `deadline_budget_exceeded=false`
    - `protect_latest_tool_result=false`
    - `max_tool_result_chars=700`

### SC-027 - Document Content Preservation for OpenClaw

Goal: prevent structured compile from degrading complete local Markdown/document reads into keyword-only fragments when OpenClaw sends the content through `18011`.

Status: repo reality, current app runtime, local beta18 package, and public controlled-beta download surface validated on 2026-05-13.

Cause:

- Markdown documents with bullet lists can look like diffs when a compressor treats `- item` lines as deletion lines without requiring real diff headers.
- OpenClaw's 45-second deadline profile previously set `protect_latest_tool_result=false`, so the newest local file read could be compressed before the model saw it.
- The old tool-result marker preserved type and size information, but did not make source preservation or expansion intent explicit enough for downstream clients.

Implementation:

- Structured compile now protects tool results classified as document content, including Markdown/prose with headings, paragraphs, Chinese text, and bullet lists.
- Diff classification now requires real diff header evidence before Markdown `- item` lines can be treated as diff lines.
- OpenClaw's deadline profile now keeps `protect_latest_tool_result=true`; the latest local read is not eligible for deterministic compression.
- Tool-result compression markers now include `retained_content`, `source_trace`, and `expand` fields so a compressed non-document result is visibly partial and recoverable by rereading the original source.
- When every oversized candidate is protected document content, the compiler returns passthrough with `reason=protected_tool_result_content` instead of reporting a misleading compression success.

Boundary:

- This is not a summarizer. Full document reads are either preserved or the client must explicitly reread the source.
- This does not add LLM calls, cloud fetches, background tasks, historical scans, or hidden memory reads to the upstream-critical path.
- This does not change user-facing memory, meter files, or retention policy.

Repo validation:

- `/usr/bin/python3 -m pytest 5_connectors/adapter/tests/test_context_compiler_compressors.py 5_connectors/adapter/tests/test_context_compiler_structured_compile.py 5_connectors/adapter/tests/test_gateway_compile_skill_suggestions.py 5_connectors/adapter/tests/test_llm_proxy_compile_event_persistence.py`: `25 passed`.
- `npm run build` in `6_console/desktop-shell`: passed.
- `cargo test` in `6_console/desktop-shell/src-tauri`: `1 passed`.
- `git diff --check`: passed.

Running validation:

- App-target promotion command copied the adapter fix into the active runtime path:
  - `OMNIMEMORA_SERVICE_DIR=/Users/sc/.omnimemora/app tools/promotion/promotion.sh adapter`
  - Log: `tools/verification/logs/promotion_20260513_212752.log`
  - Script result: `promotion_failed`
  - Failure scope: the script API gate checked during restart and reported `api_unreachable`.
- Independent post-restart checks showed running reality recovered and loaded the candidate:
  - `/debug/runtime_fingerprint`: PID `88282`, code source under `/Users/sc/.omnimemora/app/current/5_connectors/adapter/main.py`.
  - SHA-256 matched between repo reality and app runtime for `context_compiler/compressors.py`, `context_compiler/compiler.py`, and `gateway_compile.py`.
  - `/health`: HTTP `200`, repeated checks included `0.003094s` to `0.007371s`.
  - `/metrics/summary`: HTTP `200`, repeated checks included `0.005220s` to `0.023266s`.
  - `/metrics/core_capabilities`: HTTP `200`, but this sample was above the default internal `<100ms` target at `0.142017s` to `0.162794s`.
  - `/compile/status`: HTTP `200`, but this sample was above the default internal `<100ms` target at `0.115642s` to `0.143559s`.
- Direct product ingress validation:
  - A real `POST http://127.0.0.1:18011/llm/v1/messages` request with `agent_id=openclaw`, Anthropic tool context, and a long Markdown `tool_result` returned HTTP `200`.
  - Latest compile event for request `6f1d67165474`:
    - `compile_status=structured_compile_passthrough`
    - `compile_reason=protected_tool_result_content`
    - `deadline_profile=openclaw_45s_long_tool_context`
    - `deadline_profile_applied=true`
    - `original_token_estimate=8040`
    - `compiled_token_estimate=8040`
    - `structured_compile_latency_ms=34`
    - `deadline_budget_exceeded=false`
    - `protect_latest_tool_result=true`
    - `max_tool_result_chars=700`

Release validation:

- `npm run tauri:build` produced the beta18 `.app`, DMG, and updater tarball, but exited non-zero because this machine has the public updater key without `TAURI_SIGNING_PRIVATE_KEY`.
- `hdiutil imageinfo` passed for `OmniMemora Desktop_1.0.0-beta.18_aarch64.dmg`.
- `bash 4_core/local-runtime/scripts/release/build_release.sh 1.0.0-beta.18`: passed and wrote the beta18 package set.
- `/tmp/omni-publish-venv/bin/python 4_core/local-runtime/scripts/release/publish_beta_release.py 1.0.0-beta.18`: uploaded beta18 artifacts to R2 and deployed `omnimemora-control-entry`.
- Public checks:
  - `https://doloclaw.com/download`: HTTP `200` and displays `1.0.0-beta.18`.
  - `https://doloclaw.com/releases/latest.json`: redirects to the beta18 manifest and reports version `1.0.0-beta.18`.
  - `https://doloclaw.com/download/file/darwin-arm64`: redirects to the beta18 DMG and returns HTTP `200`.

Change scope:

- File count stayed flat for implementation and tests; all changes landed in existing compiler, gateway, and regression-test files.
- Resident background logic stayed flat; no daemon, scheduler, watcher, or asynchronous worker was added.
- Internal log retention remains governed by the existing product retention path; no user-facing memory path was touched.

### SC-028 - OpenClaw Harness Profile Boundary and Protocol Error Preservation

Goal: keep OpenClaw product ingress from inheriting the 45-second harness profile by default, while preserving protocol-level failure facts for the agent to handle.

Status: repo reality implemented on 2026-05-14. Running promotion is a separate step because this changes the `18011` adapter behavior.

Implementation:

- `OMNIMEMORA_STRUCTURED_COMPILE_OPENCLAW_DEADLINE_PROFILE_ENABLED` now defaults to `false`; the 45-second OpenClaw profile remains available only as an explicit compatibility experiment.
- OpenClaw keeps the normal upstream timeout budget; OmniMemora does not manage the agent's client window.
- OpenClaw upstream timeouts, upstream HTTP errors, and unexpected adapter errors preserve structured protocol error metadata instead of being converted into assistant messages.
- Failure responses preserve proxy failure metadata through protocol error bodies and compile/proxy event records.

Boundary:

- This does not disable structured compile globally.
- This does not manage OpenClaw UX, retries, final answer wording, or model behavior.
- This does not touch user-facing memory, meter files, retention policy, or the legacy `5173` surface.
- This does not silently truncate documents; document preservation remains governed by SC-027.

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
