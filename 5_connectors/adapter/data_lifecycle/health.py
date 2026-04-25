"""Lifecycle health surface for Data Lifecycle Plane."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from . import state_store, summary_store
from .policy import DataLifecyclePolicy, load_policy

HEALTH_SCHEMA_VERSION = "dlp-lifecycle-health-v1"
MAINTENANCE_TRIGGERS = {"startup_warm", "interval_refresh", "manual_refresh"}
DEGRADED_WINDOW_SECONDS = 15 * 60


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
    }
