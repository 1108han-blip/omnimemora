"""Meter Storage V2 governance surfaces (observe-only mirror, rebuild, parity)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
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
METER_STORAGE_PARITY_SNAPSHOT_SCHEMA_VERSION = "dlp-meter-storage-v2-parity-snapshot-v1"
METER_STORAGE_MODE = "dual_write_observe_only"
DEFAULT_PARITY_SAMPLE_LIMIT = 200
PARITY_SNAPSHOT_ENV = "OMNIMEMORA_DLP_METER_PARITY_SNAPSHOT_FILE"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


# Provenance-only fields: present in SQLite (new write path) but not in legacy.
# These do NOT represent business data drift; they are metadata about which
# storage path wrote the record. They must not block parity pass.
_PROVENANCE_ONLY_FIELDS = frozenset({
    "sharing_policy_source",
    "timestamp",
})

# Nested provenance-only fields (dot-path style for deep inspection).
_NESTED_PROVENANCE_ONLY_FIELDS = frozenset({
    "access_plan.sharing_policy_source",
})


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _critical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip provenance-only fields so they don't affect critical hash."""
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _PROVENANCE_ONLY_FIELDS:
            continue
        if isinstance(value, dict):
            # Check nested provenance-only fields by constructing the dot-path
            sub = _critical_payload(value)
            # If all nested keys were stripped and the value was a dict with only
            # provenance-only keys, omit the key entirely.
            if sub:
                result[key] = sub
        else:
            result[key] = value
    return result


def _critical_hash(payload: dict[str, Any]) -> str:
    """Hash over business fields only, excluding provenance-only metadata."""
    critical = _critical_payload(payload)
    return _stable_hash(critical)


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


def _default_data_lifecycle_dir() -> Path:
    return Path(os.getenv("OMNIMEMORA_DLP_DIR", str(Path.home() / ".omnimemora" / "adapter" / "data_lifecycle"))).expanduser()


def parity_snapshot_path(path: Optional[str | Path] = None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    return Path(
        os.getenv(
            PARITY_SNAPSHOT_ENV,
            str(_default_data_lifecycle_dir() / "meter_parity_snapshot.json"),
        )
    ).expanduser()


def _parity_hash_summary(parity: dict[str, Any]) -> dict[str, int]:
    return {
        "payload_hash_mismatch_count": int(parity.get("payload_hash_mismatch_count") or 0),
        "semantic_hash_mismatch_count": int(parity.get("semantic_hash_mismatch_count") or 0),
        "critical_payload_hash_mismatch_count": int(parity.get("critical_payload_hash_mismatch_count") or 0),
        "critical_mismatch_count": int(parity.get("critical_mismatch_count") or 0),
        "missing_in_sqlite_count": int(parity.get("missing_in_sqlite_count") or 0),
        "missing_in_legacy_count": int(parity.get("missing_in_legacy_count") or 0),
    }


def _parity_source_counts(parity: dict[str, Any]) -> dict[str, int]:
    return {
        "legacy_count": int(parity.get("legacy_count") or 0),
        "sqlite_count": int(parity.get("sqlite_count") or 0),
        "matching_request_id_count": int(parity.get("matching_request_id_count") or 0),
    }


def _write_json_atomic(path: Path, payload: dict[str, Any], *, tmp_prefix: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=tmp_prefix, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def build_parity_snapshot(parity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": METER_STORAGE_PARITY_SNAPSHOT_SCHEMA_VERSION,
        "generated_at": _to_iso(_utc_now()),
        "mode": METER_STORAGE_MODE,
        "source": "meter_storage_v2_parity_rebuild",
        "source_counts": _parity_source_counts(parity),
        "hash_summary": _parity_hash_summary(parity),
        "parity": parity,
    }


def write_parity_snapshot(parity: dict[str, Any], *, path: Optional[str | Path] = None) -> dict[str, Any]:
    snapshot = build_parity_snapshot(parity)
    snapshot_path = parity_snapshot_path(path)
    _write_json_atomic(snapshot_path, snapshot, tmp_prefix="meter_parity_snapshot_")
    snapshot["snapshot_path"] = str(snapshot_path)
    return snapshot


def read_parity_snapshot(*, path: Optional[str | Path] = None) -> dict[str, Any]:
    snapshot_path = parity_snapshot_path(path)
    base = {
        "schema_version": METER_STORAGE_PARITY_SCHEMA_VERSION,
        "snapshot_schema_version": METER_STORAGE_PARITY_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_path": str(snapshot_path),
        "read_mode": "snapshot_first",
        "mode": METER_STORAGE_MODE,
        "legacy_authoritative": True,
        "read_path_switch_deferred": True,
    }
    if not snapshot_path.exists():
        return {
            **base,
            "generated_at": _to_iso(_utc_now()),
            "status": "missing",
            "missing_reason": "snapshot_missing",
            "snapshot_missing": True,
        }
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            **base,
            "generated_at": _to_iso(_utc_now()),
            "status": "missing",
            "missing_reason": "snapshot_read_error",
            "snapshot_missing": True,
            "error": str(exc),
        }
    if not isinstance(payload, dict) or payload.get("schema_version") != METER_STORAGE_PARITY_SNAPSHOT_SCHEMA_VERSION:
        return {
            **base,
            "generated_at": _to_iso(_utc_now()),
            "status": "missing",
            "missing_reason": "snapshot_schema_mismatch",
            "snapshot_missing": True,
        }
    parity = payload.get("parity")
    if not isinstance(parity, dict):
        return {
            **base,
            "generated_at": _to_iso(_utc_now()),
            "status": "missing",
            "missing_reason": "snapshot_payload_missing",
            "snapshot_missing": True,
        }
    return {
        **parity,
        "snapshot_schema_version": METER_STORAGE_PARITY_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_generated_at": payload.get("generated_at"),
        "snapshot_path": str(snapshot_path),
        "snapshot_missing": False,
        "read_mode": "snapshot_first",
    }


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
        cleanup_gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_execution_gate")
        cleanup_txn_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_transaction_preview")
        cleanup_rollback_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")
        cleanup_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_quarantine_pilot")
        cleanup_stability_mod = importlib.import_module(
            "5_connectors.adapter.data_lifecycle.meter_cleanup_stability_window"
        )
        try:
            cleanup_scaleup_readiness_mod = importlib.import_module(
                "5_connectors.adapter.data_lifecycle.meter_cleanup_scaleup_readiness"
            )
        except Exception:
            cleanup_scaleup_readiness_mod = None
        try:
            cleanup_repeatable_protocol_mod = importlib.import_module(
                "5_connectors.adapter.data_lifecycle.meter_cleanup_repeatable_pilot_protocol"
            )
        except Exception:
            cleanup_repeatable_protocol_mod = None
        try:
            cleanup_second_file_proposal_mod = importlib.import_module(
                "5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_proposal"
            )
        except Exception:
            cleanup_second_file_proposal_mod = None
        try:
            cleanup_second_file_approval_readiness_mod = importlib.import_module(
                "5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_approval_readiness"
            )
        except Exception:
            cleanup_second_file_approval_readiness_mod = None
        preview = cleanup_mod.read_preview()
        cleanup_gate = cleanup_gate_mod.read_gate()
        cleanup_txn_preview = cleanup_txn_mod.read_preview()
        cleanup_rollback = cleanup_rollback_mod.read_rollback_drill_report()
        cleanup_pilot = cleanup_pilot_mod.read_latest_pilot()
        cleanup_stability = cleanup_stability_mod.read_stability_window_report()
        cleanup_scaleup_readiness = (
            cleanup_scaleup_readiness_mod.read_readiness_report() if cleanup_scaleup_readiness_mod is not None else None
        )
        cleanup_repeatable_protocol = (
            cleanup_repeatable_protocol_mod.read_protocol() if cleanup_repeatable_protocol_mod is not None else None
        )
        cleanup_second_file_proposal = (
            cleanup_second_file_proposal_mod.read_proposal() if cleanup_second_file_proposal_mod is not None else None
        )
        cleanup_second_file_approval_readiness = (
            cleanup_second_file_approval_readiness_mod.read_approval_readiness()
            if cleanup_second_file_approval_readiness_mod is not None
            else None
        )
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
                "execution_gate_status": str((cleanup_gate or {}).get("cleanup_gate_status") or "missing"),
                "execution_gate_allowed": bool((cleanup_gate or {}).get("cleanup_allowed") is True),
                "transaction_preview_status": str((cleanup_txn_preview or {}).get("status") or "missing"),
                "transaction_execution_allowed": bool((cleanup_txn_preview or {}).get("execution_allowed") is True),
                "rollback_drill_status": str((cleanup_rollback or {}).get("status") or "missing"),
                "rollback_drill_checksum_match": bool((cleanup_rollback or {}).get("checksum_match", False)),
                "rollback_required": bool((cleanup_gate or {}).get("rollback_required", True)),
                "pilot_status": str((cleanup_pilot or {}).get("status") or "missing"),
                "pilot_mode": str((cleanup_pilot or {}).get("mode") or "single_reversible_quarantine_only"),
                "source_move_executed": bool((cleanup_pilot or {}).get("source_move_executed", False)),
                "delete_executed": bool((cleanup_pilot or {}).get("delete_executed", False)),
                "compress_executed": bool((cleanup_pilot or {}).get("compress_executed", False)),
                "truncate_executed": bool((cleanup_pilot or {}).get("truncate_executed", False)),
                "batch_cleanup_executed": bool((cleanup_pilot or {}).get("batch_cleanup_executed", False)),
                "stability_window_status": str((cleanup_stability or {}).get("status") or "missing"),
                "stability_window_observed_pilot_status": str(
                    (cleanup_stability or {}).get("observed_pilot_status") or "missing"
                ),
                "stability_window_cleanup_scope_expansion_started": bool(
                    (cleanup_stability or {}).get("cleanup_scope_expansion_started", False)
                ),
                "scaleup_readiness_status": str((cleanup_scaleup_readiness or {}).get("status") or "missing"),
                "scaleup_ready": bool((cleanup_scaleup_readiness or {}).get("ready_for_scaleup") is True),
                "repeatable_pilot_protocol_status": str((cleanup_repeatable_protocol or {}).get("status") or "missing"),
                "second_file_pilot_proposal_status": str((cleanup_second_file_proposal or {}).get("status") or "missing"),
                "second_file_pilot_approval_readiness_status": str(
                    (cleanup_second_file_approval_readiness or {}).get("status") or "missing"
                ),
                "second_file_pilot_allowed": bool((cleanup_second_file_proposal or {}).get("second_file_pilot_allowed") is True),
                "cleanup_scope_expansion_started": False,
            }
        else:
            cleanup_view = {
                "status": "missing",
                "mode": "preview_only",
                "cleanup_allowed": False,
                "candidate_file_count": 0,
                "estimated_reclaim_bytes": 0,
                "blocking_reasons_count": 0,
                "execution_gate_status": "missing",
                "execution_gate_allowed": False,
                "transaction_preview_status": "missing",
                "transaction_execution_allowed": False,
                "rollback_drill_status": "missing",
                "rollback_drill_checksum_match": False,
                "rollback_required": True,
                "pilot_status": "missing",
                "pilot_mode": "single_reversible_quarantine_only",
                "source_move_executed": False,
                "delete_executed": False,
                "compress_executed": False,
                "truncate_executed": False,
                "batch_cleanup_executed": False,
                "stability_window_status": "missing",
                "stability_window_observed_pilot_status": "missing",
                "stability_window_cleanup_scope_expansion_started": False,
                "scaleup_readiness_status": "missing",
                "scaleup_ready": False,
                "repeatable_pilot_protocol_status": "missing",
                "second_file_pilot_proposal_status": "missing",
                "second_file_pilot_approval_readiness_status": "missing",
                "second_file_pilot_allowed": False,
                "cleanup_scope_expansion_started": False,
            }
    except Exception:
        cleanup_view = {
            "status": "missing",
            "mode": "preview_only",
            "cleanup_allowed": False,
            "candidate_file_count": 0,
            "estimated_reclaim_bytes": 0,
            "blocking_reasons_count": 0,
            "execution_gate_status": "missing",
            "execution_gate_allowed": False,
            "transaction_preview_status": "missing",
            "transaction_execution_allowed": False,
            "rollback_drill_status": "missing",
            "rollback_drill_checksum_match": False,
            "rollback_required": True,
            "pilot_status": "missing",
            "pilot_mode": "single_reversible_quarantine_only",
            "source_move_executed": False,
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
            "stability_window_status": "missing",
            "stability_window_observed_pilot_status": "missing",
            "stability_window_cleanup_scope_expansion_started": False,
            "scaleup_readiness_status": "missing",
            "scaleup_ready": False,
            "repeatable_pilot_protocol_status": "missing",
            "second_file_pilot_proposal_status": "missing",
            "second_file_pilot_approval_readiness_status": "missing",
            "second_file_pilot_allowed": False,
            "cleanup_scope_expansion_started": False,
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
    critical_payload_hash_mismatch_count = 0
    semantic_hash_mismatch_count = 0
    mismatch_samples: list[dict[str, Any]] = []
    for request_id in matching_ids:
        legacy_raw_hash = _stable_hash(legacy[request_id])
        sqlite_raw_hash = _stable_hash(sqlite_rows[request_id])
        legacy_critical_hash = _critical_hash(legacy[request_id])
        sqlite_critical_hash = _critical_hash(sqlite_rows[request_id])

        raw_mismatch = legacy_raw_hash != sqlite_raw_hash
        critical_mismatch = legacy_critical_hash != sqlite_critical_hash

        if raw_mismatch:
            payload_hash_mismatch_count += 1
        if critical_mismatch:
            critical_payload_hash_mismatch_count += 1
        elif raw_mismatch:
            # Raw mismatch but critical hash agrees: provenance drift only.
            semantic_hash_mismatch_count += 1

        if (raw_mismatch or critical_mismatch) and len(mismatch_samples) < max(1, int(sample_limit)):
            # Build noncritical_field_paths for provenance-only mismatches.
            noncritical_field_paths: list[str] = []
            if raw_mismatch and not critical_mismatch:
                # Check top-level provenance-only fields.
                for key in _PROVENANCE_ONLY_FIELDS:
                    if key not in legacy[request_id] and key not in sqlite_rows[request_id]:
                        continue
                    lv = legacy[request_id].get(key)
                    sv = sqlite_rows[request_id].get(key)
                    if lv != sv:
                        noncritical_field_paths.append(key)
                # Check nested provenance-only: access_plan.sharing_policy_source
                for key in {"access_plan"}:
                    if key not in legacy[request_id] or key not in sqlite_rows[request_id]:
                        continue
                    lsp = legacy[request_id][key].get("sharing_policy_source") if isinstance(legacy[request_id][key], dict) else None
                    ssp = sqlite_rows[request_id][key].get("sharing_policy_source") if isinstance(sqlite_rows[request_id][key], dict) else None
                    if lsp != ssp:
                        noncritical_field_paths.append(f"{key}.sharing_policy_source")

            classification = "critical" if critical_mismatch else "provenance_only"
            mismatch_samples.append(
                {
                    "request_id": request_id,
                    "legacy_hash": legacy_raw_hash,
                    "sqlite_hash": sqlite_raw_hash,
                    "classification": classification,
                    "noncritical_field_paths": noncritical_field_paths if noncritical_field_paths else [],
                }
            )

    critical_mismatch_count = (
        len(missing_in_sqlite) + len(missing_in_legacy) + int(critical_payload_hash_mismatch_count)
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
        "semantic_hash_mismatch_count": int(semantic_hash_mismatch_count),
        "critical_payload_hash_mismatch_count": int(critical_payload_hash_mismatch_count),
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
    snapshot = write_parity_snapshot(parity)
    return {
        "schema_version": METER_STORAGE_PARITY_REBUILD_SCHEMA_VERSION,
        "record": record,
        "parity": parity,
        "snapshot": {
            "schema_version": snapshot["schema_version"],
            "generated_at": snapshot["generated_at"],
            "snapshot_path": snapshot["snapshot_path"],
            "source_counts": snapshot["source_counts"],
            "hash_summary": snapshot["hash_summary"],
        },
    }
