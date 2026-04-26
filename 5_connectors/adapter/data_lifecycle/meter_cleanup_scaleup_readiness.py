"""Cleanup scale-up readiness report (read-only, design/readiness only)."""

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
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")
_restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
_rollback_drill = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")
_backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
_backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
_backup_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
_backup_execution_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate")
_backup_execution_proposal = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_execution_proposal"
)

METER_CLEANUP_SCALEUP_READINESS_SCHEMA_VERSION = "res-legacy-meter-cleanup-scaleup-readiness-v1"
METER_CLEANUP_SCALEUP_READINESS_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-scaleup-readiness-rebuild-v1"
METER_CLEANUP_SCALEUP_READINESS_MODE = "scaleup_readiness_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_scaleup_readiness_file).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_count(cleanup_preview: Optional[dict[str, Any]], cleanup_txn_preview: Optional[dict[str, Any]]) -> int:
    if isinstance(cleanup_txn_preview, dict):
        summary = cleanup_txn_preview.get("summary")
        if isinstance(summary, dict):
            value = int(summary.get("candidate_count", 0) or 0)
            if value >= 0:
                return value
    if isinstance(cleanup_preview, dict):
        items = [item for item in (cleanup_preview.get("would_cleanup_files") or []) if isinstance(item, dict)]
        return int(len(items))
    return 0


def _append_if_missing(blocking_reasons: list[str], reason: str) -> None:
    if reason not in blocking_reasons:
        blocking_reasons.append(reason)


def _validate_backup_artifacts(
    *,
    backup_readiness: Optional[dict[str, Any]],
    backup_plan: Optional[dict[str, Any]],
    backup_manifest: Optional[dict[str, Any]],
    backup_execution_gate: Optional[dict[str, Any]],
    backup_execution_proposal: Optional[dict[str, Any]],
    blocking_reasons: list[str],
) -> None:
    if not isinstance(backup_readiness, dict):
        _append_if_missing(blocking_reasons, "backup_export_readiness_missing")
    else:
        if bool(backup_readiness.get("backup_export_allowed", False)):
            _append_if_missing(blocking_reasons, "backup_export_readiness_invalid")

    if not isinstance(backup_plan, dict):
        _append_if_missing(blocking_reasons, "backup_export_plan_missing")
    else:
        plan_status = str(backup_plan.get("status") or "").lower()
        if plan_status and plan_status != "blocked":
            _append_if_missing(blocking_reasons, "backup_export_plan_invalid")
        if bool(backup_plan.get("execution_allowed", False)):
            _append_if_missing(blocking_reasons, "backup_export_plan_invalid")

    if not isinstance(backup_manifest, dict):
        _append_if_missing(blocking_reasons, "backup_export_package_manifest_missing")
    else:
        manifest_status = str(backup_manifest.get("status") or "").lower()
        if manifest_status and manifest_status != "blocked":
            _append_if_missing(blocking_reasons, "backup_export_package_manifest_invalid")

    if not isinstance(backup_execution_gate, dict):
        _append_if_missing(blocking_reasons, "backup_export_execution_gate_missing")
    else:
        if bool(backup_execution_gate.get("backup_export_execution_started", False)):
            _append_if_missing(blocking_reasons, "backup_export_execution_started")
        if bool(backup_execution_gate.get("cleanup_execution_started", False)):
            _append_if_missing(blocking_reasons, "cleanup_execution_started")

    if not isinstance(backup_execution_proposal, dict):
        _append_if_missing(blocking_reasons, "backup_export_execution_proposal_missing")
    else:
        proposal_status = str(backup_execution_proposal.get("proposal_status") or "").strip().lower()
        if proposal_status not in {"blocked", "ready_for_operator_decision"}:
            _append_if_missing(blocking_reasons, "backup_export_execution_proposal_invalid")
        if bool(backup_execution_proposal.get("execution_started", False)):
            _append_if_missing(blocking_reasons, "backup_export_execution_started")
        if bool(backup_execution_proposal.get("cleanup_started", False)):
            _append_if_missing(blocking_reasons, "cleanup_execution_started")


def build_scaleup_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    blocking_reasons: list[str] = []

    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    cleanup_txn_preview = _cleanup_txn_preview.read_preview(policy=current)
    cleanup_pilot = _cleanup_pilot.read_latest_pilot(policy=current)
    stability_window = _stability_window.read_stability_window_report(policy=current)
    parity = _meter_storage_v2.build_parity_report()
    restore_readback = _restore_readback.read_restore_readback_report(policy=current)
    rollback_drill = _rollback_drill.read_rollback_drill_report(policy=current)
    backup_readiness = _backup_readiness.read_readiness(policy=current)
    backup_plan = _backup_plan.read_plan(policy=current)
    backup_manifest = _backup_manifest.read_package_manifest(policy=current)
    backup_execution_gate = _backup_execution_gate.read_gate(policy=current)
    backup_execution_proposal = _backup_execution_proposal.read_execution_proposal(policy=current)

    if not isinstance(cleanup_preview, dict):
        _append_if_missing(blocking_reasons, "cleanup_preview_missing")
    if not isinstance(cleanup_txn_preview, dict):
        _append_if_missing(blocking_reasons, "cleanup_transaction_preview_missing")
    if not isinstance(cleanup_pilot, dict):
        _append_if_missing(blocking_reasons, "cleanup_pilot_missing")
    else:
        if str(cleanup_pilot.get("status") or "") != "success":
            _append_if_missing(blocking_reasons, "cleanup_pilot_not_success")
        if not bool(cleanup_pilot.get("source_move_executed", False)):
            _append_if_missing(blocking_reasons, "cleanup_pilot_source_move_not_observed")
        for key in ("delete_executed", "compress_executed", "truncate_executed", "batch_cleanup_executed"):
            if bool(cleanup_pilot.get(key, False)):
                _append_if_missing(blocking_reasons, "cleanup_pilot_forbidden_operation_observed")

    if not isinstance(stability_window, dict):
        _append_if_missing(blocking_reasons, "stability_window_missing")
    else:
        if str(stability_window.get("status") or "") != "passed":
            _append_if_missing(blocking_reasons, "stability_window_not_passed")
        if bool(stability_window.get("cleanup_scope_expansion_started", False)):
            _append_if_missing(blocking_reasons, "cleanup_scope_expansion_already_started")

    if str(parity.get("status") or "").lower() != "passed":
        _append_if_missing(blocking_reasons, "parity_not_passed")
    if int(parity.get("critical_mismatch_count", 0) or 0) != 0:
        _append_if_missing(blocking_reasons, "critical_mismatch_nonzero")

    if not isinstance(restore_readback, dict):
        _append_if_missing(blocking_reasons, "restore_readback_missing")
    else:
        if str(restore_readback.get("status") or "") != "passed":
            _append_if_missing(blocking_reasons, "restore_readback_not_passed")
        if not bool(restore_readback.get("source_retained", False)):
            _append_if_missing(blocking_reasons, "restore_readback_source_not_retained")
        if not bool(restore_readback.get("checksum_match", False)):
            _append_if_missing(blocking_reasons, "restore_readback_checksum_mismatch")
        if bool(restore_readback.get("production_restore_started", False)):
            _append_if_missing(blocking_reasons, "restore_readback_production_restore_started")
        if bool(restore_readback.get("cleanup_started", False)):
            _append_if_missing(blocking_reasons, "cleanup_execution_started")

    if not isinstance(rollback_drill, dict):
        _append_if_missing(blocking_reasons, "rollback_drill_missing")
    else:
        if str(rollback_drill.get("status") or "") != "passed":
            _append_if_missing(blocking_reasons, "rollback_drill_not_passed")
        if not bool(rollback_drill.get("staging_restore_readable", False)):
            _append_if_missing(blocking_reasons, "rollback_drill_staging_restore_not_readable")
        if not bool(rollback_drill.get("checksum_match", False)):
            _append_if_missing(blocking_reasons, "rollback_drill_checksum_mismatch")
        if bool(rollback_drill.get("production_restore_started", False)):
            _append_if_missing(blocking_reasons, "rollback_drill_production_restore_started")
        if bool(rollback_drill.get("cleanup_started", False)):
            _append_if_missing(blocking_reasons, "cleanup_execution_started")

    _validate_backup_artifacts(
        backup_readiness=backup_readiness if isinstance(backup_readiness, dict) else None,
        backup_plan=backup_plan if isinstance(backup_plan, dict) else None,
        backup_manifest=backup_manifest if isinstance(backup_manifest, dict) else None,
        backup_execution_gate=backup_execution_gate if isinstance(backup_execution_gate, dict) else None,
        backup_execution_proposal=backup_execution_proposal if isinstance(backup_execution_proposal, dict) else None,
        blocking_reasons=blocking_reasons,
    )

    candidate_count = _candidate_count(
        cleanup_preview if isinstance(cleanup_preview, dict) else None,
        cleanup_txn_preview if isinstance(cleanup_txn_preview, dict) else None,
    )
    if candidate_count <= 0:
        _append_if_missing(blocking_reasons, "no_cleanup_candidates_in_preview")

    status = "blocked" if blocking_reasons else "operator_decision_required"
    allowed_next_step = (
        "resolve_blockers_and_rebuild_scaleup_readiness"
        if status == "blocked"
        else "operator_review_and_explicit_scope_approval"
    )

    rollback_requirements = [
        "retain legacy meter source as authoritative until a separate approved execution phase",
        "if any scale-up trial is later approved, require staged restore/readback checksum verification before closure",
        "require parity status=passed with critical_mismatch_count=0 before and after any future operation",
        "keep cleanup_scope_expansion_started=false until explicit operator decision is recorded",
    ]

    return {
        "schema_version": METER_CLEANUP_SCALEUP_READINESS_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_SCALEUP_READINESS_MODE,
        "status": status,
        "ready_for_scaleup": False,
        "cleanup_scope_expansion_started": False,
        "allowed_next_step": allowed_next_step,
        "blocking_reasons": blocking_reasons,
        "required_operator_decision": True,
        "candidate_count": int(candidate_count),
        "max_batch_size_recommendation": 0,
        "rollback_requirements": rollback_requirements,
        "input_refs": {
            "cleanup_preview_hash": _json_hash(cleanup_preview),
            "cleanup_transaction_preview_hash": _json_hash(cleanup_txn_preview),
            "cleanup_pilot_hash": _json_hash(cleanup_pilot),
            "stability_window_hash": _json_hash(stability_window),
            "parity_hash": _json_hash(parity),
            "restore_readback_hash": _json_hash(restore_readback),
            "rollback_drill_hash": _json_hash(rollback_drill),
            "backup_readiness_hash": _json_hash(backup_readiness),
            "backup_plan_hash": _json_hash(backup_plan),
            "backup_manifest_hash": _json_hash(backup_manifest),
            "backup_execution_gate_hash": _json_hash(backup_execution_gate),
            "backup_execution_proposal_hash": _json_hash(backup_execution_proposal),
        },
        "summary": {
            "status": status,
            "ready_for_scaleup": False,
            "cleanup_scope_expansion_started": False,
            "required_operator_decision": True,
            "candidate_count": int(candidate_count),
            "max_batch_size_recommendation": 0,
            "blocking_count": int(len(blocking_reasons)),
        },
    }


def write_scaleup_readiness_report_atomic(
    report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None
) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_scaleup_readiness_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_scaleup_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def read_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    return read_scaleup_readiness_report(policy=policy)


def rebuild_scaleup_readiness_report(
    *, policy: Optional[DataLifecyclePolicy] = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        report = build_scaleup_readiness_report(policy=current)
        write_scaleup_readiness_report_atomic(report, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_scaleup_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((report.get("candidate_count") or 0)),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, report
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_scaleup_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise


def rebuild_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    return rebuild_scaleup_readiness_report(policy=policy)
