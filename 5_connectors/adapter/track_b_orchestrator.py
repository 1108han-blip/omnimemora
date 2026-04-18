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


def build_system_status_from_backend_health(
    *,
    backend_health: BackendHealth,
    per_agent_modes: Dict[str, str],
) -> dict:
    return track_b_status.build_track_b_status(
        backend_health=backend_health,
        routing_enabled=routing_requested_from_modes(per_agent_modes),
        override=track_b_status.read_status_override(),
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
