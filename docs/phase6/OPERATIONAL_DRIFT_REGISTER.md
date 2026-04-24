# Operational Drift Register

> **Status**: Active
> **Purpose**: Normal sink for warning/P2-P3 drift, audit-triggering drift
> **Escalation**: Audit-triggering drift requires governance/audit record under `3_governance/` using AUDIT_SCHEME terminology

---

## Entry Format

Each entry records:
- `timestamp`: ISO 8601 timestamp of observation
- `signal_id`: Unique identifier (e.g., RRS-001, ADE-001, PBK-001, DRA-001)
- `observation`: Concrete observation fact
- `reality_layer`: doc reality / repo reality / running reality
- `evidence_level`: A (live test) / B (candidate) / C (code/doc) / D (record)
- `severity`: P0 / P1 / P2 / P3
- `audit_trigger`: true / false
- `source_pointers`: Files, URLs, or commands providing evidence
- `recommended_next_action`: Concrete next step
- `status`: open / in_progress / resolved / deferred

---

## Signal Family Reference

| Family | Prefix | Description |
|--------|--------|-------------|
| Running Reality Status | RRS | Health checks, process/launchd reality vs phase6 declarations |
| Active Docs Entry | ADE | Root README, phase docs pointing to correct current surfaces |
| Promotion Backfill | PBK | Promotion log vs Layer 2/3 doc state alignment |
| Deployed Revision Alignment | DRA | Repo HEAD vs promotion log vs deployed-state marker |

---

## Severity Matrix

| Severity | Definition | Audit Trigger? |
|----------|------------|----------------|
| P0 | Directly contradicts current phase completion conclusion | Yes |
| P1 | Blocks next phase but doesn't contradict current conclusion | Yes |
| P2 | Doc/contract/presentation drift, needs cleanup | No |
| P3 | Minor optimization, not blocking | No |

---

## Routing Rules

- **Warning only (P2/P3)**: Append to this register only
- **Audit trigger (P0/P1)**: Append to this register AND require governance/audit record under `3_governance/`
- **Do NOT route** to adoption verification records unless from actual promotion execution

---

## Recent Entries

| Timestamp | Signal ID | Observation | Reality Layer | Evidence | Severity | Audit Trigger | Status |
|-----------|-----------|-------------|---------------|----------|----------|---------------|--------|

<!-- New entries appended by operational_drift_check.py -->
| 2026-04-20T11:15:06.713226 | ADE-001 | Root README 'Start here' section points to phase5  | doc reality | D | P3 | False | resolved |
| 2026-04-24T00:00:00.000000 | CSP-001-LOCAL-IMPORT-CLOSE | CSP-001 candidate pack local import: 4 files, 28 policy tests, full suite green, gofmt clean. commit `cb4d737`. Cloud download path marked deferred. | repo reality | A | P0 | False | resolved |
