"""Lifecycle health surface for Data Lifecycle Plane."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import state_store, summary_store
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
    status, recommended_action = _derive_status(
        summary_freshness=summary_freshness,
        last_maintenance=last_maintenance,
        recent_degraded_count=len(recent_degraded),
    )

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
    }
