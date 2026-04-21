---
doc_id: ADOPTION-VERIFICATION-RECORDS-004
title: OmniMemora Promotion Adoption Verification Records
owner: doc-team
status: completed
version: 1.1.0
verification_date: 2026-04-22
repo_revision: e792674
---

# OmniMemora Promotion Adoption Verification Records

**驗證日期:** 2026-04-22
**Repo Revision:** 1802314
**驗證結果:** PASSED

---

## Batch A: Memory Value Loop v1 - Contract Repair

### A-1: `upstream_forward` contract repair

**Target File:** `5_connectors/adapter/diagnostics_surface.py`
**Execution Scope:** single-file contract repair
**Repo Revision:** 1802314

**Change Made:**
- `upstream_forward` node no longer reads `remote_used_count`
- node is now explicitly:
  - `status = "not_used"`
  - `duration_ms = 0`
  - `note = "local-first v1: no upstream forwarding"`
- removed the redundant `remote_used` local variable read

**Rationale:**
- current local-first v1 does not have a real upstream-forwarding path
- `remote_used_count` should not be interpreted as live upstream forwarding evidence
- evidence layer must state this explicitly instead of implying a zero-count remote path

---

## Verification

### V-1: Contract verification

**Expected:**
- `upstream_forward` no longer derives from `remote_used_count`
- evidence layer reports local-first v1 honestly

**Result:** PASSED

**Evidence:**
```python
{
    "id": "upstream_forward",
    "label": "Upstream Forward",
    "status": "not_used",
    "duration_ms": 0,
    "note": "local-first v1: no upstream forwarding",
}
```

### V-2: Validation summary

**Result:** PASSED

**Evidence:**
- `42 tests pass`
- `python3 tools/verification/operational_drift_check.py` -> `0 signals`

### V-3: Promotion log alignment

**Related Log:** `tools/verification/logs/promotion_20260422_002956.log`

**Observed promotion result:**
- adapter promotion: passed
- ui promotion: passed

**Note:**
- this record does not reopen the overview/UI patch as an active implementation line
- it preserves the fact that the 2026-04-22 promotion log contains `ui:promoted`, so phase6 Layer 2 backfill remains aligned with drift governance

---

## Batch B: Memory Value Loop v1 — Integration Validation

### B-1: Memory Loop End-to-End Validation

**Script:** `tools/verification/test_memory_loop.py`
**Repo Revision:** 1802314

**Test Flow:**
1. Seed 4 memories directly to runtime backend via `POST /memory/write`
2. Query via `execute_runtime_compile()` with keyword-matched candidates
3. Verify `selected_count > 0` in compile result
4. Verify `packed_memory_count > 0` in generated meter

**Result:** PASSED

**Evidence:**
```
Step 3: candidates returned: 8
  [0.90] SQLAlchemy: use AsyncSession with asyncpg...
  [0.90] Pydantic v2: use model_validator...
  [0.90] FastAPI: use Depends() for dependency injection...
  [0.90] Python async/await: use asyncio.gather...

Step 4: execute_runtime_compile
  selected_count: 4
  compression_ratio: 0.000

Step 5: meter
  packed_memory_count: 4
  local_cards_used: 4
  savings_ratio: 0.626
```

### B-2: Adapter HTTP Endpoint Validation

**Endpoint:** `POST /memory/query`
**Request:** `{"query": "how to use Python async in FastAPI", "tenant": "test-tenant", "user": "test-user"}`
**Agent scope:** `openclaw-agent`

**Result:** PASSED

**Evidence from `/debug/request_evidence`:**
```json
{
  "request_class": "value_qualified",
  "value_path": ["packed_memory", "local_cards"],
  "packed_memory_count": 4,
  "local_cards_used": 4,
  "request_status": "success",
  "value_qualified": true,
  "context": {
    "before_tokens": 242,
    "after_tokens": 94,
    "saved_tokens": 148,
    "savings_ratio": 0.612,
    "selected_memory_count": 4
  }
}
```

**Interpretation:**
- The complete memory loop is functional: seed → recall → optimize → meter
- `value_qualified` classification is correctly triggered when `packed_memory_count > 0`
- `request_status: "success"` only when both `value_qualified` and `savings_ratio > 0.5`
- Remote forwarding remains `not_used` in local-first v1 (as expected)

---

## Batch C: Memory Value Loop v1 — Controlled Validation Hardening

### C-1: Canonical Validation Script

**Script:** `tools/verification/test_memory_loop.py`
**Repo Revision:** e792674

**Change Made:**
- Formalized `test_memory_loop.py` as the canonical controlled-validation asset
- Split into two explicit layers:
  - **Layer 1 — Compile layer**: `execute_runtime_compile()` + `generate_meter_artifact()`
  - **Layer 2 — HTTP layer**: `POST /memory/query` + `GET /debug/request_evidence`
- Fixed seeds: tenant/user/agent ids, seeded memory set, query set, expected outcomes
- Added structured pass/fail exit codes:
  - `0` — all validations passed
  - `1` — seed/candidate failure
  - `2` — compile layer failure
  - `3` — meter layer failure
  - `4` — HTTP layer failure
  - `5` — evidence validation failure
- Compact human-readable summary with all key metrics

**Expected outcomes (fixed contract):**
- `selected_count >= 1`
- `packed_memory_count >= 1`
- `request_class = value_qualified`
- `value_path` contains `packed_memory` and `local_cards`
- `request_status = success` only when `value_qualified = true`
- `upstream_forward status = not_used`, note = `local-first v1: no upstream forwarding`

**Result:** PASSED

**Evidence (Layer 1 — compile layer):**
```
seeded_count:       4
candidate_count:    10
selected_count:     4
packed_memory_count:4
local_cards_used:   4
savings_ratio:       0.613
compile_error:      None
```

**Evidence (Layer 2 — HTTP layer):**
```
query_request_id:   req-56645d15
request_class:      value_qualified
value_path:         ['packed_memory', 'local_cards']
value_qualified:    True
request_status:     success
upstream_status:    not_used
upstream_note:     'local-first v1: no upstream forwarding'
```

---

## Batch D: Memory Value Loop v1 — Evidence-Layer Record Alignment

### D-1: 20260422 becomes authoritative Layer 2 record

**Status:** PASSED

This record (`20260422`) now serves as the authoritative Layer 2 record for
**Memory Value Loop v1 — Controlled Validation Hardening**, capturing:
- Contract repair of `upstream_forward` (Batch A, already complete)
- Integration validation of the memory loop (Batch B, already complete)
- Formalized controlled-validation flow (Batch C, this session)
- Stable two-layer acceptance surface for future regression

### D-2: 20260421 preserved as historical promotion backfill

**Status:** Preserved as-is

`20260421` remains as the Layer 2 backfill for the 2026-04-21 adapter+ui
promotion. It does not reopen the overview/UI path as an active implementation line.

---

## Summary

### Conclusions

**Memory Value Loop v1 — PASSED**

1. `upstream_forward` is no longer falsely implied by `remote_used_count`.
2. The evidence layer now reflects the current local-first v1 product truth directly.
3. The complete memory loop (seed → recall → optimize → meter) is validated functional.
4. `value_qualified` classification correctly triggers when `packed_memory_count > 0`.
5. This batch establishes the baseline for future memory loop enhancements.
