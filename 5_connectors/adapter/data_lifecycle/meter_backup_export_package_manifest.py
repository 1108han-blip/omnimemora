"""Legacy meter backup export package manifest preview (non-destructive only)."""

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

METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION = "res-legacy-meter-backup-export-package-manifest-v1"
METER_BACKUP_EXPORT_PACKAGE_MANIFEST_REBUILD_SCHEMA_VERSION = "res-legacy-meter-backup-export-package-manifest-rebuild-v1"
METER_BACKUP_EXPORT_PACKAGE_MANIFEST_MODE = "package_manifest_preview_only"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _manifest_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_package_manifest_file).expanduser()


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _entry_from_plan(item: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(item.get("path") or "")).expanduser()
    exists = path.exists() and path.is_file()
    file_bytes = int(path.stat().st_size) if exists else int(item.get("bytes", 0) or 0)
    return {
        "name": str(item.get("name") or path.name),
        "path": str(path),
        "exists": bool(exists),
        "bytes": int(file_bytes),
        "sha256": _sha256_file(path),
        "source_plan_candidate": True,
    }


def build_package_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = _utc_now()
    plan = _backup_plan.read_plan(policy=current)
    readiness = _backup_readiness.read_readiness(policy=current)
    cleanup_preview = _cleanup_preview.read_preview(policy=current)

    blocking_reasons: list[str] = []
    source_plan_hash: Optional[str] = None
    source_readiness_hash: Optional[str] = None
    source_cleanup_preview_hash: Optional[str] = None
    files: list[dict[str, Any]] = []

    if not isinstance(plan, dict):
        blocking_reasons.append("backup_export_plan_missing")
    else:
        source_plan_hash = _stable_hash(plan)
        for item in plan.get("would_export_files") or []:
            if isinstance(item, dict):
                files.append(_entry_from_plan(item))

    if not isinstance(readiness, dict):
        blocking_reasons.append("backup_export_readiness_missing")
    else:
        source_readiness_hash = _stable_hash(readiness)

    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
    else:
        source_cleanup_preview_hash = _stable_hash(cleanup_preview)

    # Execution remains forbidden by contract in RES-013.
    blocking_reasons.append("execution_not_enabled_in_res013")
    blocking_reasons.append("backup_export_execution_not_started")
    blocking_reasons.append("cleanup_execution_not_started")
    blocking_reasons = sorted(set(blocking_reasons))

    total_bytes = int(sum(int(item.get("bytes", 0) or 0) for item in files))

    return {
        "schema_version": METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION,
        "package_id": uuid4().hex[:16],
        "generated_at": _to_iso(now),
        "mode": METER_BACKUP_EXPORT_PACKAGE_MANIFEST_MODE,
        "status": "blocked",
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "execution_allowed": False,
        "source_plan_hash": source_plan_hash,
        "source_readiness_hash": source_readiness_hash,
        "source_cleanup_preview_hash": source_cleanup_preview_hash,
        "destination_policy_snapshot": (plan or {}).get("destination_policy") or {
            "destination_env_name": "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION",
            "non_destructive_check_only": True,
        },
        "destination_status_snapshot": (plan or {}).get("destination_status") or {
            "status": "unknown",
            "path": None,
            "exists": False,
            "is_directory": False,
            "free_bytes": None,
            "required_free_bytes": None,
            "policy_ok": False,
        },
        "would_export_files": files,
        "total_bytes": total_bytes,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "file_count": int(len(files)),
            "total_bytes": total_bytes,
            "blocking_reasons_count": int(len(blocking_reasons)),
        },
    }


def write_package_manifest_atomic(payload: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _manifest_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_package_manifest_", suffix=".tmp", dir=str(path.parent))
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


def read_package_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _manifest_path(policy)
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


def rebuild_package_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    manifest = build_package_manifest(policy=current)
    write_package_manifest_atomic(manifest, policy=current)
    completed_at = _utc_now()

    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_backup_export_package_manifest_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((manifest.get("summary") or {}).get("total_bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, manifest

