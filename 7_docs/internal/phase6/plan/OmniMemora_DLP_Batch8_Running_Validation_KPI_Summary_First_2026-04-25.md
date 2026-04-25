# OmniMemora DLP Batch 8 Running Validation - KPI Summary-First (2026-04-25)

## 1. Scope

Running validation for Batch 7 summary-first KPI path.

Validation target:

- `/metrics/summary`
- `/metrics/summary_24h`
- `/metrics/core_capabilities`
- `/agents/control`

---

## 2. Promotion

Executed:

```bash
./tools/promotion/promotion.sh adapter+ui
```

Observed:

- result: `running_reality_promoted`
- log: `tools/verification/logs/promotion_20260425_104114.log`
- adapter restart truth: `changed`
- validation run happened on Stage 2 integrated candidate (`Batch 7 + Batch 9`), not an isolated Batch 7-only revision

---

## 3. Live checks (`18011`)

### 3.1 Summary freshness baseline

Manual warm-up:

- `POST /data-lifecycle/maintenance/refresh` -> `status=success`, `trigger=manual_refresh`

Health:

- `GET /data-lifecycle/status`
  - `schema_version=dlp-lifecycle-health-v1`
  - `summary.freshness=fresh`

### 3.2 Schema stability

Observed top-level keys:

- `/metrics/summary`: `token_saving_ratio / tokens_saved / request_count / avg_context_reduction`
- `/metrics/summary_24h`: previous fields + `period`
- `/metrics/core_capabilities`: `period / observed_request_count / non_value_count / cards`
- `/agents/control`: `agents / count / system_status`

No schema regression observed.

---

## 4. Sampling (80 per endpoint)

`metrics_read_degraded` ledger count:

- before sampling: `1`
- after sampling: `1`
- increment: `0` (fresh summary window)

Latency and error:

- `/metrics/summary`:
  - errors `0/80`
  - p50 `3.64ms`
  - p95 `7.39ms`
  - max `8.32ms`
- `/metrics/summary_24h`:
  - errors `0/80`
  - p50 `3.98ms`
  - p95 `6.73ms`
  - max `7.95ms`
- `/metrics/core_capabilities`:
  - errors `0/80`
  - p50 `4.41ms`
  - p95 `6.44ms`
  - max `7.34ms`
- `/agents/control`:
  - errors `0/80`
  - p50 `4.44ms`
  - p95 `6.71ms`
  - max `332.82ms`

---

## 5. Conclusion

- Batch 7 summary-first KPI hot-read path is running-stable.
- Metrics degraded ledger did not increase during fresh-summary sampling.
- Endpoint schemas remained stable.
