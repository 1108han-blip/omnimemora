import hashlib
import importlib
import json
from pathlib import Path


meter_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
meter_backup_export = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
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


def _seed_cleanup_preview(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    cleanup_preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    backup_readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(cleanup_preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(backup_readiness_path))

    p1 = _payload("req-1")
    p2 = _payload("req-2")
    _write_json(data_dir / "meters_index.json", {"req-1": p1, "req-2": p2})
    _write_json(data_dir / "meters_all.json", [p1, p2])
    meter_v2.upsert_meter(p1)
    meter_v2.upsert_meter(p2)
    meter_cleanup_preview.rebuild_preview()
    return data_dir, backup_readiness_path


def test_builds_manifest_preview_from_cleanup_candidates(tmp_path, monkeypatch):
    _data_dir, _backup_readiness_path = _seed_cleanup_preview(tmp_path, monkeypatch)
    readiness = meter_backup_export.build_readiness()
    assert readiness["schema_version"] == "res-legacy-meter-backup-export-readiness-v1"
    assert readiness["mode"] == "backup_export_readiness_only"
    assert readiness["checksum_algorithm"] == "sha256"
    assert readiness["backup_export_allowed"] is False
    assert readiness["cleanup_allowed"] is False
    assert len(readiness["would_export_files"]) >= 2
    assert readiness["export_manifest_preview"]["file_count"] == len(readiness["would_export_files"])
    assert readiness["estimated_export_bytes"] > 0
    assert readiness["required_free_bytes"] >= readiness["estimated_export_bytes"]


def test_blocks_when_cleanup_preview_missing(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    cleanup_preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    backup_readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(cleanup_preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(backup_readiness_path))
    p1 = _payload("req-1")
    _write_json(data_dir / "meters_index.json", {"req-1": p1})
    meter_v2.upsert_meter(p1)

    readiness = meter_backup_export.build_readiness()
    assert readiness["backup_export_allowed"] is False
    assert readiness["cleanup_allowed"] is False
    assert "cleanup_preview_missing" in readiness["blocking_reasons"]


def test_blocks_when_parity_not_passed(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    cleanup_preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    backup_readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(cleanup_preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(backup_readiness_path))

    p1 = _payload("req-1")
    _write_json(data_dir / "meters_index.json", {"req-1": p1})
    # sqlite intentionally missing, parity fails
    meter_cleanup_preview.rebuild_preview()
    readiness = meter_backup_export.build_readiness()
    assert readiness["backup_export_allowed"] is False
    assert readiness["cleanup_allowed"] is False
    assert "parity_not_passed" in readiness["blocking_reasons"]
    assert "critical_mismatch_nonzero" in readiness["blocking_reasons"]


def test_rebuild_does_not_mutate_legacy_files(tmp_path, monkeypatch):
    data_dir, backup_readiness_path = _seed_cleanup_preview(tmp_path, monkeypatch)
    index_file = data_dir / "meters_index.json"
    tenant_file = data_dir / "meters_all.json"
    before = {
        "index_sha": _sha256(index_file),
        "tenant_sha": _sha256(tenant_file),
        "index_mtime": index_file.stat().st_mtime_ns,
        "tenant_mtime": tenant_file.stat().st_mtime_ns,
    }
    record, readiness = meter_backup_export.rebuild_readiness()
    assert record["trigger"] == "meter_backup_export_readiness_rebuild"
    assert readiness["backup_export_allowed"] is False
    assert readiness["cleanup_allowed"] is False
    assert backup_readiness_path.exists()
    after = {
        "index_sha": _sha256(index_file),
        "tenant_sha": _sha256(tenant_file),
        "index_mtime": index_file.stat().st_mtime_ns,
        "tenant_mtime": tenant_file.stat().st_mtime_ns,
    }
    assert before == after
