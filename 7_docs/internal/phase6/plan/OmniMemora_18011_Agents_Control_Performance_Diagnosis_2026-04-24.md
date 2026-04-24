# OmniMemora 18011 /agents/control Performance Diagnosis (2026-04-24)

## 1. Scope and Constraints

Diagnosis-only batch.

- Included: sampling, call graph, data-scale profile, risk ranking.
- Excluded: `meter_store.py` logic change, `status_read_model.py` logic change, response schema change, promotion.

## 2. Running Reality Sampling

### 2.1 Endpoint sampling (`curl`, timeout 4s)

Dataset: `/tmp/agents_control_perf_samples.json` (120 samples)

- total samples: `120`
- `200` success: `46` (`38.33%`)
- timeout (`curl 28`, code `0`): `74` (`61.67%`)
- successful-response latency:
  - p50: `1.0579s`
  - p95: `2.4369s`
  - max: `3.7659s`

### 2.2 Adapter process pressure during sampling

From same sampling run (`cpu_mem` summary in `/tmp/agents_control_perf_samples.json`):

- CPU max: `94.7%`
- CPU p95: `91.9%`
- CPU mean: `85.96%`
- RSS max: `1089.33 MB`
- RSS mean: `1013.44 MB`

### 2.3 Request-window check

Dataset: `/tmp/agents_control_window.txt` (30 samples)

- all returned `200`
- latency around `0.79s` to `2.59s` in this short window

Interpretation: `18011 /agents/control` shows unstable tail behavior under repeated access; timeout ratio is non-trivial with current 4s caller timeout profile.

## 3. Data-Scale Profile

### 3.1 Meter persistence (running path)

Path: `~/.omnimemora/service/current/5_connectors/data`

- `meters_index.json` entries: `4697`
- `meters_index.json` size: `21,087,895 bytes`
- tenant aggregate files: `27`
- largest files:
  - `meters_claude_code.json`: `12,406,094 bytes`, `1668` entries
  - `meters_final-24h-tenant.json`: `6,946,733 bytes`, `1596` entries
  - `meters_codex_cli.json`: `4,517,146 bytes`, `343` entries
  - `meters_openclaw.json`: `1,379,860 bytes`, `648` entries

### 3.2 Compile/proxy event stores

Path: `~/.omnimemora/adapter`

- `compile_events.jsonl`: `8,052,274 bytes`, `1868` lines
- `proxy_events.jsonl`: `9,368,648 bytes`, `4375` lines
- `trace_events.jsonl`: `4,197,886 bytes`, `15965` lines

## 4. Repo Call Graph (Read Path)

### 4.1 Entry chain

- `5_connectors/adapter/agent_control_api.py:64`
  - `GET /agents/control`
  - calls `build_control_cards()` + `build_system_status()`

### 4.2 Core aggregation chain

- `5_connectors/adapter/application/status_read_model.py:626`
  - `build_control_cards()`
- `5_connectors/adapter/application/status_read_model.py:633`
  - runtime call: `_runtime_request("GET", "/agents/control")`
- `5_connectors/adapter/application/status_read_model.py:637`
  - `compile_store.read_recent_compile_events(limit=5000, window_minutes=30)`
- `5_connectors/adapter/application/status_read_model.py:638`
  - `compile_store.read_recent_compile_events(limit=5000, window_minutes=1440)`

Per family loop:

- `status_read_model.py:644`
  - `_collect_observed_family_meters()` (meter aggregate scan path)
- `status_read_model.py:645` and `647`
  - `_summarize_family_compile_events()` (preloaded rows filtered again by family)
- `status_read_model.py:652`
  - `compute_family_24h_metrics()` (24h meter traversal path)

### 4.3 Storage-read helpers

- Meter store:
  - `5_connectors/adapter/infrastructure/meter_store.py:153` `load_persisted_state()`
  - `...:165` glob reads `meters_*.json`
  - in-memory aggregate usage referenced by status model (`_usage_aggregates`)
- Compile store:
  - `5_connectors/adapter/infrastructure/compile_store.py:78`
    `read_recent_compile_events()`
  - `...:99-120` segment read + JSON parse + sort + limit
- Proxy store:
  - `5_connectors/adapter/infrastructure/proxy_store.py:49`
    `read_recent_events()`
  - `...:55-67` reverse scan + JSON parse + cutoff filter

## 5. Root-Cause Candidates and Evidence Level

1. Candidate A: high fan-in read-model aggregation on each `/agents/control` request  
Evidence level: **High**

- Endpoint path builds cards by combining runtime call + compile summaries + meter-derived metrics in one synchronous request.
- Under repeated calls, CPU and RSS show sustained high utilization.

2. Candidate B: large in-memory/disk-backed meter/event surfaces increase per-request scanning/filtering cost  
Evidence level: **High**

- Meter/event file sizes and line counts are substantial.
- Multiple filtering passes are visible in `status_read_model.py` read path.

3. Candidate C: current timeout coupling causes visible timeout ratio at caller side (4s)  
Evidence level: **Medium**

- 120-sample run shows 61.67% timeout at 4s budget.
- Successful p95 is below 4s, implying unstable tails rather than universal hard-fail.

## 6. Risk Ranking

- P1: control API unstable tail under repeated access (`timeout_ratio` significant).
- P1: CPU pressure can degrade adjacent adapter behavior under control-surface load.
- P2: data growth may further worsen `/agents/control` latency variance.

## 7. Minimal Patch Candidates (For Next Implementation Batch Only)

No changes were made in this diagnosis batch.  
If implementation batch is opened, minimal candidates:

- Add cheap cache/snapshot layer for `/agents/control` read model with short TTL.
- Bound expensive per-request scans (family-local indexes / incremental summaries).
- Separate hot-path card rendering fields from deep diagnostics fields.
- Introduce adaptive backoff/circuit policy server-side for repeated expensive reads.

## 8. Batch Conclusion

- Diagnosis output target met: p50/p95/max, timeout ratio, CPU/memory, call graph, data-scale profile.
- This batch does **not** claim backend issue is fixed.
- Next step should be a separate backend implementation batch if accepted.

