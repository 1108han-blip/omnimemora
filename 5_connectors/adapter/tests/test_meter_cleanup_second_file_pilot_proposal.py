from __future__ import annotations

import importlib
from pathlib import Path

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
proposal_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_proposal")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_repeatable_pilot_protocol_file=str(tmp_path / "meter_cleanup_repeatable_pilot_protocol.json"),
        meter_cleanup_second_file_pilot_proposal_file=str(tmp_path / "meter_cleanup_second_file_pilot_proposal.json"),
        meter_cleanup_preview_file=str(tmp_path / "meter_cleanup_preview.json"),
        meter_cleanup_transaction_preview_file=str(tmp_path / "meter_cleanup_transaction_preview.json"),
        meter_cleanup_pilot_record_file=str(tmp_path / "meter_cleanup_pilot_record.json"),
        meter_cleanup_stability_window_file=str(tmp_path / "meter_cleanup_stability_window.json"),
        meter_cleanup_scaleup_readiness_file=str(tmp_path / "meter_cleanup_scaleup_readiness.json"),
        meter_cleanup_rollback_drill_file=str(tmp_path / "meter_cleanup_rollback_drill.json"),
        meter_backup_export_restore_readback_file=str(tmp_path / "meter_backup_export_restore_readback.json"),
        meter_backup_export_readiness_file=str(tmp_path / "meter_backup_export_readiness.json"),
        meter_backup_export_plan_file=str(tmp_path / "meter_backup_export_plan.json"),
        meter_backup_export_package_manifest_file=str(tmp_path / "meter_backup_export_package_manifest.json"),
    )


def test_second_file_proposal_blocked_when_missing_core_checks(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    monkeypatch.setattr(proposal_mod._repeatable_protocol, "read_protocol", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._cleanup_preview, "read_preview", lambda policy=None: {"would_cleanup_files": []})
    monkeypatch.setattr(proposal_mod._cleanup_txn_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._stability_window, "read_stability_window_report", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._scaleup_readiness, "read_readiness_report", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "degraded", "critical_mismatch_count": 1})
    monkeypatch.setattr(proposal_mod._restore_readback, "read_restore_readback_report", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._backup_readiness, "read_readiness", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._backup_plan, "read_plan", lambda policy=None: None)
    monkeypatch.setattr(proposal_mod._backup_manifest, "read_package_manifest", lambda policy=None: None)

    report = proposal_mod.build_proposal(policy=policy)

    assert report["schema_version"] == "res-second-file-cleanup-pilot-proposal-v1"
    assert report["mode"] == "proposal_only"
    assert report["status"] == "blocked"
    assert report["second_file_pilot_allowed"] is False
    assert report["execution_started"] is False
    assert report["cleanup_scope_expansion_started"] is False
    assert "parity_not_clean" in report["blocking_reasons"]
    assert "stability_window_not_passed" in report["blocking_reasons"]
    assert "restore_readback_not_passed" in report["blocking_reasons"]
    assert "rollback_drill_not_passed" in report["blocking_reasons"]


def test_second_file_proposal_excludes_res023_quarantined_source(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    protocol = {"status": "proposal_only_ready"}
    preview = {
        "would_cleanup_files": [
            {"path": "/tmp/meters_res023.json", "name": "meters_res023.json", "bytes": 200, "sha256": "h1", "mtime": "t1"},
            {"path": "/tmp/meters_other.json", "name": "meters_other.json", "bytes": 100, "sha256": "h2", "mtime": "t2"},
        ]
    }
    txn_preview = {
        "items": [
            {"source": {"path": "/tmp/meters_res023.json"}, "operation": "eligible_for_future_cleanup", "blocking_reasons": []},
            {"source": {"path": "/tmp/meters_other.json"}, "operation": "eligible_for_future_cleanup", "blocking_reasons": []},
        ]
    }
    pilot = {"status": "success", "original_path": "/tmp/meters_res023.json"}
    stability = {"status": "passed"}
    scaleup = {"status": "blocked", "ready_for_scaleup": False, "cleanup_scope_expansion_started": False}
    parity = {"status": "passed", "critical_mismatch_count": 0}
    restore = {"status": "passed", "checksum_match": True, "source_retained": True}
    rollback = {"status": "passed", "staging_restore_readable": True, "checksum_match": True}

    monkeypatch.setattr(proposal_mod._repeatable_protocol, "read_protocol", lambda policy=None: protocol)
    monkeypatch.setattr(proposal_mod._cleanup_preview, "read_preview", lambda policy=None: preview)
    monkeypatch.setattr(proposal_mod._cleanup_txn_preview, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(proposal_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: pilot)
    monkeypatch.setattr(proposal_mod._stability_window, "read_stability_window_report", lambda policy=None: stability)
    monkeypatch.setattr(proposal_mod._scaleup_readiness, "read_readiness_report", lambda policy=None: scaleup)
    monkeypatch.setattr(proposal_mod._meter_storage_v2, "build_parity_report", lambda: parity)
    monkeypatch.setattr(proposal_mod._restore_readback, "read_restore_readback_report", lambda policy=None: restore)
    monkeypatch.setattr(proposal_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: rollback)
    monkeypatch.setattr(proposal_mod._backup_readiness, "read_readiness", lambda policy=None: {"status": "blocked"})
    monkeypatch.setattr(proposal_mod._backup_plan, "read_plan", lambda policy=None: {"status": "blocked"})
    monkeypatch.setattr(proposal_mod._backup_manifest, "read_package_manifest", lambda policy=None: {"status": "blocked"})

    report = proposal_mod.build_proposal(policy=policy)
    assert report["status"] == "blocked"
    assert report["selected_candidate"]["path"] == "/tmp/meters_other.json"
    assert any(x.get("path") == "/tmp/meters_res023.json" for x in report["excluded_candidates"])
    assert report["approval_hash"] is not None


def test_second_file_proposal_rebuild_writes_artifact(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    monkeypatch.setattr(
        proposal_mod,
        "build_proposal",
        lambda policy=None: {
            "schema_version": proposal_mod.METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_SCHEMA_VERSION,
            "mode": proposal_mod.METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_MODE,
            "status": "blocked",
            "selected_candidate": None,
            "estimated_reclaim_bytes": 0,
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        },
    )

    record, proposal = proposal_mod.rebuild_proposal(policy=policy)
    assert record["trigger"] == "meter_cleanup_second_file_pilot_proposal_rebuild"
    assert proposal["second_file_pilot_allowed"] is False
    assert Path(policy.meter_cleanup_second_file_pilot_proposal_file).exists()
