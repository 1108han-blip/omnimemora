# OmniMemora RES-008 Legacy Meter Cleanup Readiness Report and Gate Design (2026-04-25)

## Fixed Conclusion

`legacy meter cleanup readiness designed; cleanup execution not started`

## Scope

Design-only artifact for future cleanup readiness review.

No API, no executor, no data mutation in this batch.

## Proposed Readiness Report Schema

Report contract (future):

- `schema_version=res-legacy-meter-cleanup-readiness-v1`
- `mode=readiness_design_only`
- `legacy_files`
- `sqlite_parity`
- `read_path_flags`
- `backup_requirements`
- `approval_requirements`
- `cleanup_allowed=false`

Suggested shape:

```json
{
  "schema_version": "res-legacy-meter-cleanup-readiness-v1",
  "mode": "readiness_design_only",
  "generated_at": "2026-04-25T00:00:00Z",
  "legacy_files": [
    {
      "path": "/Users/sc/.omnimemora/adapter/meters_index.json",
      "bytes": 0,
      "record_count": 0,
      "last_accessed_at": null,
      "fallback_dependency": true
    }
  ],
  "sqlite_parity": {
    "status": "passed",
    "critical_mismatch_count": 0
  },
  "read_path_flags": {
    "request_meter_switch_enabled": true,
    "request_evidence_switch_enabled": true,
    "metrics_switch_enabled": true,
    "status_read_model_switch_enabled": true,
    "legacy_fallback_enabled": true,
    "cleanup_eligibility": "readiness_only"
  },
  "backup_requirements": {
    "backup_export_required": true,
    "checksum_manifest_required": true
  },
  "approval_requirements": {
    "operator_approval_required": true,
    "change_scope_explicit_required": true
  },
  "cleanup_allowed": false
}
```

## Proposed Gate Contract

Future cleanup proposal must require:

1. parity passed and `critical_mismatch_count=0`
2. all target read paths remain sqlite-first
3. explicit operator approval required
4. backup/export required before destructive action
5. cleanup gate record must keep `cleanup_allowed=false` until approvals and backups are complete

## Frozen Safety Boundary

- delete/move/compress/truncate execution forbidden
- fallback removal not required in this line
- no cleanup execution in RES-008
