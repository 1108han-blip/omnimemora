"""RES storage-governance invariants for RES-001..RES-006 closeout freeze."""

from __future__ import annotations

import importlib
import json

meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")
data_lifecycle_api = importlib.import_module("5_connectors.adapter.data_lifecycle_api")


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


def _write_legacy_index(data_dir, rows: dict[str, dict]):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "meters_index.json").write_text(json.dumps(rows), encoding="utf-8")


def test_res_switch_flags_are_visible_and_sqlite_first_by_default(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_path))

    _write_legacy_index(data_dir, {"req-1": _payload("req-1")})
    status = meter_storage_v2.get_status_payload()
    read_path = status["read_path"]

    assert read_path["request_meter_switch_enabled"] is True
    assert read_path["request_evidence_switch_enabled"] is True
    assert read_path["metrics_switch_enabled"] is True
    assert read_path["status_read_model_switch_enabled"] is True
    assert read_path["legacy_fallback_enabled"] is True
    assert read_path["request_meter_read_mode"] == "sqlite_first_legacy_fallback"
    assert read_path["request_evidence_read_mode"] == "sqlite_first_legacy_fallback"
    assert read_path["metrics_read_mode"] == "sqlite_first_legacy_fallback"
    assert read_path["status_read_model_read_mode"] == "sqlite_first_legacy_fallback"
    assert read_path["cleanup_eligibility"] in {"not_started", "readiness_only"}
    assert read_path["cleanup_eligibility"] == "readiness_only"


def test_meter_storage_parity_exposes_critical_mismatch_count(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_path))
    _write_legacy_index(data_dir, {"req-1": _payload("req-1")})

    parity = meter_storage_v2.build_parity_report()
    assert "critical_mismatch_count" in parity
    assert isinstance(parity["critical_mismatch_count"], int)


def test_no_meter_legacy_cleanup_delete_truncate_compress_endpoints_exist():
    router = data_lifecycle_api.router
    forbidden = [
        "/data-lifecycle/meter-storage/delete",
        "/data-lifecycle/meter-storage/move",
        "/data-lifecycle/meter-storage/truncate",
        "/data-lifecycle/meter-storage/compress",
        "/data-lifecycle/meter-storage/backup-export/execute",
        "/data-lifecycle/meter-storage/backup-export/copy",
        "/data-lifecycle/meter-storage/backup-export/archive",
        "/data-lifecycle/meter-storage/backup-export/delete",
        "/data-lifecycle/meter-storage/backup-export/move",
        "/data-lifecycle/meter-storage/backup-export/compress",
        "/data-lifecycle/meter-storage/backup-export/truncate",
        "/data-lifecycle/meter-storage/backup-export/plan/execute",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/execute",
        "/data-lifecycle/meter-storage/backup-export/approval-template/execute",
        "/data-lifecycle/meter-storage/backup-export/execution/gate/execute",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/execute",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/run",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/copy",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/archive",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/cleanup",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/delete",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/move",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/compress",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/truncate",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/execute",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/full-export",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/cleanup",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/delete",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/move",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/compress",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/truncate",
        "/data-lifecycle/meter-storage/backup-export/operator-approval/create",
        "/data-lifecycle/meter-storage/backup-export/operator-approval/approve",
        "/data-lifecycle/meter-storage/cleanup/execute",
        "/data-lifecycle/meter-storage/cleanup/delete",
        "/data-lifecycle/meter-storage/cleanup/move",
        "/data-lifecycle/meter-storage/cleanup/compress",
        "/data-lifecycle/meter-storage/cleanup/truncate",
    ]
    all_paths = {getattr(route, "path", "") for route in router.routes}
    found = [path for path in forbidden if path in all_paths]
    assert not found, f"Forbidden meter legacy cleanup endpoints found: {found}"
