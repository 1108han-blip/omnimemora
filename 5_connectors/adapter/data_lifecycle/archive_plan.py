"""Archive candidate planning (dry-run only, non-destructive)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import retention, state_store, traceability
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_CANDIDATE_PLAN_SCHEMA_VERSION = "dlp-archive-candidate-plan-v1"
ARCHIVE_CANDIDATE_PLAN_REBUILD_SCHEMA_VERSION = "dlp-archive-candidate-plan-rebuild-v1"
_PLAN_MODE = "dry_run_only"
_ELIGIBLE = "eligible"
_BLOCKED = "blocked"
_REVIEW_REQUIRED = "review_required"
_VALID_ELIGIBILITY = {_ELIGIBLE, _BLOCKED, _REVIEW_REQUIRED}
_AUTO_REVIEW_KINDS = {"dlp_summary", "dlp_ledger"}
_EVIDENCE_KINDS = {"compile_events", "proxy_events", "trace_events", "meter_index", "meter_tenant"}
_CONTROL_ARTIFACTS = {
    "retention_manifest": "retention_manifest",
    "traceability_report": "traceability_report",
}


def _plan_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_plan_file).expanduser()


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


def _artifact_stat(path: Path) -> tuple[bool, int, Optional[str]]:
    if not path.exists() or not path.is_file():
        return False, 0, None
    return True, int(path.stat().st_size), _sha256_file(path)


def _resolve_traceability_passed(report: dict[str, Any]) -> tuple[bool, int, int]:
    summary = report.get("summary") if isinstance(report, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    fail_count = int(summary.get("fail_count", 0) or 0)
    unexplained_partial_count = int(
        summary.get("unexplained_partial_count", summary.get("partial_count", 0)) or 0
    )
    passed = fail_count == 0 and unexplained_partial_count == 0
    return passed, fail_count, unexplained_partial_count


def _candidate_base(
    *,
    artifact_name: str,
    kind: str,
    path: str,
    bytes_value: int,
    sha256: Optional[str],
) -> dict[str, Any]:
    return {
        "artifact_name": artifact_name,
        "kind": kind,
        "path": path,
        "bytes": int(max(0, bytes_value)),
        "sha256": sha256,
        "eligibility": _BLOCKED,
        "reason": "unclassified",
        "required_pre_checks": [],
        "post_archive_validation": [],
        "rollback_hint": "restore artifact from pre-archive snapshot and rebuild lifecycle reports",
    }


def _classify_candidate(
    *,
    candidate: dict[str, Any],
    exists: bool,
    manifest_mode: str,
    traceability_passed: bool,
    global_block_reason: Optional[str],
) -> dict[str, Any]:
    artifact_name = str(candidate.get("artifact_name") or "")
    kind = str(candidate.get("kind") or "")
    sha256 = candidate.get("sha256")

    if global_block_reason:
        candidate["eligibility"] = _BLOCKED
        candidate["reason"] = global_block_reason
        candidate["required_pre_checks"] = [
            "rebuild traceability report and reach fail=0 and unexplained_partial=0",
        ]
        candidate["post_archive_validation"] = ["none_until_traceability_gate_passes"]
        return candidate

    if not exists:
        candidate["eligibility"] = _BLOCKED
        candidate["reason"] = "artifact_missing"
        candidate["required_pre_checks"] = ["rebuild retention manifest and confirm artifact exists"]
        candidate["post_archive_validation"] = ["none_until_artifact_exists"]
        return candidate

    if kind in _AUTO_REVIEW_KINDS or artifact_name in _CONTROL_ARTIFACTS:
        candidate["eligibility"] = _REVIEW_REQUIRED
        candidate["reason"] = "control_artifact_requires_manual_gate"
        candidate["required_pre_checks"] = [
            "manual approval for control artifact archive scope",
            "confirm lifecycle control artifact recovery path",
        ]
        candidate["post_archive_validation"] = [
            "verify /data-lifecycle/status remains readable",
            "verify retention and traceability rebuild endpoints remain healthy",
        ]
        return candidate

    if kind in _EVIDENCE_KINDS:
        if not isinstance(sha256, str) or not sha256.strip():
            candidate["eligibility"] = _BLOCKED
            candidate["reason"] = "missing_checksum"
            candidate["required_pre_checks"] = ["rebuild retention manifest to refresh checksum"]
            candidate["post_archive_validation"] = ["none_until_checksum_present"]
            return candidate
        if manifest_mode != "inventory_only":
            candidate["eligibility"] = _BLOCKED
            candidate["reason"] = "manifest_mode_not_inventory_only"
            candidate["required_pre_checks"] = ["switch retention manifest mode to inventory_only"]
            candidate["post_archive_validation"] = ["none_until_manifest_mode_inventory_only"]
            return candidate
        if not traceability_passed:
            candidate["eligibility"] = _BLOCKED
            candidate["reason"] = "traceability_not_passed"
            candidate["required_pre_checks"] = [
                "rebuild traceability report and reach fail=0 and unexplained_partial=0",
            ]
            candidate["post_archive_validation"] = ["none_until_traceability_passed"]
            return candidate
        candidate["eligibility"] = _ELIGIBLE
        candidate["reason"] = "checksum_present_traceability_passed_inventory_only"
        candidate["required_pre_checks"] = [
            "snapshot current checksum and bytes",
            "confirm archive execution gate explicitly approved",
        ]
        candidate["post_archive_validation"] = [
            "verify archived copy checksum equals source checksum",
            "verify source can be restored by rollback hint",
        ]
        return candidate

    candidate["eligibility"] = _REVIEW_REQUIRED
    candidate["reason"] = "unknown_artifact_kind_requires_manual_review"
    candidate["required_pre_checks"] = ["manual classification for unknown artifact kind"]
    candidate["post_archive_validation"] = ["manual validation by operator"]
    return candidate


def build_archive_candidate_plan(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []

    manifest = retention.read_manifest(policy=current_policy)
    report = traceability.read_report(policy=current_policy)

    manifest_ref: dict[str, Any]
    if isinstance(manifest, dict):
        manifest_ref = {
            "status": "present",
            "manifest_id": manifest.get("manifest_id"),
            "generated_at": manifest.get("generated_at"),
            "mode": manifest.get("mode"),
            "path": str(Path(current_policy.retention_manifest_file).expanduser()),
        }
    else:
        manifest_ref = {
            "status": "missing",
            "manifest_id": None,
            "generated_at": None,
            "mode": None,
            "path": str(Path(current_policy.retention_manifest_file).expanduser()),
        }
        warnings.append({"code": "missing_manifest", "message": "retention manifest missing"})

    traceability_ref: dict[str, Any]
    traceability_passed = False
    fail_count = 0
    unexplained_partial_count = 0
    if isinstance(report, dict):
        traceability_passed, fail_count, unexplained_partial_count = _resolve_traceability_passed(report)
        traceability_ref = {
            "status": "present",
            "report_id": report.get("report_id"),
            "generated_at": report.get("generated_at"),
            "fail_count": fail_count,
            "unexplained_partial_count": unexplained_partial_count,
            "path": str(Path(current_policy.traceability_report_file).expanduser()),
        }
    else:
        traceability_ref = {
            "status": "missing",
            "report_id": None,
            "generated_at": None,
            "fail_count": None,
            "unexplained_partial_count": None,
            "path": str(Path(current_policy.traceability_report_file).expanduser()),
        }
        warnings.append({"code": "missing_traceability_report", "message": "traceability report missing"})

    global_block_reason: Optional[str] = None
    if not isinstance(report, dict):
        global_block_reason = "traceability_report_missing"
    elif fail_count > 0:
        global_block_reason = "traceability_fail_count_gt_zero"
        warnings.append({"code": "traceability_fail_count_gt_zero", "count": fail_count})
    elif unexplained_partial_count > 0:
        global_block_reason = "traceability_unexplained_partial_gt_zero"
        warnings.append(
            {"code": "traceability_unexplained_partial_gt_zero", "count": unexplained_partial_count}
        )

    manifest_artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else []
    if not isinstance(manifest_artifacts, list):
        manifest_artifacts = []
    manifest_mode = str((manifest or {}).get("mode") or "")

    candidates: list[dict[str, Any]] = []
    for artifact in manifest_artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_name = str(artifact.get("name") or "").strip()
        kind = str(artifact.get("kind") or "").strip()
        path_value = str(artifact.get("path") or "").strip()
        if not artifact_name or not kind or not path_value:
            continue
        exists = bool(artifact.get("exists"))
        candidate = _candidate_base(
            artifact_name=artifact_name,
            kind=kind,
            path=path_value,
            bytes_value=int(artifact.get("bytes", 0) or 0),
            sha256=artifact.get("sha256"),
        )
        candidate = _classify_candidate(
            candidate=candidate,
            exists=exists,
            manifest_mode=manifest_mode,
            traceability_passed=traceability_passed,
            global_block_reason=global_block_reason,
        )
        candidates.append(candidate)

    # Ensure control artifacts are always represented in the plan.
    for control_name, control_kind in _CONTROL_ARTIFACTS.items():
        control_path = (
            Path(current_policy.retention_manifest_file).expanduser()
            if control_name == "retention_manifest"
            else Path(current_policy.traceability_report_file).expanduser()
        )
        already_present = any(
            str(item.get("artifact_name") or "") == control_name for item in candidates
        )
        if already_present:
            continue
        exists, size_bytes, sha256 = _artifact_stat(control_path)
        candidate = _candidate_base(
            artifact_name=control_name,
            kind=control_kind,
            path=str(control_path),
            bytes_value=size_bytes,
            sha256=sha256,
        )
        candidate = _classify_candidate(
            candidate=candidate,
            exists=exists,
            manifest_mode=manifest_mode,
            traceability_passed=traceability_passed,
            global_block_reason=global_block_reason,
        )
        candidates.append(candidate)

    eligible_count = int(sum(1 for item in candidates if item.get("eligibility") == _ELIGIBLE))
    blocked_count = int(sum(1 for item in candidates if item.get("eligibility") == _BLOCKED))
    review_required_count = int(sum(1 for item in candidates if item.get("eligibility") == _REVIEW_REQUIRED))
    total_candidate_bytes = int(sum(int(item.get("bytes", 0) or 0) for item in candidates))

    plan = {
        "schema_version": ARCHIVE_CANDIDATE_PLAN_SCHEMA_VERSION,
        "plan_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _PLAN_MODE,
        "manifest_ref": manifest_ref,
        "traceability_ref": traceability_ref,
        "candidates": candidates,
        "summary": {
            "eligible_count": eligible_count,
            "blocked_count": blocked_count,
            "review_required_count": review_required_count,
            "total_candidate_bytes": total_candidate_bytes,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }
    # Keep eligibility values bounded to the fixed contract.
    for item in plan["candidates"]:
        if item.get("eligibility") not in _VALID_ELIGIBILITY:
            item["eligibility"] = _BLOCKED
            item["reason"] = "invalid_eligibility_fallback"
    return plan


def write_plan_atomic(plan: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _plan_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_candidate_", suffix=".tmp", dir=str(path.parent))
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
    if not path.exists():
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
        plan = build_archive_candidate_plan(policy=current_policy)
        write_plan_atomic(plan, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_candidate_plan_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((plan.get("summary") or {}).get("total_candidate_bytes", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, plan
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_candidate_plan_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
