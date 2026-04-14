# Agent-First Project Framework (Hourly Edition)

Version: 2.0.0  
Status: active  
Effective Date: 2026-04-14  
Owner: project-operator

---

## 1. Purpose

This framework is designed for projects where AI agents complete most engineering work (target: 95%+ autonomous execution).  
The operating model is:

- Human sets direction, constraints, and risk boundaries.
- Agent executes implementation, testing, and documentation updates.
- CI gates enforce consistency, auditability, and release safety.

---

## 2. Core Principles

1. Machine-enforceable over narrative-only.
2. Small batches over large releases.
3. Logic priority over recency during conflict resolution.
4. No evidence, no acceptance.
5. No rollback plan, no production release.

---

## 3. Governance Stack (Top-Down Priority)

Conflict resolution order (high to low):

1. `docs/agent/AGENT_CONTRACT.yaml`
2. `AGENTS.md`
3. Active ADRs (`1_architecture/adr/`)
4. Active Canonical Specs (`1_architecture/spec/`)
5. Runbooks and other docs

If same-layer conflicts exist:

1. `supersedes` relationship
2. `status` (`active` > `draft` > `deprecated`)
3. `effective_date`
4. verifiability (code/CI-checkable wins)

---

## 4. Standard Repository Structure

```text
project/
├─ 0_governance/
│  ├─ PROJECT_CONSTITUTION.md
│  ├─ DECISION_RIGHTS.md
│  └─ RISK_CHARTER.md
├─ 1_architecture/
│  ├─ adr/
│  │  ├─ ADR-TEMPLATE.md
│  │  └─ ADR-xxxx-*.md
│  └─ spec/
│     ├─ SPEC-TEMPLATE.md
│     └─ SPEC-xxxx-*.md
├─ 2_delivery/
│  ├─ roadmap/
│  ├─ milestones/
│  └─ release_notes/
├─ 3_quality/
│  ├─ gate_definitions/
│  ├─ test_strategy/
│  └─ checklists/
├─ 4_operations/
│  ├─ runbooks/
│  ├─ incident/
│  └─ slo/
├─ 5_audit/
│  ├─ evidence/
│  ├─ compliance/
│  └─ postmortems/
├─ docs/
│  ├─ agent/
│  │  ├─ AGENT_CONTRACT.yaml
│  │  ├─ TASK_BRIEF_TEMPLATE.md
│  │  └─ DECISION_LOG_TEMPLATE.md
│  └─ standards/
│     └─ doc-schema.md
├─ tools/
│  ├─ verification/
│  └─ docs/
│     └─ consistency-check.ps1
└─ .github/workflows/
   ├─ ci.yml
   ├─ docs-governance.yml
   └─ release-gate.yml
```

---

## 5. Hourly Operating Model (Execution Windows)

Use fixed windows instead of week-based sprints.

### Window Types

1. `W1-Align (1h)`
- Clarify task scope and non-negotiable constraints.
- Generate Agent Constraint Summary (3-8 bullets).

2. `W2-Build (2h)`
- Agent implements 1-3 bounded tasks.
- Must update related Spec/ADR if behavior changes.

3. `W3-Verify (1h)`
- Run tests, linters, governance checks.
- Collect evidence package.

4. `W4-Ship (1h, optional)`
- Release if all gates pass.
- If gate fails, open next `W1-Align`.

Standard cycle: `1h + 2h + 1h (+1h)` = `4-5h`.

---

## 6. Mandatory Artifacts per Window

Each execution window must produce:

1. Task brief (goal/scope/constraints/output).
2. Decision log (chosen rule IDs + rejected options).
3. Change set ID (`CHG-YYYYMMDD-###`).
4. Evidence bundle:
- test results
- gate results
- risk notes
- rollback notes

No artifact -> window incomplete.

---

## 7. Agent Contract Requirements

`docs/agent/AGENT_CONTRACT.yaml` must include:

1. Path boundaries (allowed/disallowed paths).
2. Forbidden actions (destructive operations, raw data edits).
3. Architecture invariants (must not break interface contracts).
4. Quality gates (coverage, lint, tests, security checks).
5. Documentation linkage rules (code change requires spec/adr update).
6. Release guards (rollback plan + monitoring required).

All rules should be script-checkable whenever possible.

---

## 8. Doc Governance Rules

1. Every governance doc uses YAML front matter:
- `doc_id`
- `title`
- `owner`
- `status`
- `version` (semver)
- `effective_date`
- `depends_on`
- `supersedes`
- `last_verified_commit`

2. Exactly one canonical spec per technical domain.
3. Deprecated docs must include replacement doc ID.
4. Doc/code change linkage is mandatory in PR.

---

## 9. CI Gates (Block Merge)

Minimum blocking rules:

1. `doc_id` uniqueness.
2. Front matter completeness.
3. `depends_on` references exist.
4. deprecated docs include `superseded_by`/replacement.
5. Core code changes without linked Spec/ADR update are blocked.
6. Test and lint baseline must pass.

Rollout strategy:

- Week 1 equivalent (first 20 windows): warn mode.
- After baseline stabilizes: hard block mode.

---

## 10. Release Gating Standard

Release allowed only when:

1. All CI gates pass.
2. SLO risk accepted.
3. Rollback procedure verified.
4. Monitoring and alert thresholds configured.
5. Evidence package archived in `5_audit/evidence/`.

---

## 11. Metrics (Hourly and Daily Views)

### Throughput

1. Windows completed per day.
2. Tasks completed per window.
3. Median cycle time per task.

### Quality

1. First-pass success rate.
2. Rework rate.
3. Defects per 1k changed lines.
4. Human takeover rate.

### Consistency

1. Doc-code alignment rate.
2. Stale document age.
3. Orphan doc rate.
4. Contradiction MTTR.

---

## 12. RACI (Lean Team)

1. Product Owner
- Owns objectives and priorities.

2. Architect
- Owns ADR approval and invariants.

3. Agent Operator
- Owns task shaping, run sequencing, escalation.

4. QA/SRE/Security
- Owns gate definition, risk acceptance, release readiness.

---

## 13. Escalation Policy

Escalate to human decision immediately when:

1. P0/P1 risk detected.
2. Agent fails same path twice.
3. Contract conflict cannot be auto-resolved.
4. Architecture boundary change is requested.

Escalation record must include:

1. what failed
2. attempted options
3. recommended action
4. impact if delayed

---

## 14. New Project Bootstrap (First 8 Hours)

### H0-H1

1. Create repo structure.
2. Add constitution and risk charter.
3. Add `AGENT_CONTRACT.yaml`.

### H1-H3

1. Add ADR/SPEC templates.
2. Add doc schema.
3. Add PR template with change-set linkage fields.

### H3-H5

1. Add `docs-governance.yml`.
2. Add `consistency-check.ps1`.
3. Enable lint + unit test baseline.

### H5-H8

1. Run first full window (`W1->W3`).
2. Fix all gate failures.
3. Create first evidence bundle.
4. Tag `v0.1.0-foundation`.

---

## 15. Definition of Done (DoD)

A task is complete only if:

1. behavior is implemented and tested.
2. docs are synchronized (Spec/ADR when required).
3. CI gates pass.
4. decision log is written.
5. rollback path exists for production-impacting changes.

---

## 16. Copy-Paste Task Brief Template

```text
[Goal]

[Current State]

[Scope]

[Constraints]

[Expected Output]

[Change Set ID]
CHG-YYYYMMDD-###
```

---

## 17. Copy-Paste Decision Log Template

```text
Decision Log ID: DLOG-YYYYMMDD-###
Change Set ID: CHG-YYYYMMDD-###

Applied Rules:
- RULE-...

Rejected Options:
- Option A: reason
- Option B: reason

Risk Notes:
- ...

Validation Evidence:
- test: ...
- gate: ...

Operator Sign-off:
- name/date
```

