import importlib
import json
from pathlib import Path


archive_non_active_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.archive_non_active_candidates"
)
archive_plan_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_plan")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
retention_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.retention")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")


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
        archive_quarantine_root=str(tmp_path / "quarantine" / "source"),
        archive_quarantine_readiness_file=str(tmp_path / "archive_quarantine_readiness_plan.json"),
        archive_quarantine_record_file=str(tmp_path / "archive_quarantine_record.json"),
        archive_restore_pilot_record_file=str(tmp_path / "archive_restore_pilot_record.json"),
        archive_restore_staging_root=str(tmp_path / "restore" / "staging"),
        archive_non_active_candidate_report_file=str(tmp_path / "archive_non_active_candidate_report.json"),
    )


def _sha(path: Path):
    return archive_plan_mod._sha256_file(path)


def _write_manifest(policy, artifacts):
    payload = {
        "schema_version": "dlp-retention-manifest-v1",
        "manifest_id": "manifest-non-active-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "inventory_only",
        "artifacts": artifacts,
        "summary": {
            "artifact_count": len(artifacts),
            "exists_count": sum(1 for item in artifacts if item.get("exists")),
            "missing_count": sum(1 for item in artifacts if not item.get("exists")),
            "total_bytes": sum(int(item.get("bytes", 0) or 0) for item in artifacts),
            "warnings_count": 0,
        },
        "warnings": [],
    }
    retention_mod.write_manifest_atomic(payload, policy=policy)


def _write_plan(policy, candidates):
    payload = {
        "schema_version": "dlp-archive-candidate-plan-v1",
        "plan_id": "plan-non-active-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "dry_run_only",
        "manifest_ref": {"status": "present", "manifest_id": "manifest-non-active-test"},
        "traceability_ref": {"status": "present", "fail_count": 0, "unexplained_partial_count": 0},
        "candidates": candidates,
        "summary": {
            "eligible_count": sum(1 for item in candidates if item.get("eligibility") == "eligible"),
            "blocked_count": sum(1 for item in candidates if item.get("eligibility") == "blocked"),
            "review_required_count": sum(
                1 for item in candidates if item.get("eligibility") == "review_required"
            ),
            "total_candidate_bytes": sum(int(item.get("bytes", 0) or 0) for item in candidates),
            "warnings_count": 0,
        },
        "warnings": [],
    }
    archive_plan_mod.write_plan_atomic(payload, policy=policy)


def test_active_candidate_is_blocked_by_quarantine_guard(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    source.write_text('{"request_id":"hot"}\n', encoding="utf-8")
    sha = _sha(source)
    candidate = {
        "artifact_name": "compile_events",
        "kind": "compile_events",
        "path": str(source),
        "bytes": source.stat().st_size,
        "sha256": sha,
        "eligibility": "eligible",
        "reason": "upstream_eligible",
    }
    _write_manifest(
        policy,
        [
            {
                "name": "compile_events",
                "kind": "compile_events",
                "path": str(source),
                "exists": True,
                "bytes": source.stat().st_size,
                "sha256": sha,
            }
        ],
    )
    _write_plan(policy, [candidate])

    report = archive_non_active_mod.build_report(policy=policy)

    assert report["schema_version"] == "dlp-non-active-candidate-report-v1"
    assert report["mode"] == "non_active_selection_report_only"
    assert report["summary"]["plausible_non_active_count"] == 0
    assert report["summary"]["forbidden_count"] == 1
    blocked = [item for item in report["candidates"] if item["selection_status"] == "forbidden"]
    assert "active_or_control_kind" in blocked[0]["active_guard_reasons"]


def test_non_active_fixture_candidate_is_selected_when_eligible_and_checksum_present(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "fixture_events_export.jsonl"
    source.write_text('{"fixture":true}\n', encoding="utf-8")
    sha = _sha(source)
    candidate = {
        "artifact_name": "fixture_events_export",
        "kind": "fixture_export",
        "path": str(source),
        "bytes": source.stat().st_size,
        "sha256": sha,
        "eligibility": "eligible",
        "reason": "upstream_eligible",
    }
    _write_manifest(
        policy,
        [
            {
                "name": "fixture_events_export",
                "kind": "fixture_export",
                "path": str(source),
                "exists": True,
                "bytes": source.stat().st_size,
                "sha256": sha,
            }
        ],
    )
    _write_plan(policy, [candidate])

    report = archive_non_active_mod.build_report(policy=policy)

    assert report["summary"]["plausible_non_active_count"] == 1
    selected = [item for item in report["candidates"] if item["selection_status"] == "plausible_non_active"]
    assert selected[0]["candidate_id"] == "fixture_events_export"
    assert selected[0]["non_active_reason"] == "copy_artifact_not_in_production_read_path"
    assert report["summary"]["source_move_delete_compress_executed"] is False


def test_review_required_from_plan_is_propagated(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "fixture_events_export.jsonl"
    source.write_text('{"fixture":"review"}\n', encoding="utf-8")
    sha = _sha(source)
    candidate = {
        "artifact_name": "fixture_events_export",
        "kind": "fixture_export",
        "path": str(source),
        "bytes": source.stat().st_size,
        "sha256": sha,
        "eligibility": "review_required",
        "reason": "manual_review_from_plan",
    }
    _write_manifest(
        policy,
        [
            {
                "name": "fixture_events_export",
                "kind": "fixture_export",
                "path": str(source),
                "exists": True,
                "bytes": source.stat().st_size,
                "sha256": sha,
            }
        ],
    )
    _write_plan(policy, [candidate])

    report = archive_non_active_mod.build_report(policy=policy)

    assert report["summary"]["review_required_count"] == 1
    review = [item for item in report["candidates"] if item["selection_status"] == "review_required"]
    assert review[0]["non_active_reason"] == "source_candidate_requires_manual_review"
    assert report["summary"]["plausible_non_active_count"] == 0


def test_missing_plan_and_manifest_is_safe(tmp_path):
    policy = _build_policy(tmp_path)

    report = archive_non_active_mod.build_report(policy=policy)

    assert report["selection_source_refs"]["archive_candidate_plan"]["status"] == "missing"
    assert report["selection_source_refs"]["retention_manifest"]["status"] == "missing"
    assert report["summary"]["plausible_non_active_count"] == 0
    assert report["summary"]["forbidden_count"] == 0
    assert report["summary"]["review_required_count"] == 0
    assert {item["code"] for item in report["warnings"]} == {
        "missing_archive_candidate_plan",
        "missing_retention_manifest",
        "missing_archive_pilot_record",
    }


def test_rebuild_report_writes_report_and_does_not_mutate_source(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "fixture_events_export.jsonl"
    source.write_text('{"fixture":"stable"}\n', encoding="utf-8")
    before = source.read_text(encoding="utf-8")
    before_stat = source.stat()
    sha = _sha(source)
    candidate = {
        "artifact_name": "fixture_events_export",
        "kind": "fixture_export",
        "path": str(source),
        "bytes": source.stat().st_size,
        "sha256": sha,
        "eligibility": "eligible",
        "reason": "upstream_eligible",
    }
    _write_manifest(
        policy,
        [
            {
                "name": "fixture_events_export",
                "kind": "fixture_export",
                "path": str(source),
                "exists": True,
                "bytes": source.stat().st_size,
                "sha256": sha,
            }
        ],
    )
    _write_plan(policy, [candidate])

    record, report = archive_non_active_mod.rebuild_report(policy=policy)
    readback = archive_non_active_mod.read_report(policy=policy)
    after_stat = source.stat()

    assert record["trigger"] == "archive_non_active_candidate_report_rebuild"
    assert record["status"] == "success"
    assert report["summary"]["plausible_non_active_count"] == 1
    assert readback["report_id"] == report["report_id"]
    assert source.exists()
    assert source.read_text(encoding="utf-8") == before
    assert after_stat.st_size == before_stat.st_size
    assert Path(policy.archive_plan_file).exists()
    assert Path(policy.retention_manifest_file).exists()
    assert archive_non_active_mod._report_path(policy).exists()

    ledger_records = state_store.read_recent_records(
        limit=1,
        trigger="archive_non_active_candidate_report_rebuild",
        policy=policy,
    )
    assert ledger_records[0]["status"] == "success"


def test_archive_pilot_copy_is_selected_as_non_active_copy(tmp_path):
    policy = _build_policy(tmp_path)
    production_source = tmp_path / "compile_events.jsonl"
    archive_copy = tmp_path / "archive" / "pilot" / "p1" / "compile_events.copy"
    production_source.write_text('{"request_id":"hot"}\n', encoding="utf-8")
    archive_copy.parent.mkdir(parents=True, exist_ok=True)
    archive_copy.write_text(production_source.read_text(encoding="utf-8"), encoding="utf-8")
    sha = _sha(archive_copy)
    Path(policy.archive_pilot_record_file).write_text(
        json.dumps(
            {
                "schema_version": "dlp-archive-pilot-record-v1",
                "pilot_id": "p1",
                "status": "success",
                "source_path": str(production_source),
                "source_kind": "compile_events",
                "source_sha256": sha,
                "archive_path": str(archive_copy),
                "archive_sha256": sha,
                "archive_bytes": archive_copy.stat().st_size,
                "restore_key": "restore:compile:p1",
            }
        ),
        encoding="utf-8",
    )

    report = archive_non_active_mod.build_report(policy=policy)

    selected = [item for item in report["candidates"] if item["selection_status"] == "plausible_non_active"]
    assert len(selected) == 1
    assert selected[0]["candidate_kind"] == "archive_pilot_copy"
    assert selected[0]["archive_copy_path"] == str(archive_copy)
    assert selected[0]["origin_source_kind"] == "compile_events"
    assert selected[0]["preconditions"]["checksum_matches_lineage"] is True
