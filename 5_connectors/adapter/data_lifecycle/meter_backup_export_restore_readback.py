"""Restore/readback validation for the meter backup export copy pilot."""

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

_copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")

METER_BACKUP_EXPORT_RESTORE_READBACK_SCHEMA_VERSION = "res-legacy-meter-backup-export-restore-readback-v1"
METER_BACKUP_EXPORT_RESTORE_READBACK_REBUILD_SCHEMA_VERSION = (
    "res-legacy-meter-backup-export-restore-readback-rebuild-v1"
)
METER_BACKUP_EXPORT_RESTORE_READBACK_MODE = "restore_readback_validation_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_restore_readback_file).expanduser()


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


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _copy_pilot_ref(copy_record: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(copy_record, dict):
        return {
            "schema_version": _copy_pilot.METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION,
            "status": "missing",
            "pilot_id": None,
            "artifact_hash": None,
        }
    return {
        "schema_version": str(
            copy_record.get("schema_version") or _copy_pilot.METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION
        ),
        "status": str(copy_record.get("status") or "unknown"),
        "pilot_id": copy_record.get("pilot_id"),
        "artifact_hash": _json_hash(copy_record),
    }


def build_restore_readback_report(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    copy_record = _copy_pilot.read_latest_copy_pilot(policy=current)
    blocking_reasons: list[str] = []

    source_path: Optional[Path] = None
    backup_copy_path: Optional[Path] = None
    expected_source_sha = None
    expected_copy_sha = None

    if not isinstance(copy_record, dict):
        blocking_reasons.append("copy_pilot_missing")
    else:
        if str(copy_record.get("status") or "") not in {"success", "already_copied"}:
            blocking_reasons.append("copy_pilot_not_success")
        selected = copy_record.get("selected_candidate")
        if isinstance(selected, dict):
            raw_source = str(selected.get("path") or "")
            if raw_source:
                source_path = Path(raw_source).expanduser()
        raw_target = str(copy_record.get("target_path") or "")
        if raw_target:
            backup_copy_path = Path(raw_target).expanduser()
        expected_source_sha = str(copy_record.get("source_sha256") or "") or None
        expected_copy_sha = str(copy_record.get("copied_sha256") or "") or None
        if not expected_source_sha or not expected_copy_sha:
            blocking_reasons.append("copy_pilot_hash_missing")
        if not bool(copy_record.get("source_retained", False)):
            blocking_reasons.append("copy_pilot_source_not_retained")
        if not bool(copy_record.get("read_path_unchanged", True)):
            blocking_reasons.append("copy_pilot_read_path_changed")
        if bool(copy_record.get("cleanup_started", False)):
            blocking_reasons.append("copy_pilot_cleanup_started")

    source_readable = bool(source_path and source_path.exists() and source_path.is_file())
    backup_copy_readable = bool(backup_copy_path and backup_copy_path.exists() and backup_copy_path.is_file())
    if isinstance(copy_record, dict) and not source_readable:
        blocking_reasons.append("source_not_readable")
    if isinstance(copy_record, dict) and not backup_copy_readable:
        blocking_reasons.append("backup_copy_not_readable")

    source_sha = _sha256_file(source_path) if source_path else None
    backup_copy_sha = _sha256_file(backup_copy_path) if backup_copy_path else None
    source_bytes = int(source_path.stat().st_size) if source_readable and source_path else 0
    backup_copy_bytes = int(backup_copy_path.stat().st_size) if backup_copy_readable and backup_copy_path else 0

    checksum_match = bool(source_sha and backup_copy_sha and source_sha == backup_copy_sha)
    expected_hash_match = bool(
        source_sha
        and backup_copy_sha
        and expected_source_sha
        and expected_copy_sha
        and source_sha == expected_source_sha
        and backup_copy_sha == expected_copy_sha
    )
    bytes_match = bool(source_readable and backup_copy_readable and source_bytes == backup_copy_bytes)

    if isinstance(copy_record, dict) and not checksum_match:
        blocking_reasons.append("checksum_mismatch")
    if isinstance(copy_record, dict) and not expected_hash_match:
        blocking_reasons.append("copy_pilot_hash_mismatch")
    if isinstance(copy_record, dict) and not bytes_match:
        blocking_reasons.append("bytes_mismatch")

    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    status = "passed" if not blocking_reasons else "blocked"

    return {
        "schema_version": METER_BACKUP_EXPORT_RESTORE_READBACK_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_BACKUP_EXPORT_RESTORE_READBACK_MODE,
        "status": status,
        "copy_pilot_ref": _copy_pilot_ref(copy_record),
        "source_path": str(source_path) if source_path else None,
        "backup_copy_path": str(backup_copy_path) if backup_copy_path else None,
        "source_readable": source_readable,
        "backup_copy_readable": backup_copy_readable,
        "source_retained": source_readable,
        "read_path_unchanged": True,
        "checksum_match": checksum_match,
        "expected_hash_match": expected_hash_match,
        "bytes_match": bytes_match,
        "source_sha256": source_sha,
        "backup_copy_sha256": backup_copy_sha,
        "source_bytes": source_bytes,
        "backup_copy_bytes": backup_copy_bytes,
        "production_restore_started": False,
        "cleanup_started": False,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "source_retained": source_readable,
            "backup_copy_readable": backup_copy_readable,
            "checksum_match": checksum_match,
            "expected_hash_match": expected_hash_match,
            "bytes_match": bytes_match,
            "production_restore_started": False,
            "cleanup_started": False,
            "blocking_count": len(blocking_reasons),
        },
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_restore_readback_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_restore_readback_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def rebuild_restore_readback_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    report = build_restore_readback_report(policy=current)
    write_report_atomic(report, policy=current)
    completed_at = datetime.now(timezone.utc)
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_backup_export_restore_readback_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int(report.get("backup_copy_bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, report
