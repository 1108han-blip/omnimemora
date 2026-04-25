# OmniMemora RES-001 to RES-006 Storage Governance Baseline Closeout (2026-04-25)

## Fixed Conclusion

`RES-001 to RES-006 storage governance baseline closed; sqlite-first read paths passed; legacy cleanup not started`

## Scope

This closeout consolidates RES-001..RES-006 only:

- RES-001 raw evidence segmentation (observe-only)
- RES-002 meter storage v2 mirror and parity governance
- RES-003 request meter read path
- RES-004 request_evidence read path
- RES-005 metrics residual read path
- RES-006 status read model read path

## Repository Reality

Baseline chain is closed in repo with dedicated ADR/SPEC + implementation + tests across RES-001..RES-006.

For RES-007 freeze hardening, this closeout adds:

1. meter-storage status projection alignment
   - `meter_storage_v2.read_path.request_evidence_switch_enabled` now reflects resolver mode
   - `meter_storage_v2.read_path.request_evidence_read_mode` added
   - `meter_storage_v2.read_path.cleanup_eligibility=readiness_only` added as freeze marker
2. safety invariant tests
   - `test_res_storage_governance_invariants.py` added
   - `test_meter_storage_parity.py` updated for full read-path flags visibility
3. no production behavior switch beyond read-only status projection
   - no meter cleanup/delete/move/compress/truncate execution path introduced

## Running Reality

Date:

- 2026-04-25

Audit and promotion:

- pre-check: `git status --short` clean
- running revision mismatch observed before freeze check (`running=f829bcd`, `HEAD=79c3a73`)
- promotion executed once: `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- restart truth: `changed`
- running revision aligned: `79c3a73`
- log: `tools/verification/logs/promotion_20260425_213416.log`

Read-path and parity assertions:

- `GET /data-lifecycle/status` -> `200`
  - `request_meter_switch_enabled=true`
  - `request_evidence_switch_enabled=true`
  - `metrics_switch_enabled=true`
  - `status_read_model_switch_enabled=true`
  - `legacy_fallback_enabled=true`
  - all four read modes = `sqlite_first_legacy_fallback`
  - `cleanup_eligibility=readiness_only`
- `GET /data-lifecycle/meter-storage/parity` -> `200`
  - `status=passed`
  - `critical_mismatch_count=0`
- endpoint smoke:
  - `GET /agents/control` -> `200`
  - `GET /metrics/summary` -> `200`
  - `GET /debug/request_evidence?request_id=req-9d93e44e` -> `200`
  - `GET /requests/req-9d93e44e/meter` -> `200`

## Readiness Matrix

| Path | SQLite-first | Legacy fallback | Running validation request id | Parity status | Cleanup eligibility |
|------|--------------|-----------------|-------------------------------|---------------|--------------------|
| RES-001 raw evidence segmentation (observe-only) | not_applicable | not_applicable | n/a | n/a | not_started |
| RES-002 meter storage v2 mirror/parity | readiness_only (mirror/parity baseline) | legacy_authoritative=true | `680b9dfba27f` | `critical_mismatch_count=0` | readiness_only |
| RES-003 `/requests/{id}/meter` | passed | passed | `req-8fbc2991` | `critical_mismatch_count=0` | readiness_only |
| RES-004 `/debug/request_evidence` | passed | passed | `req-35c5c90f` | `critical_mismatch_count=0` | readiness_only |
| RES-005 metrics residual reads | passed | passed | `req-bba632de` | `critical_mismatch_count=0` | readiness_only |
| RES-006 status read model meter reads | passed | passed | `req-9d93e44e` | `critical_mismatch_count=0` | readiness_only |

## Doc Reality

- Phase6 index updated with RES total closeout line.
- Next line freeze added in README:
  - `RES-008 Legacy Meter Cleanup Readiness Design` is design-only.
  - delete/move/compress/truncate execution remains out of scope.

## Not Done (Frozen)

- no legacy meter cleanup
- no legacy raw evidence cleanup
- no archive-at-scale execution
- no production fallback removal
- no Codex live validation
- no user-client memory governance
