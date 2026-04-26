"""Rollback/readback drill for legacy meter cleanup pilot readiness (staging-only restore)."""

from __future__ import annotations

import hashlib
import importlib
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

_copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")

METER_CLEANUP_ROLLBACK_DRILL_SCHEMA_VERSION = "res-legacy-meter-cleanup-rollback-drill-v1"
METER_CLEANUP_ROLLBACK_DRILL_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-rollback-drill-rebuild-v1"
METER_CLEANUP_ROLLBACK_DRILL_MODE = "rollback_readback_drill_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_rollback_drill_file).expanduser()


def _staging_root(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_rollback_staging_root).expanduser()


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


def _copy_to_staging(src: Path, staging_path: Path) -> None:
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(staging_path))


def build_rollback_drill_report(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    copy_pilot = _copy_pilot.read_latest_copy_pilot(policy=current)
    blocking_reasons: list[str] = []

    source_path: Optional[Path] = None
    backup_copy_path: Optional[Path] = None
    source_sha = None
    backup_copy_sha = None
    staging_restore_path: Optional[Path] = None
    staging_restore_sha = None

    if not isinstance(copy_pilot, dict):
        blocking_reasons.append("backup_copy_pilot_missing")
    else:
        selected = copy_pilot.get("selected_candidate") or {}
        raw_source = str(selected.get("path") or "")
        raw_copy = str(copy_pilot.get("target_path") or "")
        if raw_source:
            source_path = Path(raw_source).expanduser()
        if raw_copy:
            backup_copy_path = Path(raw_copy).expanduser()
        if str(copy_pilot.get("status") or "") not in {"success", "already_copied"}:
            blocking_reasons.append("backup_copy_pilot_not_success")
        if not bool(copy_pilot.get("source_retained", False)):
            blocking_reasons.append("source_not_retained")
        if not bool(copy_pilot.get("checksum_match", False)):
            blocking_reasons.append("backup_copy_checksum_mismatch")
        if bool(copy_pilot.get("cleanup_started", False)):
            blocking_reasons.append("cleanup_started")

    source_retained = bool(source_path and source_path.exists() and source_path.is_file())
    backup_copy_readable = bool(backup_copy_path and backup_copy_path.exists() and backup_copy_path.is_file())
    if isinstance(copy_pilot, dict) and not source_retained:
        blocking_reasons.append("source_not_readable")
    if isinstance(copy_pilot, dict) and not backup_copy_readable:
        blocking_reasons.append("backup_copy_not_readable")

    if backup_copy_readable and source_retained and source_path and backup_copy_path:
        source_sha = _sha256_file(source_path)
        backup_copy_sha = _sha256_file(backup_copy_path)
        staging_name = f"{backup_copy_path.name}.{uuid4().hex[:12]}.staging_restore"
        staging_restore_path = _staging_root(current) / staging_name
        _copy_to_staging(backup_copy_path, staging_restore_path)
        staging_restore_sha = _sha256_file(staging_restore_path)
    else:
        if source_retained and source_path:
            source_sha = _sha256_file(source_path)
        if backup_copy_readable and backup_copy_path:
            backup_copy_sha = _sha256_file(backup_copy_path)

    checksum_match = bool(source_sha and staging_restore_sha and source_sha == staging_restore_sha)
    staging_restore_readable = bool(staging_restore_path and staging_restore_path.exists() and staging_restore_path.is_file())
    if backup_copy_readable and source_retained and not staging_restore_readable:
        blocking_reasons.append("staging_restore_not_readable")
    if backup_copy_readable and source_retained and not checksum_match:
        blocking_reasons.append("checksum_mismatch")

    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    status = "passed" if not blocking_reasons else "blocked"

    return {
        "schema_version": METER_CLEANUP_ROLLBACK_DRILL_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_ROLLBACK_DRILL_MODE,
        "status": status,
        "source_path": str(source_path) if source_path else None,
        "backup_copy_path": str(backup_copy_path) if backup_copy_path else None,
        "staging_restore_path": str(staging_restore_path) if staging_restore_path else None,
        "source_retained": source_retained,
        "staging_restore_readable": staging_restore_readable,
        "checksum_match": checksum_match,
        "source_sha256": source_sha,
        "backup_copy_sha256": backup_copy_sha,
        "staging_restore_sha256": staging_restore_sha,
        "production_restore_started": False,
        "cleanup_started": False,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "source_retained": source_retained,
            "staging_restore_readable": staging_restore_readable,
            "checksum_match": checksum_match,
            "production_restore_started": False,
            "cleanup_started": False,
            "blocking_count": int(len(blocking_reasons)),
        },
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_rollback_drill_", suffix=".tmp", dir=str(path.parent))
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


def read_rollback_drill_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def rebuild_rollback_drill_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    report = build_rollback_drill_report(policy=current)
    write_report_atomic(report, policy=current)
    completed_at = datetime.now(timezone.utc)
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_cleanup_rollback_drill_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int(bool(report.get("staging_restore_readable"))),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, report

