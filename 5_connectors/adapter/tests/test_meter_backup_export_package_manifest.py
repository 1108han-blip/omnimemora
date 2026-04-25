import hashlib
import importlib
import json
from pathlib import Path


cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _payload(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "tenant": "all",
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed(tmp_path, monkeypatch, *, set_destination: bool = False):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    cleanup_preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    backup_readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    backup_plan_path = tmp_path / "dlp" / "meter_backup_export_plan.json"
    package_manifest_path = tmp_path / "dlp" / "meter_backup_export_package_manifest.json"
    destination = tmp_path / "dest-not-created"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(cleanup_preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(backup_readiness_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE", str(backup_plan_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PACKAGE_MANIFEST_FILE", str(package_manifest_path))
    if set_destination:
        destination.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION", str(destination))
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
    backup_plan.rebuild_plan()
    return {
        "index_file": index_file,
        "tenant_file": tenant_file,
        "backup_plan_path": backup_plan_path,
        "package_manifest_path": package_manifest_path,
        "destination": destination,
    }


def test_package_manifest_builds_from_res012_plan(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    manifest = package_manifest.build_package_manifest()
    assert manifest["schema_version"] == "res-legacy-meter-backup-export-package-manifest-v1"
    assert manifest["mode"] == "package_manifest_preview_only"
    assert manifest["backup_export_allowed"] is False
    assert manifest["cleanup_allowed"] is False
    assert manifest["execution_allowed"] is False
    assert manifest["source_plan_hash"]
    assert manifest["source_readiness_hash"]
    assert manifest["source_cleanup_preview_hash"]
    assert len(manifest["would_export_files"]) >= 2
    assert manifest["summary"]["file_count"] == len(manifest["would_export_files"])
    assert manifest["summary"]["total_bytes"] == manifest["total_bytes"]


def test_package_manifest_blocks_when_plan_missing(tmp_path, monkeypatch):
    paths = _seed(tmp_path, monkeypatch)
    paths["backup_plan_path"].unlink()
    manifest = package_manifest.build_package_manifest()
    assert "backup_export_plan_missing" in manifest["blocking_reasons"]
    assert manifest["backup_export_allowed"] is False
    assert manifest["cleanup_allowed"] is False
    assert manifest["execution_allowed"] is False


def test_package_manifest_rebuild_does_not_mutate_legacy_or_destination(tmp_path, monkeypatch):
    paths = _seed(tmp_path, monkeypatch)
    before = {
        "index_sha": _sha(paths["index_file"]),
        "tenant_sha": _sha(paths["tenant_file"]),
        "index_mtime": paths["index_file"].stat().st_mtime_ns,
        "tenant_mtime": paths["tenant_file"].stat().st_mtime_ns,
        "destination_exists": paths["destination"].exists(),
    }
    record, manifest = package_manifest.rebuild_package_manifest()
    assert record["trigger"] == "meter_backup_export_package_manifest_rebuild"
    assert manifest["mode"] == "package_manifest_preview_only"
    assert paths["package_manifest_path"].exists()
    after = {
        "index_sha": _sha(paths["index_file"]),
        "tenant_sha": _sha(paths["tenant_file"]),
        "index_mtime": paths["index_file"].stat().st_mtime_ns,
        "tenant_mtime": paths["tenant_file"].stat().st_mtime_ns,
        "destination_exists": paths["destination"].exists(),
    }
    assert before == after

