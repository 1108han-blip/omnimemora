# OmniMemora Context Runtime Product Plan

Date: 2026-05-14

Status: product plan, not implementation approval

Scope: based on the four external notes under `/Users/sc/Library/Mobile Documents/iCloud~md~obsidian/Documents/myku/omnimemora/` and the current OmniMemora repo reality.

## 1. Decision

OmniMemora should be framed as a local-first AI Context Runtime product.

The immediate product is not a generic observability platform, not a new universal gateway, and not a cloud-first AI runtime warehouse. The current product path remains:

```text
Agent
  -> OmniMemora product ingress (:18011)
  -> structured compile / memory / token intelligence
  -> user's original upstream LLM path
```

The product thesis is:

```text
Use the least necessary context tokens to preserve or improve agent capability,
then prove where tokens were spent, wasted, saved, or still risky.
```

This makes the external Runtime Layer idea useful, but only after it is constrained by current OmniMemora rules:

- MVP first; token saving first; no complexity expansion.
- Desktop app is the current user control/display surface.
- `:18011` is the only product data ingress after explicit user opt-in.
- `:8765` remains the internal memory plane.
- `:5173` remains legacy/dev only.
- The product must preserve the user's provider/base_url/model/auth semantics.
- Runtime telemetry is admissible only when it directly improves token saving, cost clarity, latency stability, or product shrinkage.

## 2. Source Synthesis

The four source documents point to one larger direction:

| Source | Useful product idea | Current decision |
| --- | --- | --- |
| `01_omnimemora-ai-runtime-audit-plan.md` | Cross-provider usage verification, divergence checks, cache and reasoning visibility, provider trust signals | Adopt as DoloToken / Token Intelligence direction, but keep outputs conservative: source/confidence labels, anomaly/watch states, no fraud claims. |
| `02_ai-runtime-telemetry-system.md` | Runtime recorder, stream timing, chunk rhythm, latency/token, future fingerprint corpus | Adopt only bounded metadata and stream timing for product-ingress requests. Reject raw-first retention and large telemetry warehouse in current MVP. |
| `03_omnimemora-runtime-layer.md` | Runtime layer can become infrastructure used by OmniMemora and later other AI systems | Treat as future product-family direction. Do not split into a separate gateway/SDK/platform until Phase 7 and Phase 8 prove local product value. |
| `04_ai-context-runtime-infrastructure.md` | Compile + memory + runtime telemetry form a closed optimization loop | Adopt as product narrative: Context Efficiency Infrastructure. Immediate loop is structured compile -> token intelligence -> optimization proof. |

## 3. Current Product Reality

Repository reality on 2026-05-14:

- Formal roadmap current line is Phase 7: Structured Compile MVP.
- Next formal line is Phase 8: DoloToken / Token Intelligence Lite.
- Phase6 is historical governance and promotion index, not the active product-value phase.
- Structured compile has already proven deterministic token reduction on Anthropic-compatible product-ingress requests while preserving tool graph semantics.
- Token Intelligence already has a local DoloToken beta package line and a first `18011` unified sampling implementation for metadata-only usage samples.

Running-reality claims are not made by this document. Any new runtime behavior still requires the promotion governance path when implementation starts.

## 4. Product Architecture Target

The target architecture is three product layers on one controlled ingress:

```text
                 Desktop control/display
                         |
                         v
Agent -> :18011 Product Ingress -> Compile Layer -> Original Upstream
                         |              |
                         |              v
                         |        Memory Layer (:8765)
                         |
                         v
                 Token Intelligence / Runtime Audit
```

Layer responsibilities:

| Layer | Responsibility | Current stage |
| --- | --- | --- |
| Compile Layer | Protocol-aware context parsing, protection, compression, rebuild, fallback | Phase 7, active |
| Memory Layer | Product memory and context recall, internal only | Existing product core |
| Runtime Audit Layer | Metadata-only token-flow accounting, latency/stream observation, divergence and waste signals | Phase 8, next/current adjacent line |

The Runtime Audit Layer must not become a second product ingress. It observes requests that already pass through `:18011` or through the separately packaged DoloToken local proxy when explicitly installed.

## 5. MVP Product Plan

### Batch A - Context Runtime Plan Freeze

Goal: make the product direction explicit without expanding runtime behavior.

Deliverables:

- This plan document.
- Optional roadmap/index sync if the operator wants formal promotion from plan to roadmap.

Exit:

- The plan clearly separates immediate product work from future infrastructure candidates.
- No code, no promotion, no live validation required.

### Batch B - Structured Compile Completion

Goal: finish Phase 7 as the core value engine.

Work allowed:

- More deterministic block compressors for high-token agent artifacts.
- Provider-aligned local token estimates where no network call is needed.
- Compile distribution telemetry on existing bounded surfaces.
- Anonymous minimal failure samples only when explicitly enabled.

Exit:

- Real product-ingress requests show positive compile token delta.
- Tool graph, role order, tool ids, tool results, and provider schemas remain valid.
- `/health`, `/metrics/summary`, and `/metrics/core_capabilities` stay fast when runtime validation is in scope.
- No raw prompt warehouse, no LLM summarization in hot path, no cloud policy dependency.

### Batch C - DoloToken Runtime Audit MVP

Goal: turn token saving into explainable token intelligence.

Work allowed:

- Unified usage envelope for OpenAI-compatible and Anthropic-compatible requests through product-owned paths.
- Source/confidence labels: provider-reported, relay-reported, official count API, compatible estimate, rough estimate.
- Block-level spend breakdown with no raw prompt/tool-output storage by default.
- Conservative waste detectors for duplicate context, long tool/log/test/diff output, retry waste, memory miss signals, and weak prompt ROI.
- Bounded retention/delete/export/disable controls.
- Local report page and local MCP read-only companion only as optional query surfaces, not capture paths.

Exit:

- A user can answer: where did tokens go, why were they spent, what was waste, what can be optimized, and whether optimization actually saved tokens.
- DoloToken does not claim exact billing truth from local estimates.
- Difference analysis stays neutral: normal, watch, anomaly, needs_review, unsupported.

### Batch D - Closed Optimization Loop

Goal: connect audit findings back to compile actions without auto-expanding behavior.

Work allowed:

- Link Token Intelligence opportunities to structured compile reason codes.
- Compare potential savings versus actual savings after compile.
- Show failed, negative, partial, and realized savings.
- Keep recommendations concrete: compile, prompt reduction, memory repair, model/workflow selection, or User Pattern Lite.

Exit:

- Product can prove actual savings from at least one optimization path.
- Recommendations do not become generic analytics.
- No automatic model switching or hidden user profiling.

## 6. Future Infrastructure Candidates

These ideas are valuable but not current MVP work:

| Candidate | Earliest condition |
| --- | --- |
| Independent Runtime SDK | Only after Phase 7/8 prove local product value and stable schemas. |
| OmniRuntime Console | Only after local report surfaces prove repeated user demand. |
| ClickHouse/Timescale telemetry backend | Only after measured local sample volume exceeds bounded SQLite/report capacity and cloud cost/privacy are designed. |
| Model fingerprint engine | Only after enough metadata-only samples exist and conservative anomaly labels are insufficient. |
| Provider Trust Score | Only after independent evidence exists; must not start as fraud scoring. |
| Runtime corpus strategy | Only with explicit user consent, anonymization, retention, export/delete, and storage-cost envelope. |

## 7. Explicit Rejections For Current Stage

Do not implement these now:

- a second mandatory gateway beside `:18011`;
- cloud-first Runtime SaaS;
- raw prompt / full tool output / full provider response retention by default;
- broad stream corpus capture;
- ClickHouse, TimescaleDB, or other heavy telemetry warehouse;
- AI provider fraud scoring;
- model authenticity probability claims;
- silent model/provider rewrites;
- hidden user behavior tracking;
- automatic cleanup/governance expansions unrelated to token saving;
- new UI/dashboard layers that do not prove token-saving value.

## 8. Success Metrics

Primary metrics:

- real input tokens saved;
- compile token delta;
- actual savings proof versus baseline;
- request share by compile status;
- top waste category by bounded sample window;
- latency of `/health`, `/metrics/summary`, and `/metrics/core_capabilities` when runtime validation is in scope.

Secondary metrics:

- source/confidence coverage for token counts;
- share of reported versus estimated usage;
- top agents/workflows by token spend;
- recommendation-to-realization ratio.

Non-metrics:

- size of telemetry corpus;
- number of dashboards;
- number of governance records;
- number of provider-specific adapters;
- provider trust score before evidence exists.

## 9. Data And Retention Rules

Default storage:

- store hashes, counts, source labels, confidence labels, block classes, latency, stream timing summaries, compact opportunities, and request ids;
- do not store raw prompt, full tool output, full provider response body, or complete stream chunks by default;
- internal logs stay capped at 7 days unless a narrower operator decision says otherwise;
- request forwarding must fail open when noncritical audit persistence fails.

Runtime samples may be retained only if they are bounded, user-visible where appropriate, deletable, exportable, and directly tied to token saving or verification.

## 10. Product Naming

Use this naming stack:

- OmniMemora: local-first AI Context Runtime product.
- Structured Compile: Phase 7 value engine.
- DoloToken: user-facing name for Token Intelligence / Runtime Audit.
- Token Intelligence Lite: internal engineering line for DoloToken.
- OmniRuntime or AI Runtime Infrastructure: future product-family candidate, not current shipped product.

Avoid:

- describing OmniMemora as a model provider;
- describing `:5173` as the current GUI dependency;
- implying DoloToken is already a cloud observability SaaS;
- implying unsigned beta packages have signed silent updates.

## 11. Admission Rules For New Work

A new task is admissible only if it directly improves at least one of:

- real token saving;
- cost clarity from source-labeled token data;
- explainable optimization opportunity;
- actual savings proof;
- latency/stability of the product path;
- product shrinkage or simplification.

Stop the work if:

- it only increases observability without an optimization path;
- it requires raw retention before value is proven;
- it creates a second ingress/control plane;
- it moves truth away from user-owned provider configuration;
- it cannot report whether file count, resident background logic, retention, and fast endpoints stayed within current product rules.

## 12. Next Step

Recommended next implementation line:

```text
Finish Phase 7 structured compile distribution and savings proof,
then use DoloToken to explain and verify those same savings.
```

Do not open independent Runtime SDK, cloud telemetry backend, or provider trust scoring until this loop is proven on local controlled-beta traffic.
