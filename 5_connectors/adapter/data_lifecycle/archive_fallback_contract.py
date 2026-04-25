"""Archive fallback simulation contract (diagnostic only)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_pilot, archive_readthrough, archive_restore_contract, state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_FALLBACK_SIMULATION_SCHEMA_VERSION = "dlp-archive-fallback-simulation-v1"
ARCHIVE_FALLBACK_SIMULATION_REBUILD_SCHEMA_VERSION = "dlp-archive-fallback-simulation-rebuild-v1"
_MODE = "diagnostic_fallback_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_fallback_simulation_file).expanduser()


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


def build_fallback_simulation_report(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    restore_key: Optional[str] = None,
) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []

    pilot = archive_pilot.read_latest_pilot_record(policy=current_policy)
    readthrough = archive_readthrough.read_report(policy=current_policy)
    readiness = archive_restore_contract.read_readiness_report(policy=current_policy)

    if not isinstance(pilot, dict):
        return {
            "schema_version": ARCHIVE_FALLBACK_SIMULATION_SCHEMA_VERSION,
            "simulation_id": uuid4().hex[:16],
            "generated_at": now.isoformat(),
            "mode": _MODE,
            "status": "missing",
            "reason": "missing_pilot_record",
            "source_missing_simulated": True,
            "fallback_available": False,
            "archive_copy_readable": False,
            "checksum_match": False,
            "production_read_path_unchanged": True,
            "request_evidence_fallback": {
                "status": "not_applicable",
                "request_id": None,
                "note": "diagnostic only; production request_evidence path unchanged",
            },
            "summary": {
                "status": "missing",
                "fallback_available": False,
                "warnings_count": 1,
            },
            "warnings": [{"code": "missing_pilot_record"}],
        }

    target_restore_key = (restore_key or str(pilot.get("restore_key") or "")).strip() or None
    source_path = Path(str(pilot.get("source_path") or "")).expanduser()
    archive_path = Path(str(pilot.get("archive_path") or "")).expanduser()
    archive_sha = _sha256_file(archive_path)
    expected_sha = str(pilot.get("source_sha256") or pilot.get("archive_sha256") or "").strip() or None
    checksum_match = bool(archive_sha and expected_sha and archive_sha == expected_sha)
    archive_copy_readable = bool(archive_sha and archive_path.exists() and archive_path.is_file())
    source_present_for_control = source_path.exists() and source_path.is_file()

    request_id = None
    request_status = "not_applicable"
    if isinstance(readthrough, dict):
        cross = readthrough.get("request_id_cross_check") or {}
        request_id = cross.get("request_id")
        request_status = str(cross.get("status") or "not_applicable")
    if request_status != "mapped" and isinstance(readiness, dict) and target_restore_key:
        for mapping in readiness.get("request_mappings") or []:
            if not isinstance(mapping, dict):
                continue
            for edge in mapping.get("evidence_chain") or []:
                if isinstance(edge, dict) and str(edge.get("restore_key") or "") == target_restore_key:
                    request_id = mapping.get("request_id")
                    request_status = "mapped"
                    break
            if request_status == "mapped":
                break

    status = "passed"
    reason = None
    if not archive_copy_readable:
        status = "failed"
        reason = "archive_copy_missing_or_unreadable"
        warnings.append({"code": "archive_copy_missing_or_unreadable"})
    elif not checksum_match:
        status = "failed"
        reason = "checksum_mismatch"
        warnings.append({"code": "checksum_mismatch"})

    fallback_available = status == "passed"
    request_evidence_fallback = {
        "status": request_status,
        "request_id": request_id,
        "restore_key": target_restore_key,
        "source_path": str(source_path),
        "archive_path": str(archive_path),
        "source_missing_simulated": True,
        "production_read_path_unchanged": True,
        "note": "diagnostic fallback simulation only; no production read-path switch",
    }

    return {
        "schema_version": ARCHIVE_FALLBACK_SIMULATION_SCHEMA_VERSION,
        "simulation_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _MODE,
        "status": status,
        "reason": reason,
        "pilot_ref": {
            "status": "present",
            "pilot_id": pilot.get("pilot_id"),
            "path": str(Path(current_policy.archive_pilot_record_file).expanduser()),
        },
        "readthrough_ref": {
            "status": "present" if isinstance(readthrough, dict) else "missing",
            "report_id": readthrough.get("report_id") if isinstance(readthrough, dict) else None,
            "path": str(Path(current_policy.archive_readthrough_report_file).expanduser()),
        },
        "readiness_ref": {
            "status": "present" if isinstance(readiness, dict) else "missing",
            "readiness_id": readiness.get("readiness_id") if isinstance(readiness, dict) else None,
            "path": str(Path(current_policy.archive_restore_readiness_file).expanduser()),
        },
        "source_path": str(source_path),
        "archive_path": str(archive_path),
        "archive_sha256": archive_sha,
        "expected_sha256": expected_sha,
        "restore_key": target_restore_key,
        "source_present_for_control": source_present_for_control,
        "source_missing_simulated": True,
        "fallback_available": fallback_available,
        "archive_copy_readable": archive_copy_readable,
        "checksum_match": checksum_match,
        "production_read_path_unchanged": True,
        "request_evidence_fallback": request_evidence_fallback,
        "summary": {
            "status": status,
            "fallback_available": fallback_available,
            "archive_copy_readable": archive_copy_readable,
            "checksum_match": checksum_match,
            "request_evidence_fallback_status": request_status,
            "production_read_path_unchanged": True,
            "validated_at": now.isoformat(),
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_fallback_", suffix=".tmp", dir=str(path.parent))
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


def read_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def rebuild_report(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    restore_key: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        report = build_fallback_simulation_report(policy=current_policy, restore_key=restore_key)
        write_report_atomic(report, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_fallback_simulation_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int(report.get("archive_bytes", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, report
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_fallback_simulation_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
