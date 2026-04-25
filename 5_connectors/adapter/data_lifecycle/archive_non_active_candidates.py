"""Non-active archive candidate selector (report only, non-destructive)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_pilot, archive_plan, archive_transaction, retention, state_store
from .policy import DataLifecyclePolicy, load_policy

NON_ACTIVE_CANDIDATE_REPORT_SCHEMA_VERSION = "dlp-non-active-candidate-report-v1"
NON_ACTIVE_CANDIDATE_REBUILD_SCHEMA_VERSION = "dlp-non-active-candidate-report-rebuild-v1"
REPORT_MODE = "non_active_selection_report_only"
PLANNED_ACTION = "quarantine_non_active_preview_only"

_FORBIDDEN_BASENAMES = {
    "compile_events.jsonl",
    "proxy_events.jsonl",
    "trace_events.jsonl",
    "meters_index.json",
    "family_window_summary.json",
    "maintenance_state.jsonl",
    "retention_manifest.json",
    "traceability_report.json",
    "archive_candidate_plan.json",
    "archive_transaction_preview.json",
    "archive_restore_readiness_report.json",
    "archive_execution_gate.json",
    "archive_operator_approval.json",
    "archive_pilot_record.json",
    "archive_readthrough_report.json",
    "archive_fallback_simulation_report.json",
    "archive_quarantine_readiness_plan.json",
    "archive_quarantine_record.json",
    "archive_restore_pilot_record.json",
}
_FORBIDDEN_KINDS = {
    "compile_events",
    "proxy_events",
    "trace_events",
    "meter_index",
    "meter_tenant",
    "dlp_summary",
    "dlp_ledger",
    "retention_manifest",
    "traceability_report",
}


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_non_active_candidate_report_file).expanduser()


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


def _line_count_file(path: Path) -> Optional[int]:
    if not path.exists() or not path.is_file():
        return None
    count = 0
    with path.open("rb") as fh:
        for _line in fh:
            count += 1
    return count


def _mtime_iso(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _active_guard_reasons(*, path: Path, kind: str) -> list[str]:
    reasons: list[str] = []
    if path.name in _FORBIDDEN_BASENAMES:
        reasons.append("active_or_control_basename")
    if path.name.startswith("meters_") and path.name.endswith(".json"):
        reasons.append("meter_hot_file_pattern")
    if kind in _FORBIDDEN_KINDS:
        reasons.append("active_or_control_kind")
    return reasons


def _candidate_payload(
    *,
    candidate_id: str,
    candidate_kind: str,
    candidate_path: Path,
    origin_source_path: Optional[str] = None,
    origin_source_kind: Optional[str] = None,
    origin_source_sha256: Optional[str] = None,
    archive_copy_path: Optional[str] = None,
    restore_key: Optional[str] = None,
    pilot_id: Optional[str] = None,
    source_record: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    exists = candidate_path.exists() and candidate_path.is_file()
    actual_sha = _sha256_file(candidate_path) if exists else None
    expected_sha = None
    if isinstance(source_record, dict):
        expected_sha = source_record.get("sha256") or source_record.get("source_sha256") or source_record.get("archive_sha256")
    if not expected_sha and origin_source_sha256 and candidate_kind == "archive_pilot_copy":
        expected_sha = origin_source_sha256
    active_reasons = _active_guard_reasons(path=candidate_path, kind=candidate_kind)

    checksum_present = bool(actual_sha)
    checksum_matches_lineage = bool(expected_sha and actual_sha and expected_sha == actual_sha)
    selection_status = "plausible_non_active"
    non_active_reason = "copy_artifact_not_in_production_read_path"
    forbidden_reason = None
    required_operator_approval = True

    source_eligibility = str((source_record or {}).get("eligibility") or "")
    if active_reasons:
        selection_status = "forbidden"
        non_active_reason = None
        forbidden_reason = ",".join(active_reasons)
        required_operator_approval = False
    elif source_eligibility == "review_required":
        selection_status = "review_required"
        non_active_reason = "source_candidate_requires_manual_review"
        required_operator_approval = True
    elif not exists:
        selection_status = "forbidden"
        non_active_reason = None
        forbidden_reason = "candidate_missing"
        required_operator_approval = False
    elif not checksum_present:
        selection_status = "forbidden"
        non_active_reason = None
        forbidden_reason = "checksum_missing"
        required_operator_approval = False
    elif expected_sha and not checksum_matches_lineage:
        selection_status = "review_required"
        non_active_reason = "checksum_lineage_mismatch_requires_review"
        required_operator_approval = True
    elif source_eligibility == "blocked":
        selection_status = "forbidden"
        non_active_reason = None
        forbidden_reason = "source_candidate_blocked"
        required_operator_approval = False

    bytes_value = int(candidate_path.stat().st_size) if exists else int((source_record or {}).get("bytes", 0) or 0)
    return {
        "candidate_id": candidate_id,
        "candidate_kind": candidate_kind,
        "candidate_path": str(candidate_path),
        "basename": candidate_path.name,
        "bytes": bytes_value,
        "sha256": actual_sha or (source_record or {}).get("sha256"),
        "mtime": _mtime_iso(candidate_path),
        "line_count": _line_count_file(candidate_path),
        "active_guard_result": "blocked" if active_reasons else "pass",
        "active_guard_reasons": active_reasons,
        "selection_status": selection_status,
        "non_active_reason": non_active_reason,
        "forbidden_reason": forbidden_reason,
        "required_operator_approval": required_operator_approval,
        "planned_action": PLANNED_ACTION,
        "would_move_source": False,
        "origin_source_path": origin_source_path,
        "origin_source_kind": origin_source_kind,
        "origin_source_sha256": origin_source_sha256,
        "archive_copy_path": archive_copy_path,
        "restore_key": restore_key,
        "pilot_id": pilot_id,
        "preconditions": {
            "candidate_exists": exists,
            "checksum_present": checksum_present,
            "checksum_matches_lineage": checksum_matches_lineage if expected_sha else None,
            "production_read_path_unchanged": True,
            "source_retained": True,
        },
    }


def build_report(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    manifest = retention.read_manifest(policy=current_policy)
    plan = archive_plan.read_plan(policy=current_policy)
    preview = archive_transaction.read_preview(policy=current_policy)
    pilot = archive_pilot.read_latest_pilot_record(policy=current_policy)

    candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not isinstance(manifest, dict):
        warnings.append({"code": "missing_retention_manifest"})

    if isinstance(plan, dict):
        for item in plan.get("candidates") or []:
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("path") or "")).expanduser()
            candidates.append(
                _candidate_payload(
                    candidate_id=str(item.get("artifact_name") or path.name or uuid4().hex[:12]),
                    candidate_kind=str(item.get("kind") or "unknown"),
                    candidate_path=path,
                    origin_source_path=str(item.get("path") or ""),
                    origin_source_kind=str(item.get("kind") or ""),
                    origin_source_sha256=item.get("sha256"),
                    source_record=item,
                )
            )
    else:
        warnings.append({"code": "missing_archive_candidate_plan"})

    if isinstance(pilot, dict):
        archive_path = Path(str(pilot.get("archive_path") or "")).expanduser()
        if str(archive_path):
            candidates.append(
                _candidate_payload(
                    candidate_id=f"archive_pilot_copy:{pilot.get('pilot_id') or archive_path.name}",
                    candidate_kind="archive_pilot_copy",
                    candidate_path=archive_path,
                    origin_source_path=pilot.get("source_path"),
                    origin_source_kind=pilot.get("source_kind"),
                    origin_source_sha256=pilot.get("source_sha256") or pilot.get("archive_sha256"),
                    archive_copy_path=str(archive_path),
                    restore_key=pilot.get("restore_key"),
                    pilot_id=pilot.get("pilot_id"),
                    source_record={
                        "sha256": pilot.get("archive_sha256") or pilot.get("source_sha256"),
                        "bytes": pilot.get("archive_bytes") or pilot.get("source_bytes"),
                    },
                )
            )
    else:
        warnings.append({"code": "missing_archive_pilot_record"})

    forbidden_count = sum(1 for item in candidates if item.get("selection_status") == "forbidden")
    plausible_count = sum(1 for item in candidates if item.get("selection_status") == "plausible_non_active")
    review_count = sum(1 for item in candidates if item.get("selection_status") == "review_required")

    return {
        "schema_version": NON_ACTIVE_CANDIDATE_REPORT_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": REPORT_MODE,
        "selection_source_refs": {
            "retention_manifest": {
                "status": "present" if isinstance(manifest, dict) else "missing",
                "manifest_id": manifest.get("manifest_id") if isinstance(manifest, dict) else None,
                "path": str(Path(current_policy.retention_manifest_file).expanduser()),
            },
            "archive_candidate_plan": {
                "status": "present" if isinstance(plan, dict) else "missing",
                "plan_id": plan.get("plan_id") if isinstance(plan, dict) else None,
                "path": str(Path(current_policy.archive_plan_file).expanduser()),
            },
            "archive_transaction_preview": {
                "status": "present" if isinstance(preview, dict) else "missing",
                "preview_id": preview.get("preview_id") if isinstance(preview, dict) else None,
                "path": str(Path(current_policy.archive_transaction_preview_file).expanduser()),
            },
            "archive_pilot": {
                "status": "present" if isinstance(pilot, dict) else "missing",
                "pilot_id": pilot.get("pilot_id") if isinstance(pilot, dict) else None,
                "path": str(Path(current_policy.archive_pilot_record_file).expanduser()),
            },
        },
        "candidates": candidates,
        "summary": {
            "total_scanned": len(candidates),
            "forbidden_count": forbidden_count,
            "plausible_non_active_count": plausible_count,
            "review_required_count": review_count,
            "source_move_delete_compress_executed": False,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_non_active_candidates_", suffix=".tmp", dir=str(path.parent))
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
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        report = build_report(policy=current_policy)
        write_report_atomic(report, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_non_active_candidate_report_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int(sum(int(item.get("bytes", 0) or 0) for item in report.get("candidates", []))),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, report
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_non_active_candidate_report_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
