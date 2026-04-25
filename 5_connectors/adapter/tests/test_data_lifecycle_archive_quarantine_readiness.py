import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
quarantine_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_quarantine_readiness")


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
    )


def _sha(path: Path):
    return quarantine_mod._sha256_file(path)


def _write_pilot(policy, *, source_path: Path, archive_path: Path, restore_key: str = "restore:compile:q"):
    payload = {
        "schema_version": "dlp-archive-pilot-record-v1",
        "pilot_id": "pilot-q",
        "mode": "copy_to_archive_only",
        "status": "success",
        "source_path": str(source_path),
        "source_kind": "compile_events",
        "source_bytes": source_path.stat().st_size,
        "source_sha256": _sha(source_path),
        "archive_path": str(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": _sha(archive_path),
        "checksum_match": True,
        "source_retained": True,
        "read_path_unchanged": True,
        "restore_key": restore_key,
    }
    Path(policy.archive_pilot_record_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_fallback(policy, *, status: str = "passed"):
    payload = {
        "schema_version": "dlp-archive-fallback-simulation-v1",
        "simulation_id": "fb-q",
        "mode": "diagnostic_fallback_only",
        "status": status,
        "source_missing_simulated": True,
        "fallback_available": status == "passed",
        "archive_copy_readable": status == "passed",
        "checksum_match": status == "passed",
        "production_read_path_unchanged": True,
    }
    Path(policy.archive_fallback_simulation_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_gate(policy, *, allowed: bool = True):
    payload = {
        "schema_version": "dlp-archive-execution-gate-v1",
        "gate_id": "gate-q",
        "mode": "gate_only",
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
    }
    Path(policy.archive_execution_gate_file).write_text(json.dumps(payload), encoding="utf-8")


def test_quarantine_readiness_ready_without_moving_source(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_fallback(policy)
    _write_gate(policy)
    before = source.read_text(encoding="utf-8")

    plan = quarantine_mod.build_quarantine_readiness_plan(policy=policy)

    assert plan["schema_version"] == "dlp-source-quarantine-readiness-plan-v1"
    assert plan["mode"] == "readiness_plan_only"
    assert plan["status"] == "ready_for_approval"
    assert plan["source_move_executed"] is False
    assert plan["source_retained"] is True
    assert plan["production_read_path_unchanged"] is True
    tx = plan.get("transaction_preview") or {}
    assert tx["planned_action"] == "quarantine_source_preview_only"
    assert tx["would_move_source"] is False
    assert tx["source_move_executed"] is False
    assert source.read_text(encoding="utf-8") == before
    assert not Path(policy.archive_quarantine_root).exists()


def test_quarantine_readiness_blocks_without_fallback_pass(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_fallback(policy, status="failed")
    _write_gate(policy)

    plan = quarantine_mod.build_quarantine_readiness_plan(policy=policy)

    assert plan["status"] == "blocked"
    assert "fallback_simulation_not_passed" in plan["blocking_reasons"]


def test_quarantine_readiness_blocks_without_gate_allowed(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_fallback(policy)
    _write_gate(policy, allowed=False)

    plan = quarantine_mod.build_quarantine_readiness_plan(policy=policy)

    assert plan["status"] == "blocked"
    assert "execution_gate_not_allowed" in plan["blocking_reasons"]


def test_quarantine_readiness_blocks_on_checksum_mismatch(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("source", encoding="utf-8")
    archive.write_text("archive", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_fallback(policy)
    _write_gate(policy)

    plan = quarantine_mod.build_quarantine_readiness_plan(policy=policy)

    assert plan["status"] == "blocked"
    assert "source_archive_checksum_mismatch" in plan["blocking_reasons"]


def test_rebuild_quarantine_readiness_writes_plan_and_ledger(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    archive = tmp_path / "archive_copy.jsonl"
    source.write_text("same", encoding="utf-8")
    archive.write_text("same", encoding="utf-8")
    _write_pilot(policy, source_path=source, archive_path=archive)
    _write_fallback(policy)
    _write_gate(policy)

    record, plan = quarantine_mod.rebuild_plan(policy=policy)

    assert record["trigger"] == "archive_quarantine_readiness_rebuild"
    assert record["status"] == "success"
    assert plan["status"] == "ready_for_approval"
    written = quarantine_mod.read_plan(policy=policy)
    assert written is not None
    assert written["schema_version"] == "dlp-source-quarantine-readiness-plan-v1"
