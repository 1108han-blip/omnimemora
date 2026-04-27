# OmniMemora RES-027B Meter Parity Degraded Root-Cause Diagnosis (2026-04-27)

## Fixed Conclusion

`meter parity degraded root cause diagnosed; second-file pilot execution not started; cleanup scope expansion not started`

## Scope

RES-027B is docs-only root-cause diagnosis for the RES-027A running parity degraded state.

Included:
- read-only product-interface checks through `http://127.0.0.1:18011`
- read-only comparison of the legacy meter payload and sqlite mirror payload for one mismatch sample
- diagnosis record and README index update

Explicitly excluded:
- no rebuild or repair executed
- no code change
- no second-file source move
- no cleanup pilot execution
- no delete/compress/truncate/batch cleanup
- no production read-path switch

## Repository Reality

- current repo revision during diagnosis: `a043e21`
- worktree before RES-027B edits: clean
- RES-027A remains closed as:
  - `repeatable cleanup pilot protocol running-validated; second-file pilot execution not started; cleanup scope expansion not started`
- RES-028 is not opened by RES-027B.

## Running Reality

Validation target:
- instance class: local product adapter
- endpoint base: `http://127.0.0.1:18011`
- actions: read-only `GET` requests only

Parity snapshot:
- `GET /data-lifecycle/meter-storage/parity` -> readable
- `status=degraded`
- `legacy_count=4901`
- `sqlite_count=4901`
- `payload_hash_mismatch_count=1`
- `critical_mismatch_count=1`
- missing legacy/sqlite samples: none observed from counts
- fixed mismatch sample: `request_id=8e1ddda147d6`

Request-level reads:
- `GET /requests/8e1ddda147d6/meter` -> readable
- `GET /debug/request_evidence?request_id=8e1ddda147d6` -> readable
- request evidence meter read:
  - `mode=sqlite_first_legacy_fallback`
  - `source=sqlite`
  - `degraded=false`
- request evidence meter shadow:
  - `status=degraded`
  - `read_source=sqlite`
  - `mismatch_fields=["access_plan"]`

## Payload Difference Diagnosis

Read-only local payload comparison:
- legacy source: `/Users/sc/.omnimemora/service/current/5_connectors/data/meters_index.json`
- sqlite source: `/Users/sc/.omnimemora/adapter/meter_store_v2/meter_store.sqlite3`
- request id: `8e1ddda147d6`

Leaf-level payload differences:

| Field | Legacy | SQLite |
|-------|--------|--------|
| `timestamp` | `2026-04-27T04:21:29.084890Z` | `2026-04-27T04:21:30.460888Z` |
| `sharing_policy_source` | `compile_orchestrator_private_first` | `ingress_private_first` |
| `access_plan.sharing_policy_source` | `compile_orchestrator_private_first` | `ingress_private_first` |

Business field comparison:
- no token/count drift observed
- no tenant drift observed
- no agent/family/client drift observed
- no query text or query-size drift observed
- no savings-ratio drift observed
- no packed/local/remote memory count drift observed

Diagnosis classification:
- `semantic_hash_mismatch_candidate`
- reason: the full parity hash includes timestamp and access-plan provenance fields whose values differ across legacy/sqlite serialization paths, while core business meter fields match.
- not classified as `critical_payload_drift` by field content inspection.

Important contract note:
- the current parity contract still counts any payload hash mismatch as critical.
- therefore running parity remains `critical_mismatch_count=1` until either parity becomes clean or this mismatch is explicitly reclassified/accepted by a future contract change.

## RES-028 Gate State

RES-028 remains blocked.

Required before RES-028 can open:
- parity clean with `critical_mismatch_count=0`, or
- the `request_id=8e1ddda147d6` mismatch is explicitly explained and accepted as non-critical by a later RES-027C contract/fix line.

RES-027B does not authorize:
- second-file pilot execution
- cleanup scope expansion
- cleanup pilot/move execution
- parity rebuild or repair

## Boundary Confirmation

- second-file pilot execution not started
- cleanup scope expansion not started
- no rebuild or repair executed
- no `/data-lifecycle/meter-storage/parity/rebuild` call was made in RES-027B
- no cleanup pilot/move endpoint was called in RES-027B
