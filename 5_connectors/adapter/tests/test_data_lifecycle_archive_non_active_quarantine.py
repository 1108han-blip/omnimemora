import importlib
import json
from pathlib import Path


non_active_quarantine_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.archive_non_active_quarantine"
)
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
        archive_non_active_candidate_report_file=str(tmp_path / "archive_non_active_candidate_report.json"),
        archive_non_active_quarantine_readiness_file=str(tmp_path / "archive_non_active_quarantine_readiness_plan.json"),
        archive_non_active_execution_gate_file=str(tmp_path / "archive_non_active_execution_gate.json"),
    )


def _sha(path: Path):
    return non_active_quarantine_mod._sha256_file(path)


def _write_json(path: str, payload: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def _seed_ready_gate(policy, *, candidate_path: Path, origin_source_path: Path, gate_allowed=True):
    candidate_sha = _sha(candidate_path)
    target = (
        Path(policy.archive_quarantine_root)
        / "non_active"
        / f"{candidate_path.name}.{candidate_sha[:12]}.quarantine"
    )
    _write_json(
        policy.archive_non_active_quarantine_readiness_file,
        {
            "schema_version": "dlp-non-active-quarantine-readiness-v1",
            "plan_id": "naq-plan-1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "non_active_quarantine_readiness_only",
            "status": "ready_for_operator_approval",
            "selected_candidate": {
                "candidate_id": "archive_pilot_copy:p1",
                "candidate_kind": "archive_pilot_copy",
                "candidate_path": str(candidate_path),
                "bytes": int(candidate_path.stat().st_size),
                "sha256": candidate_sha,
                "origin_source_path": str(origin_source_path),
                "origin_source_kind": "compile_events",
                "origin_source_sha256": _sha(origin_source_path),
                "restore_key": "restore:compile:p1",
                "pilot_id": "p1",
                "planned_quarantine_path": str(target),
            },
            "summary": {
                "selected_candidate_present": True,
                "blocking_count": 0,
                "source_move_executed": False,
                "non_active_copy_move_executed": False,
                "delete_compress_executed": False,
            },
        },
    )
    _write_json(
        policy.archive_non_active_execution_gate_file,
        {
            "schema_version": "dlp-non-active-copy-execution-gate-v1",
            "gate_id": "gate-p1",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "gate_only",
            "allowed": gate_allowed,
            "status": "allowed" if gate_allowed else "blocked",
            "blocking_reasons": [] if gate_allowed else ["missing_operator_approval"],
            "summary": {"allowed": gate_allowed, "blocking_count": 0 if gate_allowed else 1},
        },
    )
    return target


def test_non_active_archive_copy_moves_to_quarantine_and_source_retained(tmp_path):
    policy = _build_policy(tmp_path)
    origin = tmp_path / "compile_events.jsonl"
    origin.write_text('{"request_id":"source"}\n', encoding="utf-8")
    candidate_dir = Path(policy.archive_pilot_root) / "p1"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "compile_events.jsonl.copy"
    candidate.write_text(origin.read_text(encoding="utf-8"), encoding="utf-8")
    target = _seed_ready_gate(policy, candidate_path=candidate, origin_source_path=origin)

    ledger, record = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)

    assert ledger["trigger"] == "archive_non_active_copy_quarantine_execute_one"
    assert ledger["status"] == "success"
    assert record["schema_version"] == "dlp-non-active-copy-quarantine-record-v1"
    assert record["mode"] == "single_non_active_copy_quarantine_only"
    assert record["status"] == "success"
    assert record["source_move_executed"] is False
    assert record["non_active_copy_move_executed"] is True
    assert record["delete_compress_executed"] is False
    assert record["production_read_path_unchanged"] is True
    assert record["source_retained"] is True
    assert record["checksum_match"] is True
    assert origin.exists()
    assert not candidate.exists()
    assert target.exists()
    assert _sha(target) == record["candidate_sha256"]


def test_non_active_quarantine_blocks_when_gate_not_allowed(tmp_path):
    policy = _build_policy(tmp_path)
    origin = tmp_path / "compile_events.jsonl"
    origin.write_text("source\n", encoding="utf-8")
    candidate_dir = Path(policy.archive_pilot_root) / "p1"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "compile_events.jsonl.copy"
    candidate.write_text("source\n", encoding="utf-8")
    target = _seed_ready_gate(policy, candidate_path=candidate, origin_source_path=origin, gate_allowed=False)

    _, record = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)

    assert record["status"] == "blocked"
    assert "non_active_execution_gate_not_allowed" in record["blocking_reasons"]
    assert candidate.exists()
    assert not target.exists()
    assert origin.exists()


def test_non_active_quarantine_blocks_source_like_basename_even_under_pilot_root(tmp_path):
    policy = _build_policy(tmp_path)
    origin = tmp_path / "compile_events.jsonl"
    origin.write_text("source\n", encoding="utf-8")
    candidate_dir = Path(policy.archive_pilot_root) / "p1"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "compile_events.jsonl"
    candidate.write_text("copy\n", encoding="utf-8")
    target = _seed_ready_gate(policy, candidate_path=candidate, origin_source_path=origin)

    _, record = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)

    assert record["status"] == "blocked"
    assert "candidate_path_matches_active_or_control_basename" in record["blocking_reasons"]
    assert candidate.exists()
    assert not target.exists()


def test_non_active_quarantine_second_call_is_idempotent(tmp_path):
    policy = _build_policy(tmp_path)
    origin = tmp_path / "compile_events.jsonl"
    origin.write_text("source\n", encoding="utf-8")
    candidate_dir = Path(policy.archive_pilot_root) / "p1"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "compile_events.jsonl.copy"
    candidate.write_text("source\n", encoding="utf-8")
    target = _seed_ready_gate(policy, candidate_path=candidate, origin_source_path=origin)

    _, first = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    _, second = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)

    assert first["status"] == "success"
    assert second["status"] == "already_quarantined"
    assert target.exists()
    assert origin.exists()


def test_restore_pilot_can_stage_successful_non_active_quarantine_record(tmp_path):
    policy = _build_policy(tmp_path)
    origin = tmp_path / "compile_events.jsonl"
    origin.write_text('{"request_id":"restore"}\n', encoding="utf-8")
    candidate_dir = Path(policy.archive_pilot_root) / "p1"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "compile_events.jsonl.copy"
    candidate.write_text(origin.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_ready_gate(policy, candidate_path=candidate, origin_source_path=origin)
    non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)

    ledger, restore = restore_mod.execute_restore_pilot(policy=policy)

    assert ledger["status"] == "success"
    assert restore["status"] == "success"
    assert restore["restore_target_scope"] == "staging"
    assert restore["production_source_overwrite"] is False
    restored = Path(restore["restore_target_path"])
    assert restored.exists()
    assert restore["checksum_match"] is True
    assert origin.exists()
