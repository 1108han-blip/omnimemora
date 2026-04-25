import hashlib
import importlib
import json
from pathlib import Path


cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
approval_template = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template")
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


def _seed(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    cleanup_preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    backup_readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    backup_plan_path = tmp_path / "dlp" / "meter_backup_export_plan.json"
    package_manifest_path = tmp_path / "dlp" / "meter_backup_export_package_manifest.json"
    approval_template_path = tmp_path / "dlp" / "meter_backup_export_approval_template.json"
    dest_dir = tmp_path / "backup_dest"
    dest_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(cleanup_preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(backup_readiness_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE", str(backup_plan_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PACKAGE_MANIFEST_FILE", str(package_manifest_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_FILE", str(approval_template_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION", str(dest_dir))

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
    package_manifest.rebuild_package_manifest()
    return {
        "index_file": index_file,
        "tenant_file": tenant_file,
        "approval_template_path": approval_template_path,
    }


def test_approval_template_is_template_only_and_invalid_by_default(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    template = approval_template.build_approval_template()
    assert template["schema_version"] == "res-legacy-meter-backup-export-approval-template-v1"
    assert template["mode"] == "approval_template_only"
    assert template["approval_valid"] is False
    assert template["backup_export_allowed"] is False
    assert template["cleanup_allowed"] is False
    assert template["execution_allowed"] is False
    assert template["approved_plan_hash"]
    assert template["approved_readiness_hash"]
    assert template["approved_cleanup_preview_hash"]
    assert template["approved_package_manifest_hash"]
    assert template["operator_id"] is None
    assert template["approved_at"] is None
    assert "approval_template_only" in template["blocking_reasons"]


def test_approval_template_records_missing_package_manifest_block(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    manifest_path = tmp_path / "dlp" / "meter_backup_export_package_manifest.json"
    manifest_path.unlink()
    template = approval_template.build_approval_template()
    assert "backup_export_package_manifest_missing" in template["blocking_reasons"]
    assert template["approval_valid"] is False


def test_approval_template_rebuild_does_not_mutate_legacy_files(tmp_path, monkeypatch):
    paths = _seed(tmp_path, monkeypatch)
    before = {
        "index_sha": _sha(paths["index_file"]),
        "tenant_sha": _sha(paths["tenant_file"]),
        "index_mtime": paths["index_file"].stat().st_mtime_ns,
        "tenant_mtime": paths["tenant_file"].stat().st_mtime_ns,
    }
    record, template = approval_template.rebuild_approval_template()
    assert record["trigger"] == "meter_backup_export_approval_template_rebuild"
    assert template["approval_valid"] is False
    assert paths["approval_template_path"].exists()
    after = {
        "index_sha": _sha(paths["index_file"]),
        "tenant_sha": _sha(paths["tenant_file"]),
        "index_mtime": paths["index_file"].stat().st_mtime_ns,
        "tenant_mtime": paths["tenant_file"].stat().st_mtime_ns,
    }
    assert before == after

