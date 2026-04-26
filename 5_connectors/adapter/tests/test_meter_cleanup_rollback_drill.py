from __future__ import annotations

import importlib

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
rollback_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_rollback_drill_file=str(tmp_path / "meter_cleanup_rollback_drill.json"),
        meter_cleanup_rollback_staging_root=str(tmp_path / "cleanup_rollback" / "staging"),
    )


def test_cleanup_rollback_drill_staging_restore_only(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_a.json"
    backup = tmp_path / "meters_tenant_a.json.abcdef.pilotcopy"
    source.write_text('{"ok":true}', encoding="utf-8")
    backup.write_text('{"ok":true}', encoding="utf-8")
    original_source = source.read_text(encoding="utf-8")

    copy_pilot = {
        "status": "success",
        "selected_candidate": {"path": str(source)},
        "target_path": str(backup),
        "source_retained": True,
        "checksum_match": True,
        "cleanup_started": False,
    }
    monkeypatch.setattr(rollback_mod._copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)

    report = rollback_mod.build_rollback_drill_report(policy=policy)
    assert report["schema_version"] == "res-legacy-meter-cleanup-rollback-drill-v1"
    assert report["status"] == "passed"
    assert report["source_retained"] is True
    assert report["staging_restore_readable"] is True
    assert report["checksum_match"] is True
    assert report["production_restore_started"] is False
    assert report["cleanup_started"] is False
    assert source.read_text(encoding="utf-8") == original_source


def test_cleanup_rollback_drill_missing_copy_pilot_blocked(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(rollback_mod._copy_pilot, "read_latest_copy_pilot", lambda policy=None: None)

    report = rollback_mod.build_rollback_drill_report(policy=policy)
    assert report["status"] == "blocked"
    assert report["staging_restore_readable"] is False
    assert "backup_copy_pilot_missing" in report["blocking_reasons"]
    assert report["production_restore_started"] is False


def test_cleanup_rollback_drill_rebuild_writes_report(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        rollback_mod,
        "build_rollback_drill_report",
        lambda policy=None: {
            "schema_version": rollback_mod.METER_CLEANUP_ROLLBACK_DRILL_SCHEMA_VERSION,
            "status": "blocked",
            "staging_restore_readable": False,
            "checksum_match": False,
        },
    )
    record, report = rollback_mod.rebuild_rollback_drill_report(policy=policy)
    assert record["trigger"] == "meter_cleanup_rollback_drill_rebuild"
    assert report["schema_version"] == "res-legacy-meter-cleanup-rollback-drill-v1"
    assert (tmp_path / "meter_cleanup_rollback_drill.json").exists()


def test_cleanup_rollback_drill_passes_with_quarantine_source_after_pilot_move(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_q.json"
    backup = tmp_path / "meters_tenant_q.json.abcdef.pilotcopy"
    quarantine = tmp_path / "quarantine" / "meters_tenant_q.json.abcdef.quarantine"
    source.write_text('{"ok":true}', encoding="utf-8")
    backup.write_text('{"ok":true}', encoding="utf-8")
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    quarantine.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    source.unlink()

    copy_pilot = {
        "status": "success",
        "selected_candidate": {"path": str(source)},
        "target_path": str(backup),
        "source_retained": True,
        "checksum_match": True,
        "cleanup_started": False,
    }
    cleanup_pilot = {
        "status": "success",
        "source_move_executed": True,
        "original_path": str(source),
        "quarantine_path": str(quarantine),
    }
    monkeypatch.setattr(rollback_mod._copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(rollback_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: cleanup_pilot)

    report = rollback_mod.build_rollback_drill_report(policy=policy)
    assert report["status"] == "passed"
    assert report["source_retained"] is False
    assert report["source_verification_mode"] == "quarantine"
    assert report["staging_restore_readable"] is True
    assert report["checksum_match"] is True
