import hashlib
import importlib
import json
from pathlib import Path


meter_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
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


def test_preview_computes_files_count_bytes_hash(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_file = tmp_path / "dlp" / "meter_cleanup_preview.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_file))

    p1 = _payload("req-1", tenant="all")
    _write_json(data_dir / "meters_index.json", {"req-1": p1})
    _write_json(data_dir / "meters_all.json", [p1])
    meter_v2.upsert_meter(p1)

    preview = meter_cleanup_preview.build_preview()
    assert preview["schema_version"] == "res-legacy-meter-cleanup-preview-v1"
    assert preview["mode"] == "preview_only"
    assert preview["cleanup_allowed"] is False
    assert preview["backup_export_required"] is True
    assert preview["operator_approval_required"] is True
    assert preview["summary"]["legacy_file_count"] >= 2
    assert preview["summary"]["candidate_file_count"] >= 2
    assert preview["estimated_reclaim_bytes"] > 0
    assert len(preview["would_cleanup_files"]) >= 2
    assert all(item.get("sha256") for item in preview["would_cleanup_files"])


def test_preview_blocks_when_parity_failed(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_file = tmp_path / "dlp" / "meter_cleanup_preview.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_file))

    p1 = _payload("req-mismatch")
    _write_json(data_dir / "meters_index.json", {"req-mismatch": p1})
    # sqlite intentionally not written => parity fails
    preview = meter_cleanup_preview.build_preview()
    assert preview["cleanup_allowed"] is False
    assert "parity_not_passed" in preview["blocking_reasons"]
    assert "critical_mismatch_nonzero" in preview["blocking_reasons"]


def test_preview_blocks_when_backup_export_not_completed(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_file = tmp_path / "dlp" / "meter_cleanup_preview.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_file))

    p1 = _payload("req-1")
    _write_json(data_dir / "meters_index.json", {"req-1": p1})
    meter_v2.upsert_meter(p1)

    preview = meter_cleanup_preview.build_preview()
    assert preview["cleanup_allowed"] is False
    assert "backup_export_required" in preview["blocking_reasons"]
    assert "operator_approval_required" in preview["blocking_reasons"]


def test_rebuild_preview_does_not_mutate_legacy_meter_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_file = tmp_path / "dlp" / "meter_cleanup_preview.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_file))

    p1 = _payload("req-1")
    index_file = data_dir / "meters_index.json"
    tenant_file = data_dir / "meters_all.json"
    _write_json(index_file, {"req-1": p1})
    _write_json(tenant_file, [p1])
    meter_v2.upsert_meter(p1)

    before = {
        "index_sha": _sha256(index_file),
        "tenant_sha": _sha256(tenant_file),
        "index_mtime": index_file.stat().st_mtime_ns,
        "tenant_mtime": tenant_file.stat().st_mtime_ns,
    }

    record, preview = meter_cleanup_preview.rebuild_preview()
    assert record["trigger"] == "meter_cleanup_preview_rebuild"
    assert preview["cleanup_allowed"] is False
    assert preview_file.exists()

    after = {
        "index_sha": _sha256(index_file),
        "tenant_sha": _sha256(tenant_file),
        "index_mtime": index_file.stat().st_mtime_ns,
        "tenant_mtime": tenant_file.stat().st_mtime_ns,
    }
    assert before == after
