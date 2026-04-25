"""Legacy meter backup export readiness (preview only)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")

METER_BACKUP_EXPORT_READINESS_SCHEMA_VERSION = "res-legacy-meter-backup-export-readiness-v1"
METER_BACKUP_EXPORT_READINESS_REBUILD_SCHEMA_VERSION = "res-legacy-meter-backup-export-readiness-rebuild-v1"
METER_BACKUP_EXPORT_READINESS_MODE = "backup_export_readiness_only"
CHECKSUM_ALGORITHM = "sha256"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _readiness_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_readiness_file).expanduser()


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


def _to_file_entry(item: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(item.get("path") or "")).expanduser()
    exists = path.exists() and path.is_file()
    size = int(path.stat().st_size) if exists else 0
    return {
        "name": str(item.get("name") or path.name),
        "path": str(path),
        "exists": bool(exists),
        "bytes": size,
        "sha256": _sha256_file(path),
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if exists else None,
        "source_cleanup_candidate": True,
    }


def build_readiness(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    now = _utc_now()
    cleanup_preview = _cleanup_preview.read_preview(policy=policy)
    parity = _meter_storage_v2.build_parity_report()

    would_export_files: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []

    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
    else:
        for item in cleanup_preview.get("would_cleanup_files") or []:
            if isinstance(item, dict):
                would_export_files.append(_to_file_entry(item))

    read_path_flags = (((cleanup_preview or {}).get("read_path_flags")) or {}) if isinstance(cleanup_preview, dict) else {}
    all_switches_enabled = (
        bool(read_path_flags.get("request_meter_switch_enabled"))
        and bool(read_path_flags.get("request_evidence_switch_enabled"))
        and bool(read_path_flags.get("metrics_switch_enabled"))
        and bool(read_path_flags.get("status_read_model_switch_enabled"))
    )
    legacy_fallback_enabled = bool(read_path_flags.get("legacy_fallback_enabled"))

    parity_passed = str(parity.get("status") or "").lower() == "passed"
    critical_mismatch_count = int(parity.get("critical_mismatch_count") or 0)
    if not parity_passed:
        blocking_reasons.append("parity_not_passed")
    if critical_mismatch_count != 0:
        blocking_reasons.append("critical_mismatch_nonzero")
    if not all_switches_enabled:
        blocking_reasons.append("not_all_sqlite_first_switches_enabled")
    if not legacy_fallback_enabled:
        blocking_reasons.append("legacy_fallback_not_enabled")

    # RES-010 is readiness-only by contract.
    blocking_reasons.append("backup_export_execution_not_enabled_in_res010")
    blocking_reasons.append("operator_approval_required")

    estimated_export_bytes = int(sum(int(item.get("bytes", 0) or 0) for item in would_export_files))
    required_free_bytes = int(estimated_export_bytes + max(4096, 512 * len(would_export_files)))
    export_manifest_preview = {
        "schema_version": "res-legacy-meter-backup-manifest-preview-v1",
        "mode": "manifest_preview_only",
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "file_count": int(len(would_export_files)),
        "total_bytes": estimated_export_bytes,
        "files": would_export_files,
    }

    return {
        "schema_version": METER_BACKUP_EXPORT_READINESS_SCHEMA_VERSION,
        "readiness_id": state_store.new_cycle_id(),
        "generated_at": _to_iso(now),
        "mode": METER_BACKUP_EXPORT_READINESS_MODE,
        "status": "blocked",
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "would_export_files": would_export_files,
        "export_manifest_preview": export_manifest_preview,
        "estimated_export_bytes": estimated_export_bytes,
        "required_free_bytes": required_free_bytes,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "blocking_reasons": blocking_reasons,
        "sqlite_parity": {
            "status": str(parity.get("status") or "unknown"),
            "critical_mismatch_count": critical_mismatch_count,
        },
        "read_path_flags": read_path_flags,
        "summary": {
            "candidate_file_count": int(len(would_export_files)),
            "estimated_export_bytes": estimated_export_bytes,
            "blocking_reasons_count": int(len(blocking_reasons)),
        },
    }


def write_readiness_atomic(payload: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _readiness_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_readiness_", suffix=".tmp", dir=str(path.parent))
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


def read_readiness(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _readiness_path(policy)
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


def rebuild_readiness(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    readiness = build_readiness(policy=current)
    write_readiness_atomic(readiness, policy=current)
    completed_at = _utc_now()

    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_backup_export_readiness_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((readiness.get("summary") or {}).get("estimated_export_bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, readiness
