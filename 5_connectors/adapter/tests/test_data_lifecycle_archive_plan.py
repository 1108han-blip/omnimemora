import importlib
import json
from pathlib import Path


archive_plan_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_plan")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
retention_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.retention")
traceability_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.traceability")
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
    )


def _write_manifest(policy, artifacts, *, mode="inventory_only"):
    payload = {
        "schema_version": "dlp-retention-manifest-v1",
        "manifest_id": "manifest-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": mode,
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


def _write_traceability_report(policy, *, fail_count=0, unexplained_partial_count=0):
    payload = {
        "schema_version": "dlp-traceability-report-v1",
        "report_id": "report-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "manifest_ref": {"status": "present", "manifest_id": "manifest-test", "generated_at": "2026-04-25T00:00:00+00:00"},
        "samples": [],
        "summary": {
            "sample_count": 1,
            "pass_count": 1 if fail_count == 0 and unexplained_partial_count == 0 else 0,
            "partial_count": unexplained_partial_count,
            "fail_count": fail_count,
            "missing_manifest": False,
            "warnings_count": 0,
            "acceptable_partial_count": 0,
            "unexplained_partial_count": unexplained_partial_count,
            "current_epoch_sample_count": 1,
            "current_epoch_pass_count": 1 if fail_count == 0 and unexplained_partial_count == 0 else 0,
            "current_epoch_pass_rate": 1.0 if fail_count == 0 and unexplained_partial_count == 0 else 0.0,
            "partial_reason_distribution": {},
        },
        "warnings": [],
    }
    traceability_mod.write_report_atomic(payload, policy=policy)


def test_archive_plan_blocks_all_candidates_when_traceability_missing_or_not_clean(tmp_path):
    policy = _build_policy(tmp_path)
    evidence = tmp_path / "compile_events.jsonl"
    evidence.write_text('{"request_id":"req1"}\n', encoding="utf-8")
    _write_manifest(
        policy,
        [
            {
                "name": "compile_events",
                "kind": "compile_events",
                "path": str(evidence),
                "exists": True,
                "bytes": evidence.stat().st_size,
                "sha256": archive_plan_mod._sha256_file(evidence),
            }
        ],
    )

    plan_missing = archive_plan_mod.build_archive_candidate_plan(policy=policy)
    assert plan_missing["summary"]["eligible_count"] == 0
    assert plan_missing["summary"]["blocked_count"] == len(plan_missing["candidates"])
    assert all(item["eligibility"] == "blocked" for item in plan_missing["candidates"])

    _write_traceability_report(policy, fail_count=1, unexplained_partial_count=0)
    plan_fail = archive_plan_mod.build_archive_candidate_plan(policy=policy)
    assert plan_fail["summary"]["blocked_count"] == len(plan_fail["candidates"])
    assert all(item["eligibility"] == "blocked" for item in plan_fail["candidates"])

    _write_traceability_report(policy, fail_count=0, unexplained_partial_count=1)
    plan_partial = archive_plan_mod.build_archive_candidate_plan(policy=policy)
    assert plan_partial["summary"]["blocked_count"] == len(plan_partial["candidates"])
    assert all(item["eligibility"] == "blocked" for item in plan_partial["candidates"])


def test_archive_plan_marks_evidence_eligible_when_checksum_and_traceability_passed(tmp_path):
    policy = _build_policy(tmp_path)
    compile_events = tmp_path / "compile_events.jsonl"
    compile_events.write_text('{"request_id":"req-eligible"}\n', encoding="utf-8")
    _write_manifest(
        policy,
        [
            {
                "name": "compile_events",
                "kind": "compile_events",
                "path": str(compile_events),
                "exists": True,
                "bytes": compile_events.stat().st_size,
                "sha256": archive_plan_mod._sha256_file(compile_events),
            }
        ],
        mode="inventory_only",
    )
    _write_traceability_report(policy, fail_count=0, unexplained_partial_count=0)

    plan = archive_plan_mod.build_archive_candidate_plan(policy=policy)
    by_name = {item["artifact_name"]: item for item in plan["candidates"]}
    assert by_name["compile_events"]["eligibility"] == "eligible"
    assert by_name["compile_events"]["reason"] == "checksum_present_traceability_passed_inventory_only"


def test_archive_plan_marks_control_artifacts_review_required(tmp_path):
    policy = _build_policy(tmp_path)
    summary = tmp_path / "family_window_summary.json"
    ledger = tmp_path / "maintenance_state.jsonl"
    summary.write_text("{}", encoding="utf-8")
    ledger.write_text('{"cycle_id":"c1"}\n', encoding="utf-8")
    _write_manifest(
        policy,
        [
            {
                "name": "dlp_summary",
                "kind": "dlp_summary",
                "path": str(summary),
                "exists": True,
                "bytes": summary.stat().st_size,
                "sha256": archive_plan_mod._sha256_file(summary),
            },
            {
                "name": "dlp_ledger",
                "kind": "dlp_ledger",
                "path": str(ledger),
                "exists": True,
                "bytes": ledger.stat().st_size,
                "sha256": archive_plan_mod._sha256_file(ledger),
            },
        ],
    )
    _write_traceability_report(policy, fail_count=0, unexplained_partial_count=0)

    plan = archive_plan_mod.build_archive_candidate_plan(policy=policy)
    by_name = {item["artifact_name"]: item for item in plan["candidates"]}
    assert by_name["dlp_summary"]["eligibility"] == "review_required"
    assert by_name["dlp_ledger"]["eligibility"] == "review_required"
    assert by_name["retention_manifest"]["eligibility"] == "review_required"
    assert by_name["traceability_report"]["eligibility"] == "review_required"


def test_archive_plan_marks_missing_artifact_blocked(tmp_path):
    policy = _build_policy(tmp_path)
    missing = tmp_path / "trace_events.jsonl"
    _write_manifest(
        policy,
        [
            {
                "name": "trace_events",
                "kind": "trace_events",
                "path": str(missing),
                "exists": False,
                "bytes": 0,
                "sha256": None,
            }
        ],
    )
    _write_traceability_report(policy, fail_count=0, unexplained_partial_count=0)

    plan = archive_plan_mod.build_archive_candidate_plan(policy=policy)
    by_name = {item["artifact_name"]: item for item in plan["candidates"]}
    assert by_name["trace_events"]["eligibility"] == "blocked"
    assert by_name["trace_events"]["reason"] == "artifact_missing"


def test_archive_plan_rebuild_is_dry_run_and_does_not_mutate_raw_evidence(tmp_path):
    policy = _build_policy(tmp_path)
    compile_events = tmp_path / "compile_events.jsonl"
    compile_events.write_text('{"request_id":"req-no-mutate"}\n', encoding="utf-8")
    _write_manifest(
        policy,
        [
            {
                "name": "compile_events",
                "kind": "compile_events",
                "path": str(compile_events),
                "exists": True,
                "bytes": compile_events.stat().st_size,
                "sha256": archive_plan_mod._sha256_file(compile_events),
            }
        ],
    )
    _write_traceability_report(policy, fail_count=0, unexplained_partial_count=0)

    before_stat = compile_events.stat()
    record, plan = archive_plan_mod.rebuild_plan(policy=policy)
    after_stat = compile_events.stat()

    assert record["trigger"] == "archive_candidate_plan_rebuild"
    assert record["status"] == "success"
    assert plan["mode"] == "dry_run_only"

    plan_path = Path(policy.archive_plan_file)
    assert plan_path.exists()
    assert before_stat.st_size == after_stat.st_size
    assert before_stat.st_mtime_ns == after_stat.st_mtime_ns

    ledger_records = state_store.read_recent_records(limit=1, trigger="archive_candidate_plan_rebuild", policy=policy)
    assert len(ledger_records) == 1
    assert ledger_records[0]["trigger"] == "archive_candidate_plan_rebuild"


def test_archive_plan_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    plan = {
        "schema_version": "dlp-archive-candidate-plan-v1",
        "plan_id": "plan-atomic",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "dry_run_only",
        "manifest_ref": {"status": "missing"},
        "traceability_ref": {"status": "missing"},
        "candidates": [],
        "summary": {
            "eligible_count": 0,
            "blocked_count": 0,
            "review_required_count": 0,
            "total_candidate_bytes": 0,
            "warnings_count": 0,
        },
        "warnings": [],
    }

    monkeypatch.setattr(
        archive_plan_mod.os,
        "replace",
        lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")),
    )
    try:
        archive_plan_mod.write_plan_atomic(plan, policy=policy)
        assert False, "expected write_plan_atomic to fail"
    except RuntimeError:
        pass

    target = Path(policy.archive_plan_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_archive_candidate_*.tmp")) == []
