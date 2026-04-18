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


def _status_override_path() -> Path:
    explicit = os.getenv("OMNIMEMORA_TRACK_B_STATUS_PATH", "").strip()
    if explicit:
        return Path(explicit)
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
    payload: dict[str, Any] = {
        "status": "healthy" if backend_health.healthy else "degraded-capability",
        "gateway_health": "healthy",
        "capability_health": capability_health,
        "routing_requested": routing_enabled,
        "routing_effective": routing_enabled and backend_health.healthy,
        "user_action_required": False,
        "recommended_action": "none" if backend_health.healthy else "degrade_to_passthrough",
        "error_code": _derive_error_code(backend_health),
    }

    if not override:
        return payload

    status = str(override.get("status") or "").strip().lower()
    if status in _ALLOWED_STATUS:
        payload["status"] = status

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
