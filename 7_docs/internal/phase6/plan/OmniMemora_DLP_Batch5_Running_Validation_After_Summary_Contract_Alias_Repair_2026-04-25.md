# OmniMemora DLP Batch 5 Running Validation - After Summary Contract and Alias Repair (2026-04-25)

## 1. Scope

Validate running reality after:

- `07c398f` (summary contract hardening + legacy read-path thinning)
- `6a7e7ba` (family alias contract repair: `cc-haha -> claude_code`)

Boundary:

- no code changes
- promotion + running validation + docs closeout only
- no destructive maintenance
- no Codex validation gate

---

## 2. Repo Sanity

Executed:

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_plane.py
python3 -m pytest -q 5_connectors/adapter/__tests__/test_status_read_model.py
python3 -m pytest -q 5_connectors/adapter/tests/test_agent_control_api.py
```

Results:

- `15 passed`
- `21 passed`
- `7 passed`

---

## 3. Promotion and Restart Truth

Command:

```bash
./tools/promotion/promotion.sh adapter+ui
```

Evidence:

- log: `tools/verification/logs/promotion_20260425_011102.log`
- running revision: `6a7e7ba`
- adapter restart truth: `changed`
  - pre: `pid=37937`, `started_at=2026-04-24T16:51:15.860417Z`
  - post: `pid=46481`, `started_at=2026-04-24T17:11:04.832640Z`

---

## 4. DLP Summary Contract Validation (Running Artifact)

Artifact:

- `~/.omnimemora/adapter/data_lifecycle/family_window_summary.json`

Observed top keys:

- `builder_version`
- `families`
- `generated_at`
- `schema_version`
- `source_counts`

Required contract fields check:

- `schema_version / generated_at / source_counts / builder_version / families`: **PASS**
- `schema_version = dlp-family-window-summary-v1`
- `builder_version = dlp-summary-builder-v2`

Family semantic checks:

- standalone `cc-haha` family: **not present**
- standalone `cc_haha` family: **not present**
- `claude_code` family: **present**

---

## 5. DLP Ledger Validation

Artifact:

- `~/.omnimemora/adapter/data_lifecycle/maintenance_state.jsonl`

Observed:

- `startup_warm` present, latest status `success`
- `interval_refresh` present, latest status `success`
- historical `read_model_degraded` records exist in ledger (total `3`)

Fresh-path stability check during this batch:

- `read_model_degraded` count before 120-sample: `3`
- `read_model_degraded` count after 120-sample: `3`
- increment during sampling: `0`

Conclusion:

- normal fresh summary reads in this validation window did not introduce new degraded fallback records.

---

## 6. `/agents/control` Schema and Family Projection

Endpoint:

- `GET http://127.0.0.1:18011/agents/control`

Observed top-level keys:

- `agents`
- `count`
- `system_status`

Observed families:

- `claude_code`
- `codex_cli`
- `openclaw`

Checks:

- no standalone `cc-haha`/`cc_haha` control card: **PASS**
- schema stayed in established structure (no new UI semantic fields): **PASS**

---

## 7. 120x Sampling (`/agents/control`, timeout=4s)

Method:

- 120 requests, timeout 4s
- sample adapter `%CPU`/`RSS` via `ps -p <pid> -o %cpu=,rss=`
- track if `cc-haha` card appears
- track `read_model_degraded` ledger increment

Results:

- sample size: `120`
- timeout ratio: `0.00%` (`0/120`)
- error ratio: `0.00%` (`0/120`)
- latency:
  - `p50 = 8.70 ms`
  - `p95 = 16.11 ms`
  - `max = 2602.98 ms`
  - `mean = 39.84 ms`
- adapter CPU:
  - `mean = 7.04%`
  - `p95 = 34.02%`
  - `max = 95.60%`
- adapter RSS:
  - `mean = 476707.60 KB`
  - `p95 = 477296.00 KB`
  - `max = 501616 KB`
- `cc-haha` card seen during sampling: `false`
- `read_model_degraded` new records during sampling: `0`

---

## 8. Acceptance

- `cc-haha` not an independent family in running summary/control projection: **PASS**
- summary contract fields complete in running artifact: **PASS**
- `/agents/control` schema unchanged: **PASS**
- timeout tail remains acceptable and far from pre-stabilization failure mode: **PASS**
- docs-only closeout with no code modification: **PASS**

Batch 5 is closed.
