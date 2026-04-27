"""Lifecycle health surface for Data Lifecycle Plane."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import meter_storage_v2, state_store, summary_store
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


def _frozen_artifact_view(mode: Optional[str] = None) -> dict[str, Any]:
    return {
        "status": "frozen",
        "mode": mode,
        "generated_at": None,
        "artifact_count": 0,
        "total_bytes": 0,
        "warnings_count": 0,
    }


def _frozen_archive_gate_view() -> dict[str, Any]:
    return {
        "status": "frozen",
        "allowed": False,
        "gate_status": "frozen",
        "blocking_count": 0,
        "approval_status": "frozen",
        "expires_at": None,
    }


def _raw_log_retention_view(current_policy: DataLifecyclePolicy) -> dict[str, Any]:
    retention_days = 7
    max_active_lines = 1000
    logs: list[dict[str, Any]] = []
    for name, path_value in [
        ("trace_events", Path.home() / ".omnimemora" / "adapter" / "trace_events.jsonl"),
        ("proxy_events", Path.home() / ".omnimemora" / "adapter" / "proxy_events.jsonl"),
        ("compile_events", Path.home() / ".omnimemora" / "adapter" / "compile_events.jsonl"),
        ("maintenance_state", Path(current_policy.maintenance_state_file).expanduser()),
    ]:
        path = Path(path_value).expanduser()
        logs.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
                "bytes": _safe_file_size(path),
            }
        )
    return {
        "status": "bounded",
        "retention_days": retention_days,
        "max_active_lines": max_active_lines,
        "logs": logs,
    }


def _frozen_archive_views() -> dict[str, dict[str, Any]]:
    return {
        "retention_manifest": _frozen_artifact_view("frozen_internal_diagnostic"),
        "traceability_report": {
            "status": "frozen",
            "generated_at": None,
            "sample_count": 0,
            "fail_count": 0,
            "warnings_count": 0,
            "unexplained_partial_count": 0,
            "current_epoch_pass_rate": None,
        },
        "archive_plan": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "eligible_count": 0,
            "blocked_count": 0,
            "review_required_count": 0,
            "total_candidate_bytes": 0,
            "warnings_count": 0,
        },
        "archive_transaction_preview": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "eligible_input_count": 0,
            "preview_item_count": 0,
            "excluded_blocked_count": 0,
            "excluded_review_required_count": 0,
            "blocked_precondition_count": 0,
            "total_preview_bytes": 0,
            "warnings_count": 0,
        },
        "archive_restore_readiness": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "sample_count": 0,
            "mapped_request_count": 0,
            "unmapped_request_count": 0,
            "warnings_count": 0,
        },
        "archive_execution_gate": _frozen_archive_gate_view(),
        "archive_pilot": {
            "status": "frozen",
            "pilot_id": None,
            "source_kind": None,
            "source_bytes": 0,
            "archive_bytes": 0,
            "checksum_match": False,
            "source_retained": False,
            "read_path_unchanged": True,
        },
        "archive_readthrough": {
            "status": "frozen",
            "source_retained": False,
            "archive_copy_readable": False,
            "checksum_match": False,
            "read_path_unchanged": True,
            "validated_at": None,
        },
        "archive_fallback_simulation": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "fallback_available": False,
            "archive_copy_readable": False,
            "checksum_match": False,
            "source_missing_simulated": False,
            "production_read_path_unchanged": True,
            "request_evidence_fallback_status": None,
            "validated_at": None,
        },
        "archive_quarantine_readiness": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "candidate_present": False,
            "blocking_count": 0,
            "source_move_executed": False,
            "source_retained": False,
            "production_read_path_unchanged": True,
            "planned_action": None,
        },
        "archive_quarantine": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "source_kind": None,
            "source_move_executed": False,
            "source_retained": False,
            "checksum_match": False,
            "blocking_count": 0,
            "quarantine_path": None,
        },
        "archive_restore_pilot": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "restore_target_scope": None,
            "restore_target_path": None,
            "checksum_match": False,
            "production_source_overwrite": False,
            "archive_copy_retained": True,
            "quarantine_copy_retained": True,
        },
        "archive_non_active_candidates": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "total_scanned": 0,
            "plausible_non_active_count": 0,
            "forbidden_count": 0,
            "review_required_count": 0,
            "warnings_count": 0,
            "source_move_delete_compress_executed": False,
        },
        "archive_non_active_quarantine_readiness": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "selected_candidate_present": False,
            "selected_candidate_kind": None,
            "selected_candidate_path": None,
            "planned_quarantine_path": None,
            "blocking_count": 0,
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
        },
        "archive_non_active_execution_gate": {
            "status": "frozen",
            "allowed": False,
            "gate_status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "blocking_count": 0,
            "approval_status": "frozen",
            "source_move_allowed": False,
            "delete_allowed": False,
            "compress_allowed": False,
        },
        "archive_non_active_quarantine": {
            "status": "frozen",
            "mode": "automatic_cleanup_expansion_paused",
            "candidate_kind": None,
            "candidate_path": None,
            "quarantine_path": None,
            "checksum_match": False,
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
            "production_read_path_unchanged": True,
            "blocking_count": 0,
        },
    }


def build_health_payload(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    now_ts: Optional[float] = None,
    detail: str = "fast",
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
    raw_log_retention_view = _raw_log_retention_view(current_policy)
    status, recommended_action = _derive_status(
        summary_freshness=summary_freshness,
        last_maintenance=last_maintenance,
        recent_degraded_count=len(recent_degraded),
    )
    try:
        meter_storage_v2_view = meter_storage_v2.get_status_payload(detail=detail)
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
                "pilot_status": "missing",
                "pilot_mode": "single_reversible_quarantine_only",
                "source_move_executed": False,
                "delete_executed": False,
                "compress_executed": False,
                "truncate_executed": False,
                "batch_cleanup_executed": False,
                "stability_window_status": "missing",
                "stability_window_observed_pilot_status": "missing",
                "stability_window_cleanup_scope_expansion_started": False,
                "scaleup_readiness_status": "missing",
                "scaleup_ready": False,
                "repeatable_pilot_protocol_status": "missing",
                "second_file_pilot_proposal_status": "missing",
                "second_file_pilot_approval_readiness_status": "missing",
                "second_file_pilot_allowed": False,
                "cleanup_scope_expansion_started": False,
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

    payload = {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "status": status,
        "recommended_action": recommended_action,
        "detail": "fast",
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
        "raw_log_retention": raw_log_retention_view,
        "meter_storage_v2": meter_storage_v2_view,
        "frozen_governance": {
            "status": "cold_path_only",
            "detail": "use_detail_full_or_dedicated_debug_endpoints",
            "cleanup_execution_started": False,
            "backup_export_execution_started": False,
            "cleanup_scope_expansion_started": False,
        },
    }
    if str(detail or "fast").strip().lower() != "full":
        return payload

    recent_maintenance = state_store.read_recent_records(limit=20, trigger=MAINTENANCE_TRIGGERS, policy=current_policy)
    storage_inventory = _collect_storage_inventory(current_policy)
    storage_pressure, storage_recommendation = _derive_storage_pressure(
        int(storage_inventory.get("total_bytes", 0)),
        recent_maintenance,
    )
    raw_evidence_segments_view = {
        "status": "frozen",
        "mode": str(getattr(current_policy, "raw_evidence_segments_mode", "disabled") or "disabled"),
        "generated_at": None,
        "total_segments": 0,
        "active_segments": 0,
        "sealed_segments": 0,
        "total_bytes": 0,
        "warnings_count": 0,
        "mirror_enabled": getattr(current_policy, "raw_evidence_segments_mode", "disabled")
        == "dual_write_observe_only",
    }
    archive_views = _frozen_archive_views()
    payload.update(
        {
            "detail": "full",
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
        }
    )
    payload.update(
        {
        "retention_manifest": archive_views["retention_manifest"],
        "traceability_report": archive_views["traceability_report"],
        "archive_plan": archive_views["archive_plan"],
        "archive_transaction_preview": archive_views["archive_transaction_preview"],
        "archive_restore_readiness": archive_views["archive_restore_readiness"],
        "archive_execution_gate": archive_views["archive_execution_gate"],
        "archive_pilot": archive_views["archive_pilot"],
        "archive_readthrough": archive_views["archive_readthrough"],
        "archive_fallback_simulation": archive_views["archive_fallback_simulation"],
        "archive_quarantine_readiness": archive_views["archive_quarantine_readiness"],
        "archive_quarantine": archive_views["archive_quarantine"],
        "archive_restore_pilot": archive_views["archive_restore_pilot"],
        "archive_non_active_candidates": archive_views["archive_non_active_candidates"],
        "archive_non_active_quarantine_readiness": archive_views["archive_non_active_quarantine_readiness"],
        "archive_non_active_execution_gate": archive_views["archive_non_active_execution_gate"],
        "archive_non_active_quarantine": archive_views["archive_non_active_quarantine"],
        }
    )
    return payload
