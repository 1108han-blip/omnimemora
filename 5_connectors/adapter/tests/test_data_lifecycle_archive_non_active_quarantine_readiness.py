import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
readiness_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.archive_non_active_quarantine_readiness"
)
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
        archive_non_active_quarantine_readiness_file=str(tmp_path / "archive_non_active_quarantine_readiness_plan.json"),
    )


def _sha(path: Path):
    return readiness_mod._sha256_file(path)


def _write_selector_report(policy, candidates):
    Path(policy.archive_non_active_candidate_report_file).write_text(
        json.dumps(
            {
                "schema_version": "dlp-non-active-candidate-report-v1",
                "report_id": "selector-1",
                "generated_at": "2026-04-25T00:00:00+00:00",
                "mode": "non_active_selection_report_only",
                "candidates": candidates,
                "summary": {
                    "total_scanned": len(candidates),
                    "forbidden_count": sum(1 for item in candidates if item["selection_status"] == "forbidden"),
                    "plausible_non_active_count": sum(
                        1 for item in candidates if item["selection_status"] == "plausible_non_active"
                    ),
                    "review_required_count": sum(
                        1 for item in candidates if item["selection_status"] == "review_required"
                    ),
                    "source_move_delete_compress_executed": False,
                    "warnings_count": 0,
                },
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )


def _archive_copy_candidate(path: Path, *, candidate_id="archive_pilot_copy:p1"):
    sha = _sha(path)
    return {
        "candidate_id": candidate_id,
        "candidate_kind": "archive_pilot_copy",
        "candidate_path": str(path),
        "basename": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha,
        "active_guard_result": "pass",
        "active_guard_reasons": [],
        "selection_status": "plausible_non_active",
        "non_active_reason": "copy_artifact_not_in_production_read_path",
        "required_operator_approval": True,
        "planned_action": "quarantine_non_active_preview_only",
        "would_move_source": False,
        "origin_source_path": str(path.parent.parent / "compile_events.jsonl"),
        "origin_source_kind": "compile_events",
        "origin_source_sha256": sha,
        "archive_copy_path": str(path),
        "restore_key": "restore:compile:p1",
        "pilot_id": "p1",
        "preconditions": {
            "candidate_exists": True,
            "checksum_present": True,
            "checksum_matches_lineage": True,
            "production_read_path_unchanged": True,
            "source_retained": True,
        },
    }


def test_missing_selector_report_blocks_readiness(tmp_path):
    policy = _build_policy(tmp_path)

    plan = readiness_mod.build_readiness_plan(policy=policy)

    assert plan["schema_version"] == "dlp-non-active-quarantine-readiness-v1"
    assert plan["mode"] == "non_active_quarantine_readiness_only"
    assert plan["status"] == "blocked"
    assert "missing_non_active_candidate_report" in plan["blocking_reasons"]
    assert plan["source_move_executed"] is False
    assert plan["non_active_copy_move_executed"] is False


def test_selector_approved_archive_pilot_copy_becomes_readiness_candidate(tmp_path):
    policy = _build_policy(tmp_path)
    copy_path = tmp_path / "archive" / "pilot" / "p1" / "compile_events.copy"
    copy_path.parent.mkdir(parents=True)
    copy_path.write_text('{"request_id":"r1"}\n', encoding="utf-8")
    _write_selector_report(policy, [_archive_copy_candidate(copy_path)])

    plan = readiness_mod.build_readiness_plan(policy=policy)

    assert plan["status"] == "ready_for_operator_approval"
    assert plan["selected_candidate"]["candidate_kind"] == "archive_pilot_copy"
    assert plan["selected_candidate"]["candidate_path"] == str(copy_path)
    assert plan["transaction_preview"]["would_move_non_active_copy"] is False
    assert plan["transaction_preview"]["planned_action"] == "quarantine_non_active_copy_preview_only"
    assert plan["transaction_preview"]["planned_quarantine_path"].endswith(".quarantine")
    assert not Path(plan["transaction_preview"]["planned_quarantine_path"]).exists()


def test_active_source_candidate_is_not_selected(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    source.write_text('{"request_id":"hot"}\n', encoding="utf-8")
    _write_selector_report(
        policy,
        [
            {
                "candidate_id": "compile_events",
                "candidate_kind": "compile_events",
                "candidate_path": str(source),
                "selection_status": "forbidden",
                "active_guard_result": "blocked",
                "active_guard_reasons": ["active_or_control_kind"],
                "bytes": source.stat().st_size,
                "sha256": _sha(source),
            }
        ],
    )

    plan = readiness_mod.build_readiness_plan(policy=policy)

    assert plan["status"] == "blocked"
    assert "no_selector_approved_archive_pilot_copy" in plan["blocking_reasons"]
    assert plan["selected_candidate"] is None
    assert source.exists()


def test_rebuild_writes_readiness_without_moving_copy(tmp_path):
    policy = _build_policy(tmp_path)
    copy_path = tmp_path / "archive" / "pilot" / "p1" / "compile_events.copy"
    copy_path.parent.mkdir(parents=True)
    copy_path.write_text('{"request_id":"r2"}\n', encoding="utf-8")
    before = copy_path.read_text(encoding="utf-8")
    _write_selector_report(policy, [_archive_copy_candidate(copy_path)])

    record, plan = readiness_mod.rebuild_plan(policy=policy)
    readback = readiness_mod.read_plan(policy=policy)

    assert record["trigger"] == "archive_non_active_quarantine_readiness_rebuild"
    assert record["status"] == "success"
    assert plan["status"] == "ready_for_operator_approval"
    assert readback["plan_id"] == plan["plan_id"]
    assert copy_path.exists()
    assert copy_path.read_text(encoding="utf-8") == before
    assert not Path(plan["transaction_preview"]["planned_quarantine_path"]).exists()
    ledger_records = state_store.read_recent_records(
        limit=1,
        trigger="archive_non_active_quarantine_readiness_rebuild",
        policy=policy,
    )
    assert ledger_records[0]["status"] == "success"
