# Token Intelligence Lite MVP Execution Guide

Date: 2026-05-13

## Purpose

This guide converts the external GPT draft into a usable Phase 8 execution guide for OmniMemora.

Target:

> AI request receipts plus token/cost intelligence for local-first LLM users.

The product must explain where tokens were spent, why they were spent, what was waste, and which Omni optimization can reduce future cost.

## Product Position

Use:

```text
Token transparency for LLM users.
```

Do not use:

```text
Proof that a middleman is cheating.
```

Omni may detect unexplained deltas, but must report them as differences with possible causes, not accusations. Token counts can legitimately differ because of tokenizer differences, hidden context, caching, reasoning tokens, multimodal tokens, server-side tools, and relay accounting rules.

## First Packaging Decision

Phase 8 starts as a lightweight local module and local entrypoint.

```text
Client / AI tool / relay user
        ↓
Omni Token Intelligence Lite on localhost
        ↓
Configured upstream provider or relay
```

Rules:

- Default endpoint is local, for example `http://127.0.0.1:<port>`.
- No paid server requirement for MVP.
- No full desktop app requirement before audit-only trial.
- No browser extension as the primary capture path.
- Shared audit core remains reusable by full OmniMemora.

## Relationship To Omni

Token Intelligence is an Omni module with a light standalone entrypoint.

```text
shared token intelligence core
        ↓
local audit proxy / CLI for first adoption
        ↓
full OmniMemora integration for optimization and desktop control
```

The standalone entrypoint is only a distribution shape. Product truth stays in OmniMemora logic.

## MVP Scope

Included:

- OpenAI-compatible `POST /v1/chat/completions` proxy.
- Non-streaming first; streaming follows after receipt semantics are stable.
- Configurable upstream base URL and API key reference.
- Response `usage` extraction.
- Local token estimate when usage is missing.
- Source and confidence label on every token/cost number.
- Compact SQLite audit ledger.
- No raw prompt storage by default.
- Request receipt read/export.
- Local recent-usage report API or small local page.
- Difference analysis between reported usage and local estimate.
- Potential savings report.

Deferred:

- Cloud-hosted audit SaaS.
- Browser extension capture.
- Full OpenAI Responses API coverage.
- Anthropic-native `/v1/messages` beyond later compatibility work.
- Multi-tenant team billing.
- Automatic optimization.
- User behavior analytics beyond token/cost/workflow ROI.

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

Cost is not official unless provider or relay reports it. Local price-table inference must be labeled.

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
- today estimated/reported cost,
- average cost per request,
- top 10 expensive requests,
- top models by cost,
- top agents/workflows by cost,
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
- Do not build user profiling.
- Do not let audit persistence delay upstream forwarding.
- Do not add large fixture or log files.
