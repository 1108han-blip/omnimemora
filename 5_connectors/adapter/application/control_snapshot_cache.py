"""Snapshot cache for /agents/control read-model payload."""

from __future__ import annotations

import copy
import time
from typing import Optional

DEFAULT_TTL_SECONDS = 10.0

_snapshot_payload: Optional[dict] = None
_snapshot_expires_at: float = 0.0


def _cache_now() -> float:
    return time.monotonic()


def invalidate_agents_control_snapshot() -> None:
    global _snapshot_payload, _snapshot_expires_at
    _snapshot_payload = None
    _snapshot_expires_at = 0.0


def load_cached_agents_control_snapshot() -> Optional[dict]:
    if _snapshot_payload is None:
        return None
    if _cache_now() >= _snapshot_expires_at:
        return None
    return copy.deepcopy(_snapshot_payload)


def store_agents_control_snapshot(payload: dict, *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
    global _snapshot_payload, _snapshot_expires_at
    _snapshot_payload = copy.deepcopy(payload)
    _snapshot_expires_at = _cache_now() + max(0.0, float(ttl_seconds))


def force_expire_agents_control_snapshot_for_test() -> None:
    global _snapshot_expires_at
    _snapshot_expires_at = 0.0
