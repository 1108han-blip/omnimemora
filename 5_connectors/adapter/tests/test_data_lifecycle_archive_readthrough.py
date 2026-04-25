import importlib
import json
from pathlib import Path


archive_readthrough_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_readthrough")
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
        "source_sha256": archive_readthrough_mod._sha256_file(source_path),
        "archive_path": str(archive_path),
        "archive_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
        "archive_sha256": archive_readthrough_mod._sha256_file(archive_path),
        "checksum_match": True,
        "source_retained": source_path.exists(),
        "read_path_unchanged": True,
        "restore_key": restore_key,
    }
    Path(policy.archive_pilot_record_file).write_text(json.dumps(payload), encoding="utf-8")


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


def test_readthrough_pass_when_archive_readable_and_checksum_match(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("hello", encoding="utf-8")
    archive.write_text("hello", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_readiness(policy)

    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    assert report["schema_version"] == "dlp-archive-readthrough-report-v1"
    assert report["mode"] == "shadow_validation_only"
    assert report["status"] == "passed"
    assert report["archive_copy_readable"] is True
    assert report["checksum_match"] is True
    assert (report.get("request_evidence_shadow") or {}).get("read_path_unchanged") is True


def test_readthrough_missing_pilot_record_returns_missing_status(tmp_path):
    policy = _build_policy(tmp_path)
    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    assert report["status"] == "missing"
    assert report["reason"] == "missing_pilot_record"


def test_readthrough_missing_archive_copy_fails_without_source_mutation(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    source.write_text("src", encoding="utf-8")
    archive = tmp_path / "missing_archive_copy.jsonl"
    _write_pilot(policy, source_path=source, archive_path=archive)
    before = source.read_text(encoding="utf-8")
    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    assert report["status"] == "failed"
    assert report["reason"] == "archive_copy_missing_or_unreadable"
    assert source.read_text(encoding="utf-8") == before


def test_readthrough_checksum_mismatch_fails(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("source-a", encoding="utf-8")
    archive.write_text("source-b", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    assert report["status"] == "failed"
    assert report["reason"] == "checksum_mismatch"
    assert report["checksum_match"] is False


def test_readthrough_source_missing_while_archive_exists_fails(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("hello", encoding="utf-8")
    archive.write_text("hello", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    source.unlink()

    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    assert report["status"] == "failed"
    assert report["reason"] == "source_missing"
    assert report["archive_copy_readable"] is True


def test_readthrough_request_cross_check_mapped(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive, restore_key="restore:compile:mapped")
    _write_readiness(policy, restore_key="restore:compile:mapped", request_id="req-shadow-1")

    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    cross = report.get("request_id_cross_check") or {}
    assert cross["status"] == "mapped"
    assert cross["request_id"] == "req-shadow-1"
    shadow = report.get("request_evidence_shadow") or {}
    assert shadow["status"] == "mapped"
    assert shadow["request_id"] == "req-shadow-1"


def test_readthrough_request_cross_check_not_applicable_when_no_mapping(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive, restore_key="restore:compile:not-found")
    _write_readiness(policy, restore_key="restore:compile:other", request_id="req-shadow-2")

    report = archive_readthrough_mod.build_readthrough_report(policy=policy)
    cross = report.get("request_id_cross_check") or {}
    assert cross["status"] == "not_applicable"
    shadow = report.get("request_evidence_shadow") or {}
    assert shadow["status"] == "not_applicable"
