# OmniMemora RES-006 Status Read Model Meter Read-Path Running Validation Closeout (2026-04-25)

## Fixed Conclusion

`status read model meter reads switched to sqlite-first with legacy fallback; /agents/control schema and truth semantics unchanged`

## Scope

RES-006 switch only:

- switched:
  - `status_read_model._collect_observed_family_meters`
  - `status_read_model.compute_family_24h_metrics`
- not switched:
  - `/agents/control` schema
  - `derive_traffic_truth` priority semantics
  - request meter path
  - request_evidence path
  - metrics residual path
  - UI

## Repo Reality

Implemented:

1. `application/status_read_model_meter_read_resolver.py`
   - mode: `legacy_only | sqlite_first_legacy_fallback`
   - default: `sqlite_first_legacy_fallback`
   - sqlite-first + legacy fallback
   - resolver metadata: `mode/source/degraded/degraded_reason`
2. `application/status_read_model.py`
   - `_collect_observed_family_meters` now resolver-backed, then original filtering/collapse semantics retained
   - `compute_family_24h_metrics` now resolver-backed, then original value-qualified semantics retained
   - `derive_traffic_truth` unchanged
   - family alias behavior unchanged (`cc-haha -> claude_code`)
3. `data_lifecycle/meter_storage_v2.py` + `data_lifecycle/health.py`
   - read_path status includes:
     - `status_read_model_switch_enabled=true`
     - `status_read_model_read_mode=sqlite_first_legacy_fallback`
     - `legacy_fallback_enabled=true`
4. tests:
   - new status read-model resolver tests
   - status read model regression tests
   - agent control schema regression tests
   - meter parity/status regression tests

## Running Reality

Date:

- 2026-04-25

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- adapter restart truth: `changed`
- log: `tools/verification/logs/promotion_20260425_212247.log`

Validation evidence:

1. Non-Codex request generated via `/memory/query` (`agent=openclaw`)
   - validation request: `request_id=req-9d93e44e`
2. `/agents/control` validation:
   - HTTP `200`
   - top-level keys remain: `agents`, `count`, `system_status`
   - OpenClaw family `traffic_truth=real_request_observed`
   - observed `last_request_at` populated from meter evidence
   - no independent `cc-haha` family card (`HAS_CC_HAHA=False`)
3. `/data-lifecycle/status` read_path flags:
   - `status_read_model_switch_enabled=true`
   - `status_read_model_read_mode=sqlite_first_legacy_fallback`
   - `legacy_fallback_enabled=true`
4. Fallback simulation (SQLite row removed for validation request only; legacy JSON untouched):
   - `/agents/control` still HTTP `200`
   - observed traffic truth remains stable and does not crash on sqlite miss
   - `cc-haha` still not an independent family card
5. Parity restore:
   - `POST /data-lifecycle/meter-storage/parity/rebuild` -> `critical_mismatch_count=0`
   - `GET /data-lifecycle/meter-storage/parity` -> `critical_mismatch_count=0`

## Boundary Confirmation

- `/agents/control` schema unchanged
- control truth semantics unchanged (`derive_traffic_truth` priority preserved)
- family alias contract unchanged (`cc-haha` remains Claude family variant)
- request meter path unchanged
- request_evidence path unchanged
- metrics residual path unchanged
- legacy meter JSON retained
- no legacy meter delete/move/compress/truncate path introduced
