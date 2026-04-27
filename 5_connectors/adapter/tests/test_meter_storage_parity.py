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


def test_parity_snapshot_missing_does_not_build_full_report(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "dlp" / "meter_parity_snapshot.json"
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_PARITY_SNAPSHOT_FILE", str(snapshot_path))
    monkeypatch.setattr(
        meter_storage_v2,
        "build_parity_report",
        lambda: (_ for _ in ()).throw(AssertionError("GET snapshot read must not full-scan")),
    )

    report = meter_storage_v2.read_parity_snapshot()

    assert report["status"] == "missing"
    assert report["missing_reason"] == "snapshot_missing"
    assert report["snapshot_missing"] is True
    assert report["read_mode"] == "snapshot_first"


def test_parity_rebuild_writes_snapshot_and_get_reads_it(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    snapshot_path = tmp_path / "dlp" / "meter_parity_snapshot.json"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_PARITY_SNAPSHOT_FILE", str(snapshot_path))

    payload = _payload("req-snapshot-rebuild")
    _write_legacy_index(data_dir, {"req-snapshot-rebuild": payload})

    rebuilt = meter_storage_v2.parity_with_rebuild()
    snapshot_read = meter_storage_v2.read_parity_snapshot()

    assert snapshot_path.exists()
    assert rebuilt["snapshot"]["schema_version"] == "dlp-meter-storage-v2-parity-snapshot-v1"
    assert rebuilt["snapshot"]["hash_summary"]["critical_mismatch_count"] == 0
    assert snapshot_read["snapshot_missing"] is False
    assert snapshot_read["read_mode"] == "snapshot_first"
    assert snapshot_read["critical_mismatch_count"] == rebuilt["parity"]["critical_mismatch_count"]
    assert snapshot_read["payload_hash_mismatch_count"] == rebuilt["parity"]["payload_hash_mismatch_count"]
    assert snapshot_read["legacy_count"] == rebuilt["parity"]["legacy_count"]
    assert snapshot_read["sqlite_count"] == rebuilt["parity"]["sqlite_count"]


def test_parity_snapshot_atomic_write_failure_preserves_old_snapshot(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "dlp" / "meter_parity_snapshot.json"
    old_parity = {
        "schema_version": "dlp-meter-storage-v2-parity-v1",
        "generated_at": "2026-04-27T00:00:00+00:00",
        "mode": "dual_write_observe_only",
        "status": "passed",
        "legacy_count": 1,
        "sqlite_count": 1,
        "matching_request_id_count": 1,
        "payload_hash_mismatch_count": 0,
        "semantic_hash_mismatch_count": 0,
        "critical_payload_hash_mismatch_count": 0,
        "critical_mismatch_count": 0,
        "missing_in_sqlite_count": 0,
        "missing_in_legacy_count": 0,
        "hash_mismatch_samples": [],
        "read_path_switch_deferred": True,
        "legacy_authoritative": True,
    }
    new_parity = dict(old_parity, critical_mismatch_count=1, status="degraded")
    meter_storage_v2.write_parity_snapshot(old_parity, path=snapshot_path)
    before = snapshot_path.read_text(encoding="utf-8")

    def fail_replace(_src, _dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(meter_storage_v2.os, "replace", fail_replace)

    try:
        meter_storage_v2.write_parity_snapshot(new_parity, path=snapshot_path)
    except OSError:
        pass

    after = snapshot_path.read_text(encoding="utf-8")
    assert after == before
    assert meter_storage_v2.read_parity_snapshot(path=snapshot_path)["critical_mismatch_count"] == 0


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


def test_parity_detects_provenance_only_diff_status_passed(tmp_path, monkeypatch):
    """Provenance-only diff (e.g. sharing_policy_source) does not block parity pass.

    RES-027C: raw mismatch > 0, semantic mismatch > 0, critical mismatch = 0, status passed.
    """
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

    # Legacy: no sharing_policy_source.
    legacy_payload = {
        "request_id": "req-provenance-8e1ddda147d6",
        "tenant": "all",
        "agent": "claude_code",
        "family_id": "claude_code",
        "timestamp": "2026-04-25T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 100,
        "savings_ratio": 0.1,
        "query": "hello",
    }
    # SQLite: has sharing_policy_source (new write path provenance marker).
    sqlite_payload = dict(legacy_payload, sharing_policy_source="sqlite_v2_write")

    _write_legacy_index(data_dir, {"req-provenance-8e1ddda147d6": legacy_payload})
    meter_v2.upsert_meter(sqlite_payload)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "passed", f"expected passed, got {report['status']}"
    assert report["critical_mismatch_count"] == 0, f"critical mismatch must be 0, got {report['critical_mismatch_count']}"
    assert report["semantic_hash_mismatch_count"] == 1, f"semantic mismatch must be 1, got {report['semantic_hash_mismatch_count']}"
    assert report["critical_payload_hash_mismatch_count"] == 0, f"critical payload mismatch must be 0, got {report['critical_payload_hash_mismatch_count']}"
    assert report["payload_hash_mismatch_count"] == 1
    samples = report["hash_mismatch_samples"]
    assert len(samples) == 1
    assert samples[0]["request_id"] == "req-provenance-8e1ddda147d6"
    assert samples[0]["classification"] == "provenance_only"
    assert "sharing_policy_source" in samples[0]["noncritical_field_paths"]


def test_parity_detects_provenance_only_nested_diff_status_passed(tmp_path, monkeypatch):
    """Nested provenance-only diff (access_plan.sharing_policy_source) does not block parity."""
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

    legacy_payload = {
        "request_id": "req-nested-provenance",
        "tenant": "all",
        "agent": "claude_code",
        "family_id": "claude_code",
        "timestamp": "2026-04-25T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 100,
        "savings_ratio": 0.1,
        "query": "hello",
        "access_plan": {"mode": "efficient", "priority": "high"},
    }
    sqlite_payload = dict(
        legacy_payload,
        access_plan={
            "mode": "efficient",
            "priority": "high",
            "sharing_policy_source": "sqlite_v2_write",
        },
    )

    _write_legacy_index(data_dir, {"req-nested-provenance": legacy_payload})
    meter_v2.upsert_meter(sqlite_payload)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "passed"
    assert report["critical_mismatch_count"] == 0
    assert report["semantic_hash_mismatch_count"] == 1
    assert report["critical_payload_hash_mismatch_count"] == 0
    samples = report["hash_mismatch_samples"]
    assert samples[0]["classification"] == "provenance_only"
    assert "access_plan.sharing_policy_source" in samples[0]["noncritical_field_paths"]


def test_parity_detects_timestamp_only_diff_status_passed(tmp_path, monkeypatch):
    """Timestamp-only drift is temporal/provenance metadata, not business drift."""
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

    legacy_payload = _payload("req-timestamp-only")
    sqlite_payload = dict(legacy_payload, timestamp="2026-04-25T12:00:01+00:00")
    _write_legacy_index(data_dir, {"req-timestamp-only": legacy_payload})
    meter_v2.upsert_meter(sqlite_payload)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "passed"
    assert report["payload_hash_mismatch_count"] == 1
    assert report["semantic_hash_mismatch_count"] == 1
    assert report["critical_payload_hash_mismatch_count"] == 0
    assert report["critical_mismatch_count"] == 0
    samples = report["hash_mismatch_samples"]
    assert len(samples) == 1
    assert samples[0]["classification"] == "provenance_only"
    assert "timestamp" in samples[0]["noncritical_field_paths"]


def test_parity_detects_combined_temporal_and_provenance_diff_status_passed(tmp_path, monkeypatch):
    """RES-027D sample for timestamp + top-level/nested provenance drift."""
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

    legacy_payload = dict(
        _payload("req-combined-provenance"),
        access_plan={"mode": "efficient", "sharing_policy_source": "compile_orchestrator_private_first"},
        sharing_policy_source="compile_orchestrator_private_first",
    )
    sqlite_payload = dict(
        legacy_payload,
        timestamp="2026-04-25T12:00:01+00:00",
        sharing_policy_source="ingress_private_first",
        access_plan={"mode": "efficient", "sharing_policy_source": "ingress_private_first"},
    )
    _write_legacy_index(data_dir, {"req-combined-provenance": legacy_payload})
    meter_v2.upsert_meter(sqlite_payload)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "passed"
    assert report["payload_hash_mismatch_count"] == 1
    assert report["semantic_hash_mismatch_count"] == 1
    assert report["critical_payload_hash_mismatch_count"] == 0
    assert report["critical_mismatch_count"] == 0
    samples = report["hash_mismatch_samples"]
    assert len(samples) == 1
    assert samples[0]["classification"] == "provenance_only"
    assert set(samples[0]["noncritical_field_paths"]) == {
        "timestamp",
        "sharing_policy_source",
        "access_plan.sharing_policy_source",
    }


def test_parity_samples_exclude_raw_hash_identical_records(tmp_path, monkeypatch):
    """Matching raw hashes must not appear in hash_mismatch_samples."""
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

    matching_payload = _payload("req-identical")
    legacy_diff = _payload("req-business-sample", saved_tokens=100)
    sqlite_diff = _payload("req-business-sample", saved_tokens=777)
    _write_legacy_index(data_dir, {"req-identical": matching_payload, "req-business-sample": legacy_diff})
    meter_v2.upsert_meter(matching_payload)
    meter_v2.upsert_meter(sqlite_diff)

    report = meter_storage_v2.build_parity_report()
    assert report["payload_hash_mismatch_count"] == 1
    samples = report["hash_mismatch_samples"]
    assert [sample["request_id"] for sample in samples] == ["req-business-sample"]
    assert samples[0]["classification"] == "critical"


def test_parity_detects_business_field_diff_status_degraded(tmp_path, monkeypatch):
    """Business field diff (e.g. saved_tokens_estimate) blocks parity pass."""
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

    legacy_payload = _payload("req-business-diff")
    sqlite_payload = dict(legacy_payload, saved_tokens_estimate=777)  # business drift
    _write_legacy_index(data_dir, {"req-business-diff": legacy_payload})
    meter_v2.upsert_meter(sqlite_payload)

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "degraded"
    assert report["critical_mismatch_count"] == 1
    assert report["critical_payload_hash_mismatch_count"] == 1
    assert report["semantic_hash_mismatch_count"] == 0
    samples = report["hash_mismatch_samples"]
    assert samples[0]["classification"] == "critical"


def test_parity_missing_in_sqlite_counts_critical(tmp_path, monkeypatch):
    """Missing in SQLite is always a critical mismatch."""
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

    # Legacy has a record, SQLite does not.
    _write_legacy_index(data_dir, {"req-missing-sqlite": _payload("req-missing-sqlite")})
    # SQLite is empty.

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "degraded"
    assert report["critical_mismatch_count"] == 1
    assert report["missing_in_sqlite_count"] == 1
    assert report["critical_payload_hash_mismatch_count"] == 0


def test_parity_missing_in_legacy_counts_critical(tmp_path, monkeypatch):
    """Missing in legacy is always a critical mismatch."""
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

    # SQLite has a record, legacy does not.
    meter_v2.upsert_meter(_payload("req-missing-legacy"))

    report = meter_storage_v2.build_parity_report()
    assert report["status"] == "degraded"
    assert report["critical_mismatch_count"] == 1
    assert report["missing_in_legacy_count"] == 1


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
    status = meter_storage_v2.get_status_payload(detail="full")

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
    assert status["cleanup"]["status"] == "frozen"
    assert status["cleanup"]["mode"] == "manual_maintenance_preferred"
    assert status["cleanup"]["cleanup_allowed"] is False
    assert status["cleanup"]["stability_window_status"] == "frozen"
    assert status["cleanup"]["stability_window_observed_pilot_status"] == "frozen"
    assert status["cleanup"]["stability_window_cleanup_scope_expansion_started"] is False
    assert status["cleanup"]["scaleup_readiness_status"] == "frozen"
    assert status["cleanup"]["scaleup_ready"] is False
    assert status["cleanup"]["repeatable_pilot_protocol_status"] == "frozen"
    assert status["cleanup"]["second_file_pilot_proposal_status"] == "frozen"
    assert status["cleanup"]["second_file_pilot_approval_readiness_status"] == "frozen"
    assert status["cleanup"]["second_file_pilot_allowed"] is False
    assert status["cleanup"]["cleanup_scope_expansion_started"] is False
    assert status["backup_export"]["status"] == "frozen"
    assert status["backup_export"]["mode"] == "manual_maintenance_preferred"
    assert status["backup_export"]["backup_export_allowed"] is False
    assert status["backup_export"]["cleanup_allowed"] is False
    assert status["backup_export"]["execution_allowed"] is False
    assert status["backup_export"]["plan_status"] == "frozen"
    assert status["backup_export"]["dry_run_mode"] == "dry_run_preview_only"
    assert status["backup_export"]["destination_status"]["status"] == "frozen"
    assert status["backup_export"]["package_manifest_status"] == "frozen"
    assert status["backup_export"]["package_manifest_file_count"] == 0
    assert status["backup_export"]["package_manifest_total_bytes"] == 0
    assert status["backup_export"]["approval_template_status"] == "frozen"
    assert status["backup_export"]["execution_gate_status"] == "frozen"
    assert status["backup_export"]["execution_gate_allowed"] is False
    assert status["backup_export"]["approval_status"] == "frozen"
    assert status["backup_export"]["execution_proposal_status"] == "frozen"
    assert status["backup_export"]["operator_decision_required"] is False
    assert status["backup_export"]["copy_pilot_status"] == "frozen"
    assert status["backup_export"]["copy_pilot_source_retained"] is True
    assert status["backup_export"]["copy_pilot_checksum_match"] is False
    assert status["backup_export"]["copy_pilot_cleanup_started"] is False
    assert status["backup_export"]["copy_pilot_read_path_unchanged"] is True
    assert status["backup_export"]["restore_readback_status"] == "frozen"
    assert status["backup_export"]["restore_readback_source_retained"] is True
    assert status["backup_export"]["restore_readback_backup_copy_readable"] is False
    assert status["backup_export"]["restore_readback_checksum_match"] is False
    assert status["backup_export"]["restore_readback_production_restore_started"] is False
    assert status["backup_export"]["restore_readback_cleanup_started"] is False
    assert status["backup_export"]["backup_export_execution_started"] is False
    assert status["backup_export"]["cleanup_execution_started"] is False


def test_status_payload_uses_parity_snapshot_and_does_not_scan_legacy_index(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "meter_store.sqlite3"
    snapshot_path = tmp_path / "meter_parity_snapshot.json"
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_DLP_METER_PARITY_SNAPSHOT_FILE", str(snapshot_path))
    meter_storage_v2.write_parity_snapshot(
        {
            "status": "passed",
            "legacy_count": 2,
            "sqlite_count": 2,
            "critical_mismatch_count": 0,
            "payload_hash_mismatch_count": 0,
            "semantic_hash_mismatch_count": 0,
            "critical_payload_hash_mismatch_count": 0,
            "missing_in_sqlite_count": 0,
            "missing_in_legacy_count": 0,
            "matching_request_id_count": 2,
        }
    )

    def fail_legacy_index():
        raise AssertionError("legacy index scan should not run on status")

    def fail_parity_build(*args, **kwargs):
        raise AssertionError("full parity build should not run on status")

    monkeypatch.setattr(meter_storage_v2, "_legacy_index", fail_legacy_index)
    monkeypatch.setattr(meter_storage_v2, "build_parity_report", fail_parity_build)

    status = meter_storage_v2.get_status_payload()

    assert status["storage"]["legacy_count"] == 2
    assert status["cleanup"]["status"] == "frozen"
    assert status["backup_export"]["status"] == "frozen"
