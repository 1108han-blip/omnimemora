"""Archive read-through shadow validation report (diagnostic only)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_non_active_quarantine, archive_pilot, archive_restore_contract, state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_READTHROUGH_REPORT_SCHEMA_VERSION = "dlp-archive-readthrough-report-v1"
ARCHIVE_READTHROUGH_REPORT_REBUILD_SCHEMA_VERSION = "dlp-archive-readthrough-report-rebuild-v1"
_MODE = "shadow_validation_only"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_readthrough_report_file).expanduser()


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


def _request_cross_check(
    *,
    readiness: Optional[dict[str, Any]],
    restore_key: Optional[str],
) -> dict[str, Any]:
    if not isinstance(readiness, dict) or not restore_key:
        return {
            "status": "not_applicable",
            "request_id": None,
            "reason": "readiness_or_restore_key_missing",
        }
    mappings = readiness.get("request_mappings")
    if not isinstance(mappings, list):
        return {
            "status": "not_applicable",
            "request_id": None,
            "reason": "readiness_request_mappings_missing",
        }
    matched_requests: list[str] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        request_id = str(mapping.get("request_id") or "").strip()
        if not request_id:
            continue
        chain = mapping.get("evidence_chain")
        if not isinstance(chain, list):
            continue
        for edge in chain:
            if not isinstance(edge, dict):
                continue
            if str(edge.get("restore_key") or "") == restore_key:
                matched_requests.append(request_id)
                break
    if not matched_requests:
        return {
            "status": "not_applicable",
            "request_id": None,
            "reason": "restore_key_not_mapped_to_request_id",
        }
    return {
        "status": "mapped",
        "request_id": matched_requests[0],
        "matched_request_count": len(matched_requests),
        "reason": None,
    }


def _quarantined_copy_for_restore_key(
    *,
    policy: DataLifecyclePolicy,
    restore_key: Optional[str],
) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
    record = archive_non_active_quarantine.read_record(policy=policy)
    if not isinstance(record, dict):
        return None, None
    if str(record.get("status") or "") not in {"success", "already_quarantined"}:
        return None, record
    if restore_key and str(record.get("restore_key") or "") != restore_key:
        return None, record
    for key in ("quarantine_copy_path", "quarantine_path"):
        value = str(record.get(key) or "").strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if path.exists() and path.is_file():
            return path, record
    return None, record


def build_readthrough_report(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    restore_key: Optional[str] = None,
    source_path: Optional[str] = None,
) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []

    pilot = archive_pilot.read_latest_pilot_record(policy=current_policy)
    readiness = archive_restore_contract.read_readiness_report(policy=current_policy)

    if not isinstance(pilot, dict):
        return {
            "schema_version": ARCHIVE_READTHROUGH_REPORT_SCHEMA_VERSION,
            "report_id": uuid4().hex[:16],
            "generated_at": now.isoformat(),
            "mode": _MODE,
            "status": "missing",
            "reason": "missing_pilot_record",
            "pilot_ref": {
                "status": "missing",
                "pilot_id": None,
                "path": str(Path(current_policy.archive_pilot_record_file).expanduser()),
            },
            "readiness_ref": {
                "status": "present" if isinstance(readiness, dict) else "missing",
                "readiness_id": readiness.get("readiness_id") if isinstance(readiness, dict) else None,
                "path": str(Path(current_policy.archive_restore_readiness_file).expanduser()),
            },
            "source_retained": False,
            "archive_copy_readable": False,
            "checksum_match": False,
            "read_path_unchanged": True,
            "request_id_cross_check": {
                "status": "not_applicable",
                "request_id": None,
                "reason": "missing_pilot_record",
            },
            "request_evidence_shadow": {
                "status": "not_applicable",
                "source_path": None,
                "request_id": None,
                "read_path_unchanged": True,
                "note": "pilot record missing; cannot evaluate request evidence shadow cross-check",
            },
            "warnings": [{"code": "missing_pilot_record"}],
        }

    target_restore_key = (restore_key or str(pilot.get("restore_key") or "")).strip() or None
    target_source_path = (source_path or str(pilot.get("source_path") or "")).strip()
    source = Path(target_source_path).expanduser()
    archive = Path(str(pilot.get("archive_path") or "")).expanduser()
    archive_resolution_source = "pilot_archive_path"
    quarantine_record = None
    if not (archive.exists() and archive.is_file()):
        quarantined_copy, quarantine_record = _quarantined_copy_for_restore_key(
            policy=current_policy,
            restore_key=target_restore_key,
        )
        if quarantined_copy is not None:
            archive = quarantined_copy
            archive_resolution_source = "non_active_quarantine"

    source_exists = source.exists() and source.is_file()
    archive_exists = archive.exists() and archive.is_file()
    source_sha = _sha256_file(source) if source_exists else None
    archive_sha = _sha256_file(archive) if archive_exists else None
    lineage_sha = None
    if isinstance(quarantine_record, dict):
        lineage_sha = (
            quarantine_record.get("quarantine_sha256")
            or quarantine_record.get("candidate_sha256")
            or quarantine_record.get("origin_source_sha256")
        )
    current_source_checksum_match = bool(source_sha and archive_sha and source_sha == archive_sha)
    lineage_checksum_match = bool(lineage_sha and archive_sha and str(lineage_sha) == archive_sha)
    checksum_match = (
        lineage_checksum_match
        if archive_resolution_source == "non_active_quarantine"
        else current_source_checksum_match
    )
    source_retained = source_exists
    archive_copy_readable = archive_exists and archive_sha is not None
    read_path_unchanged = bool(pilot.get("read_path_unchanged", True))

    status = "passed"
    reason = None
    if not archive_copy_readable:
        status = "failed"
        reason = "archive_copy_missing_or_unreadable"
        warnings.append({"code": "archive_copy_missing_or_unreadable"})
    elif not source_retained:
        status = "failed"
        reason = "source_missing"
        warnings.append({"code": "source_missing"})
    elif not checksum_match:
        status = "failed"
        reason = "checksum_mismatch"
        warnings.append({"code": "checksum_mismatch"})

    request_id_cross_check = _request_cross_check(readiness=readiness, restore_key=target_restore_key)
    request_evidence_shadow = {
        "status": str(request_id_cross_check.get("status") or "not_applicable"),
        "source_path": str(source),
        "request_id": request_id_cross_check.get("request_id"),
        "read_path_unchanged": read_path_unchanged,
        "note": "shadow validation only; request_evidence production path remains source path",
    }

    return {
        "schema_version": ARCHIVE_READTHROUGH_REPORT_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _MODE,
        "status": status,
        "reason": reason,
        "pilot_ref": {
            "status": "present",
            "pilot_id": pilot.get("pilot_id"),
            "path": str(Path(current_policy.archive_pilot_record_file).expanduser()),
        },
        "readiness_ref": {
            "status": "present" if isinstance(readiness, dict) else "missing",
            "readiness_id": readiness.get("readiness_id") if isinstance(readiness, dict) else None,
            "path": str(Path(current_policy.archive_restore_readiness_file).expanduser()),
        },
        "source_path": str(source),
        "source_bytes": int(source.stat().st_size) if source_exists else 0,
        "source_sha256": source_sha,
        "archive_path": str(archive),
        "archive_resolution_source": archive_resolution_source,
        "archive_bytes": int(archive.stat().st_size) if archive_exists else 0,
        "archive_sha256": archive_sha,
        "lineage_sha256": lineage_sha,
        "restore_key": target_restore_key,
        "source_retained": source_retained,
        "archive_copy_readable": archive_copy_readable,
        "checksum_match": checksum_match,
        "current_source_checksum_match": current_source_checksum_match,
        "lineage_checksum_match": lineage_checksum_match,
        "read_path_unchanged": read_path_unchanged,
        "request_id_cross_check": request_id_cross_check,
        "request_evidence_shadow": request_evidence_shadow,
        "summary": {
            "status": status,
            "request_id_cross_check_status": request_evidence_shadow.get("status"),
            "source_retained": source_retained,
            "archive_copy_readable": archive_copy_readable,
            "checksum_match": checksum_match,
            "current_source_checksum_match": current_source_checksum_match,
            "lineage_checksum_match": lineage_checksum_match,
            "read_path_unchanged": read_path_unchanged,
            "archive_resolution_source": archive_resolution_source,
            "validated_at": now.isoformat(),
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_readthrough_", suffix=".tmp", dir=str(path.parent))
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
    source_path: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        report = build_readthrough_report(
            policy=current_policy,
            restore_key=restore_key,
            source_path=source_path,
        )
        write_report_atomic(report, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_readthrough_report_rebuild",
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
            trigger="archive_readthrough_report_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
