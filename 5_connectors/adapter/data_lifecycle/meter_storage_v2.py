"""Meter Storage V2 governance surfaces (observe-only mirror, rebuild, parity)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from . import state_store

_legacy_meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
_meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
_read_resolver = importlib.import_module("5_connectors.adapter.application.request_meter_read_resolver")

METER_STORAGE_STATUS_SCHEMA_VERSION = "dlp-meter-storage-v2-status-v1"
METER_STORAGE_REBUILD_SCHEMA_VERSION = "dlp-meter-storage-v2-rebuild-v1"
METER_STORAGE_PARITY_SCHEMA_VERSION = "dlp-meter-storage-v2-parity-v1"
METER_STORAGE_PARITY_REBUILD_SCHEMA_VERSION = "dlp-meter-storage-v2-parity-rebuild-v1"
METER_STORAGE_MODE = "dual_write_observe_only"
DEFAULT_PARITY_SAMPLE_LIMIT = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _legacy_index() -> dict[str, dict[str, Any]]:
    index, _tenant_aggregates = _legacy_meter_store.load_persisted_state()
    output: dict[str, dict[str, Any]] = {}
    for request_id, payload in (index or {}).items():
        if isinstance(payload, dict):
            output[str(request_id)] = payload
    return output


def _sqlite_all_records() -> dict[str, dict[str, Any]]:
    records = _meter_v2.query_recent(limit=10**9)
    output: dict[str, dict[str, Any]] = {}
    for payload in records:
        request_id = str(payload.get("request_id") or "").strip()
        if request_id:
            output[request_id] = payload
    return output


def _record_degraded(error: str) -> None:
    now = _utc_now()
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_store_v2_dual_write",
        started_at=now,
        completed_at=now,
        status="degraded",
        bytes_scanned=0,
        error=error,
    )
    state_store.append_state_record(record)


def get_status_payload() -> dict[str, Any]:
    _meter_v2.init_schema()
    meta = _meter_v2.get_meta()
    latest_error = _meter_v2.latest_write_error()
    write_error_count = _meter_v2.count_write_errors()
    sqlite_count = _meter_v2.count_records()
    legacy_count = len(_legacy_index())

    status = "healthy"
    if write_error_count > 0:
        status = "degraded"

    read_mode = str(os.getenv(_read_resolver.READ_PATH_ENV, _read_resolver.MODE_SQLITE_FIRST)).strip().lower()
    if read_mode not in {_read_resolver.MODE_SQLITE_FIRST, _read_resolver.MODE_LEGACY_ONLY}:
        read_mode = _read_resolver.MODE_SQLITE_FIRST
    request_meter_switch_enabled = read_mode == _read_resolver.MODE_SQLITE_FIRST

    return {
        "schema_version": METER_STORAGE_STATUS_SCHEMA_VERSION,
        "status": status,
        "mode": str(meta.get("mode") or METER_STORAGE_MODE),
        "read_path": {
            "legacy_authoritative": True,
            "request_meter_switch_enabled": request_meter_switch_enabled,
            "request_evidence_switch_enabled": False,
            "metrics_switch_enabled": False,
            "legacy_fallback_enabled": request_meter_switch_enabled,
            "request_meter_read_mode": read_mode,
        },
        "storage": {
            "sqlite_path": str(_meter_v2.resolve_sqlite_path()),
            "sqlite_count": sqlite_count,
            "legacy_count": legacy_count,
        },
        "write_errors": {
            "count": write_error_count,
            "latest": latest_error,
        },
    }


def rebuild_from_legacy(*, sample_limit: int = DEFAULT_PARITY_SAMPLE_LIMIT) -> tuple[dict[str, Any], dict[str, Any]]:
    started = _utc_now()
    _meter_v2.init_schema()

    scanned = 0
    upserted = 0
    failed = 0
    legacy = _legacy_index()
    for payload in legacy.values():
        scanned += 1
        try:
            _meter_v2.upsert_meter(payload)
            upserted += 1
        except Exception as exc:
            failed += 1
            _meter_v2.record_write_error(
                request_id=str(payload.get("request_id") or ""),
                error_type="rebuild_upsert_failed",
                error_message=str(exc),
                payload=payload,
            )
            _record_degraded(f"meter_store_v2_rebuild_failed:{exc}")

    completed = _utc_now()
    record = {
        "schema_version": METER_STORAGE_REBUILD_SCHEMA_VERSION,
        "cycle_id": state_store.new_cycle_id(),
        "trigger": "meter_storage_v2_rebuild",
        "started_at": _to_iso(started),
        "completed_at": _to_iso(completed),
        "status": "success" if failed == 0 else "degraded",
        "legacy_scanned_count": scanned,
        "sqlite_upserted_count": upserted,
        "failed_count": failed,
        "mode": METER_STORAGE_MODE,
        "non_destructive": True,
    }
    parity = build_parity_report(sample_limit=sample_limit)
    return record, parity


def build_parity_report(*, sample_limit: int = DEFAULT_PARITY_SAMPLE_LIMIT) -> dict[str, Any]:
    _meter_v2.init_schema()
    legacy = _legacy_index()
    sqlite_rows = _sqlite_all_records()

    legacy_ids = set(legacy.keys())
    sqlite_ids = set(sqlite_rows.keys())
    matching_ids = sorted(list(legacy_ids.intersection(sqlite_ids)))
    missing_in_sqlite = sorted(list(legacy_ids - sqlite_ids))
    missing_in_legacy = sorted(list(sqlite_ids - legacy_ids))

    payload_hash_mismatch_count = 0
    mismatch_samples: list[dict[str, Any]] = []
    for request_id in matching_ids:
        legacy_hash = _stable_hash(legacy[request_id])
        sqlite_hash = _stable_hash(sqlite_rows[request_id])
        if legacy_hash != sqlite_hash:
            payload_hash_mismatch_count += 1
            if len(mismatch_samples) < max(1, int(sample_limit)):
                mismatch_samples.append(
                    {
                        "request_id": request_id,
                        "legacy_hash": legacy_hash,
                        "sqlite_hash": sqlite_hash,
                    }
                )

    critical_mismatch_count = (
        len(missing_in_sqlite) + len(missing_in_legacy) + int(payload_hash_mismatch_count)
    )
    status = "passed" if critical_mismatch_count == 0 else "degraded"

    return {
        "schema_version": METER_STORAGE_PARITY_SCHEMA_VERSION,
        "generated_at": _to_iso(_utc_now()),
        "mode": METER_STORAGE_MODE,
        "status": status,
        "legacy_count": len(legacy_ids),
        "sqlite_count": len(sqlite_ids),
        "matching_request_id_count": len(matching_ids),
        "matching_request_id_sample_count": min(len(matching_ids), max(1, int(sample_limit))),
        "payload_hash_mismatch_count": int(payload_hash_mismatch_count),
        "critical_mismatch_count": int(critical_mismatch_count),
        "missing_in_sqlite_count": len(missing_in_sqlite),
        "missing_in_legacy_count": len(missing_in_legacy),
        "missing_in_sqlite": missing_in_sqlite[: max(1, int(sample_limit))],
        "missing_in_legacy": missing_in_legacy[: max(1, int(sample_limit))],
        "hash_mismatch_samples": mismatch_samples,
        "read_path_switch_deferred": True,
        "legacy_authoritative": True,
    }


def parity_with_rebuild(*, sample_limit: int = DEFAULT_PARITY_SAMPLE_LIMIT) -> dict[str, Any]:
    record, parity = rebuild_from_legacy(sample_limit=sample_limit)
    return {
        "schema_version": METER_STORAGE_PARITY_REBUILD_SCHEMA_VERSION,
        "record": record,
        "parity": parity,
    }
