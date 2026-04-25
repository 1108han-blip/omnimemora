"""Execution gate for future non-active copy quarantine (gate only)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_approval, archive_non_active_candidates, archive_non_active_quarantine_readiness, state_store
from .policy import DataLifecyclePolicy, load_policy

NON_ACTIVE_EXECUTION_GATE_SCHEMA_VERSION = "dlp-non-active-copy-execution-gate-v1"
NON_ACTIVE_EXECUTION_GATE_REBUILD_SCHEMA_VERSION = "dlp-non-active-copy-execution-gate-rebuild-v1"
GATE_MODE = "gate_only"


def _gate_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_non_active_execution_gate_file).expanduser()


def _json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _validate_approval(
    *,
    approval: Optional[dict[str, Any]],
    artifact_hashes: dict[str, str],
    now: datetime,
    blocking_reasons: list[str],
) -> tuple[str, Optional[str], Optional[str]]:
    if not isinstance(approval, dict):
        blocking_reasons.append("missing_operator_approval")
        return "missing", None, None
    if approval.get("schema_version") != archive_approval.ARCHIVE_OPERATOR_APPROVAL_SCHEMA_VERSION:
        blocking_reasons.append("approval_schema_mismatch")
        return "invalid_schema", str(approval.get("operator_id") or ""), approval.get("expires_at")
    expires_at = approval.get("expires_at")
    expires_at_dt = _parse_iso_utc(expires_at)
    if expires_at_dt is None:
        blocking_reasons.append("approval_expiry_invalid")
        return "invalid_expiry", str(approval.get("operator_id") or ""), expires_at
    if expires_at_dt <= now:
        blocking_reasons.append("approval_expired")
        return "expired", str(approval.get("operator_id") or ""), expires_at
    approved_hashes = approval.get("approved_artifact_hashes")
    if not isinstance(approved_hashes, dict):
        blocking_reasons.append("approval_hashes_missing")
        return "invalid_hashes", str(approval.get("operator_id") or ""), expires_at
    mismatch = []
    for key, expected in artifact_hashes.items():
        if str(approved_hashes.get(key) or "") != str(expected or ""):
            mismatch.append(key)
    if mismatch:
        blocking_reasons.append("approval_artifact_hash_mismatch")
        for key in mismatch:
            blocking_reasons.append(f"approval_{key}_mismatch")
        return "hash_mismatch", str(approval.get("operator_id") or ""), expires_at
    return "valid", str(approval.get("operator_id") or ""), expires_at


def build_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    blocking_reasons: list[str] = []
    warnings: list[dict[str, Any]] = []

    readiness = archive_non_active_quarantine_readiness.read_plan(policy=current_policy)
    selector = archive_non_active_candidates.read_report(policy=current_policy)
    approval = archive_approval.read_approval(policy=current_policy)

    if not isinstance(readiness, dict):
        blocking_reasons.append("missing_non_active_quarantine_readiness")
    else:
        if readiness.get("schema_version") != archive_non_active_quarantine_readiness.NON_ACTIVE_QUARANTINE_READINESS_SCHEMA_VERSION:
            blocking_reasons.append("non_active_quarantine_readiness_schema_mismatch")
        if readiness.get("mode") != archive_non_active_quarantine_readiness.READINESS_MODE:
            blocking_reasons.append("non_active_quarantine_readiness_mode_mismatch")
        if readiness.get("status") != "ready_for_operator_approval":
            blocking_reasons.append("non_active_quarantine_readiness_not_ready")
        selected = readiness.get("selected_candidate") if isinstance(readiness.get("selected_candidate"), dict) else {}
        if selected.get("candidate_kind") != "archive_pilot_copy":
            blocking_reasons.append("selected_candidate_not_archive_pilot_copy")
        summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
        if bool(summary.get("source_move_executed", False)):
            blocking_reasons.append("source_move_already_executed")
        if bool(summary.get("non_active_copy_move_executed", False)):
            blocking_reasons.append("non_active_copy_already_moved")
        if bool(summary.get("delete_compress_executed", False)):
            blocking_reasons.append("delete_or_compress_already_executed")
        planned_target = selected.get("planned_quarantine_path") or (readiness.get("transaction_preview") or {}).get("planned_quarantine_path")
        if planned_target and Path(str(planned_target)).expanduser().exists():
            blocking_reasons.append("planned_quarantine_target_already_exists")

    if not isinstance(selector, dict):
        blocking_reasons.append("missing_non_active_candidate_report")
    else:
        if selector.get("schema_version") != archive_non_active_candidates.NON_ACTIVE_CANDIDATE_REPORT_SCHEMA_VERSION:
            blocking_reasons.append("non_active_candidate_report_schema_mismatch")
        selector_summary = selector.get("summary") if isinstance(selector.get("summary"), dict) else {}
        if bool(selector_summary.get("source_move_delete_compress_executed", False)):
            blocking_reasons.append("selector_report_has_mutation_flag")

    artifact_hashes = {
        "non_active_quarantine_readiness_hash": _json_hash(readiness) if isinstance(readiness, dict) else "",
        "non_active_candidate_report_hash": _json_hash(selector) if isinstance(selector, dict) else "",
    }
    approval_status, approval_operator_id, approval_expires_at = _validate_approval(
        approval=approval,
        artifact_hashes=artifact_hashes,
        now=now,
        blocking_reasons=blocking_reasons,
    )

    unique_blockers: list[str] = []
    seen = set()
    for reason in blocking_reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique_blockers.append(reason)
    blocking_reasons = unique_blockers
    allowed = len(blocking_reasons) == 0
    status = "allowed" if allowed else "blocked"
    if not allowed:
        warnings.append({"code": "non_active_execution_gate_blocked", "blocking_count": len(blocking_reasons)})

    return {
        "schema_version": NON_ACTIVE_EXECUTION_GATE_SCHEMA_VERSION,
        "gate_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": GATE_MODE,
        "allowed": allowed,
        "status": status,
        "blocking_reasons": blocking_reasons,
        "required_approvals": ["operator_approval"],
        "artifact_hashes": artifact_hashes,
        "approval": {
            "status": approval_status,
            "operator_id": approval_operator_id,
            "expires_at": approval_expires_at,
        },
        "execution_scope": {
            "target": "selector_approved_archive_pilot_copy",
            "source_move_allowed": False,
            "delete_allowed": False,
            "compress_allowed": False,
            "production_read_path_switch_allowed": False,
        },
        "summary": {
            "allowed": allowed,
            "status": status,
            "blocking_count": len(blocking_reasons),
            "approval_status": approval_status,
            "source_move_allowed": False,
            "delete_allowed": False,
            "compress_allowed": False,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_gate_atomic(gate: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _gate_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_non_active_gate_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(gate, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _gate_path(policy)
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        gate = build_gate(policy=current_policy)
        write_gate_atomic(gate, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_non_active_execution_gate_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((gate.get("summary") or {}).get("blocking_count", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, gate
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_non_active_execution_gate_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
