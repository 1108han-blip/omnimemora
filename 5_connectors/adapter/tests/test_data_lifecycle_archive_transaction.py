import importlib
import json
from pathlib import Path


archive_transaction_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_transaction")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
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


def test_archive_transaction_preview_includes_eligible_only_and_required_fields(tmp_path):
    policy = _build_policy(tmp_path)
    eligible_file = tmp_path / "compile_events.jsonl"
    eligible_file.write_text('{"request_id":"req1"}\n', encoding="utf-8")
    sha256 = archive_transaction_mod._sha256_file(eligible_file)
    _write_archive_plan(
        policy,
        [
            {
                "artifact_name": "compile_events",
                "kind": "compile_events",
                "path": str(eligible_file),
                "bytes": eligible_file.stat().st_size,
                "sha256": sha256,
                "eligibility": "eligible",
                "rollback_hint": "restore from snapshot",
            },
            {
                "artifact_name": "traceability_report",
                "kind": "traceability_report",
                "path": str(tmp_path / "traceability_report.json"),
                "bytes": 0,
                "sha256": None,
                "eligibility": "review_required",
            },
            {
                "artifact_name": "proxy_events",
                "kind": "proxy_events",
                "path": str(tmp_path / "proxy_events.jsonl"),
                "bytes": 0,
                "sha256": None,
                "eligibility": "blocked",
            },
        ],
    )

    preview = archive_transaction_mod.build_transaction_preview(policy=policy)
    assert preview["schema_version"] == "dlp-archive-transaction-preview-v1"
    assert preview["mode"] == "preview_only"
    assert preview["summary"]["eligible_input_count"] == 1
    assert preview["summary"]["preview_item_count"] == 1
    assert preview["summary"]["excluded_blocked_count"] == 1
    assert preview["summary"]["excluded_review_required_count"] == 1

    item = preview["items"][0]
    for key in [
        "source_path",
        "source_sha256",
        "source_bytes",
        "planned_archive_path",
        "restore_key",
        "precondition_checks",
        "rollback_hint",
    ]:
        assert key in item
    assert item["source_sha256"] == sha256
    assert isinstance(item["precondition_checks"], list) and item["precondition_checks"]
    assert all(check.get("status") == "pass" for check in item["precondition_checks"])


def test_archive_transaction_preview_missing_candidate_plan_is_safe(tmp_path):
    policy = _build_policy(tmp_path)
    preview = archive_transaction_mod.build_transaction_preview(policy=policy)
    assert preview["summary"]["status"] == "missing_candidate_plan"
    assert preview["summary"]["preview_item_count"] == 0
    assert preview["items"] == []


def test_archive_transaction_preview_rebuild_writes_ledger_and_no_archive_dir_creation(tmp_path):
    policy = _build_policy(tmp_path)
    evidence = tmp_path / "trace_events.jsonl"
    evidence.write_text('{"request_id":"req1"}\n', encoding="utf-8")
    _write_archive_plan(
        policy,
        [
            {
                "artifact_name": "trace_events",
                "kind": "trace_events",
                "path": str(evidence),
                "bytes": evidence.stat().st_size,
                "sha256": archive_transaction_mod._sha256_file(evidence),
                "eligibility": "eligible",
            }
        ],
    )

    archive_dir = Path.home() / ".omnimemora" / "adapter" / "data_lifecycle" / "archive"
    pre_exists = archive_dir.exists()
    record, preview = archive_transaction_mod.rebuild_preview(policy=policy)
    post_exists = archive_dir.exists()

    assert record["trigger"] == "archive_transaction_preview_rebuild"
    assert record["status"] == "success"
    assert preview["mode"] == "preview_only"
    assert pre_exists == post_exists

    records = state_store.read_recent_records(
        limit=1, trigger="archive_transaction_preview_rebuild", policy=policy
    )
    assert len(records) == 1
    assert records[0]["trigger"] == "archive_transaction_preview_rebuild"


def test_archive_transaction_preview_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    preview = {
        "schema_version": "dlp-archive-transaction-preview-v1",
        "preview_id": "preview-1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "preview_only",
        "plan_ref": {"status": "missing"},
        "items": [],
        "summary": {"status": "missing_candidate_plan", "preview_item_count": 0},
        "warnings": [],
    }

    monkeypatch.setattr(
        archive_transaction_mod.os,
        "replace",
        lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")),
    )
    try:
        archive_transaction_mod.write_preview_atomic(preview, policy=policy)
        assert False, "expected write_preview_atomic to fail"
    except RuntimeError:
        pass
    target = Path(policy.archive_transaction_preview_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_archive_preview_*.tmp")) == []
