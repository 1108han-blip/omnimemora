import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


archive_execution_gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_execution_gate")
archive_approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_approval")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=30.0,
        summary_stale_max_age_seconds=3600.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        retention_manifest_file=str(tmp_path / "retention_manifest.json"),
        traceability_report_file=str(tmp_path / "traceability_report.json"),
        archive_plan_file=str(tmp_path / "archive_candidate_plan.json"),
        archive_transaction_preview_file=str(tmp_path / "archive_transaction_preview.json"),
        archive_restore_readiness_file=str(tmp_path / "archive_restore_readiness_report.json"),
        archive_execution_gate_file=str(tmp_path / "archive_execution_gate.json"),
        archive_operator_approval_file=str(tmp_path / "archive_operator_approval.json"),
    )


def _write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_upstream_valid(policy: policy_mod.DataLifecyclePolicy):
    _write_json(
        Path(policy.archive_plan_file),
        {
            "schema_version": "dlp-archive-candidate-plan-v1",
            "plan_id": "plan1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "dry_run_only",
            "traceability_ref": {"status": "present", "fail_count": 0, "unexplained_partial_count": 0},
            "candidates": [],
            "summary": {"eligible_count": 1, "blocked_count": 0, "review_required_count": 0},
        },
    )
    _write_json(
        Path(policy.archive_transaction_preview_file),
        {
            "schema_version": "dlp-archive-transaction-preview-v1",
            "preview_id": "p1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "preview_only",
            "items": [],
            "summary": {
                "status": "present",
                "eligible_input_count": 1,
                "preview_item_count": 1,
                "blocked_precondition_count": 0,
            },
        },
    )
    _write_json(
        Path(policy.archive_restore_readiness_file),
        {
            "schema_version": "dlp-archive-restore-readiness-v1",
            "readiness_id": "r1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "readiness_only",
            "summary": {"status": "present", "sample_count": 1, "mapped_request_count": 1, "unmapped_request_count": 0},
        },
    )


def test_gate_missing_approval_is_blocked(tmp_path):
    policy = _build_policy(tmp_path)
    _write_upstream_valid(policy)
    gate = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate["allowed"] is False
    assert "missing_operator_approval" in gate["blocking_reasons"]


def test_gate_allows_when_approval_hashes_match(tmp_path):
    policy = _build_policy(tmp_path)
    _write_upstream_valid(policy)
    gate_before = archive_execution_gate_mod.build_execution_gate(policy=policy)
    artifact_hashes = gate_before["artifact_hashes"]
    approval = archive_approval_mod.build_approval_artifact(
        operator_id="op-test",
        approved_artifact_hashes=artifact_hashes,
        scope="stage8-test",
        reason="validate gate allow path",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    archive_approval_mod.write_approval_atomic(approval, policy=policy)

    gate = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate["allowed"] is True
    assert gate["approval"]["status"] == "valid"
    assert gate["approved_plan_hash"] == artifact_hashes["candidate_plan_hash"]


def test_gate_blocks_expired_approval_and_hash_mismatch(tmp_path):
    policy = _build_policy(tmp_path)
    _write_upstream_valid(policy)
    gate_before = archive_execution_gate_mod.build_execution_gate(policy=policy)
    artifact_hashes = gate_before["artifact_hashes"]

    expired = archive_approval_mod.build_approval_artifact(
        operator_id="op-test",
        approved_artifact_hashes=artifact_hashes,
        scope="stage8-test",
        reason="expired",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    archive_approval_mod.write_approval_atomic(expired, policy=policy)
    gate_expired = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate_expired["allowed"] is False
    assert "approval_expired" in gate_expired["blocking_reasons"]

    valid = archive_approval_mod.build_approval_artifact(
        operator_id="op-test",
        approved_artifact_hashes=artifact_hashes,
        scope="stage8-test",
        reason="mismatch-check",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    archive_approval_mod.write_approval_atomic(valid, policy=policy)
    plan = json.loads(Path(policy.archive_plan_file).read_text(encoding="utf-8"))
    plan["plan_id"] = "plan2"
    _write_json(Path(policy.archive_plan_file), plan)
    gate_mismatch = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate_mismatch["allowed"] is False
    assert "approval_artifact_hash_mismatch" in gate_mismatch["blocking_reasons"]


def test_gate_blocks_on_missing_or_invalid_upstream(tmp_path):
    policy = _build_policy(tmp_path)
    _write_upstream_valid(policy)
    preview = json.loads(Path(policy.archive_transaction_preview_file).read_text(encoding="utf-8"))
    preview["mode"] = "not_preview_only"
    _write_json(Path(policy.archive_transaction_preview_file), preview)
    gate = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate["allowed"] is False
    assert "transaction_preview_mode_mismatch" in gate["blocking_reasons"]


def test_gate_blocks_on_traceability_fail_and_unexplained_partial(tmp_path):
    policy = _build_policy(tmp_path)
    _write_upstream_valid(policy)
    plan = json.loads(Path(policy.archive_plan_file).read_text(encoding="utf-8"))
    plan["traceability_ref"]["fail_count"] = 1
    plan["traceability_ref"]["unexplained_partial_count"] = 2
    _write_json(Path(policy.archive_plan_file), plan)
    gate = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate["allowed"] is False
    assert "traceability_fail_count_gt_zero" in gate["blocking_reasons"]
    assert "traceability_unexplained_partial_gt_zero" in gate["blocking_reasons"]


def test_gate_blocks_on_preview_precondition_and_restore_not_ready(tmp_path):
    policy = _build_policy(tmp_path)
    _write_upstream_valid(policy)
    preview = json.loads(Path(policy.archive_transaction_preview_file).read_text(encoding="utf-8"))
    preview["summary"]["blocked_precondition_count"] = 1
    _write_json(Path(policy.archive_transaction_preview_file), preview)
    readiness = json.loads(Path(policy.archive_restore_readiness_file).read_text(encoding="utf-8"))
    readiness["summary"]["status"] = "blocked_missing_preview"
    _write_json(Path(policy.archive_restore_readiness_file), readiness)
    gate = archive_execution_gate_mod.build_execution_gate(policy=policy)
    assert gate["allowed"] is False
    assert "preview_blocked_precondition_present" in gate["blocking_reasons"]
    assert "restore_readiness_not_ready" in gate["blocking_reasons"]


def test_gate_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    gate = {
        "schema_version": "dlp-archive-execution-gate-v1",
        "gate_id": "g1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "gate_only",
        "allowed": False,
        "blocking_reasons": ["missing_operator_approval"],
        "required_approvals": ["operator_approval"],
        "artifact_hashes": {},
        "approved_plan_hash": None,
        "summary": {"blocking_count": 1},
        "warnings": [],
    }
    monkeypatch.setattr(
        archive_execution_gate_mod.os,
        "replace",
        lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")),
    )
    try:
        archive_execution_gate_mod.write_gate_atomic(gate, policy=policy)
        assert False, "expected write_gate_atomic to fail"
    except RuntimeError:
        pass
    target = Path(policy.archive_execution_gate_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_archive_gate_*.tmp")) == []
