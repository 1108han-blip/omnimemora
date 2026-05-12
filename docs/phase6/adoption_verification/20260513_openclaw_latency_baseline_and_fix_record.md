# OpenClaw Latency Baseline and Fix Record - 2026-05-13

## Baseline

- Repo reality: `ba60427453d13a32a8c59d81fdfe909c89474473`
- Branch state at baseline: `master...origin/master [ahead 43]`
- Worktree state at baseline: clean
- Product path under investigation: OpenClaw -> `18011` adapter -> Anthropic-compatible `/llm/v1/messages` -> MiniMax-M2.7.
- Current product surface boundary: `18011` adapter only; `5173` is not part of this validation.

## Running Evidence Before Fix

Recent OpenClaw request ids used to split latency:

| request_id | compile | post-compile before upstream marker | upstream after marker | total to upstream success |
| --- | ---: | ---: | ---: | ---: |
| `1c1f32d260a0` | 0s | 7s | 9s | 16s |
| `b224018c6c3d` | 0s | 7s | 27s | 34s |
| `f62766736cbc` | 1s | 6s | 23s | 30s |
| `9409a6ec326a` | 0s | 7s | 23s | 30s |

Aggregate from the recent 12 OpenClaw Anthropic-path samples:

- Compile / memory search: median `0s`, max `1s`.
- Compile-success to pre-upstream marker: median `6s`, p90 `7s`, max `7s`.
- Upstream-after-marker latency: median `17.5s`, max `27s`.

## Baseline Diagnosis

- Compile is not the slow stage.
- The product-owned pre-upstream synchronous accounting path contributes a repeated `5-7s` delay.
- MiniMax first response latency remains outside direct product control.
- OpenClaw may turn diagnostic prompts into tool-use flows; this product change does not alter that client-side behavior.

## Compile Semantics Clarification

Clarification added during the 2026-05-13 Claude Code/OpenClaw investigation:

- Product intent: OmniMemora compile should evolve toward structured context compilation across user, assistant, system, tool, provider context, and OmniMemora memory layers.
- Current adapter implementation before the safety fix was narrower: it rebuilt upstream payloads from product `packed_context` plus the current user-visible query, and did not preserve the full original message graph.
- Therefore the current memory-context compile path was safe only for simple request shapes where the original message graph can be replaced by compiled memory context plus the current query.
- It was not proven safe for Claude Code/OpenClaw tool continuations containing `tool_use`, `tool_result`, assistant continuation state, or provider-required tool/result ordering.
- The immediate fix is a safety boundary, not a product-goal reduction: tool-context requests must bypass the narrow compile path until a protocol-aware structured compiler and fixtures exist.

## Structured Compile Product Constitution

Added 2026-05-13 as the working target for the next compile line:

- The highest-value product layer is structured context compilation, not raw memory injection.
- Product size is allowed to grow when the growth isolates compiler responsibility and directly serves token/cost saving on real requests.
- Single-file growth is not allowed as the default implementation strategy; protocol parsing, graph validation, compression, rebuild, and fallback logic should live in small focused modules.
- Runtime workflow blocking is not allowed: no LLM summarization, historical file scan, cloud fetch, or long persistence task may sit on the upstream-critical path by default.
- The first structured compiler should be deterministic and local-first: parse provider payloads, protect protocol-critical fields, compress only eligible text blocks, validate the rebuilt payload, and fall back to passthrough on any uncertainty.
- Strategy policy may control rollout, budgets, and agent scope after the compiler exists; it must not replace local protocol-preservation invariants.

## Fix Batches

### Batch 1 - Move Accounting Out of Pre-Upstream Path

Goal: preserve compile and the forwarded payload while removing meter/token-accounting/access-plan persistence from the upstream-critical path.

Expected behavior:

- Compile still runs before upstream.
- A minimal compile event remains before upstream dispatch.
- Full meter persistence moves to background/post-upstream handling.
- OpenClaw agent behavior and MiniMax request semantics remain unchanged.

### Batch 2 - OpenClaw Anthropic True Streaming

Goal: only for OpenClaw Anthropic streaming requests, use true upstream streaming and relay SSE bytes without waiting for the full upstream body.

Expected behavior:

- Applies to `/llm/v1/messages`, `/v1/messages`, and `/llm/anthropic` only when the request resolves to `agent_id=openclaw` and `stream=true`.
- Non-streaming requests and OpenAI/Codex paths remain unchanged.
- Streaming response bytes are relayed without JSON-level transformation.
- Post-stream memory/accounting work runs after the stream finishes.

## Validation Log

- Repo tests passed:
  - `/usr/bin/python3 -m pytest 5_connectors/adapter/tests/test_llm_proxy_agent_detection.py 5_connectors/adapter/tests/test_llm_proxy_compile_event_persistence.py 5_connectors/adapter/tests/test_llm_proxy_auto_memory_write.py`
  - `/usr/bin/python3 -m pytest 5_connectors/adapter/tests/test_gateway_compile_task_type_passthrough.py 5_connectors/adapter/tests/test_gateway_compile_internal_memory_status.py 5_connectors/adapter/tests/test_gateway_compile_skill_suggestions.py 5_connectors/adapter/tests/test_llm_proxy_responses_meter_persistence.py`
  - `/usr/bin/python3 -m py_compile 5_connectors/adapter/ingress/llm_proxy.py 5_connectors/adapter/tests/test_llm_proxy_agent_detection.py`
- Adapter promotion:
  - `tools/verification/logs/promotion_20260513_025802.log`: failed at adapter API health check while adapter was still restarting.
  - `tools/verification/logs/promotion_20260513_025850.log`: failed at adapter API health check while adapter was still restarting.
  - `tools/verification/logs/promotion_20260513_030229.log`: `final_status: running_reality_promoted`; adapter pid changed from `78112` to `80052`; code source `/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`.
  - `tools/verification/logs/promotion_20260513_030634.log`: `final_status: running_reality_promoted` after final stream-completion semantic tightening; adapter pid changed from `80052` to `82297`; code source `/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`.
- Running `18011` health after successful promotion:
  - `/health`: healthy.
  - `/metrics/summary`: returned degraded lightweight summary with `degraded_reason=summary_unavailable_no_historical_scan`.
  - `/metrics/core_capabilities`: returned real-input capability summary.
- Running endpoint timing after warmup:
  - `/health`: `0.002435s`.
  - `/metrics/summary`: `0.005386s`.
  - `/metrics/core_capabilities`: `0.183490s`.
- Pending post-fix OpenClaw request measurement: no new OpenClaw Anthropic request has been captured after the final successful `03:06:34` adapter promotion in this validation record.

## Change Scope Record

- Runtime Python file count: stayed flat for the adapter implementation path.
- Repository file count: increased by one documentation record file for the requested pre-change baseline and follow-up validation log.
- Resident background logic: stayed flat; meter persistence moved from pre-upstream synchronous execution into background/post-stream scheduling, without adding a new daemon or background service.
- Log retention policy: unchanged by this batch; no user-facing memory path was touched.
