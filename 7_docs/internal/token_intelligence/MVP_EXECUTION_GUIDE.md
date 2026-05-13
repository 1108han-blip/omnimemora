# DoloToken / Token Intelligence Lite MVP Execution Guide

Date: 2026-05-13

## Purpose

This guide converts the external GPT draft into a usable Phase 8 execution guide for OmniMemora.

Target:

> DoloToken: local AI request receipts plus token-flow intelligence for LLM users.

The product must explain where tokens were spent, why they were spent, what was waste, and which Omni optimization can reduce future token use. Cost and money views are optional interpretation layers on top of token-flow truth.

Refined product target:

> DoloToken is the LLM Usage Verification Layer for OmniMemora.

It is not a universal tokenizer and should not be marketed as exact third-party token calculation. LLM tokens are provider-specific accounting units. The product value is unified sampling, source labeling, confidence labeling, drift detection, and conservative runtime trust signals.

External name: DoloToken.

Internal name: Token Intelligence Lite.

## Product Position

Use:

```text
DoloToken gives local token transparency for LLM users.
DoloToken verifies LLM usage behavior across providers, relays, and APIs.
```

Do not use:

```text
Proof that a middleman is cheating.
Exact universal token counter.
```

Omni may detect unexplained deltas, but must report them as differences with possible causes, not accusations. Token counts can legitimately differ because of tokenizer differences, hidden context, caching, reasoning tokens, multimodal tokens, server-side tools, and relay accounting rules.

## MVP Product Goal

MVP goal:

```text
Build a unified sampling layer for every LLM request that passes through OmniMemora `18011`, then expose conservative usage verification signals without claiming absolute truth.
```

The MVP is successful when a non-technical user can answer:

- which agent, workflow, model, provider, and protocol spent tokens;
- whether the upstream reported usage or only local estimates are available;
- whether reported usage looks normal, divergent, incomplete, or unsupported;
- whether cache, latency, stream speed, finish reason, or model identity show obvious anomalies;
- where OmniMemora can reduce future token waste without hiding the measurement source.

The MVP is not required to prove:

- exact provider billing truth;
- exact hidden reasoning tokens;
- exact cache internals;
- exact model identity;
- fraud or intentional relay abuse.

Those can become later Runtime Audit / Model Fingerprinting capabilities after enough samples exist.

## First Packaging Decision

Phase 8 starts as a lightweight local module and local entrypoint.

```text
Client / AI tool / relay user
        ↓
DoloToken local proxy on localhost
        ↓
Configured upstream provider or relay
```

Rules:

- Default endpoint is local, for example `http://127.0.0.1:<port>`.
- First commercial shape can be a proprietary local CLI/local proxy download.
- No paid server requirement for MVP.
- No full desktop app requirement before audit-only trial.
- No browser extension as the primary capture path.
- Shared audit core remains reusable by full OmniMemora.

Update and distribution rules:

- Source code does not need to be open.
- The local CLI/proxy should check product-owned release metadata for online updates.
- The product may push update notices, minimum-version notices, and security/bugfix prompts through that metadata.
- Downloads must be versioned and checksum-verifiable.
- During unsigned macOS beta distribution, the user may need to allow the binary manually in Privacy & Security / Gatekeeper.
- Do not present this beta path as a signed silent updater until paid signing/notarization is actually in place.

Cloud note:

- This is a first-packaging decision, not a rejection of OmniMemora cloud assets.
- `doloclaw.com`, Cloudflare, and Railway remain available, but Token Intelligence should not depend on them until storage volume, request volume, privacy posture, and operating cost are measured.
- A cloud-hosted audit product can follow after local MVP proof; it must not be assumed as the initial route.

## Relationship To Omni

DoloToken is the standalone product name for an OmniMemora Token Intelligence module with a light local entrypoint.

```text
shared token intelligence core
        ↓
local audit proxy / CLI for first adoption
        ↓
full OmniMemora integration for optimization and desktop control
```

The standalone entrypoint is only a distribution shape. Product truth stays in OmniMemora logic.

Boundary clarification:

- OmniMemora is an agent path and optimization layer; it should not be described as owning an upstream model.
- OpenClaw and Claude Code currently use Anthropic-compatible MiniMax M2.7 paths when routed through OmniMemora.
- `gemma4:26b` is a local Ollama model option on this machine, not current OmniMemora upstream truth.
- A `/v1/models` compatibility response is not proof of actual agent model selection, upstream health, or product routing truth.

## MVP Scope

Included:

- `18011` remains the only official OmniMemora agent ingress.
- Unified sampling for LLM requests that pass through `18011`.
- OpenAI-compatible `POST /v1/chat/completions` sample normalization.
- Anthropic-compatible non-streaming `POST /v1/messages` sample normalization.
- Provider/protocol/model/request metadata.
- Input/output character counts.
- Response `usage` extraction when present.
- Local token estimate when usage is missing or for comparison.
- Source and confidence label on every token number, and on every optional cost number when cost is present.
- Latency, finish reason, status code, and route/protocol metadata.
- Cache read/write fields when the provider or relay exposes them.
- Reasoning token fields when the provider or relay exposes them.
- Compact SQLite audit ledger.
- No raw prompt storage by default.
- Request receipt read/export.
- Local recent-usage report API or small local page.
- Difference analysis between reported usage and local estimate.
- Initial conservative verification statuses: `normal`, `watch`, `anomaly`, `needs_review`, `unsupported`.
- Potential savings report.

Deferred:

- Cloud-hosted audit SaaS.
- Browser extension capture.
- Full OpenAI Responses API coverage.
- Anthropic streaming and tool-loop semantic hardening for Claude Code and OpenClaw.
- Stream cadence and token-per-second trust scoring.
- Provider tokenizer/count API integration.
- Cross-tokenizer divergence matrix.
- Model fingerprinting or "real model probability" claims.
- AI Provider Trust Score.
- Multi-tenant team billing.
- Automatic optimization.
- User behavior analytics beyond token/workflow ROI and optional cost interpretation.

Stage boundary:

- Current behavior analysis means workflow/token ROI only.
- It is not broad user profiling in the MVP.
- A future user-profile capability is not ruled out, but it must be a separate explicit product stage with user-visible controls, opt-in, retention, export, delete, and disable paths.

## Usage Source And Confidence

Every number must carry a source:

```text
provider_reported      upstream provider returned usage
relay_reported         relay or middleman returned usage
local_estimated        Omni estimated locally
post_fetch_reported    usage fetched after completion
manual_price_inferred  cost inferred from a versioned pricing table
```

Every number must carry confidence:

```text
A official_usage       provider or relay returned detailed usage
B reconciled_usage     relay usage and local estimate are within expected range
C tokenizer_estimate   local tokenizer is known or compatible
D rough_estimate       unknown tokenizer, multimodal, reasoning, server tool, or incomplete payload
```

Rough estimates must never be displayed as billing truth.

Token accounting is the foundation. Money calculation is optional because official prices, relay prices, regions, discounts, user groups, cache rules, and routing policies differ. A future calculator may support user-selected pricing profiles, but no price table is the product anchor.

## Unified Sampling Record

Every sampled request should move toward this minimum normalized shape:

```json
{
  "schema_version": "llm-usage-sample-v1",
  "request_id": "req_xxx",
  "agent_id": "openclaw",
  "workflow_tag": "coding",
  "provider": "minimax",
  "protocol": "anthropic_messages",
  "model_requested": "MiniMax-M2.7",
  "model_reported": "MiniMax-M2.7",
  "route": "/v1/messages",
  "status_code": 200,
  "input_chars": 1832,
  "output_chars": 640,
  "local_estimated_input_tokens": 512,
  "provider_input_tokens": 601,
  "provider_output_tokens": 220,
  "provider_total_tokens": 821,
  "cache_read_tokens": 0,
  "cache_write_tokens": 0,
  "reasoning_tokens": null,
  "latency_ms": 4221,
  "stream_tokens_per_second": null,
  "finish_reason": "stop",
  "usage_source": "provider_reported",
  "usage_confidence": "official_usage",
  "verification_status": "normal"
}
```

Do not store raw prompt or raw response in this MVP shape by default. Store hashes, lengths, compact block summaries, and provider-visible usage metadata.

## Verification Signals

MVP signals:

- token divergence: reported usage versus local estimate;
- chars/token ratio: rough sanity check for unusual accounting;
- usage completeness: whether input, output, total, cache, and reasoning fields exist;
- cache plausibility: whether cache read/write values are plausible for the request shape;
- latency/token: basic speed sanity check;
- model consistency: requested model, reported model, provider, and route alignment;
- finish reason risk: stop, length, error, tool, or provider-specific termination markers.

Future signals:

- stream cadence and burst analysis;
- cross-tokenizer divergence across tiktoken, provider tokenizer, sentencepiece, Qwen tokenizer, and others;
- model fingerprinting from latency, stream rhythm, refusal pattern, style entropy, tool-call timing, and stop behavior;
- AI Provider Trust Score.

Trust language:

- use `normal`, `watch`, `anomaly`, `needs_review`, `unsupported`;
- avoid `cheating`, `fake`, `fraud`, or `real Claude probability` in MVP UI unless later evidence and governance explicitly support that product line.

## Three-Ledger Model

### Token Ledger

Normalize available fields:

- input/output/total tokens,
- cached input tokens,
- cache write tokens,
- reasoning tokens,
- image/audio/video tokens,
- tool/schema/server-tool tokens when exposed.

### Cost Ledger

Normalize available fields:

- input/output cost,
- cache read/write cost,
- reasoning cost,
- tool/server-tool cost,
- total cost,
- pricing version.

Cost is not official unless provider or relay reports it. Local price-table inference must be labeled, opt-in, and treated as calculator output, not audit truth.

### Workflow ROI Ledger

Record compact metadata only:

- agent id,
- project/workspace tag,
- workflow tag,
- model,
- request status,
- latency,
- retry count,
- memory signal,
- context reuse score,
- prompt repetition score,
- potential savings,
- actual savings after optimization.

This is for token/cost/workflow ROI, not broad user profiling.

## Audit Receipt

Each request should produce a compact receipt.

Minimum fields:

- audit id and request id,
- request/response hash,
- upstream base URL hash,
- provider and requested/reported model,
- normalized usage with source and confidence,
- normalized or inferred cost with pricing version,
- latency, status, created time.

Raw prompt and response body are not part of the default receipt.

## Difference Analysis

Compare:

- local input estimate,
- local output estimate when possible,
- provider/relay reported usage,
- inferred or reported cost.

Use neutral classifications:

```text
normal_delta
warning_delta
unexplained_delta
```

For large deltas, list possible causes:

- tokenizer mismatch,
- hidden system or relay context,
- multimodal/tool tokens not counted locally,
- cache/reasoning/server-tool accounting,
- relay billing multiplier or pricing rule.

Never classify this as fraud without independent evidence.

## Privacy Defaults

Default content mode:

```text
metadata_only
```

Allowed modes:

```text
metadata_only
redacted_content
full_content
```

`full_content` is explicit opt-in only.

Required controls before normal release:

- delete audit events,
- expire audit events,
- export receipts,
- disable audit,
- disable User Pattern Lite,
- verify raw prompt storage is off by default.

## Data Model Candidate

SQLite is acceptable for MVP.

Candidate tables:

- `audit_events`,
- `audit_usage`,
- `audit_costs`,
- `audit_receipts`,
- `audit_deltas`,
- `workflow_rollups`,
- `user_pattern_candidates`,
- `user_patterns`.

Constraints:

- compact rows only;
- hashes and metadata by default;
- raw content only in opt-in side tables with retention;
- versioned pricing data;
- short transactions;
- audit write failure must not block upstream forwarding.

## First Report Surface

Keep the first dashboard small:

- today requests,
- today tokens,
- optional today estimated/reported cost,
- optional average cost per request,
- top 10 expensive requests,
- optional top models by cost,
- optional top agents/workflows by cost,
- cache hit rate when available,
- unexplained delta requests,
- potential savings by category.

## Optimization Bridge

Token Intelligence becomes OmniMemora value when audit turns into optimization.

```text
audit-only passthrough
        ↓
potential savings report
        ↓
enable structured compile / User Pattern Lite / prompt reduction
        ↓
actual savings proof
```

Recommendations must map to one of:

- structured compile,
- tool-result/log/diff compression,
- duplicate context removal,
- prompt reduction,
- memory miss repair,
- model/workflow selection,
- User Pattern Lite.

If a recommendation cannot map to an action, it is not MVP product value.

## Implementation Batches

### TI-001A - OpenAI-Compatible Audit Proxy

Implement audit-only local proxy for `POST /v1/chat/completions`.

Exit:

- request forwards to configured upstream;
- non-streaming response returns unchanged;
- audit event is written without raw prompt storage by default.

### TI-001B - Usage Normalizer

Normalize OpenAI-compatible usage fields:

- `prompt_tokens`,
- `completion_tokens`,
- `total_tokens`,
- `prompt_tokens_details.cached_tokens`,
- `completion_tokens_details.reasoning_tokens`,
- provider-specific `cost` if present.

Exit: every normalized field has source and confidence.

### TI-001C - Local Estimate Fallback

Estimate usage when upstream usage is missing.

Exit:

- estimates are labeled `local_estimated`;
- rough estimates are never displayed as billing truth.

### TI-001D - Receipt API

Add receipt read/export.

Exit: receipt contains hashes, usage, cost, source, confidence, and pricing version.

### TI-001E - Difference Analyzer

Compare reported usage with local estimates.

Exit:

- normal, warning, and unexplained delta classifications exist;
- output lists possible causes without accusation.

### TI-001F - First Report Surface

Expose recent summaries by API or small local page.

Exit:

- daily totals, top requests, top models, and unexplained deltas are visible;
- no large historical scan is required on hot read.

## Design References

Use as references, not dependencies:

- Langfuse token/cost tracking: usage type breakdown and preference for ingested usage over inferred usage: <https://langfuse.com/docs/observability/features/token-and-cost-tracking>
- OpenAI prompt caching: `cached_tokens` and `reasoning_tokens` are first-class usage fields: <https://developers.openai.com/api/docs/guides/prompt-caching>
- OpenRouter API: OpenAI-compatible usage and post-fetch generation stats are useful relay-audit references: <https://openrouter.ai/docs/api/reference/overview>
- OpenTelemetry GenAI conventions: align naming where useful, but do not send prompt/output bodies to telemetry by default: <https://opentelemetry.io/docs/specs/semconv/gen-ai/>

## Non-Regression Rules

- Do not rebrand this as a generic usage dashboard.
- Do not make cloud hosting mandatory.
- Do not make browser extension the first capture path.
- Do not store raw prompt by default.
- Do not claim exactness when the source is estimated.
- Do not build user profiling inside the Phase 8 MVP.
- Do not let a future user-profile line silently inherit audit logs without a new explicit stage and controls.
- Do not let audit persistence delay upstream forwarding.
- Do not add large fixture or log files.
