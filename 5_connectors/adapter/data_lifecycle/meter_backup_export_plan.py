"""Legacy meter backup export dry-run plan (non-destructive planning only)."""

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
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")

METER_BACKUP_EXPORT_PLAN_SCHEMA_VERSION = "res-legacy-meter-backup-export-plan-v1"
METER_BACKUP_EXPORT_PLAN_REBUILD_SCHEMA_VERSION = "res-legacy-meter-backup-export-plan-rebuild-v1"
METER_BACKUP_EXPORT_PLAN_MODE = "dry_run_preview_only"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _plan_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_plan_file).expanduser()


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _destination_status(destination_raw: str, required_free_bytes: int) -> tuple[dict[str, Any], list[str]]:
    blocking: list[str] = []
    if not destination_raw:
        blocking.append("backup_destination_not_selected")
        blocking.append("free_space_not_verified")
        return {
            "status": "blocked",
            "path": None,
            "exists": False,
            "is_directory": False,
            "free_bytes": None,
            "required_free_bytes": int(required_free_bytes),
            "policy_ok": False,
        }, blocking

    destination = Path(destination_raw).expanduser()
    exists = destination.exists()
    is_dir = destination.is_dir() if exists else False
    policy_ok = exists and is_dir and destination.is_absolute()
    free_bytes: Optional[int] = None
    if policy_ok:
        try:
            stat = os.statvfs(str(destination))
            free_bytes = int(stat.f_bavail * stat.f_frsize)
        except Exception:
            free_bytes = None

    if not policy_ok:
        blocking.append("backup_destination_policy_not_satisfied")
    if free_bytes is None or int(free_bytes) < int(required_free_bytes):
        blocking.append("free_space_not_verified")

    return {
        "status": "ok" if policy_ok and free_bytes is not None and free_bytes >= required_free_bytes else "blocked",
        "path": str(destination),
        "exists": bool(exists),
        "is_directory": bool(is_dir),
        "free_bytes": free_bytes,
        "required_free_bytes": int(required_free_bytes),
        "policy_ok": bool(policy_ok),
    }, blocking


def build_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = _utc_now()
    parity = _meter_storage_v2.build_parity_report()
    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    backup_readiness = _backup_readiness.read_readiness(policy=current)

    blocking_reasons: list[str] = []

    if not isinstance(backup_readiness, dict):
        blocking_reasons.append("backup_export_readiness_missing")
        would_export_files: list[dict[str, Any]] = []
        estimated_export_bytes = 0
        required_free_bytes = 0
        source_readiness_hash = None
    else:
        would_export_files = list(backup_readiness.get("would_export_files") or [])
        estimated_export_bytes = int(backup_readiness.get("estimated_export_bytes", 0) or 0)
        required_free_bytes = int(backup_readiness.get("required_free_bytes", 0) or 0)
        source_readiness_hash = _stable_hash(backup_readiness)

    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
        source_cleanup_preview_hash = None
    else:
        source_cleanup_preview_hash = _stable_hash(cleanup_preview)

    parity_status = str(parity.get("status") or "").lower()
    critical_mismatch_count = int(parity.get("critical_mismatch_count", 0) or 0)
    if parity_status != "passed" or critical_mismatch_count != 0:
        blocking_reasons.append("parity_not_passed")

    destination_status, destination_blocking = _destination_status(
        current.meter_backup_export_destination,
        required_free_bytes,
    )
    blocking_reasons.extend(destination_blocking)

    # Execution remains forbidden by contract in RES-012.
    blocking_reasons.append("execution_not_enabled_in_res012")
    blocking_reasons.append("cleanup_execution_forbidden")

    blocking_reasons = sorted(set(blocking_reasons))

    return {
        "schema_version": METER_BACKUP_EXPORT_PLAN_SCHEMA_VERSION,
        "plan_id": uuid4().hex[:16],
        "generated_at": _to_iso(now),
        "mode": METER_BACKUP_EXPORT_PLAN_MODE,
        "status": "blocked",
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "execution_allowed": False,
        "source_readiness_hash": source_readiness_hash,
        "source_cleanup_preview_hash": source_cleanup_preview_hash,
        "destination_policy": {
            "destination_env_name": "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION",
            "destination_required": True,
            "must_exist": True,
            "must_be_directory": True,
            "must_be_absolute_path": True,
            "must_be_writable": False,
            "non_destructive_check_only": True,
        },
        "destination_status": destination_status,
        "would_export_files": would_export_files,
        "estimated_export_bytes": int(estimated_export_bytes),
        "required_free_bytes": int(required_free_bytes),
        "blocking_reasons": blocking_reasons,
        "summary": {
            "candidate_file_count": int(len(would_export_files)),
            "estimated_export_bytes": int(estimated_export_bytes),
            "destination_status": str(destination_status.get("status") or "blocked"),
            "blocking_reasons_count": int(len(blocking_reasons)),
        },
        "parity": {
            "status": str(parity.get("status") or "unknown"),
            "critical_mismatch_count": critical_mismatch_count,
        },
    }


def write_plan_atomic(plan: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _plan_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_plan_", suffix=".tmp", dir=str(path.parent))
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
    path = _plan_path(policy)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    plan = build_plan(policy=current)
    write_plan_atomic(plan, policy=current)
    completed_at = _utc_now()

    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_backup_export_plan_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((plan.get("summary") or {}).get("estimated_export_bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, plan
