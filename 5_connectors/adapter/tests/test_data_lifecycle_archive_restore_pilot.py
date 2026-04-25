import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
restore_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_restore_pilot")


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


def _quarantine_record_path(policy):
    return Path(policy.archive_quarantine_record_file)


def _write_quarantine_record(policy, payload):
    _quarantine_record_path(policy).write_text(json.dumps(payload), encoding="utf-8")


def _sha(path: Path):
    return restore_mod._sha256_file(path)


def test_restore_blocked_without_successful_quarantine(tmp_path):
    policy = _build_policy(tmp_path)
    _write_quarantine_record(
        policy,
        {
            "schema_version": "dlp-source-quarantine-record-v1",
            "quarantine_id": "q-blocked",
            "status": "blocked",
            "quarantine_copy_path": str(tmp_path / "quarantine" / "copy.jsonl"),
        },
    )

    record, restore = restore_mod.execute_restore_pilot(policy=policy)

    assert record["trigger"] == "archive_restore_pilot_execute"
    assert record["status"] == "blocked"
    assert record["error"] == "blocked_no_successful_quarantine"
    assert restore["status"] == "blocked_no_successful_quarantine"
    assert restore["restore_target_scope"] == "staging"
    assert restore["restore_target_path"] is None


def test_restore_success_to_staging_checksum_match_with_fixture_files(tmp_path):
    policy = _build_policy(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    production_source = fixture_dir / "compile_events.production.jsonl"
    quarantine_copy = fixture_dir / "compile_events.quarantine.jsonl"
    fixture_payload = '{"request_id":"req-fixture","tenant":"all"}\n'
    production_source.write_text(fixture_payload, encoding="utf-8")
    quarantine_copy.write_text(fixture_payload, encoding="utf-8")

    _write_quarantine_record(
        policy,
        {
            "schema_version": "dlp-source-quarantine-record-v1",
            "quarantine_id": "q-success",
            "status": "success",
            "production_source_path": str(production_source),
            "quarantine_copy_path": str(quarantine_copy),
            "quarantine_sha256": _sha(quarantine_copy),
        },
    )

    record, restore = restore_mod.execute_restore_pilot(policy=policy)

    assert record["status"] == "success"
    assert restore["status"] == "success"
    assert restore["restore_target_scope"] == "staging"
    assert restore["checksum_match"] is True
    restored_path = Path(restore["restore_target_path"])
    assert restored_path.exists()
    assert restore["restore_target_checksum"] == _sha(restored_path)
    assert restore["restore_target_checksum"] == _sha(quarantine_copy)
    assert quarantine_copy.exists()


def test_restore_does_not_overwrite_production_source_by_default(tmp_path):
    policy = _build_policy(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    production_source = fixture_dir / "proxy_events.production.jsonl"
    quarantine_copy = fixture_dir / "proxy_events.quarantine.jsonl"
    production_source.write_text("prod-original\n", encoding="utf-8")
    quarantine_copy.write_text("quarantine-copy\n", encoding="utf-8")
    before = production_source.read_text(encoding="utf-8")

    _write_quarantine_record(
        policy,
        {
            "schema_version": "dlp-source-quarantine-record-v1",
            "quarantine_id": "q-no-overwrite",
            "status": "success",
            "production_source_path": str(production_source),
            "quarantine_copy_path": str(quarantine_copy),
            "quarantine_sha256": _sha(quarantine_copy),
        },
    )

    _, restore = restore_mod.execute_restore_pilot(policy=policy)

    restored_path = Path(restore["restore_target_path"])
    assert restore["status"] == "success"
    assert restore["restore_target_scope"] == "staging"
    assert restore["production_source_overwrite"] is False
    assert restored_path != production_source
    assert production_source.read_text(encoding="utf-8") == before
    assert restored_path.read_text(encoding="utf-8") == quarantine_copy.read_text(encoding="utf-8")
    assert quarantine_copy.exists()
