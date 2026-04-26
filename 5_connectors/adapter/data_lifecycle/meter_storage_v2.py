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
_request_evidence_read_resolver = importlib.import_module(
    "5_connectors.adapter.application.request_evidence_meter_read_resolver"
)
_metrics_read_resolver = importlib.import_module("5_connectors.adapter.application.metrics_meter_read_resolver")
_status_read_resolver = importlib.import_module("5_connectors.adapter.application.status_read_model_meter_read_resolver")

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
    request_evidence_mode = str(
        os.getenv(
            _request_evidence_read_resolver.READ_PATH_ENV,
            _request_evidence_read_resolver.MODE_SQLITE_FIRST,
        )
    ).strip().lower()
    if request_evidence_mode not in {
        _request_evidence_read_resolver.MODE_SQLITE_FIRST,
        _request_evidence_read_resolver.MODE_LEGACY_ONLY,
    }:
        request_evidence_mode = _request_evidence_read_resolver.MODE_SQLITE_FIRST
    request_evidence_switch_enabled = (
        request_evidence_mode == _request_evidence_read_resolver.MODE_SQLITE_FIRST
    )
    metrics_mode = str(
        os.getenv(_metrics_read_resolver.READ_PATH_ENV, _metrics_read_resolver.MODE_SQLITE_FIRST)
    ).strip().lower()
    if metrics_mode not in {_metrics_read_resolver.MODE_SQLITE_FIRST, _metrics_read_resolver.MODE_LEGACY_ONLY}:
        metrics_mode = _metrics_read_resolver.MODE_SQLITE_FIRST
    metrics_switch_enabled = metrics_mode == _metrics_read_resolver.MODE_SQLITE_FIRST
    status_mode = str(
        os.getenv(_status_read_resolver.READ_PATH_ENV, _status_read_resolver.MODE_SQLITE_FIRST)
    ).strip().lower()
    if status_mode not in {_status_read_resolver.MODE_SQLITE_FIRST, _status_read_resolver.MODE_LEGACY_ONLY}:
        status_mode = _status_read_resolver.MODE_SQLITE_FIRST
    status_switch_enabled = status_mode == _status_read_resolver.MODE_SQLITE_FIRST
    cleanup_view: dict[str, Any]
    try:
        cleanup_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
        preview = cleanup_mod.read_preview()
        if isinstance(preview, dict):
            blocking_reasons = preview.get("blocking_reasons") or []
            summary = preview.get("summary") or {}
            cleanup_view = {
                "status": str(preview.get("status") or "blocked"),
                "mode": str(preview.get("mode") or cleanup_mod.METER_CLEANUP_PREVIEW_MODE),
                "cleanup_allowed": bool(preview.get("cleanup_allowed")),
                "candidate_file_count": int(summary.get("candidate_file_count", 0) or 0),
                "estimated_reclaim_bytes": int(preview.get("estimated_reclaim_bytes", 0) or 0),
                "blocking_reasons_count": int(len(blocking_reasons)),
            }
        else:
            cleanup_view = {
                "status": "missing",
                "mode": "preview_only",
                "cleanup_allowed": False,
                "candidate_file_count": 0,
                "estimated_reclaim_bytes": 0,
                "blocking_reasons_count": 0,
            }
    except Exception:
        cleanup_view = {
            "status": "missing",
            "mode": "preview_only",
            "cleanup_allowed": False,
            "candidate_file_count": 0,
            "estimated_reclaim_bytes": 0,
            "blocking_reasons_count": 0,
        }
    backup_export_view: dict[str, Any]
    try:
        backup_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
        readiness = backup_mod.read_readiness()
        plan_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
        plan = plan_mod.read_plan()
        package_manifest_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest"
        )
        package_manifest = package_manifest_mod.read_package_manifest()
        approval_template_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template"
        )
        approval_template = approval_template_mod.read_approval_template()
        execution_gate_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate"
        )
        execution_gate = execution_gate_mod.read_gate()
        operator_approval_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval"
        )
        operator_approval = operator_approval_mod.read_operator_approval()
        execution_proposal_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_execution_proposal"
        )
        execution_proposal = execution_proposal_mod.read_execution_proposal()
        copy_pilot_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot"
        )
        copy_pilot = copy_pilot_mod.read_latest_copy_pilot()
        restore_readback_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback"
        )
        restore_readback = restore_readback_mod.read_restore_readback_report()
        if isinstance(readiness, dict):
            summary = readiness.get("summary") or {}
            blocking_reasons = readiness.get("blocking_reasons") or []
            plan_summary = (plan or {}).get("summary") or {}
            plan_blocking = (plan or {}).get("blocking_reasons") or []
            plan_dest = (plan or {}).get("destination_status")
            if not isinstance(plan_dest, dict):
                plan_dest = {
                    "status": "unknown",
                    "path": None,
                    "exists": False,
                    "is_directory": False,
                    "free_bytes": None,
                    "required_free_bytes": None,
                    "policy_ok": False,
                }
            candidate_count = int(
                plan_summary.get("candidate_file_count", summary.get("candidate_file_count", 0)) or 0
            )
            estimated_export_bytes = int(
                plan_summary.get("estimated_export_bytes", readiness.get("estimated_export_bytes", 0)) or 0
            )
            blocking_count = int(
                plan_summary.get("blocking_reasons_count", len(plan_blocking) if isinstance(plan_blocking, list) else 0)
                or len(blocking_reasons)
            )
            manifest_summary = (package_manifest or {}).get("summary") or {}
            manifest_file_count = int(
                manifest_summary.get(
                    "file_count",
                    len((package_manifest or {}).get("would_export_files") or [])
                    if isinstance((package_manifest or {}).get("would_export_files"), list)
                    else 0,
                )
                or 0
            )
            manifest_total_bytes = int(
                manifest_summary.get("total_bytes", (package_manifest or {}).get("total_bytes", 0))
                or 0
            )
            gate_summary = (execution_gate or {}).get("summary") or {}
            gate_blocking_count = int(gate_summary.get("blocking_count", 0) or 0)
            approval_status = str(
                ((execution_gate or {}).get("approval") or {}).get("status")
                or ("present" if isinstance(operator_approval, dict) else "missing")
            )
            backup_export_view = {
                "status": str(readiness.get("status") or "blocked"),
                "mode": str(readiness.get("mode") or backup_mod.METER_BACKUP_EXPORT_READINESS_MODE),
                "backup_export_allowed": bool(readiness.get("backup_export_allowed")),
                "cleanup_allowed": False,
                "execution_allowed": False,
                "candidate_file_count": candidate_count,
                "estimated_export_bytes": estimated_export_bytes,
                "blocking_reasons_count": gate_blocking_count if isinstance(execution_gate, dict) else blocking_count,
                "plan_status": str((plan or {}).get("status") or "missing"),
                "dry_run_mode": str((plan or {}).get("mode") or "dry_run_preview_only"),
                "destination_status": plan_dest,
                "package_manifest_status": str((package_manifest or {}).get("status") or "missing"),
                "package_manifest_file_count": manifest_file_count,
                "package_manifest_total_bytes": manifest_total_bytes,
                "approval_template_status": str((approval_template or {}).get("status") or "missing"),
                "execution_gate_status": str((execution_gate or {}).get("status") or "missing"),
                "execution_gate_allowed": bool((execution_gate or {}).get("allowed") is True),
                "approval_status": approval_status,
                "execution_proposal_status": str((execution_proposal or {}).get("proposal_status") or "missing"),
                "operator_decision_required": bool(
                    (execution_proposal or {}).get("operator_decision_required")
                    if isinstance(execution_proposal, dict)
                    else True
                ),
                "copy_pilot_status": str((copy_pilot or {}).get("status") or "missing"),
                "copy_pilot_source_retained": bool(
                    (copy_pilot or {}).get("source_retained")
                    if isinstance(copy_pilot, dict)
                    else True
                ),
                "copy_pilot_checksum_match": bool(
                    (copy_pilot or {}).get("checksum_match")
                    if isinstance(copy_pilot, dict)
                    else False
                ),
                "copy_pilot_cleanup_started": False,
                "copy_pilot_read_path_unchanged": True,
                "restore_readback_status": str((restore_readback or {}).get("status") or "missing"),
                "restore_readback_source_retained": bool(
                    (restore_readback or {}).get("source_retained")
                    if isinstance(restore_readback, dict)
                    else True
                ),
                "restore_readback_backup_copy_readable": bool(
                    (restore_readback or {}).get("backup_copy_readable")
                    if isinstance(restore_readback, dict)
                    else False
                ),
                "restore_readback_checksum_match": bool(
                    (restore_readback or {}).get("checksum_match")
                    if isinstance(restore_readback, dict)
                    else False
                ),
                "restore_readback_production_restore_started": False,
                "restore_readback_cleanup_started": False,
                "backup_export_execution_started": False,
                "cleanup_execution_started": False,
            }
        else:
            backup_export_view = {
                "status": "missing",
                "mode": "backup_export_readiness_only",
                "backup_export_allowed": False,
                "cleanup_allowed": False,
                "execution_allowed": False,
                "candidate_file_count": 0,
                "estimated_export_bytes": 0,
                "blocking_reasons_count": 0,
                "plan_status": "missing",
                "dry_run_mode": "dry_run_preview_only",
                "destination_status": {
                    "status": "unknown",
                    "path": None,
                    "exists": False,
                    "is_directory": False,
                    "free_bytes": None,
                    "required_free_bytes": None,
                    "policy_ok": False,
                },
                "package_manifest_status": "missing",
                "package_manifest_file_count": 0,
                "package_manifest_total_bytes": 0,
                "approval_template_status": "missing",
                "execution_gate_status": "missing",
                "execution_gate_allowed": False,
                "approval_status": "missing",
                "execution_proposal_status": "missing",
                "operator_decision_required": True,
                "copy_pilot_status": "missing",
                "copy_pilot_source_retained": True,
                "copy_pilot_checksum_match": False,
                "copy_pilot_cleanup_started": False,
                "copy_pilot_read_path_unchanged": True,
                "restore_readback_status": "missing",
                "restore_readback_source_retained": True,
                "restore_readback_backup_copy_readable": False,
                "restore_readback_checksum_match": False,
                "restore_readback_production_restore_started": False,
                "restore_readback_cleanup_started": False,
                "backup_export_execution_started": False,
                "cleanup_execution_started": False,
            }
    except Exception:
        backup_export_view = {
            "status": "missing",
            "mode": "backup_export_readiness_only",
            "backup_export_allowed": False,
            "cleanup_allowed": False,
            "execution_allowed": False,
            "candidate_file_count": 0,
            "estimated_export_bytes": 0,
            "blocking_reasons_count": 0,
            "plan_status": "missing",
            "dry_run_mode": "dry_run_preview_only",
            "destination_status": {
                "status": "unknown",
                "path": None,
                "exists": False,
                "is_directory": False,
                "free_bytes": None,
                "required_free_bytes": None,
                "policy_ok": False,
            },
            "package_manifest_status": "missing",
            "package_manifest_file_count": 0,
            "package_manifest_total_bytes": 0,
            "approval_template_status": "missing",
            "execution_gate_status": "missing",
            "execution_gate_allowed": False,
            "approval_status": "missing",
            "execution_proposal_status": "missing",
            "operator_decision_required": True,
            "copy_pilot_status": "missing",
            "copy_pilot_source_retained": True,
            "copy_pilot_checksum_match": False,
            "copy_pilot_cleanup_started": False,
            "copy_pilot_read_path_unchanged": True,
            "restore_readback_status": "missing",
            "restore_readback_source_retained": True,
            "restore_readback_backup_copy_readable": False,
            "restore_readback_checksum_match": False,
            "restore_readback_production_restore_started": False,
            "restore_readback_cleanup_started": False,
            "backup_export_execution_started": False,
            "cleanup_execution_started": False,
        }

    return {
        "schema_version": METER_STORAGE_STATUS_SCHEMA_VERSION,
        "status": status,
        "mode": str(meta.get("mode") or METER_STORAGE_MODE),
        "read_path": {
            "legacy_authoritative": True,
            "request_meter_switch_enabled": request_meter_switch_enabled,
            "request_evidence_switch_enabled": request_evidence_switch_enabled,
            "metrics_switch_enabled": metrics_switch_enabled,
            "status_read_model_switch_enabled": status_switch_enabled,
            "legacy_fallback_enabled": (
                request_meter_switch_enabled
                or request_evidence_switch_enabled
                or metrics_switch_enabled
                or status_switch_enabled
            ),
            "request_meter_read_mode": read_mode,
            "request_evidence_read_mode": request_evidence_mode,
            "metrics_read_mode": metrics_mode,
            "status_read_model_read_mode": status_mode,
            "cleanup_eligibility": "readiness_only",
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
        "cleanup": cleanup_view,
        "backup_export": backup_export_view,
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
