# OmniMemora /agents/control Snapshot Cache Closeout (2026-04-24)

## 1. Scope

This is a docs-only closeout for backend minimal stabilization commit `accfcfc`.

Batch boundary:

- Target: `/agents/control` timeout-tail stabilization.
- No response schema change.
- No truth-field semantic change.
- No `meter_store.py` persistence semantic change.
- No Codex validation gate.

## 2. Repo / Promotion Trace

- Repo commit: `accfcfc`
- Commit title: `feat(adapter): add short-ttl snapshot cache for agents control`
- Promotion log: `tools/verification/logs/promotion_20260424_235103.log`
- Promotion result: `running_reality_promoted` (`adapter+ui`)

## 3. Running Sampling Comparison (120 requests, timeout=4s)

### Baseline (pre-cache diagnosis batch)

- timeout ratio: `61.67%`
- p95 latency: `2.4369s`
- CPU mean: `85.96%`
- CPU p95: `91.9%`

### After snapshot cache stabilization

- timeout ratio: `1.67%`
- p95 latency: `2.2913s`
- CPU mean: `54.88%`
- CPU p95: `92.8%`

### Delta summary

- timeout ratio: `61.67% -> 1.67%` (tail significantly reduced)
- CPU mean: `85.96% -> 54.88%` (load average reduced)
- CPU p95: `91.9% -> 92.8%` (no obvious p95 improvement)

## 4. Closeout Judgment

This batch is **not** declared full pass for backend performance line.

- Passed: `/agents/control` timeout tail stabilized.
- Residual: CPU p95 remains high and did not show clear drop.

## 5. Optional Next Backend Batch

If CPU p95 reduction is still required, open a separate implementation batch and prioritize:

1. cold-cache singleflight for `/agents/control` rebuild
2. rebuild-path split (hot path vs heavy diagnostics path)
3. incremental summaries

Keep constraints unchanged:

- no response schema change
- no truth semantic rewrite
- no meter persistence semantic rewrite

