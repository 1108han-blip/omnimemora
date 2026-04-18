from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .backends.base import BackendHealth
from .config import config
from . import track_b_state_machine as _sm

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
            if lowered in _sm.ALLOWED_STATUS:
                sanitized[key] = lowered
            continue
        if key == "status_source":
            lowered = normalized.lower()
            if lowered in _sm.ALLOWED_STATUS_SOURCE_SCOPE:
                sanitized[key] = lowered
            continue
        sanitized[key] = normalized
    return sanitized


def write_status_override(payload: dict[str, Any]) -> dict[str, Any]:
    path = _status_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_status_override(payload)
    current_override = read_status_override()
    _sm.validate_override_scope(sanitized)
    _sm.validate_transition(current_override, sanitized)
    path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sanitized


def clear_status_override() -> None:
    path = _status_override_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return
def build_track_b_status(
    *,
    backend_health: BackendHealth,
    routing_enabled: bool,
    override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    observed = _sm.build_observed_state(
        backend_health=backend_health,
        routing_enabled=routing_enabled,
    )
    return _sm.apply_override(observed=observed, override=override)
