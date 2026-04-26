import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
stability_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_stability_window")


def _disable_runtime_http(monkeypatch):
    monkeypatch.setattr(stability_mod, "_read_runtime_json", lambda path, timeout_seconds=None: None)


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "dlp" / "maintenance_state.jsonl"),
        meter_cleanup_pilot_record_file=str(tmp_path / "dlp" / "meter_cleanup_pilot_record.json"),
        meter_cleanup_rollback_drill_file=str(tmp_path / "dlp" / "meter_cleanup_rollback_drill.json"),
        meter_backup_export_restore_readback_file=str(tmp_path / "dlp" / "meter_backup_export_restore_readback.json"),
        meter_cleanup_stability_window_file=str(tmp_path / "dlp" / "meter_cleanup_stability_window.json"),
    )


def test_stability_window_blocks_when_pilot_missing(tmp_path, monkeypatch):
    _disable_runtime_http(monkeypatch)
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(stability_mod._cleanup_pilot, "read_latest_pilot", lambda policy=None: None)
    monkeypatch.setattr(
        stability_mod._meter_storage_v2,
        "build_parity_report",
        lambda: {"status": "passed", "critical_mismatch_count": 0},
    )
    monkeypatch.setattr(
        stability_mod._restore_readback,
        "read_restore_readback_report",
        lambda policy=None: {
            "status": "passed",
            "source_retained": True,
            "backup_copy_readable": True,
            "checksum_match": True,
            "production_restore_started": False,
            "cleanup_started": False,
        },
    )
    monkeypatch.setattr(
        stability_mod._rollback_drill,
        "read_rollback_drill_report",
        lambda policy=None: {
            "status": "passed",
            "staging_restore_readable": True,
            "checksum_match": True,
            "production_restore_started": False,
            "cleanup_started": False,
        },
    )
    monkeypatch.setattr(
        stability_mod,
        "_run_smoke_sampling",
        lambda request_id=None: {"status": "passed", "sample_count_per_endpoint": 20},
    )

    report = stability_mod.build_stability_window_report(policy=policy)
    assert report["status"] == "blocked"
    assert "cleanup_pilot_missing" in report["blocking_reasons"]
    assert report["cleanup_scope_expansion_started"] is False


def test_stability_window_passes_with_expected_single_pilot(tmp_path, monkeypatch):
    _disable_runtime_http(monkeypatch)
    policy = _build_policy(tmp_path)
    original_path = tmp_path / "meter_data" / "meters_phase2-meter-dir.json"
    quarantine_path = tmp_path / "dlp" / "quarantine" / "meter_cleanup" / "meters_phase2-meter-dir.json.quarantine"
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"request_id": "phase2-meter-dir", "saved_tokens_estimate": 123}
    quarantine_path.write_text(json.dumps(payload), encoding="utf-8")
    source_sha = stability_mod._sha256_file(quarantine_path)

    monkeypatch.setattr(
        stability_mod._cleanup_pilot,
        "read_latest_pilot",
        lambda policy=None: {
            "status": "success",
            "source_move_executed": True,
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
            "original_path": str(original_path),
            "quarantine_path": str(quarantine_path),
            "quarantine_sha256_after": source_sha,
        },
    )
    monkeypatch.setattr(
        stability_mod._meter_storage_v2,
        "build_parity_report",
        lambda: {"status": "passed", "critical_mismatch_count": 0},
    )
    monkeypatch.setattr(
        stability_mod._restore_readback,
        "read_restore_readback_report",
        lambda policy=None: {
            "status": "passed",
            "source_retained": True,
            "backup_copy_readable": True,
            "checksum_match": True,
            "production_restore_started": False,
            "cleanup_started": False,
        },
    )
    monkeypatch.setattr(
        stability_mod._rollback_drill,
        "read_rollback_drill_report",
        lambda policy=None: {
            "status": "passed",
            "staging_restore_readable": True,
            "checksum_match": True,
            "production_restore_started": False,
            "cleanup_started": False,
        },
    )
    monkeypatch.setattr(
        stability_mod,
        "_run_smoke_sampling",
        lambda request_id=None: {
            "status": "passed",
            "sample_count_per_endpoint": 20,
            "total_error_count": 0,
            "total_timeout_count": 0,
        },
    )

    report = stability_mod.build_stability_window_report(policy=policy)
    assert report["status"] == "passed"
    assert report["observed_pilot_status"] == "success"
    assert report["cleanup_scope_expansion_started"] is False
    assert report["parity_summary"]["critical_mismatch_count"] == 0
    assert report["smoke_results"]["status"] == "passed"
    assert report["blocking_reasons"] == []


def test_stability_window_blocks_on_parity_mismatch(tmp_path, monkeypatch):
    _disable_runtime_http(monkeypatch)
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        stability_mod._cleanup_pilot,
        "read_latest_pilot",
        lambda policy=None: {
            "status": "success",
            "source_move_executed": True,
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
            "original_path": str(tmp_path / "meter_data" / "meters_phase2-meter-dir.json"),
            "quarantine_path": str(tmp_path / "q" / "moved.json"),
            "quarantine_sha256_after": None,
        },
    )
    monkeypatch.setattr(
        stability_mod._meter_storage_v2,
        "build_parity_report",
        lambda: {"status": "degraded", "critical_mismatch_count": 2},
    )
    monkeypatch.setattr(
        stability_mod._restore_readback,
        "read_restore_readback_report",
        lambda policy=None: {"status": "passed", "source_retained": True, "backup_copy_readable": True, "checksum_match": True},
    )
    monkeypatch.setattr(
        stability_mod._rollback_drill,
        "read_rollback_drill_report",
        lambda policy=None: {"status": "passed", "staging_restore_readable": True, "checksum_match": True},
    )
    monkeypatch.setattr(stability_mod, "_run_smoke_sampling", lambda request_id=None: {"status": "passed"})

    report = stability_mod.build_stability_window_report(policy=policy)
    assert report["status"] == "blocked"
    assert "parity_not_passed" in report["blocking_reasons"]


def test_stability_window_blocks_on_restore_or_rollback_failure(tmp_path, monkeypatch):
    _disable_runtime_http(monkeypatch)
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        stability_mod._cleanup_pilot,
        "read_latest_pilot",
        lambda policy=None: {
            "status": "success",
            "source_move_executed": True,
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
            "original_path": str(tmp_path / "meter_data" / "meters_phase2-meter-dir.json"),
            "quarantine_path": str(tmp_path / "q" / "meters_phase2-meter-dir.json.quarantine"),
            "quarantine_sha256_after": None,
        },
    )
    monkeypatch.setattr(
        stability_mod._meter_storage_v2,
        "build_parity_report",
        lambda: {"status": "passed", "critical_mismatch_count": 0},
    )
    monkeypatch.setattr(
        stability_mod._restore_readback,
        "read_restore_readback_report",
        lambda policy=None: {
            "status": "blocked",
            "source_retained": True,
            "backup_copy_readable": False,
            "checksum_match": False,
            "production_restore_started": False,
            "cleanup_started": False,
        },
    )
    monkeypatch.setattr(
        stability_mod._rollback_drill,
        "read_rollback_drill_report",
        lambda policy=None: {
            "status": "blocked",
            "staging_restore_readable": False,
            "checksum_match": False,
            "production_restore_started": False,
            "cleanup_started": False,
        },
    )
    monkeypatch.setattr(stability_mod, "_run_smoke_sampling", lambda request_id=None: {"status": "passed"})

    report = stability_mod.build_stability_window_report(policy=policy)
    assert report["status"] == "blocked"
    assert "restore_readback_not_passed" in report["blocking_reasons"]
    assert "rollback_drill_not_passed" in report["blocking_reasons"]


def test_stability_window_rebuild_writes_report_without_creating_cleanup_pilot(tmp_path, monkeypatch):
    _disable_runtime_http(monkeypatch)
    policy = _build_policy(tmp_path)
    pilot_guard = {"called": False}

    def _read_pilot(policy=None):
        pilot_guard["called"] = True
        return None

    monkeypatch.setattr(stability_mod._cleanup_pilot, "read_latest_pilot", _read_pilot)
    monkeypatch.setattr(
        stability_mod._meter_storage_v2,
        "build_parity_report",
        lambda: {"status": "passed", "critical_mismatch_count": 0},
    )
    monkeypatch.setattr(stability_mod._restore_readback, "read_restore_readback_report", lambda policy=None: None)
    monkeypatch.setattr(stability_mod._rollback_drill, "read_rollback_drill_report", lambda policy=None: None)
    monkeypatch.setattr(stability_mod, "_run_smoke_sampling", lambda request_id=None: {"status": "failed"})

    record, report = stability_mod.rebuild_stability_window_report(policy=policy)
    assert record["trigger"] == "meter_cleanup_stability_window_rebuild"
    assert report["schema_version"] == "res-legacy-meter-cleanup-stability-window-v1"
    assert pilot_guard["called"] is True
    assert Path(policy.meter_cleanup_stability_window_file).exists()
