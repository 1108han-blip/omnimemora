from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .backends.base import BackendHealth
from .config import config

_ALLOWED_STATUS = {
    "healthy",
    "degraded-capability",
    "recovering-gateway",
    "user-decision-required",
}
_ALLOWED_OVERRIDE_KEYS = {
    "status",
    "status_source",
    "transition_reason",
    "gateway_health",
    "capability_health",
    "routing_requested",
    "routing_effective",
    "user_action_required",
    "recommended_action",
    "error_code",
}
_ALLOWED_STATUS_SOURCE_SCOPE = {
    "runtime-restart-monitor": {"healthy", "recovering-gateway", "degraded-capability"},
    "gateway-exit-monitor": {"user-decision-required"},
    "manual-override": _ALLOWED_STATUS,
    "internal-test": _ALLOWED_STATUS,
}
_ALLOWED_STATUS_TRANSITIONS = {
    "healthy": {"healthy", "degraded-capability", "recovering-gateway", "user-decision-required"},
    "degraded-capability": {"healthy", "degraded-capability", "recovering-gateway", "user-decision-required"},
    "recovering-gateway": {"healthy", "degraded-capability", "recovering-gateway", "user-decision-required"},
    "user-decision-required": {"user-decision-required", "healthy"},
}


def _status_override_path() -> Path:
    explicit = os.getenv("OMNIMEMORA_TRACK_B_STATUS_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("OMNIMEMORA_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir).resolve() / "track_b_status.json"
    return Path(config.omnimemora_usage_state_path).resolve().parent / "track_b_status.json"


def read_status_override() -> Optional[dict[str, Any]]:
    path = _status_override_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def sanitize_status_override(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in _ALLOWED_OVERRIDE_KEYS:
            continue
        if key in {"routing_requested", "routing_effective", "user_action_required"}:
            sanitized[key] = bool(value)
            continue
        normalized = str(value or "").strip()
        if not normalized:
            continue
        if key == "status":
            lowered = normalized.lower()
            if lowered in _ALLOWED_STATUS:
                sanitized[key] = lowered
            continue
        if key == "status_source":
            lowered = normalized.lower()
            if lowered in _ALLOWED_STATUS_SOURCE_SCOPE:
                sanitized[key] = lowered
            continue
        sanitized[key] = normalized
    return sanitized


def _validate_override_scope(sanitized: dict[str, Any]) -> None:
    status = str(sanitized.get("status") or "").strip().lower()
    if not status:
        return
    source = str(sanitized.get("status_source") or "").strip().lower()
    if not source:
        raise ValueError("status_source is required when status is set")
    allowed = _ALLOWED_STATUS_SOURCE_SCOPE.get(source)
    if not allowed:
        raise ValueError(f"unsupported status_source: {source}")
    if status not in allowed:
        raise ValueError(f"status_source {source} cannot write status {status}")


def _validate_status_transition(current_override: Optional[dict[str, Any]], sanitized: dict[str, Any]) -> None:
    next_status = str(sanitized.get("status") or "").strip().lower()
    if not next_status:
        return
    current_status = str((current_override or {}).get("status") or "").strip().lower()
    if not current_status:
        return
    if current_status == next_status:
        return
    allowed = _ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise ValueError(f"invalid Track B transition: {current_status} -> {next_status}")
    source = str(sanitized.get("status_source") or "").strip().lower()
    if current_status == "user-decision-required" and source not in {"manual-override", "internal-test"}:
        raise ValueError("user-decision-required can only be cleared by explicit user action or test override")


def write_status_override(payload: dict[str, Any]) -> dict[str, Any]:
    path = _status_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_status_override(payload)
    current_override = read_status_override()
    _validate_override_scope(sanitized)
    _validate_status_transition(current_override, sanitized)
    path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sanitized


def clear_status_override() -> None:
    path = _status_override_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _capability_health_state(backend_health: BackendHealth) -> str:
    return "healthy" if backend_health.healthy else "degraded"


def _derive_error_code(backend_health: BackendHealth) -> Optional[str]:
    if backend_health.healthy:
        return None
    details = backend_health.details or {}
    for key in ("error_code", "code", "status"):
        value = str(details.get(key) or "").strip()
        if value:
            return value.lower().replace(" ", "_")
    return "capability_unhealthy"


def build_track_b_status(
    *,
    backend_health: BackendHealth,
    routing_enabled: bool,
    override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    capability_health = _capability_health_state(backend_health)
    observed_status = "healthy"
    observed_transition_reason = "backend_healthy"
    observed_recommended_action = "none"

    if not backend_health.healthy and routing_enabled:
        observed_status = "degraded-capability"
        observed_transition_reason = "capability_unhealthy"
        observed_recommended_action = "degrade_to_passthrough"
    elif not backend_health.healthy and not routing_enabled:
        observed_status = "healthy"
        observed_transition_reason = "route_off_passthrough"
        observed_recommended_action = "none"

    payload: dict[str, Any] = {
        "status": observed_status,
        "status_source": "observed-health",
        "transition_reason": observed_transition_reason,
        "gateway_health": "healthy",
        "capability_health": capability_health,
        "routing_requested": routing_enabled,
        "routing_effective": routing_enabled and backend_health.healthy,
        "user_action_required": False,
        "recommended_action": observed_recommended_action,
        "error_code": _derive_error_code(backend_health),
    }

    if not override:
        return payload

    status = str(override.get("status") or "").strip().lower()
    if status in _ALLOWED_STATUS:
        payload["status"] = status

    status_source = str(override.get("status_source") or "").strip().lower()
    if status_source:
        payload["status_source"] = status_source

    transition_reason = str(override.get("transition_reason") or "").strip()
    if transition_reason:
        payload["transition_reason"] = transition_reason

    gateway_health = str(override.get("gateway_health") or "").strip().lower()
    if gateway_health:
        payload["gateway_health"] = gateway_health

    capability_override = str(override.get("capability_health") or "").strip().lower()
    if capability_override:
        payload["capability_health"] = capability_override

    if "routing_requested" in override:
        payload["routing_requested"] = bool(override.get("routing_requested"))
    if "routing_effective" in override:
        payload["routing_effective"] = bool(override.get("routing_effective"))
    if "user_action_required" in override:
        payload["user_action_required"] = bool(override.get("user_action_required"))

    recommended_action = str(override.get("recommended_action") or "").strip()
    if recommended_action:
        payload["recommended_action"] = recommended_action

    if "error_code" in override:
        error_code = str(override.get("error_code") or "").strip()
        payload["error_code"] = error_code or None

    if payload["status"] == "recovering-gateway":
        payload["gateway_health"] = "recovering"
        payload["routing_effective"] = False
        payload["user_action_required"] = False
        payload["recommended_action"] = "wait_for_recovery"

    if payload["status"] == "user-decision-required":
        payload["gateway_health"] = "unhealthy"
        payload["routing_effective"] = False
        payload["user_action_required"] = True
        payload["recommended_action"] = "disable_route_or_uninstall"

    return payload
