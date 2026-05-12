# Structured Compile Mainline

## Status

- Created: 2026-05-13
- Product line: OmniMemora structured context compilation
- Current status: SC-004 running reality validated
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

Boundary:

- Offline or non-critical path first.
- No model download or network dependency in product hot path.
- Must be behind a separate compressor interface.
- Must compare against deterministic extractive baseline.

Exit:

- Adopt only if it improves token saving without quality or latency regression.

### SC-006 - Failure Corpus and Rule Refinement

Goal: use ACON-style failure analysis without building a training system.

Status: started in repo reality on 2026-05-13 with deterministic tool-schema validation. No failure corpus retention was added.

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
