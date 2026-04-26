"""Second-file cleanup pilot proposal (RES-027, proposal-only)."""

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
_repeatable_protocol = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_repeatable_pilot_protocol")
_stability_window = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_stability_window")
_scaleup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_scaleup_readiness")
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")
_restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
_rollback_drill = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")
_backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
_backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
_backup_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")

METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_SCHEMA_VERSION = "res-second-file-cleanup-pilot-proposal-v1"
METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_REBUILD_SCHEMA_VERSION = "res-second-file-cleanup-pilot-proposal-rebuild-v1"
METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_MODE = "proposal_only"


def _proposal_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_second_file_pilot_proposal_file).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _append_unique(output: list[str], reason: str) -> None:
    if reason not in output:
        output.append(reason)


def _find_txn_item(txn_preview: Optional[dict[str, Any]], source_path: str) -> Optional[dict[str, Any]]:
    if not isinstance(txn_preview, dict):
        return None
    for item in txn_preview.get("items") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or {}
        if isinstance(source, dict) and str(source.get("path") or "") == source_path:
            return item
    return None


def _candidate_risk(txn_item: Optional[dict[str, Any]]) -> str:
    if not isinstance(txn_item, dict):
        return "high"
    operation = str(txn_item.get("operation") or "blocked")
    blocking = [x for x in (txn_item.get("blocking_reasons") or []) if isinstance(x, str)]
    if operation == "eligible_for_future_cleanup" and not blocking:
        return "medium"
    if operation == "retain":
        return "high"
    return "high"


def _build_approval_hash(payload: dict[str, Any]) -> str:
    material = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_proposal(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)

    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    cleanup_txn_preview = _cleanup_txn_preview.read_preview(policy=current)
    cleanup_pilot = _cleanup_pilot.read_latest_pilot(policy=current)
    protocol = _repeatable_protocol.read_protocol(policy=current)
    stability_window = _stability_window.read_stability_window_report(policy=current)
    scaleup_readiness = _scaleup_readiness.read_readiness_report(policy=current)
    parity = _meter_storage_v2.build_parity_report()
    restore_readback = _restore_readback.read_restore_readback_report(policy=current)
    rollback_drill = _rollback_drill.read_rollback_drill_report(policy=current)
    backup_readiness = _backup_readiness.read_readiness(policy=current)
    backup_plan = _backup_plan.read_plan(policy=current)
    backup_manifest = _backup_manifest.read_package_manifest(policy=current)

    blocked_reasons: list[str] = []

    if not isinstance(protocol, dict):
        _append_unique(blocked_reasons, "repeatable_protocol_missing")
    else:
        if str(protocol.get("status") or "") == "blocked":
            _append_unique(blocked_reasons, "repeatable_protocol_blocked")

    if str(parity.get("status") or "").lower() != "passed" or int(parity.get("critical_mismatch_count", 0) or 0) != 0:
        _append_unique(blocked_reasons, "parity_not_clean")

    if not isinstance(stability_window, dict) or str(stability_window.get("status") or "") != "passed":
        _append_unique(blocked_reasons, "stability_window_not_passed")

    if not isinstance(restore_readback, dict) or str(restore_readback.get("status") or "") != "passed":
        _append_unique(blocked_reasons, "restore_readback_not_passed")

    if not isinstance(rollback_drill, dict) or str(rollback_drill.get("status") or "") != "passed":
        _append_unique(blocked_reasons, "rollback_drill_not_passed")

    if not (
        isinstance(scaleup_readiness, dict)
        and str(scaleup_readiness.get("status") or "") == "blocked"
        and not bool(scaleup_readiness.get("ready_for_scaleup", False))
        and not bool(scaleup_readiness.get("cleanup_scope_expansion_started", False))
    ):
        _append_unique(blocked_reasons, "scaleup_readiness_not_blocked_as_expected")

    preview_items = [x for x in ((cleanup_preview or {}).get("would_cleanup_files") or []) if isinstance(x, dict)]
    if not preview_items:
        _append_unique(blocked_reasons, "cleanup_preview_candidates_missing")
    if not isinstance(cleanup_txn_preview, dict):
        _append_unique(blocked_reasons, "cleanup_transaction_preview_missing")

    excluded_source_path = str((cleanup_pilot or {}).get("original_path") or "").strip()
    if not excluded_source_path and isinstance(cleanup_pilot, dict):
        selected = cleanup_pilot.get("selected_candidate") or {}
        excluded_source_path = str(selected.get("path") or "").strip()

    candidate_pool: list[dict[str, Any]] = []
    excluded_candidates: list[dict[str, Any]] = []

    for item in preview_items:
        source_path = str(item.get("path") or "").strip()
        if not source_path:
            continue
        txn_item = _find_txn_item(cleanup_txn_preview, source_path)
        if txn_item is None:
            continue

        candidate = {
            "path": source_path,
            "name": str(item.get("name") or Path(source_path).name),
            "bytes": int(item.get("bytes", 0) or 0),
            "sha256": item.get("sha256"),
            "mtime": item.get("mtime"),
            "txn_operation": str(txn_item.get("operation") or "unknown"),
            "txn_blocking_reasons": [x for x in (txn_item.get("blocking_reasons") or []) if isinstance(x, str)],
            "risk_level": _candidate_risk(txn_item),
            "estimated_reclaim_bytes": int(item.get("bytes", 0) or 0),
            "excluded": False,
            "excluded_reason": None,
        }

        if excluded_source_path and source_path == excluded_source_path:
            candidate["excluded"] = True
            candidate["excluded_reason"] = "already_quarantined_in_res023"
            excluded_candidates.append(candidate)
            continue

        if str(candidate.get("txn_operation") or "") != "eligible_for_future_cleanup":
            candidate["excluded"] = True
            candidate["excluded_reason"] = "transaction_preview_not_eligible"
            excluded_candidates.append(candidate)
            continue

        candidate_pool.append(candidate)

    selected_candidate = None
    if candidate_pool:
        candidate_pool.sort(key=lambda x: int(x.get("estimated_reclaim_bytes", 0) or 0), reverse=True)
        selected_candidate = dict(candidate_pool[0])

    if selected_candidate is None:
        _append_unique(blocked_reasons, "no_eligible_candidate_after_res023_exclusion")

    if excluded_source_path:
        _append_unique(blocked_reasons, "res023_quarantined_source_excluded")

    proposal_status = "blocked" if blocked_reasons else "proposal_ready_for_operator_review"

    backup_export_refs = {
        "readiness": {
            "status": str((backup_readiness or {}).get("status") or "missing"),
            "artifact_hash": _json_hash(backup_readiness),
        },
        "plan": {
            "status": str((backup_plan or {}).get("status") or "missing"),
            "artifact_hash": _json_hash(backup_plan),
        },
        "package_manifest": {
            "status": str((backup_manifest or {}).get("status") or "missing"),
            "artifact_hash": _json_hash(backup_manifest),
        },
    }

    rollback_refs = {
        "restore_readback": {
            "status": str((restore_readback or {}).get("status") or "missing"),
            "checksum_match": bool((restore_readback or {}).get("checksum_match", False)),
            "source_retained": bool((restore_readback or {}).get("source_retained", False)),
            "artifact_hash": _json_hash(restore_readback),
        },
        "rollback_drill": {
            "status": str((rollback_drill or {}).get("status") or "missing"),
            "staging_restore_readable": bool((rollback_drill or {}).get("staging_restore_readable", False)),
            "checksum_match": bool((rollback_drill or {}).get("checksum_match", False)),
            "artifact_hash": _json_hash(rollback_drill),
        },
    }

    approval_material = {
        "selected_candidate": {
            "path": (selected_candidate or {}).get("path"),
            "sha256": (selected_candidate or {}).get("sha256"),
            "bytes": int((selected_candidate or {}).get("bytes", 0) or 0),
        },
        "protocol_hash": _json_hash(protocol),
        "scaleup_readiness_hash": _json_hash(scaleup_readiness),
        "parity_hash": _json_hash(parity),
        "stability_window_hash": _json_hash(stability_window),
        "restore_readback_hash": _json_hash(restore_readback),
        "rollback_drill_hash": _json_hash(rollback_drill),
        "backup_readiness_hash": _json_hash(backup_readiness),
        "backup_plan_hash": _json_hash(backup_plan),
        "backup_manifest_hash": _json_hash(backup_manifest),
    }
    approval_hash = _build_approval_hash(approval_material) if selected_candidate else None

    return {
        "schema_version": METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_SCHEMA_VERSION,
        "proposal_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_MODE,
        "status": proposal_status,
        "selection_source": "cleanup_preview_plus_transaction_preview",
        "selected_candidate": selected_candidate,
        "candidate_pool": candidate_pool,
        "excluded_candidates": excluded_candidates,
        "candidate_risk": {
            "level": (selected_candidate or {}).get("risk_level", "high"),
            "reasons": (selected_candidate or {}).get("txn_blocking_reasons", []),
        },
        "estimated_reclaim_bytes": int((selected_candidate or {}).get("estimated_reclaim_bytes", 0) or 0),
        "backup_export_refs": backup_export_refs,
        "rollback_refs": rollback_refs,
        "approval_hash": approval_hash,
        "required_operator_approval": True,
        "second_file_pilot_allowed": False,
        "execution_started": False,
        "cleanup_scope_expansion_started": False,
        "allowed_next_step": "second-file pilot requires explicit approval",
        "blocking_reasons": blocked_reasons,
        "input_refs": {
            "protocol_hash": _json_hash(protocol),
            "cleanup_preview_hash": _json_hash(cleanup_preview),
            "cleanup_transaction_preview_hash": _json_hash(cleanup_txn_preview),
            "cleanup_pilot_hash": _json_hash(cleanup_pilot),
            "scaleup_readiness_hash": _json_hash(scaleup_readiness),
            "stability_window_hash": _json_hash(stability_window),
            "parity_hash": _json_hash(parity),
            "restore_readback_hash": _json_hash(restore_readback),
            "rollback_drill_hash": _json_hash(rollback_drill),
            "backup_readiness_hash": _json_hash(backup_readiness),
            "backup_plan_hash": _json_hash(backup_plan),
            "backup_manifest_hash": _json_hash(backup_manifest),
        },
        "summary": {
            "status": proposal_status,
            "blocking_count": len(blocked_reasons),
            "candidate_pool_count": len(candidate_pool),
            "excluded_candidate_count": len(excluded_candidates),
            "selected_candidate_present": selected_candidate is not None,
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        },
    }


def write_proposal_atomic(proposal: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _proposal_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_second_file_proposal_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(proposal, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_proposal(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _proposal_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_proposal(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        proposal = build_proposal(policy=current)
        write_proposal_atomic(proposal, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_second_file_pilot_proposal_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((proposal.get("estimated_reclaim_bytes") or 0)),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, proposal
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_second_file_pilot_proposal_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise
