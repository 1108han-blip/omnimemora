"""Legacy meter backup export execution proposal artifact (proposal-only)."""

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

_backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
_package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
_execution_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate")
_operator_approval = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval")

METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_SCHEMA_VERSION = "res-legacy-meter-backup-export-execution-proposal-v1"
METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_REBUILD_SCHEMA_VERSION = "res-legacy-meter-backup-export-execution-proposal-rebuild-v1"
METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_MODE = "proposal_only"


def _proposal_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_execution_proposal_file).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _proposal_status(
    gate: Optional[dict[str, Any]],
    approval: Optional[dict[str, Any]],
    blocking_reasons: list[str],
) -> str:
    if not isinstance(gate, dict):
        return "blocked"
    gate_status = str(gate.get("status") or "blocked")
    gate_allowed = bool(gate.get("allowed") is True)
    has_approval = isinstance(approval, dict)
    if gate_status == "allowed" and gate_allowed and has_approval and not blocking_reasons:
        return "ready_for_operator_decision"
    return "blocked"


def build_execution_proposal(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)

    gate = _execution_gate.read_gate(policy=current)
    approval = _operator_approval.read_operator_approval(policy=current)
    package_manifest = _package_manifest.read_package_manifest(policy=current)
    plan = _backup_plan.read_plan(policy=current)

    gate_ref = {
        "schema_version": _execution_gate.METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION,
        "status": "missing",
        "path": str(Path(current.meter_backup_export_execution_gate_file).expanduser()),
        "artifact_hash": None,
    }
    if isinstance(gate, dict):
        gate_ref["status"] = str(gate.get("status") or "blocked")
        gate_ref["artifact_hash"] = _json_hash(gate)

    approval_ref = {
        "schema_version": _operator_approval.METER_BACKUP_EXPORT_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "status": "missing",
        "path": str(Path(current.meter_backup_export_operator_approval_file).expanduser()),
        "artifact_hash": None,
    }
    if isinstance(approval, dict):
        approval_ref["status"] = "present"
        approval_ref["artifact_hash"] = _json_hash(approval)

    package_manifest_ref = {
        "schema_version": _package_manifest.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION,
        "status": "missing",
        "path": str(Path(current.meter_backup_export_package_manifest_file).expanduser()),
        "artifact_hash": None,
    }
    if isinstance(package_manifest, dict):
        package_manifest_ref["status"] = str(package_manifest.get("status") or "present")
        package_manifest_ref["artifact_hash"] = _json_hash(package_manifest)

    destination_snapshot = {
        "path": str(current.meter_backup_export_destination or ""),
        "status": "unknown",
        "exists": False,
        "is_directory": False,
        "free_bytes": None,
        "required_free_bytes": None,
        "policy_ok": False,
    }
    estimated_export_bytes = 0
    candidate_file_count = 0
    if isinstance(plan, dict):
        plan_destination = plan.get("destination_status")
        if isinstance(plan_destination, dict):
            destination_snapshot = {
                "path": str(plan_destination.get("path") or ""),
                "status": str(plan_destination.get("status") or "unknown"),
                "exists": bool(plan_destination.get("exists") is True),
                "is_directory": bool(plan_destination.get("is_directory") is True),
                "free_bytes": plan_destination.get("free_bytes"),
                "required_free_bytes": plan_destination.get("required_free_bytes"),
                "policy_ok": bool(plan_destination.get("policy_ok") is True),
            }
        summary = plan.get("summary") or {}
        estimated_export_bytes = int(summary.get("estimated_export_bytes", plan.get("estimated_export_bytes", 0)) or 0)
        candidate_file_count = int(summary.get("candidate_file_count", len(plan.get("would_export_files") or [])) or 0)
    elif isinstance(package_manifest, dict):
        manifest_summary = package_manifest.get("summary") or {}
        estimated_export_bytes = int(manifest_summary.get("total_bytes", package_manifest.get("total_bytes", 0)) or 0)
        candidate_file_count = int(
            manifest_summary.get("file_count", len(package_manifest.get("would_export_files") or [])) or 0
        )

    blocking_reasons = []
    if not isinstance(gate, dict):
        blocking_reasons.append("execution_gate_missing")
    else:
        blocking_reasons.extend(list(gate.get("blocking_reasons") or []))
        if str(gate.get("status") or "blocked") != "allowed":
            blocking_reasons.append("execution_gate_not_allowed")
        if gate_ref["artifact_hash"] is None:
            blocking_reasons.append("execution_gate_hash_missing")
    if not isinstance(package_manifest, dict):
        blocking_reasons.append("backup_export_package_manifest_missing")
    if not isinstance(plan, dict):
        blocking_reasons.append("backup_export_plan_missing")
    if not isinstance(approval, dict):
        blocking_reasons.append("operator_approval_missing")

    dedup: list[str] = []
    seen = set()
    for reason in blocking_reasons:
        if reason not in seen:
            seen.add(reason)
            dedup.append(reason)
    blocking_reasons = dedup

    proposal_status = _proposal_status(gate, approval, blocking_reasons)
    rollback_requirements = [
        "execution proposal does not authorize execution",
        "real export requires explicit operator decision and separate execution batch",
        "legacy meter source files must remain unchanged",
        "cleanup execution remains not started",
    ]

    return {
        "schema_version": METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_SCHEMA_VERSION,
        "proposal_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_MODE,
        "proposal_status": proposal_status,
        "execution_started": False,
        "cleanup_started": False,
        "gate_ref": gate_ref,
        "approval_ref": approval_ref,
        "package_manifest_ref": package_manifest_ref,
        "destination_snapshot": destination_snapshot,
        "estimated_export_bytes": estimated_export_bytes,
        "candidate_file_count": candidate_file_count,
        "rollback_requirements": rollback_requirements,
        "operator_decision_required": True,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": proposal_status,
            "execution_started": False,
            "cleanup_started": False,
            "operator_decision_required": True,
            "blocking_count": len(blocking_reasons),
            "estimated_export_bytes": estimated_export_bytes,
            "candidate_file_count": candidate_file_count,
        },
    }


def write_execution_proposal_atomic(
    proposal: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None
) -> Path:
    path = _proposal_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_execution_proposal_", suffix=".tmp", dir=str(path.parent))
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


def read_execution_proposal(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def rebuild_execution_proposal(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        proposal = build_execution_proposal(policy=current)
        write_execution_proposal_atomic(proposal, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_backup_export_execution_proposal_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((proposal.get("estimated_export_bytes") or 0)),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, proposal
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_backup_export_execution_proposal_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise
