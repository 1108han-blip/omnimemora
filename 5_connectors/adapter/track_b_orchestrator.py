from __future__ import annotations

from typing import Dict

from .backends.base import BackendHealth
from . import track_b_status


def routing_requested_from_modes(per_agent_modes: Dict[str, str]) -> bool:
    return any(mode == "force_if_possible" for mode in per_agent_modes.values())


def backend_health_from_runtime_state(health_state: str) -> BackendHealth:
    normalized = str(health_state or "").strip().lower()
    return BackendHealth(
        healthy=normalized == "healthy",
        backend_type="omnimemora_runtime",
        details={"source": "runtime_health_state", "state": normalized or "unknown"},
    )


def _apply_combined_recovery_contract(*, payload: dict, routing_requested: bool) -> dict:
    normalized = dict(payload)

    # Gateway-level failure always wins over capability-level degradation.
    if str(normalized.get("gateway_health") or "").strip().lower() != "healthy":
        return normalized

    # Once the user has disabled route or uninstalled, the steady state must
    # converge to passthrough rather than drifting back into an enhanced path.
    if not routing_requested:
        normalized["status"] = "healthy"
        normalized["routing_requested"] = False
        normalized["routing_effective"] = False
        normalized["user_action_required"] = False
        normalized["recommended_action"] = "none"
        if not str(normalized.get("transition_reason") or "").strip():
            normalized["transition_reason"] = "route_off_passthrough"

    return normalized


def build_system_status_from_backend_health(
    *,
    backend_health: BackendHealth,
    per_agent_modes: Dict[str, str],
) -> dict:
    routing_requested = routing_requested_from_modes(per_agent_modes)
    payload = track_b_status.build_track_b_status(
        backend_health=backend_health,
        routing_enabled=routing_requested,
        override=track_b_status.read_status_override(),
    )
    return _apply_combined_recovery_contract(
        payload=payload,
        routing_requested=routing_requested,
    )


def build_system_status_from_runtime_health(
    *,
    runtime_health_state: str,
    per_agent_modes: Dict[str, str],
) -> dict:
    return build_system_status_from_backend_health(
        backend_health=backend_health_from_runtime_state(runtime_health_state),
        per_agent_modes=per_agent_modes,
    )
