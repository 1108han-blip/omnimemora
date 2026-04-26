from __future__ import annotations

import importlib
from pathlib import Path

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
protocol_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_repeatable_pilot_protocol")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_repeatable_pilot_protocol_file=str(tmp_path / "meter_cleanup_repeatable_pilot_protocol.json"),
        meter_cleanup_preview_file=str(tmp_path / "meter_cleanup_preview.json"),
        meter_cleanup_transaction_preview_file=str(tmp_path / "meter_cleanup_transaction_preview.json"),
        meter_cleanup_pilot_record_file=str(tmp_path / "meter_cleanup_pilot_record.json"),
        meter_cleanup_stability_window_file=str(tmp_path / "meter_cleanup_stability_window.json"),
        meter_cleanup_scaleup_readiness_file=str(tmp_path / "meter_cleanup_scaleup_readiness.json"),
        meter_cleanup_rollback_drill_file=str(tmp_path / "meter_cleanup_rollback_drill.json"),
        meter_backup_export_restore_readback_file=str(tmp_path / "meter_backup_export_restore_readback.json"),
    )


def test_repeatable_protocol_layers_checks_and_defaults(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    monkeypatch.setattr(protocol_mod._cleanup_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(protocol_mod._cleanup_txn_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(protocol_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: None)
    monkeypatch.setattr(protocol_mod._stability_window, "read_stability_window_report", lambda policy=None: None)
    monkeypatch.setattr(protocol_mod._scaleup_readiness, "read_readiness_report", lambda policy=None: None)
    monkeypatch.setattr(protocol_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "degraded", "critical_mismatch_count": 2})
    monkeypatch.setattr(protocol_mod._restore_readback, "read_restore_readback_report", lambda policy=None: None)
    monkeypatch.setattr(protocol_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: None)

    report = protocol_mod.build_protocol(policy=policy)

    assert report["schema_version"] == "res-repeatable-cleanup-pilot-protocol-v1"
    assert report["mode"] == "proposal_only"
    assert report["status"] == "blocked"
    assert isinstance(report["required_per_pilot_checks"], list)
    assert isinstance(report["one_time_mechanism_checks"], list)
    assert isinstance(report["batch_summary_checks"], list)
    assert report["second_file_pilot_allowed"] is False
    assert report["execution_started"] is False
    assert report["cleanup_scope_expansion_started"] is False
    assert "parity_clean" in report["blocking_reasons"]
    assert "stability_passed" in report["blocking_reasons"]


def test_repeatable_protocol_rebuild_writes_artifact(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    monkeypatch.setattr(
        protocol_mod,
        "build_protocol",
        lambda policy=None: {
            "schema_version": protocol_mod.METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_SCHEMA_VERSION,
            "mode": protocol_mod.METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_MODE,
            "status": "proposal_only_ready",
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
            "summary": {"preview_candidate_count": 1},
        },
    )

    record, report = protocol_mod.rebuild_protocol(policy=policy)
    assert record["trigger"] == "meter_cleanup_repeatable_pilot_protocol_rebuild"
    assert report["second_file_pilot_allowed"] is False
    assert Path(policy.meter_cleanup_repeatable_pilot_protocol_file).exists()
