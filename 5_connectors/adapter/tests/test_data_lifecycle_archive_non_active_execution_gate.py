import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_approval")
gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_non_active_execution_gate")
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
        archive_pilot_root=str(tmp_path / "archive" / "pilot"),
        archive_pilot_record_file=str(tmp_path / "archive_pilot_record.json"),
        archive_readthrough_report_file=str(tmp_path / "archive_readthrough_report.json"),
        archive_fallback_simulation_file=str(tmp_path / "archive_fallback_simulation_report.json"),
        archive_quarantine_root=str(tmp_path / "quarantine" / "source"),
        archive_quarantine_readiness_file=str(tmp_path / "archive_quarantine_readiness_plan.json"),
        archive_quarantine_record_file=str(tmp_path / "archive_quarantine_record.json"),
        archive_restore_pilot_record_file=str(tmp_path / "archive_restore_pilot_record.json"),
        archive_restore_staging_root=str(tmp_path / "restore" / "staging"),
        archive_non_active_candidate_report_file=str(tmp_path / "archive_non_active_candidate_report.json"),
        archive_non_active_quarantine_readiness_file=str(tmp_path / "archive_non_active_quarantine_readiness_plan.json"),
        archive_non_active_execution_gate_file=str(tmp_path / "archive_non_active_execution_gate.json"),
    )


def _write_json(path: str, payload: dict):
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_upstream(policy, *, target_exists=False):
    copy_path = Path(policy.archive_pilot_root) / "p1" / "compile_events.copy"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_text('{"request_id":"r"}\n', encoding="utf-8")
    planned_target = Path(policy.archive_quarantine_root) / "non_active" / "compile_events.copy.quarantine"
    if target_exists:
        planned_target.parent.mkdir(parents=True, exist_ok=True)
        planned_target.write_text(copy_path.read_text(encoding="utf-8"), encoding="utf-8")
    selector = {
        "schema_version": "dlp-non-active-candidate-report-v1",
        "report_id": "selector-1",
        "mode": "non_active_selection_report_only",
        "summary": {"source_move_delete_compress_executed": False},
        "candidates": [],
    }
    readiness = {
        "schema_version": "dlp-non-active-quarantine-readiness-v1",
        "plan_id": "ready-1",
        "mode": "non_active_quarantine_readiness_only",
        "status": "ready_for_operator_approval",
        "selected_candidate": {
            "candidate_id": "archive_pilot_copy:p1",
            "candidate_kind": "archive_pilot_copy",
            "candidate_path": str(copy_path),
            "bytes": copy_path.stat().st_size,
            "sha256": gate_mod._json_hash({"copy": str(copy_path)})[:16],
            "planned_quarantine_path": str(planned_target),
        },
        "transaction_preview": {
            "planned_action": "quarantine_non_active_copy_preview_only",
            "planned_quarantine_path": str(planned_target),
            "source_move_executed": False,
            "would_move_non_active_copy": False,
            "production_read_path_unchanged": True,
        },
        "summary": {
            "status": "ready_for_operator_approval",
            "selected_candidate_present": True,
            "blocking_count": 0,
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
            "warnings_count": 0,
        },
    }
    _write_json(policy.archive_non_active_candidate_report_file, selector)
    _write_json(policy.archive_non_active_quarantine_readiness_file, readiness)
    return selector, readiness


def test_gate_blocks_missing_approval(tmp_path):
    policy = _build_policy(tmp_path)
    _write_valid_upstream(policy)

    gate = gate_mod.build_gate(policy=policy)

    assert gate["schema_version"] == "dlp-non-active-copy-execution-gate-v1"
    assert gate["allowed"] is False
    assert "missing_operator_approval" in gate["blocking_reasons"]
    assert gate["execution_scope"]["source_move_allowed"] is False


def test_gate_allows_when_approval_hashes_match(tmp_path):
    policy = _build_policy(tmp_path)
    _write_valid_upstream(policy)
    before = gate_mod.build_gate(policy=policy)
    approval = approval_mod.build_approval_artifact(
        operator_id="op-non-active",
        approved_artifact_hashes=before["artifact_hashes"],
        scope="non-active-copy-quarantine",
        reason="test allow",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    approval_mod.write_approval_atomic(approval, policy=policy)

    gate = gate_mod.build_gate(policy=policy)

    assert gate["allowed"] is True
    assert gate["approval"]["status"] == "valid"
    assert gate["summary"]["source_move_allowed"] is False
    assert gate["summary"]["delete_allowed"] is False
    assert gate["summary"]["compress_allowed"] is False


def test_gate_blocks_when_readiness_changes_after_approval(tmp_path):
    policy = _build_policy(tmp_path)
    _write_valid_upstream(policy)
    before = gate_mod.build_gate(policy=policy)
    approval = approval_mod.build_approval_artifact(
        operator_id="op-non-active",
        approved_artifact_hashes=before["artifact_hashes"],
        scope="non-active-copy-quarantine",
        reason="test mismatch",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    approval_mod.write_approval_atomic(approval, policy=policy)
    readiness = json.loads(Path(policy.archive_non_active_quarantine_readiness_file).read_text(encoding="utf-8"))
    readiness["plan_id"] = "ready-2"
    _write_json(policy.archive_non_active_quarantine_readiness_file, readiness)

    gate = gate_mod.build_gate(policy=policy)

    assert gate["allowed"] is False
    assert "approval_artifact_hash_mismatch" in gate["blocking_reasons"]
    assert "approval_non_active_quarantine_readiness_hash_mismatch" in gate["blocking_reasons"]


def test_gate_blocks_not_ready_or_existing_target(tmp_path):
    policy = _build_policy(tmp_path)
    _write_valid_upstream(policy, target_exists=True)
    readiness = json.loads(Path(policy.archive_non_active_quarantine_readiness_file).read_text(encoding="utf-8"))
    readiness["status"] = "blocked"
    _write_json(policy.archive_non_active_quarantine_readiness_file, readiness)

    gate = gate_mod.build_gate(policy=policy)

    assert gate["allowed"] is False
    assert "non_active_quarantine_readiness_not_ready" in gate["blocking_reasons"]
    assert "planned_quarantine_target_already_exists" in gate["blocking_reasons"]


def test_gate_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    gate = {
        "schema_version": "dlp-non-active-copy-execution-gate-v1",
        "gate_id": "g1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "gate_only",
        "allowed": False,
        "status": "blocked",
        "blocking_reasons": ["missing_operator_approval"],
        "summary": {"blocking_count": 1},
    }
    monkeypatch.setattr(
        gate_mod.os,
        "replace",
        lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")),
    )
    try:
        gate_mod.write_gate_atomic(gate, policy=policy)
        assert False, "expected write_gate_atomic to fail"
    except RuntimeError:
        pass
    target = Path(policy.archive_non_active_execution_gate_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_non_active_gate_*.tmp")) == []
