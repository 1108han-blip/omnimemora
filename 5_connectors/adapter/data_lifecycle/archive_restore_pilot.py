"""Conditional restore pilot skeleton (staging-only default)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_RESTORE_PILOT_SCHEMA_VERSION = "dlp-archive-restore-pilot-record-v1"
ARCHIVE_RESTORE_PILOT_MODE = "conditional_restore_to_staging"
ARCHIVE_RESTORE_PILOT_TRIGGER = "archive_restore_pilot_execute"
BLOCKED_NO_SUCCESSFUL_QUARANTINE = "blocked_no_successful_quarantine"


def _base_dir(policy: DataLifecyclePolicy) -> Path:
    return Path(policy.archive_restore_readiness_file).expanduser().parent


def _quarantine_record_path(policy: DataLifecyclePolicy) -> Path:
    return Path(policy.archive_quarantine_record_file).expanduser()


def _restore_record_path(policy: DataLifecyclePolicy) -> Path:
    return Path(policy.archive_restore_pilot_record_file).expanduser()


def _staging_restore_root(policy: DataLifecyclePolicy) -> Path:
    return Path(policy.archive_restore_staging_root).expanduser()


def _read_json_dict(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


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


def _copy_file_atomic(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_restore_copy_", suffix=".tmp", dir=str(dst.parent))
    try:
        os.close(fd)
        shutil.copyfile(str(src), tmp)
        with open(tmp, "rb") as fh:
            os.fsync(fh.fileno())
        os.replace(tmp, str(dst))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _write_record_atomic(record: dict[str, Any], *, policy: DataLifecyclePolicy) -> Path:
    path = _restore_record_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_restore_pilot_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_latest_restore_pilot_record(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    current_policy = policy or load_policy()
    return _read_json_dict(_restore_record_path(current_policy))


def _extract_quarantine_copy_path(quarantine_record: dict[str, Any]) -> Optional[Path]:
    for key in ("quarantine_copy_path", "quarantine_path", "path"):
        value = str(quarantine_record.get(key) or "").strip()
        if value:
            return Path(value).expanduser()
    return None


def _is_successful_quarantine_record(quarantine_record: Optional[dict[str, Any]]) -> bool:
    if not isinstance(quarantine_record, dict):
        return False
    status = str(quarantine_record.get("status") or "").strip().lower()
    return status in {"success", "successful", "successful_quarantine"}


def _blocked_record(*, reason: str, quarantine_record: Optional[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    quarantine_status = None
    if isinstance(quarantine_record, dict):
        quarantine_status = quarantine_record.get("status")
    return {
        "schema_version": ARCHIVE_RESTORE_PILOT_SCHEMA_VERSION,
        "restore_id": uuid4().hex[:12],
        "generated_at": now,
        "mode": ARCHIVE_RESTORE_PILOT_MODE,
        "status": BLOCKED_NO_SUCCESSFUL_QUARANTINE,
        "message": reason,
        "quarantine_ref": {
            "status": quarantine_status,
            "path": str(_extract_quarantine_copy_path(quarantine_record) or ""),
        },
        "restore_target_scope": "staging",
        "restore_target_path": None,
        "restore_target_checksum": None,
        "quarantine_checksum": None,
        "checksum_match": False,
        "archive_copy_retained": True,
        "quarantine_copy_retained": True,
        "production_source_overwrite": False,
    }


def execute_restore_pilot(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()

    def _append(status: str, bytes_scanned: int, error: Optional[str]) -> dict[str, Any]:
        completed_at = datetime.now(timezone.utc)
        ledger = state_store.build_record(
            cycle_id=cycle_id,
            trigger=ARCHIVE_RESTORE_PILOT_TRIGGER,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            bytes_scanned=bytes_scanned,
            error=error,
        )
        state_store.append_state_record(ledger, policy=current_policy)
        return ledger

    quarantine_record = _read_json_dict(_quarantine_record_path(current_policy))
    if not _is_successful_quarantine_record(quarantine_record):
        blocked = _blocked_record(
            reason="restore pilot blocked: no successful quarantine record",
            quarantine_record=quarantine_record,
        )
        _write_record_atomic(blocked, policy=current_policy)
        return _append("blocked", 0, BLOCKED_NO_SUCCESSFUL_QUARANTINE), blocked

    quarantine_copy_path = _extract_quarantine_copy_path(quarantine_record)
    if quarantine_copy_path is None or not quarantine_copy_path.exists() or not quarantine_copy_path.is_file():
        blocked = _blocked_record(
            reason="restore pilot blocked: quarantine copy is missing",
            quarantine_record=quarantine_record,
        )
        _write_record_atomic(blocked, policy=current_policy)
        return _append("blocked", 0, "quarantine_copy_missing"), blocked

    quarantine_sha = _sha256_file(quarantine_copy_path)
    target_name = f"{quarantine_copy_path.name}.{(quarantine_sha or 'unknown')[:12]}.restored"
    restore_target = _staging_restore_root(current_policy) / target_name
    _copy_file_atomic(quarantine_copy_path, restore_target)

    restore_sha = _sha256_file(restore_target)
    checksum_match = bool(quarantine_sha and restore_sha and quarantine_sha == restore_sha)
    production_source_path = str((quarantine_record or {}).get("production_source_path") or "").strip()
    payload = {
        "schema_version": ARCHIVE_RESTORE_PILOT_SCHEMA_VERSION,
        "restore_id": uuid4().hex[:12],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": ARCHIVE_RESTORE_PILOT_MODE,
        "status": "success" if checksum_match else "failed",
        "message": "restore copied to staging target" if checksum_match else "restore checksum mismatch",
        "quarantine_ref": {
            "status": quarantine_record.get("status"),
            "path": str(quarantine_copy_path),
            "quarantine_id": quarantine_record.get("quarantine_id"),
        },
        "restore_target_scope": "staging",
        "restore_target_path": str(restore_target),
        "restore_target_checksum": restore_sha,
        "quarantine_checksum": quarantine_sha,
        "checksum_match": checksum_match,
        "archive_copy_retained": True,
        "quarantine_copy_retained": quarantine_copy_path.exists() and quarantine_copy_path.is_file(),
        "production_source_path": production_source_path or None,
        "production_source_overwrite": False,
    }
    _write_record_atomic(payload, policy=current_policy)
    ledger_status = "success" if checksum_match else "failed"
    ledger_error = None if checksum_match else "restore_checksum_mismatch"
    bytes_scanned = int(restore_target.stat().st_size) if restore_target.exists() else 0
    return _append(ledger_status, bytes_scanned, ledger_error), payload
