from __future__ import annotations

from typing import Any, Dict, Optional, Set

from .backends.base import BackendHealth

ALLOWED_STATUS: Set[str] = {
    "healthy",
    "degraded-capability",
    "recovering-gateway",
    "user-decision-required",
}

ALLOWED_STATUS_SOURCE_SCOPE: Dict[str, Set[str]] = {
    "runtime-restart-monitor": {"healthy", "recovering-gateway", "degraded-capability"},
    "gateway-restart-monitor": {"healthy", "recovering-gateway"},
    "gateway-exit-monitor": {"user-decision-required"},
    "manual-override": ALLOWED_STATUS,
    "internal-test": ALLOWED_STATUS,
}

ALLOWED_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    "healthy": {"healthy", "degraded-capability", "recovering-gateway", "user-decision-required"},
    "degraded-capability": {"healthy", "degraded-capability", "recovering-gateway", "user-decision-required"},
    "recovering-gateway": {"healthy", "degraded-capability", "recovering-gateway", "user-decision-required"},
    "user-decision-required": {"user-decision-required", "healthy"},
}


def derive_error_code(backend_health: BackendHealth) -> Optional[str]:
    if backend_health.healthy:
        return None
    details = backend_health.details or {}
    for key in ("error_code", "code", "status"):
        value = str(details.get(key) or "").strip()
        if value:
            return value.lower().replace(" ", "_")
    return "capability_unhealthy"


def capability_health_state(backend_health: BackendHealth) -> str:
    return "healthy" if backend_health.healthy else "degraded"


def build_observed_state(*, backend_health: BackendHealth, routing_enabled: bool) -> dict[str, Any]:
    capability_health = capability_health_state(backend_health)
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

    return {
        "status": observed_status,
        "status_source": "observed-health",
        "transition_reason": observed_transition_reason,
        "gateway_health": "healthy",
        "capability_health": capability_health,
        "routing_requested": routing_enabled,
        "routing_effective": routing_enabled and backend_health.healthy,
        "user_action_required": False,
        "recommended_action": observed_recommended_action,
        "error_code": derive_error_code(backend_health),
    }


def validate_override_scope(sanitized: dict[str, Any]) -> None:
    status = str(sanitized.get("status") or "").strip().lower()
    if not status:
        return
    source = str(sanitized.get("status_source") or "").strip().lower()
    if not source:
        raise ValueError("status_source is required when status is set")
    allowed = ALLOWED_STATUS_SOURCE_SCOPE.get(source)
    if not allowed:
        raise ValueError(f"unsupported status_source: {source}")
    if status not in allowed:
        raise ValueError(f"status_source {source} cannot write status {status}")


def validate_transition(current_override: Optional[dict[str, Any]], sanitized: dict[str, Any]) -> None:
    next_status = str(sanitized.get("status") or "").strip().lower()
    if not next_status:
        return
    current_status = str((current_override or {}).get("status") or "").strip().lower()
    if not current_status:
        return
    if current_status == next_status:
        return
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise ValueError(f"invalid Track B transition: {current_status} -> {next_status}")
    source = str(sanitized.get("status_source") or "").strip().lower()
    if current_status == "user-decision-required" and source not in {"manual-override", "internal-test"}:
        raise ValueError("user-decision-required can only be cleared by explicit user action or test override")


def apply_override(*, observed: dict[str, Any], override: Optional[dict[str, Any]]) -> dict[str, Any]:
    payload = dict(observed)
    if not override:
        return payload

    status = str(override.get("status") or "").strip().lower()
    if status in ALLOWED_STATUS:
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
