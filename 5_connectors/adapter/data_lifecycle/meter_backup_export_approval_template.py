"""Legacy meter backup export approval template (template only, non-executable)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
_backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
_backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
_package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")

METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_SCHEMA_VERSION = "res-legacy-meter-backup-export-approval-template-v1"
METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_REBUILD_SCHEMA_VERSION = "res-legacy-meter-backup-export-approval-template-rebuild-v1"
METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_MODE = "approval_template_only"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: Optional[datetime]) -> Optional[str]:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).isoformat()


def _template_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_approval_template_file).expanduser()


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_approval_template(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = _utc_now()
    expires_at = now + timedelta(hours=24)

    plan = _backup_plan.read_plan(policy=current)
    readiness = _backup_readiness.read_readiness(policy=current)
    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    package_manifest = _package_manifest.read_package_manifest(policy=current)

    blocking_reasons: list[str] = []
    approved_plan_hash: Optional[str] = None
    approved_readiness_hash: Optional[str] = None
    approved_cleanup_preview_hash: Optional[str] = None
    approved_package_manifest_hash: Optional[str] = None

    if isinstance(plan, dict):
        approved_plan_hash = _stable_hash(plan)
    else:
        blocking_reasons.append("backup_export_plan_missing")

    if isinstance(readiness, dict):
        approved_readiness_hash = _stable_hash(readiness)
    else:
        blocking_reasons.append("backup_export_readiness_missing")

    if isinstance(cleanup_preview, dict):
        approved_cleanup_preview_hash = _stable_hash(cleanup_preview)
    else:
        blocking_reasons.append("cleanup_preview_missing")

    if isinstance(package_manifest, dict):
        approved_package_manifest_hash = _stable_hash(package_manifest)
    else:
        blocking_reasons.append("backup_export_package_manifest_missing")

    # RES-013 template is not a valid approval artifact.
    blocking_reasons.append("approval_template_only")
    blocking_reasons.append("backup_export_execution_not_started")
    blocking_reasons.append("cleanup_execution_not_started")
    blocking_reasons = sorted(set(blocking_reasons))

    destination_path = None
    if isinstance(plan, dict):
        destination_path = ((plan.get("destination_status") or {}).get("path")) or None

    return {
        "schema_version": METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_SCHEMA_VERSION,
        "template_id": state_store.new_cycle_id(),
        "generated_at": _to_iso(now),
        "mode": METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_MODE,
        "status": "blocked",
        "approval_valid": False,
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "execution_allowed": False,
        "operator_id": None,
        "approved_at": None,
        "expires_at": _to_iso(expires_at),
        "approved_plan_hash": approved_plan_hash,
        "approved_readiness_hash": approved_readiness_hash,
        "approved_cleanup_preview_hash": approved_cleanup_preview_hash,
        "approved_package_manifest_hash": approved_package_manifest_hash,
        "destination_path": destination_path,
        "reason": "template_only_not_executable",
        "blocking_reasons": blocking_reasons,
        "summary": {
            "approval_valid": False,
            "blocking_reasons_count": int(len(blocking_reasons)),
        },
    }


def write_approval_template_atomic(payload: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _template_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_approval_template_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_approval_template(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _template_path(policy)
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


def rebuild_approval_template(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    template = build_approval_template(policy=current)
    write_approval_template_atomic(template, policy=current)
    completed_at = _utc_now()

    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_backup_export_approval_template_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=0,
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, template

