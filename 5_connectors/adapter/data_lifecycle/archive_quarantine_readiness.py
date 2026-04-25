"""Source quarantine readiness plan (plan only, no source move)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_execution_gate, archive_fallback_contract, archive_pilot, state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_QUARANTINE_READINESS_SCHEMA_VERSION = "dlp-source-quarantine-readiness-plan-v1"
ARCHIVE_QUARANTINE_READINESS_REBUILD_SCHEMA_VERSION = "dlp-source-quarantine-readiness-rebuild-v1"
_MODE = "readiness_plan_only"
_PLANNED_ACTION = "quarantine_source_preview_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_quarantine_readiness_file).expanduser()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _planned_target_path(*, policy: DataLifecyclePolicy, source_path: Path, source_sha256: Optional[str]) -> str:
    suffix = (source_sha256 or "unknown")[:12]
    return str(Path(policy.archive_quarantine_root).expanduser() / f"{source_path.name}.{suffix}.quarantine")


def build_quarantine_readiness_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []

    pilot = archive_pilot.read_latest_pilot_record(policy=current_policy)
    fallback = archive_fallback_contract.read_report(policy=current_policy)
    gate = archive_execution_gate.read_gate(policy=current_policy)

    if not isinstance(pilot, dict):
        blocking_reasons.append("missing_pilot_record")
        source_path = Path("")
        archive_path = Path("")
        source_sha = None
        archive_sha = None
    else:
        source_path = Path(str(pilot.get("source_path") or "")).expanduser()
        archive_path = Path(str(pilot.get("archive_path") or "")).expanduser()
        source_sha = _sha256_file(source_path)
        archive_sha = _sha256_file(archive_path)

    if not isinstance(fallback, dict):
        blocking_reasons.append("missing_fallback_simulation")
    elif str(fallback.get("status") or "") != "passed":
        blocking_reasons.append("fallback_simulation_not_passed")

    if not isinstance(gate, dict):
        blocking_reasons.append("missing_execution_gate")
    elif not bool(gate.get("allowed")):
        blocking_reasons.append("execution_gate_not_allowed")

    if isinstance(pilot, dict):
        expected_sha = str(pilot.get("source_sha256") or pilot.get("archive_sha256") or "").strip()
        if not source_path.exists() or not source_path.is_file():
            blocking_reasons.append("source_missing")
        if not archive_path.exists() or not archive_path.is_file():
            blocking_reasons.append("archive_copy_missing")
        if not source_sha or not archive_sha or source_sha != archive_sha:
            blocking_reasons.append("source_archive_checksum_mismatch")
        if expected_sha and source_sha and source_sha != expected_sha:
            blocking_reasons.append("source_checksum_mismatch_with_pilot")

    unique_blockers: list[str] = []
    for reason in blocking_reasons:
        if reason not in unique_blockers:
            unique_blockers.append(reason)
    blocking_reasons = unique_blockers
    for reason in blocking_reasons:
        warnings.append({"code": reason})

    status = "ready_for_approval" if not blocking_reasons else "blocked"
    planned_target = (
        _planned_target_path(policy=current_policy, source_path=source_path, source_sha256=source_sha)
        if isinstance(pilot, dict)
        else None
    )
    candidate = {
        "source_path": str(source_path) if isinstance(pilot, dict) else None,
        "source_kind": pilot.get("source_kind") if isinstance(pilot, dict) else None,
        "source_bytes": int(pilot.get("source_bytes", 0) or 0) if isinstance(pilot, dict) else 0,
        "source_sha256": source_sha,
        "archive_path": str(archive_path) if isinstance(pilot, dict) else None,
        "archive_sha256": archive_sha,
        "restore_key": pilot.get("restore_key") if isinstance(pilot, dict) else None,
        "planned_quarantine_path": planned_target,
    }
    transaction_preview = {
        "planned_action": _PLANNED_ACTION,
        "would_move_source": False,
        "source_move_executed": False,
        "production_read_path_unchanged": True,
        "candidate": candidate,
        "rollback_hint": "no rollback needed because source is not moved in readiness_plan_only mode",
    }
    approval_requirements = {
        "operator_approval_required": True,
        "execution_gate_allowed_required": True,
        "matching_artifact_hashes_required": True,
        "actual_quarantine_requires_separate_approval": True,
    }

    return {
        "schema_version": ARCHIVE_QUARANTINE_READINESS_SCHEMA_VERSION,
        "plan_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _MODE,
        "status": status,
        "blocking_reasons": blocking_reasons,
        "pilot_ref": {
            "status": "present" if isinstance(pilot, dict) else "missing",
            "pilot_id": pilot.get("pilot_id") if isinstance(pilot, dict) else None,
            "path": str(Path(current_policy.archive_pilot_record_file).expanduser()),
        },
        "fallback_ref": {
            "status": fallback.get("status") if isinstance(fallback, dict) else "missing",
            "simulation_id": fallback.get("simulation_id") if isinstance(fallback, dict) else None,
            "path": str(Path(current_policy.archive_fallback_simulation_file).expanduser()),
        },
        "gate_ref": {
            "status": gate.get("status") if isinstance(gate, dict) else "missing",
            "allowed": bool(gate.get("allowed")) if isinstance(gate, dict) else False,
            "gate_id": gate.get("gate_id") if isinstance(gate, dict) else None,
            "path": str(Path(current_policy.archive_execution_gate_file).expanduser()),
        },
        "candidate": candidate,
        "transaction_preview": transaction_preview,
        "approval_requirements": approval_requirements,
        "source_move_executed": False,
        "source_retained": bool(source_path.exists() and source_path.is_file()) if isinstance(pilot, dict) else False,
        "production_read_path_unchanged": True,
        "summary": {
            "status": status,
            "candidate_present": isinstance(pilot, dict),
            "blocking_count": len(blocking_reasons),
            "source_move_executed": False,
            "production_read_path_unchanged": True,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_plan_atomic(plan: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_quarantine_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def rebuild_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        plan = build_quarantine_readiness_plan(policy=current_policy)
        write_plan_atomic(plan, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_quarantine_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((plan.get("candidate") or {}).get("source_bytes", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, plan
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_quarantine_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
