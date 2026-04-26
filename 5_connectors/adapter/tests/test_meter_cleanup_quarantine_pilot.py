from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_quarantine_pilot")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_selected_candidate_file=str(tmp_path / "meter_cleanup_selected_candidate.json"),
        meter_cleanup_pilot_approval_template_file=str(tmp_path / "meter_cleanup_pilot_approval_template.json"),
        meter_cleanup_pilot_operator_approval_file=str(tmp_path / "meter_cleanup_pilot_operator_approval.json"),
        meter_cleanup_quarantine_root=str(tmp_path / "quarantine" / "meter_cleanup"),
        meter_cleanup_pilot_record_file=str(tmp_path / "meter_cleanup_pilot_record.json"),
    )


def _sha256(path: Path) -> str:
    return pilot_mod._sha256_file(path) or ""


def _mtime(path: Path) -> str:
    return pilot_mod._mtime_iso(path) or ""


def test_selected_candidate_blocks_meters_index(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_index.json"
    backup = tmp_path / "meters_index.json.pilotcopy"
    source.write_text('{"index":1}', encoding="utf-8")
    backup.write_text('{"index":1}', encoding="utf-8")

    cleanup_preview = {"would_cleanup_files": [{"path": str(source), "sha256": _sha256(source), "mtime": _mtime(source)}]}
    copy_pilot = {
        "status": "success",
        "source_retained": True,
        "checksum_match": True,
        "selected_candidate": {"path": str(source)},
        "target_path": str(backup),
        "copied_sha256": _sha256(backup),
    }
    restore_readback = {
        "status": "passed",
        "checksum_match": True,
        "source_path": str(source),
        "backup_copy_path": str(backup),
    }
    txn_preview = {"items": [{"source": {"path": str(source)}, "operation": "blocked"}]}
    rollback = {"status": "passed", "staging_restore_readable": True, "checksum_match": True}

    monkeypatch.setattr(pilot_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(pilot_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(
        pilot_mod._backup_restore_readback, "read_restore_readback_report", lambda policy=None: restore_readback
    )
    monkeypatch.setattr(
        pilot_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "passed", "critical_mismatch_count": 0}
    )
    monkeypatch.setattr(pilot_mod._cleanup_txn, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(pilot_mod._cleanup_rollback, "read_rollback_drill_report", lambda policy=None: rollback)

    selected = pilot_mod.build_selected_candidate(policy=policy)
    assert selected["status"] == "blocked"
    assert "selected_source_is_meters_index" in selected["blocking_reasons"]


def test_artifact_hash_ignores_generated_at_field():
    payload_a = {"schema_version": "x", "generated_at": "2026-04-26T00:00:00+00:00", "summary": {"status": "passed"}}
    payload_b = {"schema_version": "x", "generated_at": "2026-04-26T00:01:00+00:00", "summary": {"status": "passed"}}
    assert pilot_mod._artifact_hash(payload_a) == pilot_mod._artifact_hash(payload_b)


def test_quarantine_one_moves_single_source_file_with_matching_approval(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_a.json"
    backup = tmp_path / "meters_tenant_a.json.pilotcopy"
    source.write_text('{"tenant":"a"}', encoding="utf-8")
    backup.write_text('{"tenant":"a"}', encoding="utf-8")

    cleanup_preview = {"would_cleanup_files": [{"path": str(source), "sha256": _sha256(source), "mtime": _mtime(source)}]}
    copy_pilot = {
        "status": "success",
        "source_retained": True,
        "checksum_match": True,
        "selected_candidate": {"path": str(source)},
        "target_path": str(backup),
        "copied_sha256": _sha256(backup),
    }
    restore_readback = {
        "status": "passed",
        "checksum_match": True,
        "source_path": str(source),
        "backup_copy_path": str(backup),
    }
    txn_preview = {"items": [{"source": {"path": str(source)}, "operation": "eligible_for_future_cleanup"}]}
    rollback = {"status": "passed", "staging_restore_readable": True, "checksum_match": True}

    monkeypatch.setattr(pilot_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(pilot_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(
        pilot_mod._backup_restore_readback, "read_restore_readback_report", lambda policy=None: restore_readback
    )
    monkeypatch.setattr(
        pilot_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "passed", "critical_mismatch_count": 0}
    )
    monkeypatch.setattr(pilot_mod._cleanup_txn, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(pilot_mod._cleanup_rollback, "read_rollback_drill_report", lambda policy=None: rollback)

    selected = pilot_mod.build_selected_candidate(policy=policy)
    approval = {
        "schema_version": pilot_mod.METER_CLEANUP_PILOT_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "operator_id": "op-res023",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "source_path": selected["selected_candidate"]["path"],
        "source_sha256": selected["selected_candidate"]["sha256"],
        "source_mtime": selected["selected_candidate"]["mtime"],
        "backup_copy_path": selected["backup_copy"]["path"],
        "backup_copy_sha256": selected["backup_copy"]["sha256"],
        "restore_readback_report_hash": selected["artifact_hashes"]["restore_readback_report_hash"],
        "parity_report_hash": selected["artifact_hashes"]["parity_report_hash"],
        "transaction_preview_hash": selected["artifact_hashes"]["transaction_preview_hash"],
        "target_quarantine_path": selected["planned_quarantine_path"],
        "reason": "RES-023 pilot",
    }
    Path(policy.meter_cleanup_pilot_operator_approval_file).write_text(json.dumps(approval), encoding="utf-8")

    record, pilot = pilot_mod.execute_single_file_quarantine(policy=policy)
    assert record["trigger"] == "meter_cleanup_quarantine_pilot_quarantine_one"
    assert pilot["status"] == "success"
    assert pilot["source_move_executed"] is True
    assert pilot["delete_executed"] is False
    assert pilot["compress_executed"] is False
    assert pilot["truncate_executed"] is False
    assert pilot["batch_cleanup_executed"] is False
    assert source.exists() is False
    assert Path(pilot["quarantine_path"]).exists() is True


def test_quarantine_one_blocks_on_expired_approval(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_b.json"
    backup = tmp_path / "meters_tenant_b.json.pilotcopy"
    source.write_text('{"tenant":"b"}', encoding="utf-8")
    backup.write_text('{"tenant":"b"}', encoding="utf-8")

    cleanup_preview = {"would_cleanup_files": [{"path": str(source), "sha256": _sha256(source), "mtime": _mtime(source)}]}
    copy_pilot = {
        "status": "success",
        "source_retained": True,
        "checksum_match": True,
        "selected_candidate": {"path": str(source)},
        "target_path": str(backup),
        "copied_sha256": _sha256(backup),
    }
    restore_readback = {
        "status": "passed",
        "checksum_match": True,
        "source_path": str(source),
        "backup_copy_path": str(backup),
    }
    txn_preview = {"items": [{"source": {"path": str(source)}, "operation": "eligible_for_future_cleanup"}]}
    rollback = {"status": "passed", "staging_restore_readable": True, "checksum_match": True}

    monkeypatch.setattr(pilot_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(pilot_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(
        pilot_mod._backup_restore_readback, "read_restore_readback_report", lambda policy=None: restore_readback
    )
    monkeypatch.setattr(
        pilot_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "passed", "critical_mismatch_count": 0}
    )
    monkeypatch.setattr(pilot_mod._cleanup_txn, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(pilot_mod._cleanup_rollback, "read_rollback_drill_report", lambda policy=None: rollback)

    selected = pilot_mod.build_selected_candidate(policy=policy)
    approval = {
        "schema_version": pilot_mod.METER_CLEANUP_PILOT_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "operator_id": "op-res023",
        "approved_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
        "source_path": selected["selected_candidate"]["path"],
        "source_sha256": selected["selected_candidate"]["sha256"],
        "source_mtime": selected["selected_candidate"]["mtime"],
        "backup_copy_path": selected["backup_copy"]["path"],
        "backup_copy_sha256": selected["backup_copy"]["sha256"],
        "restore_readback_report_hash": selected["artifact_hashes"]["restore_readback_report_hash"],
        "parity_report_hash": selected["artifact_hashes"]["parity_report_hash"],
        "transaction_preview_hash": selected["artifact_hashes"]["transaction_preview_hash"],
        "target_quarantine_path": selected["planned_quarantine_path"],
    }
    Path(policy.meter_cleanup_pilot_operator_approval_file).write_text(json.dumps(approval), encoding="utf-8")

    _, pilot = pilot_mod.execute_single_file_quarantine(policy=policy)
    assert pilot["status"] == "blocked"
    assert "operator_approval_expired" in pilot["blocking_reasons"]
    assert source.exists() is True


def test_quarantine_one_blocks_on_source_hash_drift_after_approval(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_c.json"
    backup = tmp_path / "meters_tenant_c.json.pilotcopy"
    source.write_text('{"tenant":"c"}', encoding="utf-8")
    backup.write_text('{"tenant":"c"}', encoding="utf-8")

    cleanup_preview = {"would_cleanup_files": [{"path": str(source), "sha256": _sha256(source), "mtime": _mtime(source)}]}
    copy_pilot = {
        "status": "success",
        "source_retained": True,
        "checksum_match": True,
        "selected_candidate": {"path": str(source)},
        "target_path": str(backup),
        "copied_sha256": _sha256(backup),
    }
    restore_readback = {
        "status": "passed",
        "checksum_match": True,
        "source_path": str(source),
        "backup_copy_path": str(backup),
    }
    txn_preview = {"items": [{"source": {"path": str(source)}, "operation": "eligible_for_future_cleanup"}]}
    rollback = {"status": "passed", "staging_restore_readable": True, "checksum_match": True}

    monkeypatch.setattr(pilot_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(pilot_mod._backup_copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(
        pilot_mod._backup_restore_readback, "read_restore_readback_report", lambda policy=None: restore_readback
    )
    monkeypatch.setattr(
        pilot_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "passed", "critical_mismatch_count": 0}
    )
    monkeypatch.setattr(pilot_mod._cleanup_txn, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(pilot_mod._cleanup_rollback, "read_rollback_drill_report", lambda policy=None: rollback)

    selected = pilot_mod.build_selected_candidate(policy=policy)
    approval = {
        "schema_version": pilot_mod.METER_CLEANUP_PILOT_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "operator_id": "op-res023",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "source_path": selected["selected_candidate"]["path"],
        "source_sha256": selected["selected_candidate"]["sha256"],
        "source_mtime": selected["selected_candidate"]["mtime"],
        "backup_copy_path": selected["backup_copy"]["path"],
        "backup_copy_sha256": selected["backup_copy"]["sha256"],
        "restore_readback_report_hash": selected["artifact_hashes"]["restore_readback_report_hash"],
        "parity_report_hash": selected["artifact_hashes"]["parity_report_hash"],
        "transaction_preview_hash": selected["artifact_hashes"]["transaction_preview_hash"],
        "target_quarantine_path": selected["planned_quarantine_path"],
    }
    Path(policy.meter_cleanup_pilot_operator_approval_file).write_text(json.dumps(approval), encoding="utf-8")

    source.write_text('{"tenant":"c","drift":true}', encoding="utf-8")

    _, pilot = pilot_mod.execute_single_file_quarantine(policy=policy)
    assert pilot["status"] == "blocked"
    assert "source_hash_drift" in pilot["blocking_reasons"]
    assert source.exists() is True
