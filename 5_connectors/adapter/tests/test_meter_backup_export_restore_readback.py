import hashlib
import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
approval_template = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template")
execution_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate")
copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")
restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _payload(request_id: str, query: str) -> dict:
    return {
        "request_id": request_id,
        "tenant": "all",
        "agent": "openclaw",
        "family_id": "openclaw",
        "timestamp": "2026-04-26T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 100,
        "savings_ratio": 0.1,
        "query": query,
    }


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_policy(tmp_path, destination: Path):
    return policy_mod.DataLifecyclePolicy(
        summary_file=str(tmp_path / "dlp" / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "dlp" / "maintenance_state.jsonl"),
        meter_cleanup_preview_file=str(tmp_path / "dlp" / "meter_cleanup_preview.json"),
        meter_backup_export_readiness_file=str(tmp_path / "dlp" / "meter_backup_export_readiness.json"),
        meter_backup_export_plan_file=str(tmp_path / "dlp" / "meter_backup_export_plan.json"),
        meter_backup_export_package_manifest_file=str(tmp_path / "dlp" / "meter_backup_export_package_manifest.json"),
        meter_backup_export_approval_template_file=str(tmp_path / "dlp" / "meter_backup_export_approval_template.json"),
        meter_backup_export_execution_gate_file=str(tmp_path / "dlp" / "meter_backup_export_execution_gate.json"),
        meter_backup_export_operator_approval_file=str(tmp_path / "dlp" / "meter_backup_export_operator_approval.json"),
        meter_backup_export_execution_proposal_file=str(tmp_path / "dlp" / "meter_backup_export_execution_proposal.json"),
        meter_backup_export_copy_pilot_root=str(tmp_path / "dlp" / "backup_export" / "pilot"),
        meter_backup_export_copy_pilot_record_file=str(tmp_path / "dlp" / "meter_backup_export_copy_pilot_record.json"),
        meter_backup_export_restore_readback_file=str(tmp_path / "dlp" / "meter_backup_export_restore_readback.json"),
        meter_backup_export_copy_pilot_allow_override=True,
        meter_backup_export_destination=str(destination),
    )


def _seed_copy_pilot(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    destination = tmp_path / "backup_destination"
    destination.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))

    policy = _build_policy(tmp_path, destination)
    p1 = _payload("req-1", "a")
    p2 = _payload("req-2", "larger-query")
    index_file = data_dir / "meters_index.json"
    tenant_file = data_dir / "meters_all.json"
    _write_json(index_file, {"req-1": p1, "req-2": p2})
    _write_json(tenant_file, [p1, p2])
    meter_v2.upsert_meter(p1)
    meter_v2.upsert_meter(p2)
    cleanup_preview.rebuild_preview(policy=policy)
    backup_readiness.rebuild_readiness(policy=policy)
    backup_plan.rebuild_plan(policy=policy)
    package_manifest.rebuild_package_manifest(policy=policy)
    approval_template.rebuild_approval_template(policy=policy)
    execution_gate.rebuild_gate(policy=policy)
    _record, pilot = copy_pilot.run_one_copy_pilot(policy=policy)
    return policy, pilot


def test_restore_readback_blocks_when_copy_pilot_missing(tmp_path):
    policy = _build_policy(tmp_path, tmp_path / "backup_destination")
    report = restore_readback.build_restore_readback_report(policy=policy)
    assert report["status"] == "blocked"
    assert "copy_pilot_missing" in report["blocking_reasons"]
    assert report["production_restore_started"] is False
    assert report["cleanup_started"] is False


def test_restore_readback_passes_for_copy_pilot_and_keeps_source_retained(tmp_path, monkeypatch):
    policy, pilot = _seed_copy_pilot(tmp_path, monkeypatch)
    source = Path(str((pilot["selected_candidate"] or {})["path"]))
    before_sha = _sha(source)
    before_mtime = source.stat().st_mtime_ns

    record, report = restore_readback.rebuild_restore_readback_report(policy=policy)
    assert record["trigger"] == "meter_backup_export_restore_readback_rebuild"
    assert report["schema_version"] == "res-legacy-meter-backup-export-restore-readback-v1"
    assert report["mode"] == "restore_readback_validation_only"
    assert report["status"] == "passed"
    assert report["source_retained"] is True
    assert report["source_readable"] is True
    assert report["backup_copy_readable"] is True
    assert report["checksum_match"] is True
    assert report["expected_hash_match"] is True
    assert report["bytes_match"] is True
    assert report["read_path_unchanged"] is True
    assert report["production_restore_started"] is False
    assert report["cleanup_started"] is False

    assert _sha(source) == before_sha
    assert source.stat().st_mtime_ns == before_mtime


def test_restore_readback_blocks_when_backup_copy_is_corrupted(tmp_path, monkeypatch):
    policy, pilot = _seed_copy_pilot(tmp_path, monkeypatch)
    target = Path(str(pilot["target_path"]))
    target.write_text("corrupted", encoding="utf-8")

    report = restore_readback.build_restore_readback_report(policy=policy)
    assert report["status"] == "blocked"
    assert "checksum_mismatch" in report["blocking_reasons"]
    assert "copy_pilot_hash_mismatch" in report["blocking_reasons"]
    assert report["checksum_match"] is False


def test_restore_readback_blocks_when_copy_pilot_hashes_are_missing(tmp_path, monkeypatch):
    policy, pilot = _seed_copy_pilot(tmp_path, monkeypatch)
    pilot.pop("source_sha256", None)
    pilot.pop("copied_sha256", None)
    _write_json(Path(policy.meter_backup_export_copy_pilot_record_file), pilot)

    report = restore_readback.build_restore_readback_report(policy=policy)

    assert report["status"] == "blocked"
    assert "copy_pilot_hash_missing" in report["blocking_reasons"]
    assert "copy_pilot_hash_mismatch" in report["blocking_reasons"]
    assert report["checksum_match"] is True
    assert report["expected_hash_match"] is False
    assert report["production_restore_started"] is False
    assert report["cleanup_started"] is False


def test_restore_readback_blocks_when_source_missing(tmp_path, monkeypatch):
    policy, pilot = _seed_copy_pilot(tmp_path, monkeypatch)
    source = Path(str((pilot["selected_candidate"] or {})["path"]))
    source.unlink()

    report = restore_readback.build_restore_readback_report(policy=policy)
    assert report["status"] == "blocked"
    assert "source_not_readable" in report["blocking_reasons"]
    assert report["source_retained"] is False


def test_restore_readback_read_latest_returns_written_report(tmp_path, monkeypatch):
    policy, _pilot = _seed_copy_pilot(tmp_path, monkeypatch)
    _record, report = restore_readback.rebuild_restore_readback_report(policy=policy)
    latest = restore_readback.read_restore_readback_report(policy=policy)
    assert latest is not None
    assert latest["report_id"] == report["report_id"]


def test_restore_readback_passes_using_quarantine_source_after_cleanup_pilot_move(tmp_path, monkeypatch):
    policy, pilot = _seed_copy_pilot(tmp_path, monkeypatch)
    source = Path(str((pilot["selected_candidate"] or {})["path"]))
    quarantine = tmp_path / "dlp" / "quarantine" / source.name
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    shutil_payload = source.read_text(encoding="utf-8")
    quarantine.write_text(shutil_payload, encoding="utf-8")
    source.unlink()

    cleanup_pilot_record = {
        "status": "success",
        "source_move_executed": True,
        "original_path": str(source),
        "quarantine_path": str(quarantine),
    }
    monkeypatch.setattr(restore_readback._cleanup_pilot, "read_latest_pilot", lambda policy=None: cleanup_pilot_record)

    report = restore_readback.build_restore_readback_report(policy=policy)
    assert report["status"] == "passed"
    assert report["source_readable"] is True
    assert report["source_retained"] is False
    assert report["source_verification_mode"] == "quarantine"
    assert report["checksum_match"] is True
