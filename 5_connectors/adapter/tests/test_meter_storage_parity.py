import importlib
import json


meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")


def _payload(request_id: str, saved_tokens: int = 100) -> dict:
    return {
        "request_id": request_id,
        "tenant": "all",
        "agent": "claude_code",
        "family_id": "claude_code",
        "timestamp": "2026-04-25T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": saved_tokens,
        "savings_ratio": 0.1,
        "query": "hello",
    }


def _write_legacy_index(data_dir, rows: dict[str, dict]):
    data_dir.mkdir(parents=True, exist_ok=True)
    index_path = data_dir / "meters_index.json"
    index_path.write_text(json.dumps(rows), encoding="utf-8")


def test_parity_report_passes_when_legacy_and_sqlite_match(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    plan_path = tmp_path / "dlp" / "meter_backup_export_plan.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(readiness_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE", str(plan_path))

    payload = _payload("req-match")
    _write_legacy_index(data_dir, {"req-match": payload})
    meter_v2.upsert_meter(payload)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "passed"
    assert report["critical_mismatch_count"] == 0
    assert report["matching_request_id_count"] == 1


def test_parity_report_detects_missing_and_hash_mismatch(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    plan_path = tmp_path / "dlp" / "meter_backup_export_plan.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(readiness_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE", str(plan_path))

    legacy_a = _payload("req-a", saved_tokens=100)
    legacy_b = _payload("req-b", saved_tokens=200)
    _write_legacy_index(data_dir, {"req-a": legacy_a, "req-b": legacy_b})

    sqlite_a = _payload("req-a", saved_tokens=777)  # hash mismatch
    sqlite_c = _payload("req-c", saved_tokens=300)  # missing in legacy
    meter_v2.upsert_meter(sqlite_a)
    meter_v2.upsert_meter(sqlite_c)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "degraded"
    assert report["missing_in_sqlite_count"] == 1
    assert report["missing_in_legacy_count"] == 1
    assert report["payload_hash_mismatch_count"] == 1
    assert report["critical_mismatch_count"] == 3


def test_rebuild_and_status_payload_keep_legacy_authoritative(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    preview_path = tmp_path / "dlp" / "meter_cleanup_preview.json"
    readiness_path = tmp_path / "dlp" / "meter_backup_export_readiness.json"
    plan_path = tmp_path / "dlp" / "meter_backup_export_plan.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE", str(preview_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE", str(readiness_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE", str(plan_path))

    _write_legacy_index(
        data_dir,
        {
            "req-1": _payload("req-1", saved_tokens=11),
            "req-2": _payload("req-2", saved_tokens=22),
        },
    )
    record, parity = meter_storage_v2.rebuild_from_legacy()
    status = meter_storage_v2.get_status_payload()

    assert record["non_destructive"] is True
    assert record["legacy_scanned_count"] == 2
    assert parity["critical_mismatch_count"] == 0
    assert status["read_path"]["legacy_authoritative"] is True
    assert status["read_path"]["request_meter_switch_enabled"] is True
    assert status["read_path"]["request_evidence_switch_enabled"] is True
    assert status["read_path"]["metrics_switch_enabled"] is True
    assert status["read_path"]["status_read_model_switch_enabled"] is True
    assert status["read_path"]["legacy_fallback_enabled"] is True
    assert status["read_path"]["request_meter_read_mode"] == "sqlite_first_legacy_fallback"
    assert status["read_path"]["request_evidence_read_mode"] == "sqlite_first_legacy_fallback"
    assert status["read_path"]["metrics_read_mode"] == "sqlite_first_legacy_fallback"
    assert status["read_path"]["status_read_model_read_mode"] == "sqlite_first_legacy_fallback"
    assert status["read_path"]["cleanup_eligibility"] == "readiness_only"
    assert status["cleanup"]["status"] == "missing"
    assert status["cleanup"]["mode"] == "preview_only"
    assert status["cleanup"]["cleanup_allowed"] is False
    assert status["cleanup"]["stability_window_status"] == "missing"
    assert status["cleanup"]["stability_window_observed_pilot_status"] == "missing"
    assert status["cleanup"]["stability_window_cleanup_scope_expansion_started"] is False
    assert status["cleanup"]["scaleup_readiness_status"] == "missing"
    assert status["cleanup"]["scaleup_ready"] is False
    assert status["cleanup"]["cleanup_scope_expansion_started"] is False
    assert status["backup_export"]["status"] == "missing"
    assert status["backup_export"]["mode"] == "backup_export_readiness_only"
    assert status["backup_export"]["backup_export_allowed"] is False
    assert status["backup_export"]["cleanup_allowed"] is False
    assert status["backup_export"]["execution_allowed"] is False
    assert status["backup_export"]["plan_status"] == "missing"
    assert status["backup_export"]["dry_run_mode"] == "dry_run_preview_only"
    assert status["backup_export"]["destination_status"]["status"] == "unknown"
    assert status["backup_export"]["package_manifest_status"] == "missing"
    assert status["backup_export"]["package_manifest_file_count"] == 0
    assert status["backup_export"]["package_manifest_total_bytes"] == 0
    assert status["backup_export"]["approval_template_status"] == "missing"
    assert status["backup_export"]["execution_gate_status"] == "missing"
    assert status["backup_export"]["execution_gate_allowed"] is False
    assert status["backup_export"]["approval_status"] == "missing"
    assert status["backup_export"]["execution_proposal_status"] == "missing"
    assert status["backup_export"]["operator_decision_required"] is True
    assert status["backup_export"]["copy_pilot_status"] == "missing"
    assert status["backup_export"]["copy_pilot_source_retained"] is True
    assert status["backup_export"]["copy_pilot_checksum_match"] is False
    assert status["backup_export"]["copy_pilot_cleanup_started"] is False
    assert status["backup_export"]["copy_pilot_read_path_unchanged"] is True
    assert status["backup_export"]["restore_readback_status"] == "missing"
    assert status["backup_export"]["restore_readback_source_retained"] is True
    assert status["backup_export"]["restore_readback_backup_copy_readable"] is False
    assert status["backup_export"]["restore_readback_checksum_match"] is False
    assert status["backup_export"]["restore_readback_production_restore_started"] is False
    assert status["backup_export"]["restore_readback_cleanup_started"] is False
    assert status["backup_export"]["backup_export_execution_started"] is False
    assert status["backup_export"]["cleanup_execution_started"] is False
