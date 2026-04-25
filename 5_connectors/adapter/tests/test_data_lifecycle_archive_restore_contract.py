import importlib
import json
from pathlib import Path


archive_transaction_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_transaction")
archive_restore_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_restore_contract")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
traceability_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.traceability")


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
        archive_pilot_root=str(tmp_path / "archive" / "pilot"),
        archive_pilot_record_file=str(tmp_path / "archive_pilot_record.json"),
    )


def _write_archive_plan(policy, candidates):
    payload = {
        "schema_version": "dlp-archive-candidate-plan-v1",
        "plan_id": "plan-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "dry_run_only",
        "manifest_ref": {"status": "present"},
        "traceability_ref": {"status": "present"},
        "candidates": candidates,
        "summary": {
            "eligible_count": sum(1 for item in candidates if item.get("eligibility") == "eligible"),
            "blocked_count": sum(1 for item in candidates if item.get("eligibility") == "blocked"),
            "review_required_count": sum(1 for item in candidates if item.get("eligibility") == "review_required"),
            "total_candidate_bytes": sum(int(item.get("bytes", 0) or 0) for item in candidates),
            "warnings_count": 0,
        },
        "warnings": [],
    }
    Path(policy.archive_plan_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_traceability_report(policy, samples):
    payload = {
        "schema_version": "dlp-traceability-report-v1",
        "report_id": "report-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "manifest_ref": {"status": "present", "manifest_id": "manifest-test"},
        "samples": samples,
        "summary": {
            "sample_count": len(samples),
            "pass_count": len(samples),
            "partial_count": 0,
            "fail_count": 0,
            "missing_manifest": False,
            "warnings_count": 0,
            "acceptable_partial_count": 0,
            "unexplained_partial_count": 0,
            "current_epoch_sample_count": len(samples),
            "current_epoch_pass_count": len(samples),
            "current_epoch_pass_rate": 1.0 if samples else None,
            "partial_reason_distribution": {},
        },
        "warnings": [],
    }
    traceability_mod.write_report_atomic(payload, policy=policy)


def test_archive_restore_readiness_maps_request_to_checksum_and_restore_key(tmp_path):
    policy = _build_policy(tmp_path)
    evidence = tmp_path / "compile_events.jsonl"
    evidence.write_text('{"request_id":"req1"}\n', encoding="utf-8")
    _write_archive_plan(
        policy,
        [
            {
                "artifact_name": "compile_events",
                "kind": "compile_events",
                "path": str(evidence),
                "bytes": evidence.stat().st_size,
                "sha256": archive_transaction_mod._sha256_file(evidence),
                "eligibility": "eligible",
            }
        ],
    )
    archive_transaction_mod.rebuild_preview(policy=policy)
    _write_traceability_report(
        policy,
        samples=[
            {
                "request_id": "req1",
                "sources_found": ["compile"],
                "missing_sources": [],
                "request_evidence_buildable": True,
                "trace_id_found": None,
                "status": "pass",
            }
        ],
    )

    report = archive_restore_mod.build_restore_readiness_report(policy=policy)
    assert report["schema_version"] == "dlp-archive-restore-readiness-v1"
    assert report["mode"] == "readiness_only"
    assert report["summary"]["sample_count"] == 1
    assert report["summary"]["mapped_request_count"] == 1
    chain = report["request_mappings"][0]["evidence_chain"][0]
    assert chain["checksum"] is not None
    assert isinstance(chain["restore_key"], str) and chain["restore_key"].startswith("restore:")


def test_archive_restore_readiness_missing_preview_is_safe(tmp_path):
    policy = _build_policy(tmp_path)
    report = archive_restore_mod.build_restore_readiness_report(policy=policy)
    assert report["summary"]["status"] == "blocked_missing_preview"
    assert report["request_mappings"] == []


def test_archive_restore_readiness_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    report = {
        "schema_version": "dlp-archive-restore-readiness-v1",
        "readiness_id": "r1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "readiness_only",
        "transaction_preview_ref": {"status": "missing"},
        "traceability_ref": {"status": "missing"},
        "request_mappings": [],
        "summary": {"status": "blocked_missing_preview", "sample_count": 0},
        "warnings": [],
    }

    monkeypatch.setattr(
        archive_restore_mod.os,
        "replace",
        lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")),
    )
    try:
        archive_restore_mod.write_readiness_atomic(report, policy=policy)
        assert False, "expected write_readiness_atomic to fail"
    except RuntimeError:
        pass
    target = Path(policy.archive_restore_readiness_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_archive_restore_*.tmp")) == []


def test_archive_restore_readiness_rebuild_writes_ledger_trigger(tmp_path):
    policy = _build_policy(tmp_path)
    evidence = tmp_path / "compile_events.jsonl"
    evidence.write_text('{"request_id":"req-ledger"}\n', encoding="utf-8")
    _write_archive_plan(
        policy,
        [
            {
                "artifact_name": "compile_events",
                "kind": "compile_events",
                "path": str(evidence),
                "bytes": evidence.stat().st_size,
                "sha256": archive_transaction_mod._sha256_file(evidence),
                "eligibility": "eligible",
            }
        ],
    )
    archive_transaction_mod.rebuild_preview(policy=policy)
    _write_traceability_report(
        policy,
        samples=[
            {
                "request_id": "req-ledger",
                "sources_found": ["compile"],
                "missing_sources": [],
                "request_evidence_buildable": True,
                "trace_id_found": None,
                "status": "pass",
            }
        ],
    )
    record, report = archive_restore_mod.rebuild_readiness_report(policy=policy)
    assert record["trigger"] == "archive_restore_readiness_rebuild"
    assert record["status"] == "success"
    assert report["summary"]["sample_count"] == 1


def test_archive_restore_readiness_verifies_pilot_copy_checksum(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    source.write_text("pilot", encoding="utf-8")
    archive = tmp_path / "archive" / "pilot" / "pid" / "compile_events.jsonl.copy"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("pilot", encoding="utf-8")
    _write_archive_plan(
        policy,
        [
            {
                "artifact_name": "compile_events",
                "kind": "compile_events",
                "path": str(source),
                "bytes": source.stat().st_size,
                "sha256": archive_transaction_mod._sha256_file(source),
                "eligibility": "eligible",
            }
        ],
    )
    archive_transaction_mod.rebuild_preview(policy=policy)
    _write_traceability_report(
        policy,
        samples=[
            {
                "request_id": "req-pilot",
                "sources_found": ["compile"],
                "missing_sources": [],
                "request_evidence_buildable": True,
                "trace_id_found": None,
                "status": "pass",
            }
        ],
    )
    pilot_record = {
        "schema_version": "dlp-archive-pilot-record-v1",
        "pilot_id": "pid",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "copy_to_archive_only",
        "status": "success",
        "source_path": str(source),
        "source_kind": "compile_events",
        "source_bytes": source.stat().st_size,
        "source_sha256": archive_transaction_mod._sha256_file(source),
        "archive_path": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": archive_transaction_mod._sha256_file(archive),
        "checksum_match": True,
        "source_retained": True,
        "read_path_unchanged": True,
        "restore_key": "restore:compile:abc",
    }
    Path(policy.archive_pilot_record_file).write_text(json.dumps(pilot_record), encoding="utf-8")
    report = archive_restore_mod.build_restore_readiness_report(policy=policy)
    pilot = report.get("pilot_copy_verification") or {}
    assert pilot["status"] == "verified"
    assert pilot["checksum_match"] is True
    assert report["summary"]["pilot_copy_status"] == "verified"
