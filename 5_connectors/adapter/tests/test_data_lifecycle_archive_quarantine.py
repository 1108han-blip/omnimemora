import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


archive_approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_approval")
archive_quarantine_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_quarantine")
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
        archive_quarantine_root=str(tmp_path / "quarantine" / "source"),
        archive_quarantine_readiness_file=str(tmp_path / "archive_quarantine_readiness_plan.json"),
        archive_quarantine_record_file=str(tmp_path / "archive_quarantine_record.json"),
        archive_restore_pilot_record_file=str(tmp_path / "archive_restore_pilot_record.json"),
        archive_restore_staging_root=str(tmp_path / "restore" / "staging"),
    )


def _sha(path: Path):
    return archive_quarantine_mod._sha256_file(path)


def _write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_prereqs(
    policy,
    *,
    source_path: Path,
    source_kind: str,
    quarantine_path: Path,
    gate_allowed: bool = True,
    fallback_status: str = "passed",
    readthrough_status: str = "passed",
):
    archive_copy = source_path.parent / f"{source_path.stem}.archive-copy{source_path.suffix}"
    archive_copy.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    source_sha = _sha(source_path)
    archive_sha = _sha(archive_copy)

    _write_json(
        Path(policy.archive_quarantine_readiness_file),
        {
            "schema_version": "dlp-source-quarantine-readiness-plan-v1",
            "plan_id": "qplan1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "readiness_plan_only",
            "status": "ready_for_approval",
            "candidate": {
                "source_path": str(source_path),
                "source_kind": source_kind,
                "source_bytes": int(source_path.stat().st_size),
                "source_sha256": source_sha,
                "archive_path": str(archive_copy),
                "archive_sha256": archive_sha,
                "planned_quarantine_path": str(quarantine_path),
            },
        },
    )
    _write_json(
        Path(policy.archive_execution_gate_file),
        {
            "schema_version": "dlp-archive-execution-gate-v1",
            "gate_id": "g1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "gate_only",
            "allowed": gate_allowed,
            "status": "allowed" if gate_allowed else "blocked",
        },
    )
    approval = archive_approval_mod.build_approval_artifact(
        operator_id="operator-q",
        approved_artifact_hashes={"candidate_plan_hash": "dummy"},
        scope="stage12b",
        reason="test",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    archive_approval_mod.write_approval_atomic(approval, policy=policy)
    _write_json(
        Path(policy.archive_fallback_simulation_file),
        {
            "schema_version": "dlp-archive-fallback-simulation-v1",
            "simulation_id": "fb1",
            "mode": "diagnostic_fallback_only",
            "status": fallback_status,
        },
    )
    _write_json(
        Path(policy.archive_readthrough_report_file),
        {
            "schema_version": "dlp-archive-readthrough-report-v1",
            "report_id": "rt1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "shadow_validation_only",
            "status": readthrough_status,
        },
    )
    _write_json(
        Path(policy.archive_pilot_record_file),
        {
            "schema_version": "dlp-archive-pilot-record-v1",
            "pilot_id": "pilot1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "copy_to_archive_only",
            "status": "success",
            "source_path": str(source_path),
            "source_kind": source_kind,
            "source_bytes": int(source_path.stat().st_size),
            "source_sha256": source_sha,
            "archive_path": str(archive_copy),
            "archive_sha256": archive_sha,
            "restore_key": "restore:test",
        },
    )


def test_active_source_is_blocked_and_source_unchanged(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "compile_events.jsonl"
    source.write_text('{"request_id":"hot"}\n', encoding="utf-8")
    before = source.read_text(encoding="utf-8")
    quarantine_path = tmp_path / "quarantine" / "source" / "compile_events.q"
    _seed_prereqs(
        policy,
        source_path=source,
        source_kind="compile_events",
        quarantine_path=quarantine_path,
    )

    _, record = archive_quarantine_mod.execute_single_artifact_quarantine(policy=policy)

    assert record["schema_version"] == "dlp-source-quarantine-record-v1"
    assert record["mode"] == "single_artifact_quarantine_only"
    assert record["status"] == "blocked"
    assert "candidate_is_active_hot_source" in record["blocking_reasons"]
    assert record["source_move_executed"] is False
    assert source.exists()
    assert source.read_text(encoding="utf-8") == before
    assert not quarantine_path.exists()


def test_non_active_fixture_moved_to_quarantine_with_checksum_match(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "fixture_events.jsonl"
    source.write_text('{"fixture":1}\n', encoding="utf-8")
    quarantine_path = tmp_path / "quarantine" / "source" / "fixture_events.q"
    _seed_prereqs(
        policy,
        source_path=source,
        source_kind="fixture_export",
        quarantine_path=quarantine_path,
    )

    _, record = archive_quarantine_mod.execute_single_artifact_quarantine(policy=policy)

    assert record["status"] == "success"
    assert record["source_move_executed"] is True
    assert record["checksum_match"] is True
    assert not source.exists()
    assert quarantine_path.exists()
    assert record["quarantine_sha256"] == record["source_sha256"]


def test_missing_gate_approval_fallback_readthrough_blocks(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "fixture_events.jsonl"
    source.write_text('{"fixture":2}\n', encoding="utf-8")
    quarantine_path = tmp_path / "quarantine" / "source" / "fixture_events.q"
    # readiness + pilot only; intentionally omit gate/approval/fallback/readthrough
    source_sha = _sha(source)
    _write_json(
        Path(policy.archive_quarantine_readiness_file),
        {
            "schema_version": "dlp-source-quarantine-readiness-plan-v1",
            "plan_id": "qplan2",
            "mode": "readiness_plan_only",
            "status": "ready_for_approval",
            "candidate": {
                "source_path": str(source),
                "source_kind": "fixture_export",
                "source_sha256": source_sha,
                "planned_quarantine_path": str(quarantine_path),
            },
        },
    )
    _write_json(
        Path(policy.archive_pilot_record_file),
        {
            "schema_version": "dlp-archive-pilot-record-v1",
            "pilot_id": "pilot2",
            "mode": "copy_to_archive_only",
            "status": "success",
            "source_path": str(source),
            "source_kind": "fixture_export",
            "source_sha256": source_sha,
        },
    )

    _, record = archive_quarantine_mod.execute_single_artifact_quarantine(policy=policy)

    assert record["status"] == "blocked"
    assert "missing_execution_gate" in record["blocking_reasons"]
    assert "missing_operator_approval" in record["blocking_reasons"]
    assert "missing_fallback_simulation" in record["blocking_reasons"]
    assert "missing_readthrough_report" in record["blocking_reasons"]
    assert source.exists()
    assert not quarantine_path.exists()


def test_second_call_is_safe_already_quarantined(tmp_path):
    policy = _build_policy(tmp_path)
    source = tmp_path / "fixture_events.jsonl"
    source.write_text('{"fixture":3}\n', encoding="utf-8")
    quarantine_path = tmp_path / "quarantine" / "source" / "fixture_events.q"
    _seed_prereqs(
        policy,
        source_path=source,
        source_kind="fixture_export",
        quarantine_path=quarantine_path,
    )

    _, first = archive_quarantine_mod.execute_single_artifact_quarantine(policy=policy)
    _, second = archive_quarantine_mod.execute_single_artifact_quarantine(policy=policy)

    assert first["status"] == "success"
    assert second["status"] in {"already_quarantined", "success"}
    assert not source.exists()
    assert quarantine_path.exists()
