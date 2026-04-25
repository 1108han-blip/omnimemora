import importlib
import json
from pathlib import Path


fallback_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_fallback_contract")
readthrough_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_readthrough")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=30.0,
        summary_stale_max_age_seconds=3600.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        retention_manifest_file=str(tmp_path / "retention_manifest.json"),
        traceability_report_file=str(tmp_path / "traceability_report.json"),
        archive_plan_file=str(tmp_path / "archive_candidate_plan.json"),
        archive_transaction_preview_file=str(tmp_path / "archive_transaction_preview.json"),
        archive_restore_readiness_file=str(tmp_path / "archive_restore_readiness_report.json"),
        archive_execution_gate_file=str(tmp_path / "archive_execution_gate.json"),
        archive_operator_approval_file=str(tmp_path / "archive_operator_approval.json"),
        archive_pilot_root=str(tmp_path / "archive" / "pilot"),
        archive_pilot_record_file=str(tmp_path / "archive_pilot_record.json"),
        archive_readthrough_report_file=str(tmp_path / "archive_readthrough_report.json"),
        archive_fallback_simulation_file=str(tmp_path / "archive_fallback_simulation_report.json"),
    )


def _write_pilot(policy, *, source_path: Path, archive_path: Path, restore_key: str = "restore:compile:abc"):
    payload = {
        "schema_version": "dlp-archive-pilot-record-v1",
        "pilot_id": "pilot-1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "copy_to_archive_only",
        "status": "success",
        "source_path": str(source_path),
        "source_kind": "compile_events",
        "source_bytes": source_path.stat().st_size if source_path.exists() else 0,
        "source_sha256": readthrough_mod._sha256_file(source_path),
        "archive_path": str(archive_path),
        "archive_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
        "archive_sha256": readthrough_mod._sha256_file(archive_path),
        "checksum_match": True,
        "source_retained": source_path.exists(),
        "read_path_unchanged": True,
        "restore_key": restore_key,
    }
    Path(policy.archive_pilot_record_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_readthrough(policy, *, restore_key: str = "restore:compile:abc", request_id: str = "req-1"):
    payload = {
        "schema_version": "dlp-archive-readthrough-report-v1",
        "report_id": "readthrough-1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "shadow_validation_only",
        "status": "passed",
        "source_retained": True,
        "archive_copy_readable": True,
        "checksum_match": True,
        "read_path_unchanged": True,
        "restore_key": restore_key,
        "request_id_cross_check": {"status": "mapped", "request_id": request_id},
    }
    Path(policy.archive_readthrough_report_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_readiness(policy, *, restore_key: str = "restore:compile:abc", request_id: str = "req-1"):
    payload = {
        "schema_version": "dlp-archive-restore-readiness-v1",
        "readiness_id": "ready-1",
        "mode": "readiness_only",
        "request_mappings": [
            {
                "request_id": request_id,
                "status": "mapped",
                "evidence_chain": [
                    {
                        "evidence_source": "compile",
                        "candidate_kind": "compile_events",
                        "restore_key": restore_key,
                        "status": "mapped",
                    }
                ],
            }
        ],
    }
    Path(policy.archive_restore_readiness_file).write_text(json.dumps(payload), encoding="utf-8")


def test_fallback_simulation_passes_without_mutating_source(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_readthrough(policy)
    _write_readiness(policy)
    before = source.read_text(encoding="utf-8")

    report = fallback_mod.build_fallback_simulation_report(policy=policy)

    assert report["schema_version"] == "dlp-archive-fallback-simulation-v1"
    assert report["mode"] == "diagnostic_fallback_only"
    assert report["status"] == "passed"
    assert report["source_missing_simulated"] is True
    assert report["fallback_available"] is True
    assert report["archive_copy_readable"] is True
    assert report["checksum_match"] is True
    assert report["production_read_path_unchanged"] is True
    assert source.read_text(encoding="utf-8") == before


def test_fallback_simulation_missing_pilot_is_safe_missing(tmp_path):
    policy = _build_policy(tmp_path)
    report = fallback_mod.build_fallback_simulation_report(policy=policy)
    assert report["status"] == "missing"
    assert report["reason"] == "missing_pilot_record"
    assert report["fallback_available"] is False


def test_fallback_simulation_missing_archive_copy_fails_without_source_mutation(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "missing_archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    before = source.read_text(encoding="utf-8")

    report = fallback_mod.build_fallback_simulation_report(policy=policy)

    assert report["status"] == "failed"
    assert report["reason"] == "archive_copy_missing_or_unreadable"
    assert report["fallback_available"] is False
    assert source.read_text(encoding="utf-8") == before


def test_fallback_simulation_checksum_mismatch_fails(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("source", encoding="utf-8")
    archive.write_text("archive", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)

    report = fallback_mod.build_fallback_simulation_report(policy=policy)

    assert report["status"] == "failed"
    assert report["reason"] == "checksum_mismatch"
    assert report["checksum_match"] is False


def test_fallback_simulation_uses_readiness_when_readthrough_mapping_missing(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive, restore_key="restore:compile:fallback")
    _write_readiness(policy, restore_key="restore:compile:fallback", request_id="req-fallback-1")

    report = fallback_mod.build_fallback_simulation_report(policy=policy)

    fallback = report.get("request_evidence_fallback") or {}
    assert fallback["status"] == "mapped"
    assert fallback["request_id"] == "req-fallback-1"
    assert fallback["production_read_path_unchanged"] is True


def test_rebuild_fallback_simulation_writes_report_and_ledger(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)

    record, report = fallback_mod.rebuild_report(policy=policy)

    assert record["trigger"] == "archive_fallback_simulation_rebuild"
    assert record["status"] == "success"
    assert report["status"] == "passed"
    written = fallback_mod.read_report(policy=policy)
    assert written is not None
    assert written["schema_version"] == "dlp-archive-fallback-simulation-v1"
