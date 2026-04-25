"""Archive execution gate (gate-only, no execution)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_plan, archive_transaction, archive_restore_contract, state_store, health, archive_approval
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_EXECUTION_GATE_SCHEMA_VERSION = "dlp-archive-execution-gate-v1"
ARCHIVE_EXECUTION_GATE_REBUILD_SCHEMA_VERSION = "dlp-archive-execution-gate-rebuild-v1"
_GATE_MODE = "gate_only"


def _gate_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_execution_gate_file).expanduser()


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


def _artifact_hashes(
    *,
    plan: dict[str, Any],
    preview: dict[str, Any],
    readiness: dict[str, Any],
    lifecycle_health: dict[str, Any],
) -> dict[str, str]:
    return {
        "candidate_plan_hash": _json_hash(plan),
        "transaction_preview_hash": _json_hash(preview),
        "restore_readiness_hash": _json_hash(readiness),
        "lifecycle_health_hash": _json_hash(lifecycle_health),
    }


def _validate_approval(
    *,
    approval: Optional[dict[str, Any]],
    artifact_hashes: dict[str, str],
    now: datetime,
    blocking_reasons: list[str],
) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    # returns (approval_status, operator_id, expires_at, approved_plan_hash)
    if not isinstance(approval, dict):
        blocking_reasons.append("missing_operator_approval")
        return "missing", None, None, None

    if str(approval.get("schema_version") or "") != archive_approval.ARCHIVE_OPERATOR_APPROVAL_SCHEMA_VERSION:
        blocking_reasons.append("approval_schema_mismatch")
        return "invalid_schema", str(approval.get("operator_id") or ""), approval.get("expires_at"), None

    expires_at = approval.get("expires_at")
    expires_at_dt = _parse_iso_utc(expires_at)
    if expires_at_dt is None:
        blocking_reasons.append("approval_expiry_invalid")
        return "invalid_expiry", str(approval.get("operator_id") or ""), expires_at, None
    if expires_at_dt <= now:
        blocking_reasons.append("approval_expired")
        return "expired", str(approval.get("operator_id") or ""), expires_at, None

    approved_hashes = approval.get("approved_artifact_hashes")
    if not isinstance(approved_hashes, dict):
        blocking_reasons.append("approval_hashes_missing")
        return "invalid_hashes", str(approval.get("operator_id") or ""), expires_at, None

    approved_plan_hash = approved_hashes.get("candidate_plan_hash")
    mismatch_keys = []
    for key, expected in artifact_hashes.items():
        actual = approved_hashes.get(key)
        if str(actual or "") != str(expected or ""):
            mismatch_keys.append(key)
    if mismatch_keys:
        blocking_reasons.append("approval_artifact_hash_mismatch")
        if "candidate_plan_hash" in mismatch_keys:
            blocking_reasons.append("approval_plan_hash_mismatch")
        return "hash_mismatch", str(approval.get("operator_id") or ""), expires_at, approved_plan_hash

    return "valid", str(approval.get("operator_id") or ""), expires_at, approved_plan_hash


def build_execution_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    blocking_reasons: list[str] = []
    warnings: list[dict[str, Any]] = []
    required_approvals = ["operator_approval"]

    plan = archive_plan.read_plan(policy=current_policy)
    preview = archive_transaction.read_preview(policy=current_policy)
    readiness = archive_restore_contract.read_readiness_report(policy=current_policy)
    lifecycle = health.build_health_payload(policy=current_policy)
    approval = archive_approval.read_approval(policy=current_policy)

    if not isinstance(plan, dict):
        blocking_reasons.append("missing_candidate_plan")
    if not isinstance(preview, dict):
        blocking_reasons.append("missing_transaction_preview")
    if not isinstance(readiness, dict):
        blocking_reasons.append("missing_restore_readiness")
    if not isinstance(lifecycle, dict):
        blocking_reasons.append("missing_lifecycle_health")

    artifact_hashes = {
        "candidate_plan_hash": "",
        "transaction_preview_hash": "",
        "restore_readiness_hash": "",
        "lifecycle_health_hash": "",
    }
    approved_plan_hash: Optional[str] = None
    approval_status = "missing"
    approval_operator_id: Optional[str] = None
    approval_expires_at: Optional[str] = None

    if isinstance(plan, dict) and isinstance(preview, dict) and isinstance(readiness, dict) and isinstance(lifecycle, dict):
        if str(plan.get("schema_version") or "") != archive_plan.ARCHIVE_CANDIDATE_PLAN_SCHEMA_VERSION:
            blocking_reasons.append("candidate_plan_schema_mismatch")
        if str(plan.get("mode") or "") != "dry_run_only":
            blocking_reasons.append("candidate_plan_mode_mismatch")

        if str(preview.get("schema_version") or "") != archive_transaction.ARCHIVE_TRANSACTION_PREVIEW_SCHEMA_VERSION:
            blocking_reasons.append("transaction_preview_schema_mismatch")
        if str(preview.get("mode") or "") != "preview_only":
            blocking_reasons.append("transaction_preview_mode_mismatch")

        if str(readiness.get("schema_version") or "") != archive_restore_contract.ARCHIVE_RESTORE_READINESS_SCHEMA_VERSION:
            blocking_reasons.append("restore_readiness_schema_mismatch")
        if str(readiness.get("mode") or "") != "readiness_only":
            blocking_reasons.append("restore_readiness_mode_mismatch")

        traceability_ref = plan.get("traceability_ref") if isinstance(plan.get("traceability_ref"), dict) else {}
        fail_count = traceability_ref.get("fail_count")
        unexplained_partial_count = traceability_ref.get("unexplained_partial_count")
        if isinstance(fail_count, int) and fail_count > 0:
            blocking_reasons.append("traceability_fail_count_gt_zero")
        if isinstance(unexplained_partial_count, int) and unexplained_partial_count > 0:
            blocking_reasons.append("traceability_unexplained_partial_gt_zero")

        preview_summary = preview.get("summary") if isinstance(preview.get("summary"), dict) else {}
        if int(preview_summary.get("blocked_precondition_count", 0) or 0) > 0:
            blocking_reasons.append("preview_blocked_precondition_present")

        readiness_summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
        if str(readiness_summary.get("status") or "") != "present":
            blocking_reasons.append("restore_readiness_not_ready")

        artifact_hashes = _artifact_hashes(plan=plan, preview=preview, readiness=readiness, lifecycle_health=lifecycle)
        approval_status, approval_operator_id, approval_expires_at, approved_plan_hash = _validate_approval(
            approval=approval,
            artifact_hashes=artifact_hashes,
            now=now,
            blocking_reasons=blocking_reasons,
        )

    unique_blocking_reasons = []
    seen = set()
    for reason in blocking_reasons:
        if reason not in seen:
            seen.add(reason)
            unique_blocking_reasons.append(reason)
    blocking_reasons = unique_blocking_reasons

    allowed = len(blocking_reasons) == 0
    status = "allowed" if allowed else "blocked"
    if not allowed:
        warnings.append({"code": "gate_blocked", "blocking_count": len(blocking_reasons)})

    return {
        "schema_version": ARCHIVE_EXECUTION_GATE_SCHEMA_VERSION,
        "gate_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _GATE_MODE,
        "allowed": allowed,
        "status": status,
        "blocking_reasons": blocking_reasons,
        "required_approvals": required_approvals,
        "artifact_hashes": artifact_hashes,
        "approved_plan_hash": approved_plan_hash,
        "approval": {
            "status": approval_status,
            "operator_id": approval_operator_id,
            "expires_at": approval_expires_at,
        },
        "summary": {
            "allowed": allowed,
            "status": status,
            "blocking_count": len(blocking_reasons),
            "approval_status": approval_status,
            "expires_at": approval_expires_at,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_gate_atomic(gate: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _gate_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_gate_", suffix=".tmp", dir=str(path.parent))
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
    if not path.exists():
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
        gate = build_execution_gate(policy=current_policy)
        write_gate_atomic(gate, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_execution_gate_rebuild",
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
            trigger="archive_execution_gate_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
