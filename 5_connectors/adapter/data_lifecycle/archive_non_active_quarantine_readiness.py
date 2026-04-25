"""Non-active quarantine readiness plan (preview only, non-destructive)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_non_active_candidates, state_store
from .policy import DataLifecyclePolicy, load_policy

NON_ACTIVE_QUARANTINE_READINESS_SCHEMA_VERSION = "dlp-non-active-quarantine-readiness-v1"
NON_ACTIVE_QUARANTINE_READINESS_REBUILD_SCHEMA_VERSION = "dlp-non-active-quarantine-readiness-rebuild-v1"
READINESS_MODE = "non_active_quarantine_readiness_only"
PLANNED_ACTION = "quarantine_non_active_copy_preview_only"


def _plan_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_non_active_quarantine_readiness_file).expanduser()


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


def _planned_quarantine_path(*, policy: DataLifecyclePolicy, candidate_path: Path, sha256: Optional[str]) -> str:
    suffix = (sha256 or "unknown")[:12]
    root = Path(policy.archive_quarantine_root).expanduser() / "non_active"
    return str(root / f"{candidate_path.name}.{suffix}.quarantine")


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, str]:
    # Prefer small archive copies first to keep future pilot quarantine bounded.
    return (
        0 if candidate.get("candidate_kind") == "archive_pilot_copy" else 1,
        int(candidate.get("bytes", 0) or 0),
        str(candidate.get("candidate_id") or ""),
    )


def _select_candidate(report: dict[str, Any]) -> Optional[dict[str, Any]]:
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        return None
    plausible = [
        item
        for item in candidates
        if isinstance(item, dict)
        and item.get("selection_status") == "plausible_non_active"
        and item.get("candidate_kind") == "archive_pilot_copy"
        and item.get("active_guard_result") == "pass"
    ]
    if not plausible:
        return None
    return sorted(plausible, key=_candidate_sort_key)[0]


def build_readiness_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    report = archive_non_active_candidates.read_report(policy=current_policy)
    warnings: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []

    if not isinstance(report, dict):
        blocking_reasons.append("missing_non_active_candidate_report")
        selected = None
    elif report.get("schema_version") != archive_non_active_candidates.NON_ACTIVE_CANDIDATE_REPORT_SCHEMA_VERSION:
        blocking_reasons.append("non_active_candidate_report_schema_mismatch")
        selected = None
    else:
        selected = _select_candidate(report)
        if selected is None:
            blocking_reasons.append("no_selector_approved_archive_pilot_copy")

    candidate_path = Path(str((selected or {}).get("candidate_path") or "")).expanduser()
    candidate_exists = candidate_path.exists() and candidate_path.is_file() if str(candidate_path) else False
    candidate_sha = _sha256_file(candidate_path) if candidate_exists else None
    expected_sha = (selected or {}).get("sha256")
    if selected is not None:
        if not candidate_exists:
            blocking_reasons.append("selected_candidate_missing")
        if not candidate_sha:
            blocking_reasons.append("selected_candidate_checksum_missing")
        if expected_sha and candidate_sha and expected_sha != candidate_sha:
            blocking_reasons.append("selected_candidate_checksum_mismatch")
        if bool((selected.get("preconditions") or {}).get("production_read_path_unchanged")) is not True:
            blocking_reasons.append("production_read_path_not_confirmed_unchanged")

    unique_blockers: list[str] = []
    for reason in blocking_reasons:
        if reason not in unique_blockers:
            unique_blockers.append(reason)
    blocking_reasons = unique_blockers
    warnings.extend({"code": reason} for reason in blocking_reasons)

    status = "ready_for_operator_approval" if not blocking_reasons else "blocked"
    planned_target = (
        _planned_quarantine_path(policy=current_policy, candidate_path=candidate_path, sha256=candidate_sha)
        if selected is not None
        else None
    )
    selected_view = None
    if selected is not None:
        selected_view = {
            "candidate_id": selected.get("candidate_id"),
            "candidate_kind": selected.get("candidate_kind"),
            "candidate_path": str(candidate_path),
            "bytes": int(selected.get("bytes", 0) or 0),
            "sha256": candidate_sha or selected.get("sha256"),
            "origin_source_path": selected.get("origin_source_path"),
            "origin_source_kind": selected.get("origin_source_kind"),
            "origin_source_sha256": selected.get("origin_source_sha256"),
            "restore_key": selected.get("restore_key"),
            "pilot_id": selected.get("pilot_id"),
            "planned_quarantine_path": planned_target,
        }

    return {
        "schema_version": NON_ACTIVE_QUARANTINE_READINESS_SCHEMA_VERSION,
        "plan_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": READINESS_MODE,
        "status": status,
        "blocking_reasons": blocking_reasons,
        "selector_report_ref": {
            "status": "present" if isinstance(report, dict) else "missing",
            "report_id": report.get("report_id") if isinstance(report, dict) else None,
            "path": str(Path(current_policy.archive_non_active_candidate_report_file).expanduser()),
        },
        "selected_candidate": selected_view,
        "transaction_preview": {
            "planned_action": PLANNED_ACTION,
            "would_move_non_active_copy": False,
            "source_move_executed": False,
            "production_read_path_unchanged": True,
            "planned_quarantine_path": planned_target,
            "rollback_hint": "no rollback needed because readiness mode does not move the non-active copy",
        },
        "approval_requirements": {
            "operator_approval_required": True,
            "selector_approved_candidate_required": True,
            "checksum_lineage_required": True,
            "actual_quarantine_requires_separate_gate": True,
        },
        "source_move_executed": False,
        "non_active_copy_move_executed": False,
        "delete_compress_executed": False,
        "production_read_path_unchanged": True,
        "summary": {
            "status": status,
            "selected_candidate_present": selected is not None,
            "blocking_count": len(blocking_reasons),
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_plan_atomic(plan: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _plan_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_non_active_quarantine_", suffix=".tmp", dir=str(path.parent))
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
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        plan = build_readiness_plan(policy=current_policy)
        write_plan_atomic(plan, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        bytes_scanned = int(((plan.get("selected_candidate") or {}).get("bytes", 0)) or 0)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_non_active_quarantine_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=bytes_scanned,
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, plan
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_non_active_quarantine_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
