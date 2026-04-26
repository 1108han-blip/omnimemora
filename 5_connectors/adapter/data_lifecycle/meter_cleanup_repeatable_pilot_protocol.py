"""Repeatable cleanup pilot protocol (RES-027, proposal-only)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
_cleanup_txn_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_transaction_preview")
_cleanup_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_quarantine_pilot")
_stability_window = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_stability_window")
_scaleup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_scaleup_readiness")
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")
_restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
_rollback_drill = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")

METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_SCHEMA_VERSION = "res-repeatable-cleanup-pilot-protocol-v1"
METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_REBUILD_SCHEMA_VERSION = "res-repeatable-cleanup-pilot-protocol-rebuild-v1"
METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_MODE = "proposal_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_repeatable_pilot_protocol_file).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _append_unique(output: list[str], reason: str) -> None:
    if reason not in output:
        output.append(reason)


def build_protocol(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)

    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    cleanup_txn_preview = _cleanup_txn_preview.read_preview(policy=current)
    cleanup_pilot = _cleanup_pilot.read_latest_pilot(policy=current)
    stability_window = _stability_window.read_stability_window_report(policy=current)
    scaleup_readiness = _scaleup_readiness.read_readiness_report(policy=current)
    parity = _meter_storage_v2.build_parity_report()
    restore_readback = _restore_readback.read_restore_readback_report(policy=current)
    rollback_drill = _rollback_drill.read_rollback_drill_report(policy=current)

    one_time_mechanism_checks = [
        {
            "check_id": "pilot_record_success",
            "description": "RES-023 pilot record exists and status=success",
            "required": True,
            "passed": bool(isinstance(cleanup_pilot, dict) and str(cleanup_pilot.get("status") or "") == "success"),
        },
        {
            "check_id": "pilot_source_move_observed_once",
            "description": "single-file reversible source move observed",
            "required": True,
            "passed": bool(isinstance(cleanup_pilot, dict) and bool(cleanup_pilot.get("source_move_executed", False))),
        },
        {
            "check_id": "pilot_forbidden_ops_absent",
            "description": "delete/compress/truncate/batch flags remain false",
            "required": True,
            "passed": bool(
                isinstance(cleanup_pilot, dict)
                and not bool(cleanup_pilot.get("delete_executed", False))
                and not bool(cleanup_pilot.get("compress_executed", False))
                and not bool(cleanup_pilot.get("truncate_executed", False))
                and not bool(cleanup_pilot.get("batch_cleanup_executed", False))
            ),
        },
    ]

    required_per_pilot_checks = [
        {
            "check_id": "parity_clean",
            "description": "parity passed with critical_mismatch_count=0",
            "required": True,
            "passed": bool(
                str(parity.get("status") or "").lower() == "passed"
                and int(parity.get("critical_mismatch_count", 0) or 0) == 0
            ),
        },
        {
            "check_id": "stability_passed",
            "description": "stability-window status=passed",
            "required": True,
            "passed": bool(isinstance(stability_window, dict) and str(stability_window.get("status") or "") == "passed"),
        },
        {
            "check_id": "restore_readback_passed",
            "description": "restore/readback status=passed and checksum/source-retained true",
            "required": True,
            "passed": bool(
                isinstance(restore_readback, dict)
                and str(restore_readback.get("status") or "") == "passed"
                and bool(restore_readback.get("checksum_match", False))
                and bool(restore_readback.get("source_retained", False))
            ),
        },
        {
            "check_id": "rollback_drill_passed",
            "description": "rollback drill status=passed and staging readable",
            "required": True,
            "passed": bool(
                isinstance(rollback_drill, dict)
                and str(rollback_drill.get("status") or "") == "passed"
                and bool(rollback_drill.get("staging_restore_readable", False))
                and bool(rollback_drill.get("checksum_match", False))
            ),
        },
        {
            "check_id": "scaleup_blocked_as_expected",
            "description": "scaleup readiness remains blocked with no scope expansion",
            "required": True,
            "passed": bool(
                isinstance(scaleup_readiness, dict)
                and str(scaleup_readiness.get("status") or "") == "blocked"
                and not bool(scaleup_readiness.get("ready_for_scaleup", False))
                and not bool(scaleup_readiness.get("cleanup_scope_expansion_started", False))
            ),
        },
    ]

    preview_candidate_count = 0
    if isinstance(cleanup_preview, dict):
        preview_candidate_count = len([x for x in (cleanup_preview.get("would_cleanup_files") or []) if isinstance(x, dict)])
    txn_candidate_count = 0
    if isinstance(cleanup_txn_preview, dict):
        txn_candidate_count = int(((cleanup_txn_preview.get("summary") or {}).get("candidate_count", 0) or 0))

    batch_summary_checks = [
        {
            "check_id": "cleanup_preview_available",
            "description": "cleanup preview artifact exists",
            "required": True,
            "passed": isinstance(cleanup_preview, dict),
        },
        {
            "check_id": "transaction_preview_available",
            "description": "cleanup transaction preview artifact exists",
            "required": True,
            "passed": isinstance(cleanup_txn_preview, dict),
        },
        {
            "check_id": "candidate_pool_non_empty",
            "description": "preview/transaction candidate pool is non-empty",
            "required": True,
            "passed": bool(preview_candidate_count > 0 and txn_candidate_count > 0),
        },
    ]

    operator_approval_requirements = [
        "second-file pilot requires explicit approval",
        "approval must bind proposal artifact hash and protocol artifact hash",
        "approval must declare source retained and production read-path unchanged",
        "approval must include rollback/readback checkpoint before and after pilot",
    ]

    stop_conditions = [
        "parity_not_passed_or_critical_mismatch_nonzero",
        "stability_window_not_passed",
        "restore_readback_not_passed",
        "rollback_drill_not_passed",
        "scaleup_readiness_not_blocked_as_expected",
        "forbidden_operation_observed(delete|compress|truncate|batch_cleanup|production_read_path_switch)",
    ]

    blocking_reasons: list[str] = []
    for check in one_time_mechanism_checks + required_per_pilot_checks + batch_summary_checks:
        if check.get("required") and not check.get("passed"):
            _append_unique(blocking_reasons, str(check.get("check_id") or "unknown_check_failed"))

    status = "blocked" if blocking_reasons else "proposal_only_ready"

    return {
        "schema_version": METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_MODE,
        "status": status,
        "required_per_pilot_checks": required_per_pilot_checks,
        "one_time_mechanism_checks": one_time_mechanism_checks,
        "batch_summary_checks": batch_summary_checks,
        "operator_approval_requirements": operator_approval_requirements,
        "stop_conditions": stop_conditions,
        "allowed_next_step": "second-file pilot proposal only",
        "second_file_pilot_allowed": False,
        "execution_started": False,
        "cleanup_scope_expansion_started": False,
        "blocking_reasons": blocking_reasons,
        "input_refs": {
            "cleanup_preview_hash": _json_hash(cleanup_preview),
            "cleanup_transaction_preview_hash": _json_hash(cleanup_txn_preview),
            "cleanup_pilot_hash": _json_hash(cleanup_pilot),
            "stability_window_hash": _json_hash(stability_window),
            "scaleup_readiness_hash": _json_hash(scaleup_readiness),
            "parity_hash": _json_hash(parity),
            "restore_readback_hash": _json_hash(restore_readback),
            "rollback_drill_hash": _json_hash(rollback_drill),
        },
        "summary": {
            "status": status,
            "blocking_count": len(blocking_reasons),
            "preview_candidate_count": int(preview_candidate_count),
            "transaction_candidate_count": int(txn_candidate_count),
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        },
    }


def write_protocol_atomic(protocol: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_repeatable_protocol_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(protocol, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_protocol(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _report_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_protocol(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        protocol = build_protocol(policy=current)
        write_protocol_atomic(protocol, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_repeatable_pilot_protocol_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int(((protocol.get("summary") or {}).get("preview_candidate_count", 0) or 0)),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, protocol
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_repeatable_pilot_protocol_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise
