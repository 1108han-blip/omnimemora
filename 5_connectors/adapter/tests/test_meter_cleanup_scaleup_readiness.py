from __future__ import annotations

import importlib
from pathlib import Path

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
readiness_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_scaleup_readiness")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_scaleup_readiness_file=str(tmp_path / "meter_cleanup_scaleup_readiness.json"),
        meter_cleanup_preview_file=str(tmp_path / "meter_cleanup_preview.json"),
        meter_cleanup_transaction_preview_file=str(tmp_path / "meter_cleanup_transaction_preview.json"),
        meter_cleanup_pilot_record_file=str(tmp_path / "meter_cleanup_pilot_record.json"),
        meter_cleanup_stability_window_file=str(tmp_path / "meter_cleanup_stability_window.json"),
        meter_cleanup_rollback_drill_file=str(tmp_path / "meter_cleanup_rollback_drill.json"),
        meter_backup_export_restore_readback_file=str(tmp_path / "meter_backup_export_restore_readback.json"),
        meter_backup_export_readiness_file=str(tmp_path / "meter_backup_export_readiness.json"),
        meter_backup_export_plan_file=str(tmp_path / "meter_backup_export_plan.json"),
        meter_backup_export_package_manifest_file=str(tmp_path / "meter_backup_export_package_manifest.json"),
        meter_backup_export_execution_gate_file=str(tmp_path / "meter_backup_export_execution_gate.json"),
        meter_backup_export_execution_proposal_file=str(tmp_path / "meter_backup_export_execution_proposal.json"),
    )


def test_scaleup_readiness_blocked_on_missing_or_failed_key_inputs(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    monkeypatch.setattr(readiness_mod._cleanup_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._cleanup_txn_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._stability_window, "read_stability_window_report", lambda policy=None: None)
    monkeypatch.setattr(
        readiness_mod._meter_storage_v2,
        "build_parity_report",
        lambda: {"status": "degraded", "critical_mismatch_count": 3},
    )
    monkeypatch.setattr(readiness_mod._restore_readback, "read_restore_readback_report", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._backup_readiness, "read_readiness", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._backup_plan, "read_plan", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._backup_manifest, "read_package_manifest", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._backup_execution_gate, "read_gate", lambda policy=None: None)
    monkeypatch.setattr(readiness_mod._backup_execution_proposal, "read_execution_proposal", lambda policy=None: None)

    report = readiness_mod.build_scaleup_readiness_report(policy=policy)
    assert report["schema_version"] == "res-legacy-meter-cleanup-scaleup-readiness-v1"
    assert report["mode"] == "scaleup_readiness_only"
    assert report["status"] == "blocked"
    assert report["ready_for_scaleup"] is False
    assert report["cleanup_scope_expansion_started"] is False
    assert "cleanup_preview_missing" in report["blocking_reasons"]
    assert "stability_window_missing" in report["blocking_reasons"]
    assert "parity_not_passed" in report["blocking_reasons"]
    assert "restore_readback_missing" in report["blocking_reasons"]
    assert "rollback_drill_missing" in report["blocking_reasons"]
    assert "backup_export_plan_missing" in report["blocking_reasons"]


def test_scaleup_readiness_blocked_when_backup_export_artifacts_invalid(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    cleanup_preview = {"would_cleanup_files": [{"path": "/tmp/meters_x.json"}]}
    cleanup_txn_preview = {"summary": {"candidate_count": 1}}
    cleanup_pilot = {
        "status": "success",
        "source_move_executed": True,
        "delete_executed": False,
        "compress_executed": False,
        "truncate_executed": False,
        "batch_cleanup_executed": False,
    }
    stability_window = {"status": "passed", "cleanup_scope_expansion_started": False}
    parity = {"status": "passed", "critical_mismatch_count": 0}
    restore_readback = {
        "status": "passed",
        "source_retained": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
    }
    rollback_drill = {
        "status": "passed",
        "staging_restore_readable": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
    }

    monkeypatch.setattr(readiness_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(readiness_mod._cleanup_txn_preview, "read_preview", lambda policy=None: cleanup_txn_preview)
    monkeypatch.setattr(readiness_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: cleanup_pilot)
    monkeypatch.setattr(
        readiness_mod._stability_window, "read_stability_window_report", lambda policy=None: stability_window
    )
    monkeypatch.setattr(readiness_mod._meter_storage_v2, "build_parity_report", lambda: parity)
    monkeypatch.setattr(
        readiness_mod._restore_readback, "read_restore_readback_report", lambda policy=None: restore_readback
    )
    monkeypatch.setattr(readiness_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: rollback_drill)

    monkeypatch.setattr(
        readiness_mod._backup_readiness,
        "read_readiness",
        lambda policy=None: {"status": "blocked", "backup_export_allowed": False},
    )
    monkeypatch.setattr(
        readiness_mod._backup_plan,
        "read_plan",
        lambda policy=None: {"status": "allowed", "execution_allowed": True},
    )
    monkeypatch.setattr(
        readiness_mod._backup_manifest,
        "read_package_manifest",
        lambda policy=None: {"status": "allowed"},
    )
    monkeypatch.setattr(
        readiness_mod._backup_execution_gate,
        "read_gate",
        lambda policy=None: {"status": "allowed", "backup_export_execution_started": True, "cleanup_execution_started": False},
    )
    monkeypatch.setattr(
        readiness_mod._backup_execution_proposal,
        "read_execution_proposal",
        lambda policy=None: {"proposal_status": "unknown", "execution_started": True, "cleanup_started": False},
    )

    report = readiness_mod.build_scaleup_readiness_report(policy=policy)
    assert report["status"] == "blocked"
    assert "backup_export_plan_invalid" in report["blocking_reasons"]
    assert "backup_export_package_manifest_invalid" in report["blocking_reasons"]
    assert "backup_export_execution_started" in report["blocking_reasons"]
    assert "backup_export_execution_proposal_invalid" in report["blocking_reasons"]


def test_scaleup_readiness_pilot_and_stability_passed_still_not_auto_ready(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    cleanup_preview = {"would_cleanup_files": [{"path": "/tmp/meters_a.json"}, {"path": "/tmp/meters_b.json"}]}
    cleanup_txn_preview = {"summary": {"candidate_count": 2}}
    cleanup_pilot = {
        "status": "success",
        "source_move_executed": True,
        "delete_executed": False,
        "compress_executed": False,
        "truncate_executed": False,
        "batch_cleanup_executed": False,
    }
    stability_window = {"status": "passed", "cleanup_scope_expansion_started": False}
    parity = {"status": "passed", "critical_mismatch_count": 0}
    restore_readback = {
        "status": "passed",
        "source_retained": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
    }
    rollback_drill = {
        "status": "passed",
        "staging_restore_readable": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
    }
    backup_readiness = {"status": "blocked", "backup_export_allowed": False}
    backup_plan = {"status": "blocked", "execution_allowed": False}
    backup_manifest = {"status": "blocked"}
    backup_execution_gate = {"status": "allowed", "backup_export_execution_started": False, "cleanup_execution_started": False}
    backup_execution_proposal = {
        "proposal_status": "ready_for_operator_decision",
        "execution_started": False,
        "cleanup_started": False,
    }

    monkeypatch.setattr(readiness_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(readiness_mod._cleanup_txn_preview, "read_preview", lambda policy=None: cleanup_txn_preview)
    monkeypatch.setattr(readiness_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: cleanup_pilot)
    monkeypatch.setattr(
        readiness_mod._stability_window, "read_stability_window_report", lambda policy=None: stability_window
    )
    monkeypatch.setattr(readiness_mod._meter_storage_v2, "build_parity_report", lambda: parity)
    monkeypatch.setattr(
        readiness_mod._restore_readback, "read_restore_readback_report", lambda policy=None: restore_readback
    )
    monkeypatch.setattr(readiness_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: rollback_drill)
    monkeypatch.setattr(readiness_mod._backup_readiness, "read_readiness", lambda policy=None: backup_readiness)
    monkeypatch.setattr(readiness_mod._backup_plan, "read_plan", lambda policy=None: backup_plan)
    monkeypatch.setattr(readiness_mod._backup_manifest, "read_package_manifest", lambda policy=None: backup_manifest)
    monkeypatch.setattr(readiness_mod._backup_execution_gate, "read_gate", lambda policy=None: backup_execution_gate)
    monkeypatch.setattr(
        readiness_mod._backup_execution_proposal, "read_execution_proposal", lambda policy=None: backup_execution_proposal
    )

    report = readiness_mod.build_scaleup_readiness_report(policy=policy)
    assert report["status"] == "operator_decision_required"
    assert report["blocking_reasons"] == []
    assert report["ready_for_scaleup"] is False
    assert report["required_operator_decision"] is True
    assert report["candidate_count"] == 2
    assert report["max_batch_size_recommendation"] == 0
    assert report["cleanup_scope_expansion_started"] is False


def test_scaleup_readiness_rebuild_writes_artifact(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        readiness_mod,
        "build_scaleup_readiness_report",
        lambda policy=None: {
            "schema_version": readiness_mod.METER_CLEANUP_SCALEUP_READINESS_SCHEMA_VERSION,
            "status": "blocked",
            "ready_for_scaleup": False,
            "cleanup_scope_expansion_started": False,
            "required_operator_decision": True,
            "candidate_count": 1,
            "blocking_reasons": ["sample"],
        },
    )
    record, report = readiness_mod.rebuild_scaleup_readiness_report(policy=policy)
    assert record["trigger"] == "meter_cleanup_scaleup_readiness_rebuild"
    assert report["ready_for_scaleup"] is False
    assert Path(policy.meter_cleanup_scaleup_readiness_file).exists()
