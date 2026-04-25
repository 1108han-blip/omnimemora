"""Metrics residual meter read resolver with sqlite-first + legacy fallback."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

_meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
_meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
TokenSavingsMeter = _meter_store.TokenSavingsMeter

READ_PATH_ENV = "OMNIMEMORA_METRICS_METER_READ_PATH"
MODE_LEGACY_ONLY = "legacy_only"
MODE_SQLITE_FIRST = "sqlite_first_legacy_fallback"
_SUPPORTED_MODES = {MODE_LEGACY_ONLY, MODE_SQLITE_FIRST}


@dataclass
class MetricsMetersResolution:
    meters: list[TokenSavingsMeter]
    mode: str
    source: str
    degraded: bool
    degraded_reason: Optional[str]


@dataclass
class MetricsTenantsResolution:
    tenants: list[str]
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


def resolve_metrics_meters(
    *,
    tenant: str,
    since_utc: Optional[datetime],
    limit: int,
    legacy_collect_fn: Callable[[str], list[Any]],
) -> MetricsMetersResolution:
    mode = current_read_path_mode()
    if mode == MODE_LEGACY_ONLY:
        legacy = [_to_meter(m) for m in legacy_collect_fn(tenant)]
        legacy_meters = [m for m in legacy if m is not None]
        return MetricsMetersResolution(
            meters=legacy_meters,
            mode=mode,
            source="legacy",
            degraded=False,
            degraded_reason=None,
        )

    try:
        since_iso = None
        if since_utc is not None:
            since_iso = since_utc.astimezone(timezone.utc).isoformat()
        sqlite_rows = _meter_store_v2.query_recent(
            tenant=None if tenant == "all" else tenant,
            limit=limit,
            since_iso=since_iso,
        )
    except Exception as exc:
        legacy = [_to_meter(m) for m in legacy_collect_fn(tenant)]
        legacy_meters = [m for m in legacy if m is not None]
        return MetricsMetersResolution(
            meters=legacy_meters,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason=f"sqlite_read_error:{exc}",
        )

    sqlite_meters: list[TokenSavingsMeter] = []
    malformed_count = 0
    for payload in sqlite_rows:
        meter = _to_meter(payload)
        if meter is None:
            malformed_count += 1
            continue
        sqlite_meters.append(meter)

    if malformed_count > 0:
        legacy = [_to_meter(m) for m in legacy_collect_fn(tenant)]
        legacy_meters = [m for m in legacy if m is not None]
        return MetricsMetersResolution(
            meters=legacy_meters,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason="sqlite_payload_malformed",
        )

    if sqlite_meters:
        return MetricsMetersResolution(
            meters=sqlite_meters,
            mode=mode,
            source="sqlite",
            degraded=False,
            degraded_reason=None,
        )

    legacy = [_to_meter(m) for m in legacy_collect_fn(tenant)]
    legacy_meters = [m for m in legacy if m is not None]
    if legacy_meters:
        return MetricsMetersResolution(
            meters=legacy_meters,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason="sqlite_miss",
        )

    return MetricsMetersResolution(
        meters=[],
        mode=mode,
        source="sqlite",
        degraded=False,
        degraded_reason=None,
    )


def resolve_metrics_tenants(
    *,
    legacy_list_tenants_fn: Callable[[], list[str]],
) -> MetricsTenantsResolution:
    mode = current_read_path_mode()
    if mode == MODE_LEGACY_ONLY:
        return MetricsTenantsResolution(
            tenants=sorted(set(legacy_list_tenants_fn())),
            mode=mode,
            source="legacy",
            degraded=False,
            degraded_reason=None,
        )

    try:
        sqlite_tenants = _meter_store_v2.list_tenants()
    except Exception as exc:
        return MetricsTenantsResolution(
            tenants=sorted(set(legacy_list_tenants_fn())),
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason=f"sqlite_read_error:{exc}",
        )

    if sqlite_tenants:
        return MetricsTenantsResolution(
            tenants=sorted(set(sqlite_tenants)),
            mode=mode,
            source="sqlite",
            degraded=False,
            degraded_reason=None,
        )

    legacy_tenants = sorted(set(legacy_list_tenants_fn()))
    if legacy_tenants:
        return MetricsTenantsResolution(
            tenants=legacy_tenants,
            mode=mode,
            source="legacy_fallback",
            degraded=True,
            degraded_reason="sqlite_miss",
        )

    return MetricsTenantsResolution(
        tenants=[],
        mode=mode,
        source="sqlite",
        degraded=False,
        degraded_reason=None,
    )
