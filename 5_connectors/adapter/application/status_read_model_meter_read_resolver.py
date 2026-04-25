"""Status read-model meter resolver: sqlite-first with legacy fallback."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional

_meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
_meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
TokenSavingsMeter = _meter_store.TokenSavingsMeter

READ_PATH_ENV = "OMNIMEMORA_STATUS_READ_MODEL_METER_READ_PATH"
MODE_LEGACY_ONLY = "legacy_only"
MODE_SQLITE_FIRST = "sqlite_first_legacy_fallback"
_SUPPORTED_MODES = {MODE_LEGACY_ONLY, MODE_SQLITE_FIRST}


@dataclass
class StatusReadModelMetersResolution:
    meters: list[Any]
    mode: str
    source: str
    degraded: bool
    degraded_reason: Optional[str]


def current_read_path_mode() -> str:
    value = str(os.getenv(READ_PATH_ENV, MODE_SQLITE_FIRST)).strip().lower()
    if value in _SUPPORTED_MODES:
        return value
    return MODE_SQLITE_FIRST


def _to_meter(payload: Any) -> Optional[TokenSavingsMeter]:
    if payload is None:
        return None
    if isinstance(payload, TokenSavingsMeter):
        return payload
    if isinstance(payload, dict):
        try:
            return TokenSavingsMeter(**payload)
        except Exception:
            return None
    if hasattr(payload, "to_dict"):
        try:
            return TokenSavingsMeter(**payload.to_dict())
        except Exception:
            return None
    return None


def resolve_status_read_model_meters(
    *,
    family_id: str,
    window_minutes: int,
    legacy_collect_fn: Callable[[str, int], list[Any]],
    family_match_fn: Callable[[Any, str], bool],
) -> StatusReadModelMetersResolution:
    mode = current_read_path_mode()
    if mode == MODE_LEGACY_ONLY:
        legacy = list(legacy_collect_fn(family_id, window_minutes))
        return StatusReadModelMetersResolution(
            meters=legacy,
            mode=mode,
            source="legacy",
            degraded=False,
            degraded_reason=None,
        )

    since_utc = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    since_iso = since_utc.isoformat()
    try:
        sqlite_rows = _meter_store_v2.query_recent(
            since_iso=since_iso,
            limit=200000,
        )
    except Exception as exc:
        legacy = list(legacy_collect_fn(family_id, window_minutes))
        return StatusReadModelMetersResolution(
            meters=legacy,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason=f"sqlite_read_error:{exc}",
        )

    sqlite_family: list[TokenSavingsMeter] = []
    malformed_count = 0
    for payload in sqlite_rows:
        meter = _to_meter(payload)
        if meter is None:
            malformed_count += 1
            continue
        if family_match_fn(meter, family_id):
            sqlite_family.append(meter)

    if malformed_count > 0:
        legacy = list(legacy_collect_fn(family_id, window_minutes))
        return StatusReadModelMetersResolution(
            meters=legacy,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason="sqlite_payload_malformed",
        )

    if sqlite_family:
        return StatusReadModelMetersResolution(
            meters=sqlite_family,
            mode=mode,
            source="sqlite",
            degraded=False,
            degraded_reason=None,
        )

    legacy_meters = list(legacy_collect_fn(family_id, window_minutes))
    if legacy_meters:
        return StatusReadModelMetersResolution(
            meters=legacy_meters,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason="sqlite_miss",
        )

    return StatusReadModelMetersResolution(
        meters=[],
        mode=mode,
        source="sqlite",
        degraded=False,
        degraded_reason=None,
    )
