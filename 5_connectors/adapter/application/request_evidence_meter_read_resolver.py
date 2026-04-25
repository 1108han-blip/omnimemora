"""Request-evidence meter resolver with shadow parity support."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

_4_core = importlib.import_module("4_core.logic.v2_compute")
TokenSavingsMeter = _4_core.TokenSavingsMeter

_meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")

READ_PATH_ENV = "OMNIMEMORA_REQUEST_EVIDENCE_METER_READ_PATH"
MODE_LEGACY_ONLY = "legacy_only"
MODE_SQLITE_FIRST = "sqlite_first_legacy_fallback"
_SUPPORTED_MODES = {MODE_LEGACY_ONLY, MODE_SQLITE_FIRST}


@dataclass
class RequestEvidenceMeterResolution:
    mode: str
    selected_source: str
    selected_meter: Optional[TokenSavingsMeter]
    legacy_meter: Optional[TokenSavingsMeter]
    sqlite_meter: Optional[TokenSavingsMeter]
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


def resolve_request_evidence_meter(
    request_id: str,
    *,
    legacy_get_meter_fn: Callable[[str], Any],
) -> RequestEvidenceMeterResolution:
    mode = current_read_path_mode()
    legacy_meter = _to_meter(legacy_get_meter_fn(request_id))

    sqlite_meter: Optional[TokenSavingsMeter] = None
    sqlite_error_reason: Optional[str] = None
    try:
        sqlite_payload = _meter_store_v2.get_meter(request_id)
        sqlite_meter = _to_meter(sqlite_payload)
        if sqlite_payload is not None and sqlite_meter is None:
            sqlite_error_reason = "sqlite_payload_malformed"
    except Exception as exc:
        sqlite_error_reason = f"sqlite_read_error:{exc}"

    if mode == MODE_LEGACY_ONLY:
        return RequestEvidenceMeterResolution(
            mode=mode,
            selected_source="legacy",
            selected_meter=legacy_meter,
            legacy_meter=legacy_meter,
            sqlite_meter=sqlite_meter,
            degraded=False,
            degraded_reason=None,
        )

    if sqlite_meter is not None:
        return RequestEvidenceMeterResolution(
            mode=mode,
            selected_source="sqlite",
            selected_meter=sqlite_meter,
            legacy_meter=legacy_meter,
            sqlite_meter=sqlite_meter,
            degraded=False,
            degraded_reason=None,
        )

    if legacy_meter is not None:
        return RequestEvidenceMeterResolution(
            mode=mode,
            selected_source="legacy_fallback",
            selected_meter=legacy_meter,
            legacy_meter=legacy_meter,
            sqlite_meter=sqlite_meter,
            degraded=True,
            degraded_reason=sqlite_error_reason or "sqlite_miss",
        )

    return RequestEvidenceMeterResolution(
        mode=mode,
        selected_source="sqlite",
        selected_meter=None,
        legacy_meter=legacy_meter,
        sqlite_meter=sqlite_meter,
        degraded=True,
        degraded_reason=sqlite_error_reason or "sqlite_miss_and_legacy_miss",
    )
