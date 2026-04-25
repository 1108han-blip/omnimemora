import hashlib
import importlib
import json
from pathlib import Path


cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _payload(request_id: str, tenant: str = "all") -> dict:
    return {
        "request_id": request_id,
        "tenant": tenant,
        "agent": "openclaw",
        "family_id": "openclaw",
        "timestamp": "2026-04-25T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 100,
        "savings_ratio": 0.1,
        "query": "hello",
    }


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _seed(tmp_path, monkeypatch, *, set_destination: bool = True):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    cleanup_preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    backup_readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    backup_plan_path = tmp_path / "dlp" / "meter_backup_export_plan.json"
    dest_dir = tmp_path / "backup_dest"
    dest_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(cleanup_preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(backup_readiness_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE", str(backup_plan_path))
    if set_destination:
        monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION", str(dest_dir))
    else:
        monkeypatch.delenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION", raising=False)

    p1 = _payload("req-1")
    p2 = _payload("req-2")
    index_file = data_dir / "meters_index.json"
    tenant_file = data_dir / "meters_all.json"
    _write_json(index_file, {"req-1": p1, "req-2": p2})
    _write_json(tenant_file, [p1, p2])
    meter_v2.upsert_meter(p1)
    meter_v2.upsert_meter(p2)
    cleanup_preview.rebuild_preview()
    backup_readiness.rebuild_readiness()
    return {
        "data_dir": data_dir,
        "index_file": index_file,
        "tenant_file": tenant_file,
        "backup_plan_path": backup_plan_path,
        "dest_dir": dest_dir,
    }


def test_plan_builds_from_readiness_and_cleanup_preview(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, set_destination=True)
    plan = backup_plan.build_plan()
    assert plan["schema_version"] == "res-legacy-meter-backup-export-plan-v1"
    assert plan["mode"] == "dry_run_preview_only"
    assert plan["backup_export_allowed"] is False
    assert plan["cleanup_allowed"] is False
    assert plan["execution_allowed"] is False
    assert len(plan["would_export_files"]) >= 2
    assert plan["estimated_export_bytes"] > 0
    assert plan["source_readiness_hash"]
    assert plan["source_cleanup_preview_hash"]


def test_missing_readiness_blocks(tmp_path, monkeypatch):
    paths = _seed(tmp_path, monkeypatch, set_destination=True)
    # Remove readiness artifact to simulate missing.
    readiness_file = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    readiness_file.unlink()
    plan = backup_plan.build_plan()
    assert "backup_export_readiness_missing" in plan["blocking_reasons"]
    assert plan["backup_export_allowed"] is False
    assert plan["cleanup_allowed"] is False
    assert plan["execution_allowed"] is False
    assert paths["backup_plan_path"].exists() is False


def test_destination_unset_blocks_with_backup_destination_not_selected(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, set_destination=False)
    plan = backup_plan.build_plan()
    assert "backup_destination_not_selected" in plan["blocking_reasons"]
    assert "free_space_not_verified" in plan["blocking_reasons"]


def test_insufficient_free_space_blocks(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, set_destination=True)
    # Inflate required free bytes in readiness artifact.
    readiness = backup_readiness.read_readiness()
    assert isinstance(readiness, dict)
    readiness["required_free_bytes"] = 10**18
    backup_readiness.write_readiness_atomic(readiness)
    plan = backup_plan.build_plan()
    assert "free_space_not_verified" in plan["blocking_reasons"]


def test_parity_mismatch_blocks(tmp_path, monkeypatch):
    paths = _seed(tmp_path, monkeypatch, set_destination=True)
    # Create legacy/sqlite mismatch after readiness build.
    p3 = _payload("req-3")
    payload = json.loads(paths["index_file"].read_text(encoding="utf-8"))
    payload["req-3"] = p3
    paths["index_file"].write_text(json.dumps(payload), encoding="utf-8")
    plan = backup_plan.build_plan()
    assert "parity_not_passed" in plan["blocking_reasons"]


def test_rebuild_writes_only_plan_and_does_not_mutate_legacy_files(tmp_path, monkeypatch):
    paths = _seed(tmp_path, monkeypatch, set_destination=True)
    before = {
        "index_sha": _sha256(paths["index_file"]),
        "tenant_sha": _sha256(paths["tenant_file"]),
        "index_mtime": paths["index_file"].stat().st_mtime_ns,
        "tenant_mtime": paths["tenant_file"].stat().st_mtime_ns,
    }
    record, plan = backup_plan.rebuild_plan()
    assert record["trigger"] == "meter_backup_export_plan_rebuild"
    assert plan["mode"] == "dry_run_preview_only"
    assert paths["backup_plan_path"].exists()
    after = {
        "index_sha": _sha256(paths["index_file"]),
        "tenant_sha": _sha256(paths["tenant_file"]),
        "index_mtime": paths["index_file"].stat().st_mtime_ns,
        "tenant_mtime": paths["tenant_file"].stat().st_mtime_ns,
    }
    assert before == after
