"""Lifecycle health surface for Data Lifecycle Plane."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import (
    state_store,
    summary_store,
    retention,
    traceability,
    archive_plan,
    archive_transaction,
    archive_restore_contract,
    archive_execution_gate,
    archive_pilot,
    archive_readthrough,
    archive_fallback_contract,
    archive_quarantine_readiness,
    archive_quarantine,
    archive_restore_pilot,
    archive_non_active_candidates,
    archive_non_active_quarantine_readiness,
    archive_non_active_execution_gate,
    archive_non_active_quarantine,
    raw_evidence_segments,
    meter_storage_v2,
)
from .policy import DataLifecyclePolicy, load_policy

HEALTH_SCHEMA_VERSION = "dlp-lifecycle-health-v1"
MAINTENANCE_TRIGGERS = {"startup_warm", "interval_refresh", "manual_refresh"}
DEGRADED_WINDOW_SECONDS = 15 * 60
STORAGE_PRESSURE_WARNING_BYTES = 512 * 1024 * 1024
STORAGE_PRESSURE_CRITICAL_BYTES = 2 * 1024 * 1024 * 1024


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _is_valid_summary_contract(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    required_keys = {
        "schema_version",
        "generated_at",
        "source_counts",
        "builder_version",
        "families",
    }
    if not required_keys.issubset(set(payload.keys())):
        return False
    if payload.get("schema_version") != "dlp-family-window-summary-v1":
        return False
    if not isinstance(payload.get("generated_at"), (int, float)):
        return False
    if not isinstance(payload.get("source_counts"), dict):
        return False
    if not isinstance(payload.get("builder_version"), str):
        return False
    if not isinstance(payload.get("families"), dict):
        return False
    return True


def _summary_freshness(
    payload: Optional[dict[str, Any]],
    *,
    policy: DataLifecyclePolicy,
    now_ts: float,
) -> str:
    if payload is None:
        return "missing"
    if not _is_valid_summary_contract(payload):
        return "invalid"
    if summary_store.is_summary_fresh(payload, policy=policy, now_ts=now_ts):
        return "fresh"
    if summary_store.is_summary_usable_when_stale(payload, policy=policy, now_ts=now_ts):
        return "stale_usable"
    return "expired"


def _recent_degraded_records(*, policy: DataLifecyclePolicy, now_ts: float) -> list[dict[str, Any]]:
    candidates = state_store.read_recent_records(limit=100, trigger="read_model_degraded", policy=policy)
    output: list[dict[str, Any]] = []
    cutoff_ts = now_ts - float(DEGRADED_WINDOW_SECONDS)
    for record in candidates:
        completed = _parse_iso_utc(record.get("completed_at"))
        if completed is None:
            output.append(record)
            continue
        if completed.timestamp() >= cutoff_ts:
            output.append(record)
    return output


def _derive_status(
    *,
    summary_freshness: str,
    last_maintenance: Optional[dict[str, Any]],
    recent_degraded_count: int,
) -> tuple[str, str]:
    if isinstance(last_maintenance, dict) and str(last_maintenance.get("status") or "").lower() == "failed":
        return "maintenance_failed", "inspect_last_maintenance_error_and_retry_manual_refresh"
    if summary_freshness == "missing" and last_maintenance is None:
        return "uninitialized", "wait_startup_warm_or_trigger_manual_refresh"
    if summary_freshness == "fresh" and recent_degraded_count == 0:
        return "healthy", "none"
    if summary_freshness == "stale_usable":
        return "stale_usable", "manual_refresh_recommended"
    if recent_degraded_count > 0:
        return "degraded", "inspect_recent_degraded_and_trigger_manual_refresh"
    return "degraded", "trigger_manual_refresh"


def _safe_file_size(path_value: Any) -> int:
    try:
        path = Path(str(path_value)).expanduser()
        if path.exists() and path.is_file():
            return int(path.stat().st_size)
    except Exception:
        return 0
    return 0


def _collect_storage_inventory(policy: DataLifecyclePolicy) -> dict[str, Any]:
    tracked: list[dict[str, Any]] = []

    summary_path = Path(policy.summary_file).expanduser()
    ledger_path = Path(policy.maintenance_state_file).expanduser()
    compile_path = Path.home() / ".omnimemora" / "adapter" / "compile_events.jsonl"
    proxy_path = Path.home() / ".omnimemora" / "adapter" / "proxy_events.jsonl"
    meter_data_dir = Path.home() / ".omnimemora" / "adapter" / "data"

    for label, path in [
        ("dlp_summary", summary_path),
        ("dlp_ledger", ledger_path),
        ("compile_events", compile_path),
        ("proxy_events", proxy_path),
    ]:
        size = _safe_file_size(path)
        tracked.append({"name": label, "path": str(path), "bytes": size})

    if meter_data_dir.exists() and meter_data_dir.is_dir():
        meter_files = sorted(meter_data_dir.glob("meters*.json"))
        meter_total = 0
        for file_path in meter_files:
            meter_total += _safe_file_size(file_path)
        tracked.append(
            {
                "name": "meter_data_dir",
                "path": str(meter_data_dir),
                "bytes": int(meter_total),
                "file_count": len(meter_files),
            }
        )

    total_bytes = int(sum(int(item.get("bytes", 0) or 0) for item in tracked))
    return {
        "total_bytes": total_bytes,
        "tracked_files": sorted(tracked, key=lambda item: int(item.get("bytes", 0) or 0), reverse=True),
    }


def _derive_storage_pressure(total_bytes: int, recent_maintenance: list[dict[str, Any]]) -> tuple[str, str]:
    max_bytes_scanned = max((int(record.get("bytes_scanned", 0) or 0) for record in recent_maintenance), default=0)
    if total_bytes >= STORAGE_PRESSURE_CRITICAL_BYTES:
        return "critical", "prepare_non_destructive_archive_manifest_high_priority"
    if total_bytes >= STORAGE_PRESSURE_WARNING_BYTES:
        return "warning", "prepare_non_destructive_archive_manifest"
    # Maintenance pressure guardrail: heavy repeated scanning hints future pressure.
    if max_bytes_scanned >= int(STORAGE_PRESSURE_WARNING_BYTES * 0.75):
        return "warning", "review_maintenance_scan_pressure_and_prepare_manifest"
    return "normal", "none"


def build_health_payload(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    now_ts: Optional[float] = None,
) -> dict[str, Any]:
    current_policy = policy or load_policy()
    current_now = float(now_ts if now_ts is not None else time.time())

    summary_payload = summary_store.read_summary(policy=current_policy)
    summary_freshness = _summary_freshness(summary_payload, policy=current_policy, now_ts=current_now)
    summary_generated_at = (
        float(summary_payload.get("generated_at"))
        if isinstance(summary_payload, dict) and isinstance(summary_payload.get("generated_at"), (int, float))
        else None
    )
    summary_age_seconds = (
        max(0.0, current_now - float(summary_generated_at)) if isinstance(summary_generated_at, (int, float)) else None
    )

    last_maintenance = state_store.latest_record(trigger=MAINTENANCE_TRIGGERS, policy=current_policy)
    recent_degraded = _recent_degraded_records(policy=current_policy, now_ts=current_now)
    recent_maintenance = state_store.read_recent_records(limit=20, trigger=MAINTENANCE_TRIGGERS, policy=current_policy)
    storage_inventory = _collect_storage_inventory(current_policy)
    storage_pressure, storage_recommendation = _derive_storage_pressure(
        int(storage_inventory.get("total_bytes", 0)),
        recent_maintenance,
    )
    retention_manifest = retention.read_manifest(policy=current_policy)
    if isinstance(retention_manifest, dict):
        retention_summary = retention_manifest.get("summary") or {}
        retention_manifest_view = {
            "status": "present",
            "generated_at": retention_manifest.get("generated_at"),
            "artifact_count": int(retention_summary.get("artifact_count", 0) or 0),
            "total_bytes": int(retention_summary.get("total_bytes", 0) or 0),
            "warnings_count": int(retention_summary.get("warnings_count", 0) or 0),
        }
    else:
        retention_manifest_view = {
            "status": "missing",
            "generated_at": None,
            "artifact_count": 0,
            "total_bytes": 0,
            "warnings_count": 0,
        }
    raw_segments_manifest = raw_evidence_segments.read_manifest(policy=current_policy)
    if isinstance(raw_segments_manifest, dict):
        raw_summary = raw_segments_manifest.get("summary") or {}
        raw_evidence_segments_view = {
            "status": "present",
            "mode": raw_segments_manifest.get("mode"),
            "generated_at": raw_segments_manifest.get("generated_at"),
            "total_segments": int(raw_summary.get("total_segments", 0) or 0),
            "active_segments": int(raw_summary.get("active_segments", 0) or 0),
            "sealed_segments": int(raw_summary.get("sealed_segments", 0) or 0),
            "total_bytes": int(raw_summary.get("total_bytes", 0) or 0),
            "warnings_count": int(raw_summary.get("warnings_count", 0) or 0),
        }
    else:
        raw_evidence_segments_view = {
            "status": "missing",
            "mode": None,
            "generated_at": None,
            "total_segments": 0,
            "active_segments": 0,
            "sealed_segments": 0,
            "total_bytes": 0,
            "warnings_count": 0,
        }
    traceability_report = traceability.read_report(policy=current_policy)
    if isinstance(traceability_report, dict):
        trace_summary = traceability_report.get("summary") or {}
        traceability_report_view = {
            "status": "present",
            "generated_at": traceability_report.get("generated_at"),
            "sample_count": int(trace_summary.get("sample_count", 0) or 0),
            "fail_count": int(trace_summary.get("fail_count", 0) or 0),
            "warnings_count": int(trace_summary.get("warnings_count", 0) or 0),
            "unexplained_partial_count": int(trace_summary.get("unexplained_partial_count", 0) or 0),
            "current_epoch_pass_rate": trace_summary.get("current_epoch_pass_rate"),
        }
    else:
        traceability_report_view = {
            "status": "missing",
            "generated_at": None,
            "sample_count": 0,
            "fail_count": 0,
            "warnings_count": 0,
            "unexplained_partial_count": 0,
            "current_epoch_pass_rate": None,
        }
    archive_candidate_plan = archive_plan.read_plan(policy=current_policy)
    if isinstance(archive_candidate_plan, dict):
        archive_summary = archive_candidate_plan.get("summary") or {}
        archive_plan_view = {
            "status": "present",
            "mode": archive_candidate_plan.get("mode"),
            "eligible_count": int(archive_summary.get("eligible_count", 0) or 0),
            "blocked_count": int(archive_summary.get("blocked_count", 0) or 0),
            "review_required_count": int(archive_summary.get("review_required_count", 0) or 0),
            "total_candidate_bytes": int(archive_summary.get("total_candidate_bytes", 0) or 0),
            "warnings_count": int(archive_summary.get("warnings_count", 0) or 0),
        }
    else:
        archive_plan_view = {
            "status": "missing",
            "mode": None,
            "eligible_count": 0,
            "blocked_count": 0,
            "review_required_count": 0,
            "total_candidate_bytes": 0,
            "warnings_count": 0,
        }
    archive_txn_preview = archive_transaction.read_preview(policy=current_policy)
    if isinstance(archive_txn_preview, dict):
        txn_summary = archive_txn_preview.get("summary") or {}
        archive_txn_view = {
            "status": "present",
            "mode": archive_txn_preview.get("mode"),
            "eligible_input_count": int(txn_summary.get("eligible_input_count", 0) or 0),
            "preview_item_count": int(txn_summary.get("preview_item_count", 0) or 0),
            "excluded_blocked_count": int(txn_summary.get("excluded_blocked_count", 0) or 0),
            "excluded_review_required_count": int(txn_summary.get("excluded_review_required_count", 0) or 0),
            "blocked_precondition_count": int(txn_summary.get("blocked_precondition_count", 0) or 0),
            "total_preview_bytes": int(txn_summary.get("total_preview_bytes", 0) or 0),
            "warnings_count": int(txn_summary.get("warnings_count", 0) or 0),
        }
    else:
        archive_txn_view = {
            "status": "missing",
            "mode": None,
            "eligible_input_count": 0,
            "preview_item_count": 0,
            "excluded_blocked_count": 0,
            "excluded_review_required_count": 0,
            "blocked_precondition_count": 0,
            "total_preview_bytes": 0,
            "warnings_count": 0,
        }
    archive_restore_readiness = archive_restore_contract.read_readiness_report(policy=current_policy)
    if isinstance(archive_restore_readiness, dict):
        readiness_summary = archive_restore_readiness.get("summary") or {}
        archive_restore_view = {
            "status": "present",
            "mode": archive_restore_readiness.get("mode"),
            "sample_count": int(readiness_summary.get("sample_count", 0) or 0),
            "mapped_request_count": int(readiness_summary.get("mapped_request_count", 0) or 0),
            "unmapped_request_count": int(readiness_summary.get("unmapped_request_count", 0) or 0),
            "warnings_count": int(readiness_summary.get("warnings_count", 0) or 0),
        }
    else:
        archive_restore_view = {
            "status": "missing",
            "mode": None,
            "sample_count": 0,
            "mapped_request_count": 0,
            "unmapped_request_count": 0,
            "warnings_count": 0,
        }
    archive_exec_gate = archive_execution_gate.read_gate(policy=current_policy)
    if isinstance(archive_exec_gate, dict):
        gate_summary = archive_exec_gate.get("summary") or {}
        gate_approval = archive_exec_gate.get("approval") or {}
        archive_gate_view = {
            "status": "present",
            "allowed": bool(archive_exec_gate.get("allowed")),
            "gate_status": archive_exec_gate.get("status"),
            "blocking_count": int(gate_summary.get("blocking_count", len(archive_exec_gate.get("blocking_reasons") or [])) or 0),
            "approval_status": gate_approval.get("status", gate_summary.get("approval_status")),
            "expires_at": gate_approval.get("expires_at", gate_summary.get("expires_at")),
        }
    else:
        archive_gate_view = {
            "status": "missing",
            "allowed": False,
            "gate_status": "missing",
            "blocking_count": 0,
            "approval_status": "missing",
            "expires_at": None,
        }
    latest_pilot = archive_pilot.read_latest_pilot_record(policy=current_policy)
    if isinstance(latest_pilot, dict):
        archive_pilot_view = {
            "status": "present",
            "pilot_id": latest_pilot.get("pilot_id"),
            "source_kind": latest_pilot.get("source_kind"),
            "source_bytes": int(latest_pilot.get("source_bytes", 0) or 0),
            "archive_bytes": int(latest_pilot.get("archive_bytes", 0) or 0),
            "checksum_match": bool(latest_pilot.get("checksum_match")),
            "source_retained": bool(latest_pilot.get("source_retained", False)),
            "read_path_unchanged": bool(latest_pilot.get("read_path_unchanged", True)),
        }
    else:
        archive_pilot_view = {
            "status": "missing",
            "pilot_id": None,
            "source_kind": None,
            "source_bytes": 0,
            "archive_bytes": 0,
            "checksum_match": False,
            "source_retained": False,
            "read_path_unchanged": True,
        }
    latest_readthrough = archive_readthrough.read_report(policy=current_policy)
    if isinstance(latest_readthrough, dict):
        archive_readthrough_view = {
            "status": str(latest_readthrough.get("status") or "present"),
            "source_retained": bool(latest_readthrough.get("source_retained", False)),
            "archive_copy_readable": bool(latest_readthrough.get("archive_copy_readable", False)),
            "checksum_match": bool(latest_readthrough.get("checksum_match", False)),
            "read_path_unchanged": bool(latest_readthrough.get("read_path_unchanged", True)),
            "validated_at": latest_readthrough.get("generated_at"),
        }
    else:
        archive_readthrough_view = {
            "status": "missing",
            "source_retained": False,
            "archive_copy_readable": False,
            "checksum_match": False,
            "read_path_unchanged": True,
            "validated_at": None,
        }
    archive_fallback = archive_fallback_contract.read_report(policy=current_policy)
    if isinstance(archive_fallback, dict):
        fallback_summary = archive_fallback.get("summary") or {}
        archive_fallback_view = {
            "status": str(archive_fallback.get("status") or "present"),
            "mode": archive_fallback.get("mode"),
            "fallback_available": bool(archive_fallback.get("fallback_available", False)),
            "archive_copy_readable": bool(archive_fallback.get("archive_copy_readable", False)),
            "checksum_match": bool(archive_fallback.get("checksum_match", False)),
            "source_missing_simulated": bool(archive_fallback.get("source_missing_simulated", False)),
            "production_read_path_unchanged": bool(
                archive_fallback.get("production_read_path_unchanged", True)
            ),
            "request_evidence_fallback_status": fallback_summary.get("request_evidence_fallback_status"),
            "validated_at": fallback_summary.get("validated_at", archive_fallback.get("generated_at")),
        }
    else:
        archive_fallback_view = {
            "status": "missing",
            "mode": None,
            "fallback_available": False,
            "archive_copy_readable": False,
            "checksum_match": False,
            "source_missing_simulated": False,
            "production_read_path_unchanged": True,
            "request_evidence_fallback_status": None,
            "validated_at": None,
        }
    quarantine_readiness = archive_quarantine_readiness.read_plan(policy=current_policy)
    if isinstance(quarantine_readiness, dict):
        quarantine_summary = quarantine_readiness.get("summary") or {}
        archive_quarantine_readiness_view = {
            "status": str(quarantine_readiness.get("status") or "present"),
            "mode": quarantine_readiness.get("mode"),
            "candidate_present": bool(quarantine_summary.get("candidate_present", False)),
            "blocking_count": int(quarantine_summary.get("blocking_count", 0) or 0),
            "source_move_executed": bool(quarantine_readiness.get("source_move_executed", False)),
            "source_retained": bool(quarantine_readiness.get("source_retained", False)),
            "production_read_path_unchanged": bool(
                quarantine_readiness.get("production_read_path_unchanged", True)
            ),
            "planned_action": (quarantine_readiness.get("transaction_preview") or {}).get("planned_action"),
        }
    else:
        archive_quarantine_readiness_view = {
            "status": "missing",
            "mode": None,
            "candidate_present": False,
            "blocking_count": 0,
            "source_move_executed": False,
            "source_retained": False,
            "production_read_path_unchanged": True,
            "planned_action": None,
        }
    quarantine_record = archive_quarantine.read_record(policy=current_policy)
    if isinstance(quarantine_record, dict):
        quarantine_summary = quarantine_record.get("summary") or {}
        archive_quarantine_view = {
            "status": str(quarantine_record.get("status") or "present"),
            "mode": quarantine_record.get("mode"),
            "source_kind": quarantine_record.get("source_kind"),
            "source_move_executed": bool(quarantine_record.get("source_move_executed", False)),
            "source_retained": bool(quarantine_record.get("source_retained", False)),
            "checksum_match": bool(quarantine_record.get("checksum_match", False)),
            "blocking_count": int(
                quarantine_summary.get(
                    "blocking_count",
                    len(quarantine_record.get("blocking_reasons") or []),
                )
                or 0
            ),
            "quarantine_path": quarantine_record.get("quarantine_path"),
        }
    else:
        archive_quarantine_view = {
            "status": "missing",
            "mode": None,
            "source_kind": None,
            "source_move_executed": False,
            "source_retained": False,
            "checksum_match": False,
            "blocking_count": 0,
            "quarantine_path": None,
        }
    restore_pilot = archive_restore_pilot.read_latest_restore_pilot_record(policy=current_policy)
    if isinstance(restore_pilot, dict):
        archive_restore_pilot_view = {
            "status": str(restore_pilot.get("status") or "present"),
            "mode": restore_pilot.get("mode"),
            "restore_target_scope": restore_pilot.get("restore_target_scope"),
            "restore_target_path": restore_pilot.get("restore_target_path"),
            "checksum_match": bool(restore_pilot.get("checksum_match", False)),
            "production_source_overwrite": bool(restore_pilot.get("production_source_overwrite", False)),
            "archive_copy_retained": bool(restore_pilot.get("archive_copy_retained", True)),
            "quarantine_copy_retained": bool(restore_pilot.get("quarantine_copy_retained", True)),
        }
    else:
        archive_restore_pilot_view = {
            "status": "missing",
            "mode": None,
            "restore_target_scope": None,
            "restore_target_path": None,
            "checksum_match": False,
            "production_source_overwrite": False,
            "archive_copy_retained": True,
            "quarantine_copy_retained": True,
        }
    non_active_report = archive_non_active_candidates.read_report(policy=current_policy)
    if isinstance(non_active_report, dict):
        non_active_summary = non_active_report.get("summary") or {}
        archive_non_active_view = {
            "status": "present",
            "mode": non_active_report.get("mode"),
            "total_scanned": int(non_active_summary.get("total_scanned", 0) or 0),
            "plausible_non_active_count": int(non_active_summary.get("plausible_non_active_count", 0) or 0),
            "forbidden_count": int(non_active_summary.get("forbidden_count", 0) or 0),
            "review_required_count": int(non_active_summary.get("review_required_count", 0) or 0),
            "warnings_count": int(non_active_summary.get("warnings_count", 0) or 0),
            "source_move_delete_compress_executed": bool(
                non_active_summary.get("source_move_delete_compress_executed", False)
            ),
        }
    else:
        archive_non_active_view = {
            "status": "missing",
            "mode": None,
            "total_scanned": 0,
            "plausible_non_active_count": 0,
            "forbidden_count": 0,
            "review_required_count": 0,
            "warnings_count": 0,
            "source_move_delete_compress_executed": False,
        }
    non_active_quarantine = archive_non_active_quarantine_readiness.read_plan(policy=current_policy)
    if isinstance(non_active_quarantine, dict):
        non_active_quarantine_summary = non_active_quarantine.get("summary") or {}
        selected_candidate = non_active_quarantine.get("selected_candidate") or {}
        archive_non_active_quarantine_view = {
            "status": str(non_active_quarantine.get("status") or "present"),
            "mode": non_active_quarantine.get("mode"),
            "selected_candidate_present": bool(non_active_quarantine_summary.get("selected_candidate_present", False)),
            "selected_candidate_kind": selected_candidate.get("candidate_kind"),
            "selected_candidate_path": selected_candidate.get("candidate_path"),
            "planned_quarantine_path": selected_candidate.get("planned_quarantine_path")
            or (non_active_quarantine.get("transaction_preview") or {}).get("planned_quarantine_path"),
            "blocking_count": int(non_active_quarantine_summary.get("blocking_count", 0) or 0),
            "source_move_executed": bool(non_active_quarantine_summary.get("source_move_executed", False)),
            "non_active_copy_move_executed": bool(
                non_active_quarantine_summary.get("non_active_copy_move_executed", False)
            ),
            "delete_compress_executed": bool(non_active_quarantine_summary.get("delete_compress_executed", False)),
        }
    else:
        archive_non_active_quarantine_view = {
            "status": "missing",
            "mode": None,
            "selected_candidate_present": False,
            "selected_candidate_kind": None,
            "selected_candidate_path": None,
            "planned_quarantine_path": None,
            "blocking_count": 0,
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
        }
    non_active_gate = archive_non_active_execution_gate.read_gate(policy=current_policy)
    if isinstance(non_active_gate, dict):
        gate_summary = non_active_gate.get("summary") or {}
        gate_approval = non_active_gate.get("approval") or {}
        archive_non_active_gate_view = {
            "status": "present",
            "allowed": bool(non_active_gate.get("allowed", False)),
            "gate_status": non_active_gate.get("status"),
            "mode": non_active_gate.get("mode"),
            "blocking_count": int(gate_summary.get("blocking_count", 0) or 0),
            "approval_status": gate_approval.get("status", gate_summary.get("approval_status")),
            "source_move_allowed": bool(gate_summary.get("source_move_allowed", False)),
            "delete_allowed": bool(gate_summary.get("delete_allowed", False)),
            "compress_allowed": bool(gate_summary.get("compress_allowed", False)),
        }
    else:
        archive_non_active_gate_view = {
            "status": "missing",
            "allowed": False,
            "gate_status": "missing",
            "mode": None,
            "blocking_count": 0,
            "approval_status": "missing",
            "source_move_allowed": False,
            "delete_allowed": False,
            "compress_allowed": False,
        }
    non_active_quarantine_record = archive_non_active_quarantine.read_record(policy=current_policy)
    if isinstance(non_active_quarantine_record, dict):
        non_active_quarantine_record_summary = non_active_quarantine_record.get("summary") or {}
        archive_non_active_quarantine_record_view = {
            "status": str(non_active_quarantine_record.get("status") or "present"),
            "mode": non_active_quarantine_record.get("mode"),
            "candidate_kind": non_active_quarantine_record.get("candidate_kind"),
            "candidate_path": non_active_quarantine_record.get("candidate_path"),
            "quarantine_path": non_active_quarantine_record.get("quarantine_path"),
            "checksum_match": bool(non_active_quarantine_record.get("checksum_match", False)),
            "source_move_executed": bool(non_active_quarantine_record.get("source_move_executed", False)),
            "non_active_copy_move_executed": bool(
                non_active_quarantine_record.get(
                    "non_active_copy_move_executed",
                    non_active_quarantine_record_summary.get("non_active_copy_move_executed", False),
                )
            ),
            "delete_compress_executed": bool(non_active_quarantine_record.get("delete_compress_executed", False)),
            "production_read_path_unchanged": bool(
                non_active_quarantine_record.get("production_read_path_unchanged", True)
            ),
            "blocking_count": int(
                non_active_quarantine_record_summary.get(
                    "blocking_count",
                    len(non_active_quarantine_record.get("blocking_reasons") or []),
                )
                or 0
            ),
        }
    else:
        archive_non_active_quarantine_record_view = {
            "status": "missing",
            "mode": None,
            "candidate_kind": None,
            "candidate_path": None,
            "quarantine_path": None,
            "checksum_match": False,
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
            "production_read_path_unchanged": True,
            "blocking_count": 0,
        }
    status, recommended_action = _derive_status(
        summary_freshness=summary_freshness,
        last_maintenance=last_maintenance,
        recent_degraded_count=len(recent_degraded),
    )
    try:
        meter_storage_v2_view = meter_storage_v2.get_status_payload()
    except Exception:
        meter_storage_v2_view = {
            "schema_version": meter_storage_v2.METER_STORAGE_STATUS_SCHEMA_VERSION,
            "status": "missing",
            "mode": meter_storage_v2.METER_STORAGE_MODE,
            "read_path": {
                "legacy_authoritative": True,
                "request_meter_switch_enabled": False,
                "request_evidence_switch_enabled": False,
                "metrics_switch_enabled": False,
                "status_read_model_switch_enabled": False,
                "legacy_fallback_enabled": False,
                "request_meter_read_mode": "legacy_only",
                "request_evidence_read_mode": "legacy_only",
                "metrics_read_mode": "legacy_only",
                "status_read_model_read_mode": "legacy_only",
                "cleanup_eligibility": "not_started",
            },
            "storage": {
                "sqlite_path": None,
                "sqlite_count": 0,
                "legacy_count": 0,
            },
            "write_errors": {"count": 0, "latest": None},
            "cleanup": {
                "status": "missing",
                "mode": "preview_only",
                "cleanup_allowed": False,
                "candidate_file_count": 0,
                "estimated_reclaim_bytes": 0,
                "blocking_reasons_count": 0,
                "execution_gate_status": "missing",
                "execution_gate_allowed": False,
                "transaction_preview_status": "missing",
                "transaction_execution_allowed": False,
                "rollback_drill_status": "missing",
                "rollback_drill_checksum_match": False,
                "rollback_required": True,
            },
            "backup_export": {
                "status": "missing",
                "mode": "backup_export_readiness_only",
                "backup_export_allowed": False,
                "cleanup_allowed": False,
                "execution_allowed": False,
                "candidate_file_count": 0,
                "estimated_export_bytes": 0,
                "blocking_reasons_count": 0,
                "plan_status": "missing",
                "dry_run_mode": "dry_run_preview_only",
                "destination_status": {
                    "status": "unknown",
                    "path": None,
                    "exists": False,
                    "is_directory": False,
                    "free_bytes": None,
                    "required_free_bytes": None,
                    "policy_ok": False,
                },
                "package_manifest_status": "missing",
                "package_manifest_file_count": 0,
                "package_manifest_total_bytes": 0,
                "approval_template_status": "missing",
                "execution_gate_status": "missing",
                "execution_gate_allowed": False,
                "approval_status": "missing",
                "backup_export_execution_started": False,
                "cleanup_execution_started": False,
            },
        }

    return {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "status": status,
        "recommended_action": recommended_action,
        "summary": {
            "present": isinstance(summary_payload, dict),
            "contract_valid": _is_valid_summary_contract(summary_payload),
            "freshness": summary_freshness,
            "generated_at": summary_generated_at,
            "age_seconds": summary_age_seconds,
            "ttl_seconds": float(current_policy.summary_ttl_seconds),
            "stale_max_age_seconds": float(current_policy.summary_stale_max_age_seconds),
        },
        "maintenance": {
            "last_record": last_maintenance,
            "last_status": (last_maintenance or {}).get("status"),
            "last_trigger": (last_maintenance or {}).get("trigger"),
        },
        "recent_degraded_fallback": {
            "window_seconds": int(DEGRADED_WINDOW_SECONDS),
            "count": len(recent_degraded),
            "latest_record": recent_degraded[0] if recent_degraded else None,
        },
        "storage_pressure": storage_pressure,
        "storage": {
            "total_bytes": int(storage_inventory.get("total_bytes", 0)),
            "recommendation": storage_recommendation,
            "tracked_files": storage_inventory.get("tracked_files", []),
            "recent_maintenance_scanned_bytes_max": max(
                (int(record.get("bytes_scanned", 0) or 0) for record in recent_maintenance),
                default=0,
            ),
        },
        "raw_evidence_segments": raw_evidence_segments_view,
        "meter_storage_v2": meter_storage_v2_view,
        "retention_manifest": retention_manifest_view,
        "traceability_report": traceability_report_view,
        "archive_plan": archive_plan_view,
        "archive_transaction_preview": archive_txn_view,
        "archive_restore_readiness": archive_restore_view,
        "archive_execution_gate": archive_gate_view,
        "archive_pilot": archive_pilot_view,
        "archive_readthrough": archive_readthrough_view,
        "archive_fallback_simulation": archive_fallback_view,
        "archive_quarantine_readiness": archive_quarantine_readiness_view,
        "archive_quarantine": archive_quarantine_view,
        "archive_restore_pilot": archive_restore_pilot_view,
        "archive_non_active_candidates": archive_non_active_view,
        "archive_non_active_quarantine_readiness": archive_non_active_quarantine_view,
        "archive_non_active_execution_gate": archive_non_active_gate_view,
        "archive_non_active_quarantine": archive_non_active_quarantine_record_view,
    }
