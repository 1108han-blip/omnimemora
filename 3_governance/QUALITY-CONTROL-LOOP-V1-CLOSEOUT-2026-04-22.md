# V1 Quality Control Loop — Closeout Record

**Date**: 2026-04-22
**Status**: Closed
**Batch**: V1 QC Loop Implementation — Phase 5 Enhancement Line

---

## Objective

Establish a controlled quality control loop for the OmniMemora Phase 5 baseline, focused on context layer quality verification.

---

## Repository Reality (Code & Schema)

### Policy Version Management
- Local-first versioned policy directory: `5_connectors/adapter/config/policies/`
  - `manifest.json` — tracks active_version, candidate_version, last_verified_report, last_promoted_at
  - `local-default-v1.json` — initial active policy
- `policy_version_manager.py` — manages local policy loading with path injection for testing
- `cloud/policy_loader.py` — updated to use local active policy (V1: cloud cannot override)
- Key separation: `record_verification()` updates last_verified_report; only `promote_candidate()` sets last_promoted_at

### Offline Deterministic Comparison Runner
- `tools/verification/quality_control/runner.py` — runs golden cases against active/candidate policies locally
- `tools/verification/quality_control/models.py` — GoldenCase, CaseResult, PolicyEvaluationResult, ComparisonReport
- `tools/verification/quality_control/loader.py` — loads golden cases from fixture files
- Golden case format: self-contained with candidate_memories, supports must_pass/scored gates
- Promotion gates: active must_pass all pass, candidate must_pass all pass, candidate.score >= active.score

### Diagnostics CLI
- `tools/verification/quality_control/diagnostics.py` — read-only report
- Reads manifest.last_verified_report first, falls back to latest report
- Reports: policy_version distribution, promotion readiness (4-gate check)

### Wrapper Feedback Schema Upgrade
- `tools/usage_log.py` — execution_feedback enum (better/same/worse/failed/unknown), subjective_score 1-5|null, policy_version field
- `tools/memrun.py` — extracts policy_version from adapter response and passes to emit_real_usage_log()
- `5_connectors/adapter/main.py` — MemoryQueryResponse includes policy_version field

### Governance Contract
- `3_governance/QUALITY-CONTROL-LOOP-V1-CONTRACT.md` — documents all interfaces, gates, and constraints

---

## Running Reality (Verified)

### Unit Tests
```
python3 -m 5_connectors.adapter.__tests__.test_policy_version_manager
10 passed, 0 failed
```

### Offline Runner
```
python3 tools/verification/quality_control/runner.py
Active: must_pass 2/2, scored 2/2, total_score 4.0, promotion_allowed True
```

### Diagnostics
```
python3 tools/verification/quality_control/diagnostics.py --json
policy_version distribution readable, manifest state correct
```

### Runtime /memory/query
```
curl -X POST http://127.0.0.1:18011/memory/query ... | jq '.policy_version'
"local-default-v1"  ✓
```

### Wrapper Usage Log
```
policy_version field present in usage_logs.jsonl entries  ✓
```

---

## Excluded Artifacts (Not Part of This Batch)

The following modified/new files are NOT part of this batch and remain in working tree:
- `9_adr/README.md`
- `9_adr/ADR-0008-skill-suggestion-boundary.md`
- `docs/spec/SPEC-SKILL-SUGGESTION-CONSTRAINTS-002.md`
- `docs/spec/SPEC-SKILL-SUGGESTION-MODULE-001.md`

---

## Constraints Maintained

- **No automatic learning**: V1 does not modify policy based on feedback
- **No automatic promotion**: Human confirmation required for candidate → active
- **No cloud policy as primary path**: Local active manifest is sole source of truth
- **Context layer only**: Hard gate verifies context layer quality, not final answer quality
- **implementation → bypass=true**: Maintained as correct product semantics

---

## Acceptance Criteria

- [x] Only active, no candidate → baseline report produced
- [x] Candidate all must_pass + scored not degraded → promotion allowed
- [x] Candidate any must_pass fails → promotion blocked
- [x] Cloud enabled → local active manifest remains sole active source
- [x] Tests use path injection, do not pollute repo manifest.json
- [x] Only promote_candidate() sets last_promoted_at
- [x] record_verification() updates last_verified_report only, does not change active_version
- [x] policy_version贯通: adapter response → memrun → usage_logs.jsonl → diagnostics

---

## Files in This Batch

**Modified**:
- `5_connectors/adapter/cloud/__init__.py`
- `5_connectors/adapter/cloud/policy_loader.py`
- `5_connectors/adapter/main.py`
- `tools/memrun.py`
- `tools/usage_log.py`

**New**:
- `3_governance/QUALITY-CONTROL-LOOP-V1-CONTRACT.md`
- `5_connectors/adapter/__tests__/test_policy_version_manager.py`
- `5_connectors/adapter/config/policies/manifest.json`
- `5_connectors/adapter/config/policies/local-default-v1.json`
- `5_connectors/adapter/config/policies/local-candidate-v1.json` (verification artifact)
- `5_connectors/adapter/policy_version_manager.py`
- `tools/verification/quality_control/diagnostics.py`
- `tools/verification/quality_control/golden_cases/sample_cases.json`
- `tools/verification/quality_control/loader.py`
- `tools/verification/quality_control/models.py`
- `tools/verification/quality_control/runner.py`
