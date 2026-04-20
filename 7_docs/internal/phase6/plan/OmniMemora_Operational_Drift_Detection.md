# OmniMemora Operational Drift Detection

> **Status**: Adopted ✓
> **Version**: 1.0.0
> **Date**: 2026-04-20
> **Owner**: doc-team

---

## 1. Overview

**Purpose**: Build a lightweight, operator-invoked drift check that compares four surfaces:
1. Active docs
2. Latest promotion evidence
3. Live running reality
4. Deployed revision state

**Design Principles**:
- No new service, no background monitor, no new governance system
- Standalone command, run manually before opening new mainline, before phase closeout, after promotion
- Warning-level drift → dedicated phase6 drift register
- Audit-triggering drift → reuse existing `AUDIT_SCHEME.md` as escalation path

---

## 2. Signal Families

### 2.1 Running Reality Status (`RRS-*`)

**What it checks**:
- `8765/health` → Runtime health
- `18011/health` → Adapter health
- `5173` → UI accessibility
- Adapter `launchctl` plist reality
- Adapter process reality

**Comparison**: Against current phase6 declarations

**Audit trigger condition**: Any direct contradiction with declared running reality

**Evidence level**: A (live curl/launchctl)

### 2.2 Active Docs Entry (`ADE-*`)

**What it checks**:
- Repo root README points to correct phase docs
- Active phase docs reference current phase surfaces
- No stale phase5 entry docs

**Audit trigger condition**: Simple entry drift is warning; only an audit trigger if it causes direct phase conclusion conflict

**Evidence level**: D (document inspection)

### 2.3 Promotion Backfill (`PBK-*`)

**What it checks**:
- Latest `promotion_*.log` exists
- Promotion log compared with Layer 2 and Layer 3 doc state
- Full-stack success claimed has corresponding evidence

**Audit trigger condition**:
- Missing Layer 2 backfill → warning (P2)
- Full-stack success claimed without satisfying evidence-routing conditions → audit trigger (P1)

**Evidence level**: C (log parsing), D (record cross-reference)

### 2.4 Deployed Revision Alignment (`DRA-*`)

**What it checks**:
- Repo `HEAD`
- Latest promotion log `repo_revision`
- Service-current deployed-state marker

**Classification**:
- `repo_ahead`: Repo HEAD newer than marker → warning (P2) unless docs claim running reality already promoted
- `running_unknown`: No marker, no log → P3
- `running_contradiction`: Marker contradicts log AND repo → audit trigger (P1)

**Evidence level**: C (marker/log), A (if marker exists)

---

## 3. Invocation Rules

### 3.1 When to Run

| Trigger | Purpose |
|---------|---------|
| Before opening new mainline | Verify no accumulated drift before next phase |
| Before phase closeout | Final drift check before declaring phase done |
| After any promotion | Verify promotion didn't create unexpected drift |

### 3.2 Default Mode

```bash
python3 tools/verification/operational_drift_check.py
```

- Read-only summary to stdout
- Exit `0` = no audit-triggering drift
- Exit `1` = audit-triggering drift present
- Exit `2` = checker error

### 3.3 Register Update Mode

```bash
python3 tools/verification/operational_drift_check.py --write-register
```

- Same checks as default
- Appends entries to `docs/phase6/OPERATIONAL_DRIFT_REGISTER.md`

---

## 4. Routing Rules

### 4.1 Warning Only (P2/P3)

→ Append to `OPERATIONAL_DRIFT_REGISTER.md` only

### 4.2 Audit Trigger (P0/P1)

→ Append to drift register AND require governance/audit record under `3_governance/` using AUDIT_SCHEME terminology

### 4.3 Do Not Route To

- Adoption verification records (unless from actual promotion execution)
- GOV-RECORD (unless audit-triggering drift)

---

## 5. Deployed-State Marker

**Location**: `~/.omnimemora/service/current/.omnimemora_promotion_state.json`

**Written by**: `tools/promotion/promotion.sh` after result emission

**Fields**:
```json
{
  "timestamp": "2026-04-20T00:01:51",
  "target": "runtime+adapter+ui",
  "repo_revision": "6f7704b",
  "final_status": "running_reality_promoted",
  "primary_breakpoint": "none",
  "log_file": "tools/verification/logs/promotion_20260420_000151.log"
}
```

**`primary_breakpoint` vocabulary**:
- `none` — promotion succeeded, no breakpoint
- `build`, `file_sync`, `reload`, `health_check`, `ui_bringup`, `ui_alignment`, `prerequisite_failed` — structured failure from promotion log
- `unknown` — failure line in log has no actionable reason (e.g. `adapter:failed` with no trailing reason); requires human triage of the promotion log

**Purpose**: Current logs alone cannot reliably prove running revision alignment; this marker provides a reliable anchor.

---

## 6. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No audit-triggering drift |
| 1 | Audit-triggering drift present |
| 2 | Checker error |

---

## 7. Test Plan

### 7.1 Fixture-Based Checks

| Fixture | Signal | Expected |
|---------|--------|----------|
| Full-stack success | DRA | No drift |
| Uncontracted warning | RRS | P2 warning |
| Missing Layer 2 backfill | PBK | P2 warning |
| Stale root README phase entry | ADE | P3 warning |
| Deployed revision mismatch | DRA | P1/P2 depending on classification |

### 7.2 Local Smoke Run

```bash
python3 tools/verification/operational_drift_check.py
```

Verify:
- Read-only by default (no file modification)
- Resolves active phase6 doc surface
- Emits stable severity and audit-trigger classification

### 7.3 Real Promotion Integration

```bash
./tools/promotion/promotion.sh adapter
```

Verify:
- Deployed-state marker updates
- Checker reads new log/marker pair
- Contractized adapter plist reality warning does NOT false-trigger audit

---

## 8. Interface Specification

### 8.1 `operational_drift_check.py`

```
python3 tools/verification/operational_drift_check.py [--write-register]
```

**Arguments**:
- `--write-register`: Append/update entries in drift register

**Output**: Summary table to stdout

**Exit codes**: 0, 1, 2 as specified above

### 8.2 Drift Register Entry Fields

| Field | Description |
|-------|-------------|
| timestamp | ISO 8601 when signal was observed |
| signal_id | Family prefix + 3-digit sequence (e.g., RRS-001) |
| observation | Concrete observation fact |
| reality_layer | doc reality / repo reality / candidate reality / running reality |
| evidence_level | A / B / C / D |
| severity | P0 / P1 / P2 / P3 |
| audit_trigger | true / false |
| source_pointers | Files, URLs, commands |
| recommended_next_action | Concrete next step |
| status | open / in_progress / resolved / deferred |

---

## 9. Relationships to Existing Artifacts

| Artifact | Relationship |
|----------|--------------|
| `AUDIT_SCHEME.md` | Escalation authority for P0/P1 drift |
| `promotion.sh` | Writes deployed-state marker after promotion |
| `PROMOTION_USAGE_GOVERNANCE.md` | Drift check is complementary to promotion governance |
| `OPERATIONAL_DRIFT_REGISTER.md` | Primary sink for drift entries |
| Phase6 plan README | This document registered as next sub-workstream |

---

## 10. Adoption Criteria

- [x] `operational_drift_check.py` is executable and passes smoke test
- [x] Drift register template created
- [x] `promotion.sh` updated to write deployed-state marker
- [x] This plan document merged
- [x] Phase6 plan README updated to reference this workstream
- [x] One real promotion integration validation completed

### Closeout Record

**Adoption Gate Passed:** 2026-04-20 12:22:14
**Real Integration Run:** `./tools/promotion/promotion.sh adapter` (RIR-1)
**Repo Revision:** 843eea5
**Marker:** `~/.omnimemora/service/current/.omnimemora_promotion_state.json` written and verified
**Drift Check Post-Promotion:** 0 signals, exit 0, ADE-001 resolved
**Plist warning:** contractized non-blocking (per adoption contract)
