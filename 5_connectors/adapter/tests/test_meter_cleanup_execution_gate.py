from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
cleanup_gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_execution_gate")
operator_approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_execution_gate_file=str(tmp_path / "meter_cleanup_execution_gate.json"),
        meter_cleanup_preview_file=str(tmp_path / "meter_cleanup_preview.json"),
        meter_backup_export_plan_file=str(tmp_path / "meter_backup_export_plan.json"),
        meter_backup_export_readiness_file=str(tmp_path / "meter_backup_export_readiness.json"),
        meter_backup_export_package_manifest_file=str(tmp_path / "meter_backup_export_package_manifest.json"),
        meter_backup_export_copy_pilot_record_file=str(tmp_path / "meter_backup_export_copy_pilot_record.json"),
        meter_backup_export_restore_readback_file=str(tmp_path / "meter_backup_export_restore_readback.json"),
        meter_backup_export_operator_approval_file=str(tmp_path / "meter_backup_export_operator_approval.json"),
    )


def test_cleanup_execution_gate_missing_inputs_is_blocked(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.delenv("OMNIMEMORA_RUNNING_REVISION", raising=False)
    monkeypatch.delenv("OMNIMEMORA_ADAPTER_RUNNING_REVISION", raising=False)
    monkeypatch.setenv("OMNIMEMORA_PROMOTION_STATE_FILE", str(tmp_path / "missing_marker.json"))

    monkeypatch.setattr(cleanup_gate_mod._cleanup_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._restore_readback, "read_restore_readback_report", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "degraded", "critical_mismatch_count": 2})
    monkeypatch.setattr(cleanup_gate_mod._backup_plan, "read_plan", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._backup_readiness, "read_readiness", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._backup_manifest, "read_package_manifest", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._operator_approval, "read_operator_approval", lambda policy=None: None)

    gate = cleanup_gate_mod.build_execution_gate(policy=policy)
    assert gate["schema_version"] == "res-legacy-meter-cleanup-execution-gate-v1"
    assert gate["cleanup_gate_status"] == "blocked"
    assert gate["cleanup_allowed"] is False
    assert gate["rollback_required"] is True
    assert "running_revision_missing" in gate["blocking_reasons"]
    assert "cleanup_execution_not_enabled_in_res020" in gate["blocking_reasons"]


def test_cleanup_execution_gate_collects_hashes_even_when_default_deny(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setenv("OMNIMEMORA_RUNNING_REVISION", "rev-test-001")

    source = tmp_path / "meters_tenant_a.json"
    source.write_text('{"k":"v"}', encoding="utf-8")
    preview = {
        "would_cleanup_files": [
            {
                "name": source.name,
                "path": str(source),
                "sha256": "abc123",
                "mtime": "2026-04-26T00:00:00+00:00",
            }
        ]
    }
    plan = {"schema_version": "res-legacy-meter-backup-export-plan-v1", "destination_status": {"path": "/tmp/backup"}}
    readiness = {"schema_version": "res-legacy-meter-backup-export-readiness-v1"}
    manifest = {"schema_version": "res-legacy-meter-backup-export-package-manifest-v1"}
    copy_pilot = {"status": "success", "source_retained": True, "checksum_match": True, "cleanup_started": False}
    restore = {
        "status": "passed",
        "source_retained": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
    }
    parity = {"status": "passed", "critical_mismatch_count": 0}
    approval = operator_approval_mod.build_approval_artifact(
        operator_id="op-1",
        destination_path="/tmp/backup",
        approved_plan_hash=cleanup_gate_mod._json_hash(plan) or "",
        approved_package_manifest_hash=cleanup_gate_mod._json_hash(manifest) or "",
        approved_readiness_hash=cleanup_gate_mod._json_hash(readiness) or "",
        approved_cleanup_preview_hash=cleanup_gate_mod._json_hash(preview) or "",
        reason="test",
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    monkeypatch.setattr(cleanup_gate_mod._cleanup_preview, "read_preview", lambda policy=None: preview)
    monkeypatch.setattr(cleanup_gate_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(cleanup_gate_mod._restore_readback, "read_restore_readback_report", lambda policy=None: restore)
    monkeypatch.setattr(cleanup_gate_mod._meter_storage_v2, "build_parity_report", lambda: parity)
    monkeypatch.setattr(cleanup_gate_mod._backup_plan, "read_plan", lambda policy=None: plan)
    monkeypatch.setattr(cleanup_gate_mod._backup_readiness, "read_readiness", lambda policy=None: readiness)
    monkeypatch.setattr(cleanup_gate_mod._backup_manifest, "read_package_manifest", lambda policy=None: manifest)
    monkeypatch.setattr(cleanup_gate_mod._operator_approval, "read_operator_approval", lambda policy=None: approval)

    gate = cleanup_gate_mod.build_execution_gate(policy=policy)
    assert gate["running_revision"] == "rev-test-001"
    assert gate["source_file_hashes"][str(source)] == "abc123"
    assert gate["required_approval_hashes"]["approved_plan_hash"]
    assert gate["cleanup_allowed"] is False
    assert "cleanup_execution_not_enabled_in_res020" in gate["blocking_reasons"]


def test_cleanup_execution_gate_rebuild_writes_gate_file(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        cleanup_gate_mod,
        "build_execution_gate",
        lambda policy=None: {
            "schema_version": cleanup_gate_mod.METER_CLEANUP_EXECUTION_GATE_SCHEMA_VERSION,
            "cleanup_gate_status": "blocked",
            "cleanup_allowed": False,
            "rollback_required": True,
            "summary": {"source_file_count": 1},
        },
    )
    record, gate = cleanup_gate_mod.rebuild_gate(policy=policy)
    assert record["trigger"] == "meter_cleanup_execution_gate_rebuild"
    assert gate["cleanup_allowed"] is False
    assert (tmp_path / "meter_cleanup_execution_gate.json").exists()


def test_cleanup_execution_gate_reads_running_revision_from_promotion_marker(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    marker = tmp_path / ".omnimemora_promotion_state.json"
    marker.write_text(
        '{"timestamp":"2026-04-26T03:11:53","target":"adapter+ui","repo_revision":"rev-marker-001"}',
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNIMEMORA_RUNNING_REVISION", raising=False)
    monkeypatch.delenv("OMNIMEMORA_ADAPTER_RUNNING_REVISION", raising=False)
    monkeypatch.setenv("OMNIMEMORA_PROMOTION_STATE_FILE", str(marker))

    monkeypatch.setattr(cleanup_gate_mod._cleanup_preview, "read_preview", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._restore_readback, "read_restore_readback_report", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "degraded", "critical_mismatch_count": 2})
    monkeypatch.setattr(cleanup_gate_mod._backup_plan, "read_plan", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._backup_readiness, "read_readiness", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._backup_manifest, "read_package_manifest", lambda policy=None: None)
    monkeypatch.setattr(cleanup_gate_mod._operator_approval, "read_operator_approval", lambda policy=None: None)

    gate = cleanup_gate_mod.build_execution_gate(policy=policy)
    assert gate["running_revision"] == "rev-marker-001"
    assert gate["running_revision_source"].startswith("marker:")
    assert "running_revision_missing" not in gate["blocking_reasons"]
