# OmniMemora Data Lifecycle Plane Mainline Launch (2026-04-25)

## 1. Mainline Position

Data Lifecycle Plane (DLP) is launched as a **formal product architecture correction mainline**.

This line is explicitly:

- not a CSP follow-up enhancement
- not a 5173 UI optimization extension

## 2. Product Boundary Correction

- OmniMemora does not manage client-side memories of Claude Code / OpenClaw / Codex / plugin / skill.
- DLP governance target is OmniMemora internal telemetry/evidence assets:
  - telemetry
  - evidence
  - meter
  - trace
  - summary
  - maintenance state
- Phase-1 DLP does not delete product core memory content.
- `5173` only displays maintenance status and exposes manual maintenance trigger.
- `18011` remains the product data ingress and request protocol semantics must stay unchanged.

## 3. Architecture Rules

1. Extract, Don’t Accrete
2. Hot Path Reads Summary
3. Raw Evidence Stays Traceable
4. Local Autonomous Maintenance
5. No Client Memory Control

## 4. Batch 0 Deliverables (Docs-Only)

- Product definition correction:
  - `0_blueprint/PRODUCT_DEFINITION.md`
- Architecture decision:
  - `docs/adr/DECISION-DLP-001.md`
- Engineering spec:
  - `docs/spec/SPEC-DATA-LIFECYCLE-PLANE-001.md`
- Active plan/index update:
  - `7_docs/internal/phase6/plan/README.md`
  - `7_docs/internal/phase6/plan/OmniMemora_Controlled_Beta_Next_Step_Engineering_Plan_2026-04-23.md`

## 5. Next Implementation Entry

After Batch 0 docs closeout:

- build minimal skeleton for `summary_store` and `maintenance_manager`
- then extract responsibilities from:
  - `status_read_model.py`
  - `meter_store.py`

