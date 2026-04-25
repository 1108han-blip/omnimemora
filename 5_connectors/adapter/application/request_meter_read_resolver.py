"""Request-meter read-path resolver for narrow sqlite-first switch."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

_4_core = importlib.import_module("4_core.logic.v2_compute")
TokenSavingsMeter = _4_core.TokenSavingsMeter

_meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
_state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")

READ_PATH_ENV = "OMNIMEMORA_REQUEST_METER_READ_PATH"
MODE_LEGACY_ONLY = "legacy_only"
MODE_SQLITE_FIRST = "sqlite_first_legacy_fallback"
_SUPPORTED_MODES = {MODE_LEGACY_ONLY, MODE_SQLITE_FIRST}


@dataclass
class MeterReadResolution:
    meter: Optional[TokenSavingsMeter]
    mode: str
    source: str
    degraded: bool
    degraded_reason: Optional[str]


def current_read_path_mode() -> str:
    value = str(os.getenv(READ_PATH_ENV, MODE_SQLITE_FIRST)).strip().lower()
    if value in _SUPPORTED_MODES:
        return value
    return MODE_SQLITE_FIRST


def _append_degraded_record(reason: str) -> None:
    now = datetime.now(timezone.utc)
    record = _state_store.build_record(
        cycle_id=_state_store.new_cycle_id(),
        trigger="request_meter_read_fallback",
        started_at=now,
        completed_at=now,
        status="degraded",
        bytes_scanned=0,
        error=reason,
    )
    _state_store.append_state_record(record)


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


def resolve_request_meter(
    request_id: str,
    *,
    legacy_get_meter_fn: Callable[[str], Any],
) -> MeterReadResolution:
    mode = current_read_path_mode()
    if mode == MODE_LEGACY_ONLY:
        meter = _to_meter(legacy_get_meter_fn(request_id))
        return MeterReadResolution(
            meter=meter,
            mode=mode,
            source="legacy",
            degraded=False,
            degraded_reason=None,
        )

    try:
        sqlite_payload = _meter_store_v2.get_meter(request_id)
    except Exception as exc:
        reason = f"sqlite_read_error:{exc}"
        _append_degraded_record(reason)
        legacy_meter = _to_meter(legacy_get_meter_fn(request_id))
        return MeterReadResolution(
            meter=legacy_meter,
            mode=mode,
            source="legacy_fallback" if legacy_meter else "sqlite",
            degraded=True,
            degraded_reason=reason,
        )

    if sqlite_payload is not None:
        sqlite_meter = _to_meter(sqlite_payload)
        if sqlite_meter is not None:
            return MeterReadResolution(
                meter=sqlite_meter,
                mode=mode,
                source="sqlite",
                degraded=False,
                degraded_reason=None,
            )
        reason = "sqlite_payload_malformed"
        _append_degraded_record(reason)
        legacy_meter = _to_meter(legacy_get_meter_fn(request_id))
        return MeterReadResolution(
            meter=legacy_meter,
            mode=mode,
            source="legacy_fallback" if legacy_meter else "sqlite",
            degraded=True,
            degraded_reason=reason,
        )

    reason = "sqlite_miss"
    _append_degraded_record(reason)
    legacy_meter = _to_meter(legacy_get_meter_fn(request_id))
    return MeterReadResolution(
        meter=legacy_meter,
        mode=mode,
        source="legacy_fallback" if legacy_meter else "sqlite",
        degraded=True,
        degraded_reason=reason,
    )
