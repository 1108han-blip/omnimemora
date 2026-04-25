"""Meter backup export execution gate evaluator (gate-only, no execution)."""

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
_backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
_backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
_package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
_approval_template = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template")
_operator_approval = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval")

METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION = "res-legacy-meter-backup-export-execution-gate-v1"
METER_BACKUP_EXPORT_EXECUTION_GATE_REBUILD_SCHEMA_VERSION = "res-legacy-meter-backup-export-execution-gate-rebuild-v1"
METER_BACKUP_EXPORT_EXECUTION_GATE_MODE = "execution_gate_only"


def _gate_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_execution_gate_file).expanduser()


def _json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_execution_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    blocking_reasons: list[str] = []

    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    readiness = _backup_readiness.read_readiness(policy=current)
    plan = _backup_plan.read_plan(policy=current)
    package_manifest = _package_manifest.read_package_manifest(policy=current)
    approval_template = _approval_template.read_approval_template(policy=current)
    operator_approval = _operator_approval.read_operator_approval(policy=current)

    expected_cleanup_hash: Optional[str] = None
    expected_readiness_hash: Optional[str] = None
    expected_plan_hash: Optional[str] = None
    expected_manifest_hash: Optional[str] = None
    expected_destination_path: Optional[str] = None

    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
    else:
        expected_cleanup_hash = _json_hash(cleanup_preview)

    if not isinstance(readiness, dict):
        blocking_reasons.append("backup_export_readiness_missing")
    else:
        expected_readiness_hash = _json_hash(readiness)
        if str(readiness.get("mode") or "") != "backup_export_readiness_only":
            blocking_reasons.append("backup_export_readiness_mode_mismatch")

    if not isinstance(plan, dict):
        blocking_reasons.append("backup_export_plan_missing")
    else:
        expected_plan_hash = _json_hash(plan)
        if str(plan.get("mode") or "") != "dry_run_preview_only":
            blocking_reasons.append("backup_export_plan_mode_mismatch")
        expected_destination_path = str(((plan.get("destination_status") or {}).get("path")) or "")

    if not isinstance(package_manifest, dict):
        blocking_reasons.append("backup_export_package_manifest_missing")
    else:
        expected_manifest_hash = _json_hash(package_manifest)
        if str(package_manifest.get("mode") or "") != "package_manifest_preview_only":
            blocking_reasons.append("backup_export_package_manifest_mode_mismatch")

    if not isinstance(approval_template, dict):
        blocking_reasons.append("backup_export_approval_template_missing")
    else:
        if str(approval_template.get("mode") or "") != "approval_template_only":
            blocking_reasons.append("backup_export_approval_template_mode_mismatch")

    approval_validation = _operator_approval.validate_operator_approval(
        approval=operator_approval,
        expected_plan_hash=expected_plan_hash,
        expected_package_manifest_hash=expected_manifest_hash,
        expected_readiness_hash=expected_readiness_hash,
        expected_cleanup_preview_hash=expected_cleanup_hash,
        expected_destination_path=expected_destination_path,
        now=now,
    )
    blocking_reasons.extend(list(approval_validation.get("blocking_reasons") or []))

    dedup: list[str] = []
    seen = set()
    for reason in blocking_reasons:
        if reason not in seen:
            seen.add(reason)
            dedup.append(reason)
    blocking_reasons = dedup

    allowed = len(blocking_reasons) == 0
    status = "allowed" if allowed else "blocked"
    return {
        "schema_version": METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION,
        "gate_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_BACKUP_EXPORT_EXECUTION_GATE_MODE,
        "allowed": allowed,
        "status": status,
        "backup_export_execution_started": False,
        "cleanup_execution_started": False,
        "artifact_hashes": {
            "plan_hash": expected_plan_hash,
            "package_manifest_hash": expected_manifest_hash,
            "readiness_hash": expected_readiness_hash,
            "cleanup_preview_hash": expected_cleanup_hash,
        },
        "approval": {
            "status": str(approval_validation.get("status") or "missing"),
            "operator_id": approval_validation.get("operator_id"),
            "expires_at": approval_validation.get("expires_at"),
            "destination_path": approval_validation.get("destination_path"),
        },
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "allowed": allowed,
            "approval_status": str(approval_validation.get("status") or "missing"),
            "blocking_count": int(len(blocking_reasons)),
            "backup_export_execution_started": False,
            "cleanup_execution_started": False,
        },
    }


def write_gate_atomic(gate: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _gate_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_execution_gate_", suffix=".tmp", dir=str(path.parent))
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
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        gate = build_execution_gate(policy=current)
        write_gate_atomic(gate, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_backup_export_execution_gate_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((gate.get("summary") or {}).get("blocking_count", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, gate
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_backup_export_execution_gate_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise
