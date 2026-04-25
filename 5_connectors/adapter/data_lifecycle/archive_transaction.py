"""Archive transaction preview (safety preview only, non-destructive)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_plan, state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_TRANSACTION_PREVIEW_SCHEMA_VERSION = "dlp-archive-transaction-preview-v1"
ARCHIVE_TRANSACTION_PREVIEW_REBUILD_SCHEMA_VERSION = "dlp-archive-transaction-preview-rebuild-v1"
_PREVIEW_MODE = "preview_only"
_ARCHIVE_BASE_DIR = Path.home() / ".omnimemora" / "adapter" / "data_lifecycle" / "archive"


def _preview_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_transaction_preview_file).expanduser()


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


def _planned_archive_path(source_path: Path, source_sha256: Optional[str]) -> str:
    suffix = (source_sha256 or "nohash")[:12]
    return str(_ARCHIVE_BASE_DIR / f"{source_path.name}.{suffix}.archive")


def _restore_key(*, source_path: Path, source_sha256: Optional[str], kind: str) -> str:
    material = f"{kind}|{source_path}|{source_sha256 or ''}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:20]
    return f"restore:{kind}:{digest}"


def _precondition_checks(
    *,
    candidate: dict[str, Any],
    source_path: Path,
    source_sha256: Optional[str],
    source_bytes: int,
) -> list[dict[str, Any]]:
    expected_sha256 = candidate.get("sha256")
    expected_bytes = int(candidate.get("bytes", 0) or 0)
    kind = str(candidate.get("kind") or "")
    is_trace_events = kind == "trace_events"
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "check": "source_exists",
            "status": "pass" if source_path.exists() and source_path.is_file() else "fail",
            "expected": True,
        }
    )
    checks.append(
        {
            "check": "source_sha256_match",
            "status": "pass"
            if (
                (expected_sha256 == source_sha256 and source_sha256 is not None)
                or (is_trace_events and source_sha256 is not None)
            )
            else "fail",
            "expected": expected_sha256,
            "actual": source_sha256,
            "note": "trace_events volatile writes allowed during validation"
            if is_trace_events
            else None,
        }
    )
    checks.append(
        {
            "check": "source_bytes_match",
            "status": "pass" if (expected_bytes == source_bytes or is_trace_events) else "fail",
            "expected": expected_bytes,
            "actual": source_bytes,
            "note": "trace_events volatile writes allowed during validation"
            if is_trace_events
            else None,
        }
    )
    checks.append(
        {
            "check": "candidate_eligibility",
            "status": "pass" if str(candidate.get("eligibility")) == "eligible" else "fail",
            "expected": "eligible",
            "actual": candidate.get("eligibility"),
        }
    )
    return checks


def _is_checks_passed(checks: list[dict[str, Any]]) -> bool:
    return all(str(item.get("status") or "") == "pass" for item in checks)


def build_transaction_preview(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []

    plan = archive_plan.read_plan(policy=current_policy)
    if not isinstance(plan, dict):
        return {
            "schema_version": ARCHIVE_TRANSACTION_PREVIEW_SCHEMA_VERSION,
            "preview_id": uuid4().hex[:16],
            "generated_at": now.isoformat(),
            "mode": _PREVIEW_MODE,
            "plan_ref": {
                "status": "missing",
                "plan_id": None,
                "generated_at": None,
                "path": str(Path(current_policy.archive_plan_file).expanduser()),
            },
            "items": [],
            "summary": {
                "status": "missing_candidate_plan",
                "eligible_input_count": 0,
                "preview_item_count": 0,
                "excluded_blocked_count": 0,
                "excluded_review_required_count": 0,
                "excluded_other_count": 0,
                "blocked_precondition_count": 0,
                "total_preview_bytes": 0,
                "warnings_count": 1,
            },
            "warnings": [{"code": "missing_archive_candidate_plan", "message": "archive candidate plan not found"}],
        }

    plan_candidates = plan.get("candidates")
    if not isinstance(plan_candidates, list):
        plan_candidates = []

    excluded_blocked_count = 0
    excluded_review_required_count = 0
    excluded_other_count = 0
    blocked_precondition_count = 0
    eligible_candidates: list[dict[str, Any]] = []
    for candidate in plan_candidates:
        if not isinstance(candidate, dict):
            continue
        eligibility = str(candidate.get("eligibility") or "")
        if eligibility == "eligible":
            eligible_candidates.append(candidate)
            continue
        if eligibility == "blocked":
            excluded_blocked_count += 1
        elif eligibility == "review_required":
            excluded_review_required_count += 1
        else:
            excluded_other_count += 1

    items: list[dict[str, Any]] = []
    for candidate in eligible_candidates:
        source_path = Path(str(candidate.get("path") or "")).expanduser()
        source_exists = source_path.exists() and source_path.is_file()
        source_bytes = int(source_path.stat().st_size) if source_exists else 0
        source_sha256 = _sha256_file(source_path) if source_exists else None
        checks = _precondition_checks(
            candidate=candidate,
            source_path=source_path,
            source_sha256=source_sha256,
            source_bytes=source_bytes,
        )
        if not _is_checks_passed(checks):
            blocked_precondition_count += 1
            warnings.append(
                {
                    "code": "preview_item_precondition_failed",
                    "artifact_name": candidate.get("artifact_name"),
                    "path": str(source_path),
                }
            )
            continue
        kind = str(candidate.get("kind") or "")
        item = {
            "artifact_name": candidate.get("artifact_name"),
            "kind": kind,
            "source_path": str(source_path),
            "source_sha256": source_sha256,
            "source_bytes": source_bytes,
            "planned_archive_path": _planned_archive_path(source_path, source_sha256),
            "restore_key": _restore_key(source_path=source_path, source_sha256=source_sha256, kind=kind),
            "precondition_checks": checks,
            "rollback_hint": candidate.get("rollback_hint")
            or "restore source from snapshot and regenerate lifecycle artifacts",
        }
        items.append(item)

    return {
        "schema_version": ARCHIVE_TRANSACTION_PREVIEW_SCHEMA_VERSION,
        "preview_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _PREVIEW_MODE,
        "plan_ref": {
            "status": "present",
            "plan_id": plan.get("plan_id"),
            "generated_at": plan.get("generated_at"),
            "path": str(Path(current_policy.archive_plan_file).expanduser()),
        },
        "items": items,
        "summary": {
            "status": "present",
            "eligible_input_count": len(eligible_candidates),
            "preview_item_count": len(items),
            "excluded_blocked_count": excluded_blocked_count,
            "excluded_review_required_count": excluded_review_required_count,
            "excluded_other_count": excluded_other_count,
            "blocked_precondition_count": blocked_precondition_count,
            "total_preview_bytes": int(sum(int(item.get("source_bytes", 0) or 0) for item in items)),
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_preview_atomic(preview: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _preview_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_preview_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(preview, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_preview(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _preview_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_preview(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        preview = build_transaction_preview(policy=current_policy)
        write_preview_atomic(preview, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_transaction_preview_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((preview.get("summary") or {}).get("total_preview_bytes", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, preview
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_transaction_preview_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
