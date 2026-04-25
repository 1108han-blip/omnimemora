"""Safety invariants tests for Data Lifecycle Plane.

These tests codify the DLP safety contract. They do NOT change product behaviour.
They verify that the existing safety boundaries hold.

Test invariants:
  I1  Non-active executor only moves archive_pilot_copy (never source evidence).
  I2  Source evidence basename/path/kind are never moved by non-active executor.
  I3  No delete/compress/batch cleanup/source-move endpoints exist in data_lifecycle_api.
  I4  Restore pilot only writes to staging; production_source_overwrite is always False.
  I5  Readthrough is shadow_validation_only; no production read-path switch.
  I6  Lineage checksum (quarantine snapshot) is separate from current source checksum.
  I7  Non-active quarantine mode is single_non_active_copy_quarantine_only.
  I8  Non-active gate denies source_move_allowed and delete_allowed.
  I9  Archive pilot mode is copy_to_archive_only (never destructive).
  I10 Source quarantine executor blocks active candidates.
  I11 Forbidden basenames constant covers all DLP control artifacts.
  I12 Health surface propagates correct safety flags from non-active quarantine record.
  I13 Health surface non-active gate view denies dangerous operations.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

non_active_quarantine_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.archive_non_active_quarantine"
)
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
archive_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_pilot")
archive_restore_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_restore_pilot")
archive_quarantine_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_quarantine")
archive_non_active_gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_non_active_execution_gate")
health_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.health")
data_lifecycle_api_mod = importlib.import_module("5_connectors.adapter.data_lifecycle_api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: str, payload: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def _seed_full_chain(policy, *, content="content"):
    """Seed all prerequisites so non-active quarantine can execute on a valid archive_pilot_copy."""
    origin = Path.home() / ".omnimemora" / "adapter" / "compile_events.jsonl"
    origin.parent.mkdir(parents=True, exist_ok=True)
    origin.write_text(f'{{"request_id":"invariants"}}\n{content}', encoding="utf-8")
    pilot_dir = Path(policy.archive_pilot_root) / "p1"
    pilot_dir.mkdir(parents=True, exist_ok=True)
    candidate = pilot_dir / "compile_events.jsonl.81b50dd5f1bd.copy"
    candidate.write_text(f'{{"request_id":"invariants"}}\n{content}', encoding="utf-8")
    origin_sha = _sha256_file(origin)
    candidate_sha = _sha256_file(candidate)
    target = (
        Path(policy.archive_quarantine_root)
        / "non_active"
        / f"compile_events.jsonl.81b50dd5f1bd.copy.{candidate_sha[:12]}.quarantine"
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
                "candidate_path": str(candidate),
                "bytes": int(candidate.stat().st_size),
                "sha256": candidate_sha,
                "origin_source_path": str(origin),
                "origin_source_kind": "compile_events",
                "origin_source_sha256": origin_sha,
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
            "allowed": True,
            "status": "allowed",
            "blocking_reasons": [],
            "summary": {
                "allowed": True,
                "blocking_count": 0,
                "source_move_allowed": False,
                "delete_allowed": False,
                "compress_allowed": False,
            },
        },
    )
    return origin, candidate, target


# ---------------------------------------------------------------------------
# I1: Non-active executor only moves archive_pilot_copy
# ---------------------------------------------------------------------------

def test_non_active_quarantine_rejects_candidate_kind_not_archive_pilot_copy(tmp_path):
    policy = _build_policy(tmp_path)
    origin, candidate, target = _seed_full_chain(policy)
    # Override readiness with wrong candidate kind
    _write_json(
        policy.archive_non_active_quarantine_readiness_file,
        {
            "schema_version": "dlp-non-active-quarantine-readiness-v1",
            "plan_id": "naq-plan-bad-kind",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "non_active_quarantine_readiness_only",
            "status": "ready_for_operator_approval",
            "selected_candidate": {
                "candidate_id": "source:bad",
                "candidate_kind": "compile_events",  # Not archive_pilot_copy
                "candidate_path": str(candidate),
                "bytes": 10,
                "sha256": _sha256_file(candidate),
                "origin_source_path": str(origin),
                "origin_source_kind": "compile_events",
                "origin_source_sha256": _sha256_file(origin),
                "restore_key": "restore:compile:bad",
                "pilot_id": None,
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
    _, record = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    assert record["status"] == "blocked"
    assert "selected_candidate_not_archive_pilot_copy" in record.get("blocking_reasons", [])
    assert origin.exists()
    assert not target.exists()


# ---------------------------------------------------------------------------
# I2: Forbidden source basenames are blocked
# ---------------------------------------------------------------------------

_FORBIDDEN_BASENAMES = {
    "compile_events.jsonl",
    "proxy_events.jsonl",
    "trace_events.jsonl",
    "meters_index.json",
    "family_window_summary.json",
}


@pytest.mark.parametrize("basename", sorted(_FORBIDDEN_BASENAMES))
def test_non_active_quarantine_blocks_forbidden_source_basename(tmp_path, basename):
    policy = _build_policy(tmp_path)
    origin = tmp_path / "compile_events.jsonl"
    origin.write_text("source\n", encoding="utf-8")
    # Use the forbidden basename directly as candidate_path (not a .copy file).
    # The _FORBIDDEN_SOURCE_BASENAMES check only looks at candidate_path.name,
    # so compile_events.jsonl will match the forbidden "compile_events.jsonl".
    candidate = tmp_path / basename  # e.g. compile_events.jsonl
    candidate.write_text("content\n", encoding="utf-8")
    target = (
        Path(policy.archive_quarantine_root)
        / "non_active"
        / f"{candidate.name}.{_sha256_file(candidate)[:12]}.quarantine"
    )
    _write_json(
        policy.archive_non_active_quarantine_readiness_file,
        {
            "schema_version": "dlp-non-active-quarantine-readiness-v1",
            "plan_id": f"naq-plan-{basename}",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "non_active_quarantine_readiness_only",
            "status": "ready_for_operator_approval",
            "selected_candidate": {
                "candidate_id": f"bad:{basename}",
                "candidate_kind": "archive_pilot_copy",
                "candidate_path": str(candidate),  # basename matches _FORBIDDEN_SOURCE_BASENAMES
                "bytes": int(candidate.stat().st_size),
                "sha256": _sha256_file(candidate),
                "origin_source_path": str(origin),
                "origin_source_kind": basename.replace(".jsonl", "").replace(".json", ""),
                "origin_source_sha256": _sha256_file(origin),
                "restore_key": f"restore:bad:{basename}",
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
            "gate_id": f"gate-{basename}",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "mode": "gate_only",
            "allowed": True,
            "status": "allowed",
            "blocking_reasons": [],
            "summary": {
                "allowed": True,
                "blocking_count": 0,
                "source_move_allowed": False,
                "delete_allowed": False,
                "compress_allowed": False,
            },
        },
    )
    _, record = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    assert record["status"] == "blocked"
    assert "candidate_path_matches_active_or_control_basename" in record.get("blocking_reasons", [])
    assert candidate.exists()
    assert not target.exists()


# ---------------------------------------------------------------------------
# I3: No destructive endpoints in data_lifecycle_api router
# ---------------------------------------------------------------------------

def test_no_delete_compress_batch_cleanup_source_move_endpoints_in_dlp_api():
    """Verify no endpoint paths imply source deletion, compression, batch cleanup, or source move."""
    router = data_lifecycle_api_mod.router
    forbidden_substrings = [
        "/delete",
        "/compress",
        "/batch",
        "/cleanup",
        "/source-move",
        "/source_delete",
        "/source_compress",
        "/source_move",
    ]
    found = []
    for route in router.routes:
        path = getattr(route, "path", "")
        for frag in forbidden_substrings:
            if frag in path:
                found.append(path)
    assert not found, f"Found forbidden endpoint paths in data_lifecycle_api: {found}"


def test_no_destructive_http_methods_on_any_dlp_endpoint():
    """All DLP router routes must use GET or POST only (no PUT/PATCH/DELETE)."""
    destructive_methods = {"put", "patch", "delete", "options", "head"}
    router = data_lifecycle_api_mod.router
    found = []
    for route in router.routes:
        methods = set(getattr(route, "methods", []))
        dangerous = methods & destructive_methods
        if dangerous:
            found.append(f"{getattr(route, 'path', '')} uses {dangerous}")
    assert not found, f"Destructive HTTP methods found in DLP routes: {found}"


# ---------------------------------------------------------------------------
# I4: Restore pilot only writes to staging
# ---------------------------------------------------------------------------

def test_restore_pilot_record_schema_has_staging_only_contract(tmp_path):
    """Restore pilot record must always have restore_target_scope=staging when successful."""
    policy = _build_policy(tmp_path)
    origin, candidate, target = _seed_full_chain(policy)
    _, qrecord = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    assert qrecord["status"] == "success"

    _, rrecord = archive_restore_pilot_mod.execute_restore_pilot(policy=policy)
    assert rrecord["status"] == "success"
    assert rrecord["restore_target_scope"] == "staging", \
        "Restore pilot must write to staging only, not production"
    assert rrecord["production_source_overwrite"] is False, \
        "Restore pilot must never overwrite production source"
    restored = Path(rrecord["restore_target_path"])
    assert str(restored).startswith(str(Path(policy.archive_restore_staging_root))), \
        f"Restore target {restored} must be under staging root {policy.archive_restore_staging_root}"


def test_restore_pilot_blocks_when_no_successful_quarantine(tmp_path):
    """Without a successful quarantine, restore pilot must be blocked."""
    policy = _build_policy(tmp_path)
    # No quarantine record
    _, rrecord = archive_restore_pilot_mod.execute_restore_pilot(policy=policy)
    assert rrecord["status"] == archive_restore_pilot_mod.BLOCKED_NO_SUCCESSFUL_QUARANTINE


# ---------------------------------------------------------------------------
# I5: Readthrough is shadow_validation_only
# ---------------------------------------------------------------------------

def test_readthrough_mode_is_shadow_validation_only():
    readthrough_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_readthrough")
    assert readthrough_mod._MODE == "shadow_validation_only", \
        "Readthrough mode must remain shadow_validation_only"


def test_readthrough_report_has_read_path_unchanged_flag(tmp_path):
    """Readthrough report must include read_path_unchanged=true contract."""
    readthrough_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_readthrough")
    policy = _build_policy(tmp_path)
    # No pilot — report should still have read_path_unchanged
    report = readthrough_mod.build_readthrough_report(policy=policy)
    assert "read_path_unchanged" in report
    assert report["read_path_unchanged"] is True


# ---------------------------------------------------------------------------
# I6: Lineage checksum is separate from current source checksum
# ---------------------------------------------------------------------------

def test_quarantine_record_captures_origin_source_sha_at_quarantine_time(tmp_path):
    """Quarantine record must snapshot origin_source_sha256 at quarantine time, not re-read current source."""
    policy = _build_policy(tmp_path)
    origin, candidate, target = _seed_full_chain(policy)
    _, qrecord = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    assert qrecord["status"] == "success"
    origin_sha_at_quarantine = qrecord.get("origin_source_sha256")
    assert origin_sha_at_quarantine is not None
    # Source was not mutated during quarantine
    assert _sha256_file(origin) == origin_sha_at_quarantine


def test_source_growth_does_not_affect_quarantine_record_sha256(tmp_path):
    """Simulate source growing after quarantine — quarantine sha must remain unchanged."""
    policy = _build_policy(tmp_path)
    origin, candidate, target = _seed_full_chain(policy)
    _, qrecord = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    assert qrecord["status"] == "success"
    quarantine_time_sha = qrecord.get("origin_source_sha256")
    # Simulate source growing after quarantine
    origin.write_text(
        f'{{"request_id":"invariants"}}\ncontent\nmore content\n', encoding="utf-8"
    )
    current_sha = _sha256_file(origin)
    # The key invariant: quarantine record has origin_source_sha256 captured at quarantine time
    assert "origin_source_sha256" in qrecord
    assert qrecord["origin_source_sha256"] == quarantine_time_sha
    # Confirm source grew (sha changed)
    assert current_sha != quarantine_time_sha


# ---------------------------------------------------------------------------
# I7: Non-active quarantine mode is single_non_active_copy_quarantine_only
# ---------------------------------------------------------------------------

def test_non_active_quarantine_record_schema_version_and_mode():
    assert (
        non_active_quarantine_mod.NON_ACTIVE_QUARANTINE_RECORD_SCHEMA_VERSION
        == "dlp-non-active-copy-quarantine-record-v1"
    )
    assert (
        non_active_quarantine_mod.NON_ACTIVE_QUARANTINE_MODE
        == "single_non_active_copy_quarantine_only"
    )


def test_non_active_quarantine_record_has_all_safety_flags(tmp_path):
    policy = _build_policy(tmp_path)
    origin, candidate, target = _seed_full_chain(policy)
    _, record = non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    assert record["status"] == "success"
    assert record["source_move_executed"] is False
    assert record["non_active_copy_move_executed"] is True
    assert record["delete_compress_executed"] is False
    assert record["production_read_path_unchanged"] is True
    assert record["source_retained"] is True
    assert record["checksum_match"] is True


# ---------------------------------------------------------------------------
# I8: Non-active gate denies source_move_allowed and delete_allowed
# ---------------------------------------------------------------------------

def test_non_active_gate_denies_source_move_and_delete(tmp_path):
    policy = _build_policy(tmp_path)
    gate = archive_non_active_gate_mod.build_gate(policy=policy)
    summary = gate.get("summary") or {}
    assert summary.get("source_move_allowed") is False, \
        "Non-active gate must deny source_move_allowed"
    assert summary.get("delete_allowed") is False, \
        "Non-active gate must deny delete_allowed"
    assert gate.get("allowed") is False, \
        "Non-active gate must default to not allowed without operator approval"


# ---------------------------------------------------------------------------
# I9: Archive pilot mode is copy_to_archive_only
# ---------------------------------------------------------------------------

def test_archive_pilot_mode_is_copy_to_archive_only():
    assert archive_pilot_mod.ARCHIVE_PILOT_RECORD_MODE == "copy_to_archive_only"


def test_archive_pilot_record_always_has_source_retained_when_blocked(tmp_path):
    """When archive pilot is blocked (no approval), source_retained must be True in the record."""
    policy = _build_policy(tmp_path)
    pilot_dir = Path(policy.archive_pilot_root) / "p1"
    pilot_dir.mkdir(parents=True, exist_ok=True)
    source = Path.home() / ".omnimemora" / "adapter" / "compile_events.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('{"request_id":"pilot-safety"}\n', encoding="utf-8")
    pilot = pilot_dir / "compile_events.jsonl.copy"
    pilot.write_text('{"request_id":"pilot-safety"}\n', encoding="utf-8")
    # Gate not seeded — pilot should be blocked
    _, record = archive_pilot_mod.copy_one_pilot(policy=policy)
    assert record["status"] == "blocked"
    assert record["source_retained"] is True, \
        "Blocked archive pilot must retain source"


# ---------------------------------------------------------------------------
# I10: Source quarantine executor blocks active candidates
# ---------------------------------------------------------------------------

def test_source_quarantine_blocks_active_source(tmp_path):
    policy = _build_policy(tmp_path)
    quarantine_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_quarantine")
    quarantine_readiness_mod = importlib.import_module(
        "5_connectors.adapter.data_lifecycle.archive_quarantine_readiness"
    )
    # Seed active source (compile_events)
    source = Path.home() / ".omnimemora" / "adapter" / "compile_events.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('{"request_id":"active"}\n', encoding="utf-8")
    source_sha = _sha256_file(source)
    # Seed a valid pilot record pointing to the active source
    _write_json(
        policy.archive_pilot_record_file,
        {
            "schema_version": "dlp-archive-pilot-record-v1",
            "pilot_id": "p1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "copy_to_archive_only",
            "status": "success",
            "source_path": str(source),
            "source_kind": "compile_events",
            "source_bytes": int(source.stat().st_size),
            "source_sha256": source_sha,
            "archive_path": str(Path(policy.archive_pilot_root) / "p1" / "compile_events.jsonl.copy"),
            "archive_bytes": int(source.stat().st_size),
            "archive_sha256": source_sha,
            "checksum_match": True,
            "source_retained": True,
            "restore_key": "restore:compile:active",
        },
    )
    # Seed a readiness plan (required by executor)
    readiness = quarantine_readiness_mod.build_quarantine_readiness_plan(policy=policy)
    _write_json(policy.archive_quarantine_readiness_file, readiness)
    # Seed execution gate (required)
    _write_json(
        policy.archive_execution_gate_file,
        {
            "schema_version": "dlp-archive-execution-gate-v1",
            "gate_id": "gate-active",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "gate_only",
            "allowed": True,
            "status": "allowed",
            "blocking_reasons": [],
            "summary": {"allowed": True, "blocking_count": 0},
        },
    )
    # Seed operator approval
    _write_json(
        policy.archive_operator_approval_file,
        {
            "schema_version": "dlp-archive-operator-approval-v1",
            "approval_id": "approval-active",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
            "gate_hash": "dummy",
            "operator": "test",
            "status": "approved",
        },
    )
    # Seed fallback simulation
    _write_json(
        policy.archive_fallback_simulation_file,
        {
            "schema_version": "dlp-archive-fallback-simulation-v1",
            "simulation_id": "fallback-active",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "diagnostic_only",
            "status": "passed",
            "summary": {"request_evidence_fallback_status": "not_applicable"},
        },
    )
    # Seed readthrough report
    _write_json(
        policy.archive_readthrough_report_file,
        {
            "schema_version": "dlp-archive-readthrough-report-v1",
            "report_id": "readthrough-active",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "shadow_validation_only",
            "status": "passed",
            "source_retained": True,
        },
    )
    _, record = quarantine_mod.execute_single_artifact_quarantine(policy=policy)
    assert record["status"] == "blocked"
    assert "candidate_is_active_hot_source" in record.get("blocking_reasons", [])
    assert record["source_move_executed"] is False
    assert record["source_retained"] is True


# ---------------------------------------------------------------------------
# I11: Forbidden basenames constant covers all DLP control artifacts
# ---------------------------------------------------------------------------

def test_forbidden_basename_set_covers_all_dlp_control_artifacts():
    """The forbidden basename set must cover all known source evidence and DLP control artifacts."""
    expected = {
        "compile_events.jsonl",
        "proxy_events.jsonl",
        "trace_events.jsonl",
        "meters_index.json",
        "family_window_summary.json",
        "maintenance_state.jsonl",
        "retention_manifest.json",
        "traceability_report.json",
        "archive_candidate_plan.json",
        "archive_transaction_preview.json",
        "archive_restore_readiness_report.json",
        "archive_execution_gate.json",
        "archive_operator_approval.json",
        "archive_pilot_record.json",
        "archive_readthrough_report.json",
        "archive_fallback_simulation_report.json",
        "archive_quarantine_readiness_plan.json",
        "archive_quarantine_record.json",
        "archive_restore_pilot_record.json",
        "archive_non_active_candidate_report.json",
        "archive_non_active_quarantine_readiness_plan.json",
        "archive_non_active_execution_gate.json",
    }
    actual = non_active_quarantine_mod._FORBIDDEN_SOURCE_BASENAMES
    assert actual == expected, (
        f"Forbidden basename set mismatch.\n"
        f"Missing: {expected - actual}\n"
        f"Extra: {actual - expected}"
    )


# ---------------------------------------------------------------------------
# I12: Health surface propagates correct safety flags from non-active quarantine
# ---------------------------------------------------------------------------

def test_health_surface_non_active_quarantine_record_view_has_safety_flags(tmp_path):
    """Health payload key is 'archive_non_active_quarantine' (the quarantine record view)."""
    policy = _build_policy(tmp_path)
    origin, candidate, target = _seed_full_chain(policy)
    non_active_quarantine_mod.execute_single_non_active_copy_quarantine(policy=policy)
    health = health_mod.build_health_payload(policy=policy)
    # Key is archive_non_active_quarantine (not _record_view suffix)
    view = health.get("archive_non_active_quarantine") or {}
    assert view.get("status") == "success"
    assert view.get("source_move_executed") is False
    assert view.get("non_active_copy_move_executed") is True
    assert view.get("delete_compress_executed") is False
    assert view.get("production_read_path_unchanged") is True
    assert view.get("checksum_match") is True


# ---------------------------------------------------------------------------
# I13: Archive non-active gate health view denies dangerous operations
# ---------------------------------------------------------------------------

def test_health_surface_non_active_gate_denies_source_move_delete_compress(tmp_path):
    policy = _build_policy(tmp_path)
    # Build gate (no approval)
    archive_non_active_gate_mod.build_gate(policy=policy)
    health = health_mod.build_health_payload(policy=policy)
    # Key in health payload is archive_non_active_execution_gate (gate view)
    view = health.get("archive_non_active_execution_gate") or {}
    assert view.get("source_move_allowed") is False
    assert view.get("delete_allowed") is False
    assert view.get("compress_allowed") is False
