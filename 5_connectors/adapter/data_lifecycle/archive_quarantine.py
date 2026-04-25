"""Single-artifact source quarantine executor."""

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

from . import (
    archive_approval,
    archive_execution_gate,
    archive_fallback_contract,
    archive_pilot,
    archive_quarantine_readiness,
    archive_readthrough,
    state_store,
)
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_SOURCE_QUARANTINE_RECORD_SCHEMA_VERSION = "dlp-source-quarantine-record-v1"
ARCHIVE_SOURCE_QUARANTINE_MODE = "single_artifact_quarantine_only"

_BLOCKED = "blocked"
_SUCCESS = "success"
_ALREADY_QUARANTINED = "already_quarantined"
_FAILED = "failed"
_TRIGGER = "archive_source_quarantine_execute_one"

_ALLOWED_PILOT_STATUSES = {"success", "already_copied"}
_ACTIVE_BASENAMES = {
    "compile_events.jsonl",
    "proxy_events.jsonl",
    "trace_events.jsonl",
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
    "meters_index.json",
}
_ACTIVE_KINDS = {
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


def _record_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    env_override = os.getenv("OMNIMEMORA_DLP_ARCHIVE_QUARANTINE_RECORD_FILE", "").strip()
    if env_override:
        return Path(env_override).expanduser()
    return Path(current.archive_quarantine_record_file).expanduser()


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


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _resolve_quarantine_target(
    *,
    policy: DataLifecyclePolicy,
    readiness: Optional[dict[str, Any]],
    source_path: Path,
    source_sha256: Optional[str],
) -> Path:
    candidate = readiness.get("candidate") if isinstance(readiness, dict) else {}
    planned = str((candidate or {}).get("planned_quarantine_path") or "").strip()
    if planned:
        return Path(planned).expanduser()
    suffix = (source_sha256 or "unknown")[:12]
    root = Path(policy.archive_quarantine_root).expanduser()
    return root / f"{source_path.name}.{suffix}.quarantine"


def _is_active_hot_source(*, source_path: Path, source_kind: str) -> bool:
    basename = source_path.name
    if basename in _ACTIVE_BASENAMES:
        return True
    if basename.startswith("meters_") and basename.endswith(".json"):
        return True
    if source_kind in _ACTIVE_KINDS:
        return True
    return False


def _record_payload(
    *,
    status: str,
    blocking_reasons: list[str],
    message: str,
    source_path: Path,
    quarantine_path: Path,
    source_kind: str,
    source_sha256: Optional[str],
    quarantine_sha256: Optional[str],
    source_move_executed: bool,
    source_retained: bool,
    source_bytes: int,
    quarantine_bytes: int,
) -> dict[str, Any]:
    return {
        "schema_version": ARCHIVE_SOURCE_QUARANTINE_RECORD_SCHEMA_VERSION,
        "record_id": uuid4().hex[:16],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": ARCHIVE_SOURCE_QUARANTINE_MODE,
        "status": status,
        "message": message,
        "blocking_reasons": list(blocking_reasons),
        "source_path": str(source_path),
        "source_kind": source_kind,
        "source_bytes": int(max(0, source_bytes)),
        "source_sha256": source_sha256,
        "quarantine_path": str(quarantine_path),
        "quarantine_bytes": int(max(0, quarantine_bytes)),
        "quarantine_sha256": quarantine_sha256,
        "checksum_match": bool(source_sha256 and quarantine_sha256 and source_sha256 == quarantine_sha256),
        "source_move_executed": bool(source_move_executed),
        "source_retained": bool(source_retained),
        "read_path_unchanged": True,
        "production_read_path_unchanged": True,
        "summary": {
            "status": status,
            "blocking_count": len(blocking_reasons),
            "source_move_executed": bool(source_move_executed),
            "source_retained": bool(source_retained),
            "checksum_match": bool(source_sha256 and quarantine_sha256 and source_sha256 == quarantine_sha256),
        },
        "warnings": [{"code": reason} for reason in blocking_reasons],
    }


def write_record_atomic(record: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _record_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_quarantine_execute_", suffix=".tmp", dir=str(path.parent))
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


def read_record(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _record_path(policy)
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def execute_single_artifact_quarantine(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()

    readiness = archive_quarantine_readiness.read_plan(policy=current_policy)
    gate = archive_execution_gate.read_gate(policy=current_policy)
    approval = archive_approval.read_approval(policy=current_policy)
    fallback = archive_fallback_contract.read_report(policy=current_policy)
    readthrough = archive_readthrough.read_report(policy=current_policy)
    pilot = archive_pilot.read_latest_pilot_record(policy=current_policy)

    source_path = Path(str((pilot or {}).get("source_path") or "")).expanduser()
    source_kind = str((pilot or {}).get("source_kind") or "")
    source_sha256 = str((pilot or {}).get("source_sha256") or "").strip() or None
    quarantine_path = _resolve_quarantine_target(
        policy=current_policy,
        readiness=readiness,
        source_path=source_path if str(source_path) else Path("source-missing"),
        source_sha256=source_sha256,
    )

    def append_ledger(status: str, bytes_scanned: int, error: Optional[str]) -> dict[str, Any]:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger=_TRIGGER,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            bytes_scanned=int(max(0, bytes_scanned)),
            error=error,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record

    # Idempotent/safe path: source already moved and quarantined artifact matches expected checksum.
    if (
        source_sha256
        and str(source_path)
        and (not source_path.exists())
        and quarantine_path.exists()
        and quarantine_path.is_file()
        and _sha256_file(quarantine_path) == source_sha256
    ):
        quarantine_sha = _sha256_file(quarantine_path)
        payload = _record_payload(
            status=_ALREADY_QUARANTINED,
            blocking_reasons=[],
            message="source already quarantined; no move executed",
            source_path=source_path,
            quarantine_path=quarantine_path,
            source_kind=source_kind,
            source_sha256=source_sha256,
            quarantine_sha256=quarantine_sha,
            source_move_executed=False,
            source_retained=False,
            source_bytes=0,
            quarantine_bytes=int(quarantine_path.stat().st_size),
        )
        write_record_atomic(payload, policy=current_policy)
        ledger = append_ledger(_SUCCESS, int(quarantine_path.stat().st_size), None)
        return ledger, payload

    blocking_reasons: list[str] = []

    if not isinstance(readiness, dict):
        blocking_reasons.append("missing_quarantine_readiness_plan")
    else:
        if str(readiness.get("schema_version") or "") != archive_quarantine_readiness.ARCHIVE_QUARANTINE_READINESS_SCHEMA_VERSION:
            blocking_reasons.append("quarantine_readiness_schema_mismatch")
        if str(readiness.get("mode") or "") != "readiness_plan_only":
            blocking_reasons.append("quarantine_readiness_mode_mismatch")
        if str(readiness.get("status") or "") != "ready_for_approval":
            blocking_reasons.append("quarantine_readiness_not_ready_for_approval")

    if not isinstance(gate, dict):
        blocking_reasons.append("missing_execution_gate")
    elif not bool(gate.get("allowed")):
        blocking_reasons.append("execution_gate_not_allowed")

    if not isinstance(approval, dict):
        blocking_reasons.append("missing_operator_approval")
    else:
        if str(approval.get("schema_version") or "") != archive_approval.ARCHIVE_OPERATOR_APPROVAL_SCHEMA_VERSION:
            blocking_reasons.append("approval_schema_mismatch")
        expires_at_dt = _parse_iso_utc(approval.get("expires_at"))
        if expires_at_dt is None:
            blocking_reasons.append("approval_expiry_invalid")
        elif expires_at_dt <= datetime.now(timezone.utc):
            blocking_reasons.append("approval_expired")

    if not isinstance(fallback, dict):
        blocking_reasons.append("missing_fallback_simulation")
    elif str(fallback.get("status") or "") != "passed":
        blocking_reasons.append("fallback_simulation_not_passed")

    if not isinstance(readthrough, dict):
        blocking_reasons.append("missing_readthrough_report")
    elif str(readthrough.get("status") or "") != "passed":
        blocking_reasons.append("readthrough_not_passed")

    if not isinstance(pilot, dict):
        blocking_reasons.append("missing_pilot_record")
    else:
        if str(pilot.get("status") or "") not in _ALLOWED_PILOT_STATUSES:
            blocking_reasons.append("pilot_not_success")
        if not str(source_path):
            blocking_reasons.append("pilot_source_path_missing")
        if not source_kind:
            blocking_reasons.append("pilot_source_kind_missing")

    source_exists = source_path.exists() and source_path.is_file() if str(source_path) else False
    if str(source_path) and not source_exists:
        blocking_reasons.append("source_missing")
    if source_exists:
        actual_source_sha256 = _sha256_file(source_path)
        if source_sha256 and actual_source_sha256 != source_sha256:
            blocking_reasons.append("source_checksum_mismatch_with_pilot")
        source_sha256 = actual_source_sha256 or source_sha256

    if source_exists and _is_active_hot_source(source_path=source_path, source_kind=source_kind):
        blocking_reasons.append("candidate_is_active_hot_source")

    unique_blockers: list[str] = []
    seen = set()
    for reason in blocking_reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique_blockers.append(reason)
    blocking_reasons = unique_blockers

    source_bytes = int(source_path.stat().st_size) if source_exists else 0
    if blocking_reasons:
        payload = _record_payload(
            status=_BLOCKED,
            blocking_reasons=blocking_reasons,
            message="quarantine blocked by preconditions or active-source guard",
            source_path=source_path,
            quarantine_path=quarantine_path,
            source_kind=source_kind,
            source_sha256=source_sha256,
            quarantine_sha256=_sha256_file(quarantine_path),
            source_move_executed=False,
            source_retained=source_exists,
            source_bytes=source_bytes,
            quarantine_bytes=int(quarantine_path.stat().st_size) if quarantine_path.exists() else 0,
        )
        write_record_atomic(payload, policy=current_policy)
        ledger = append_ledger(_BLOCKED, source_bytes, ",".join(blocking_reasons))
        return ledger, payload

    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if quarantine_path.exists() and quarantine_path.is_file():
            quarantine_sha = _sha256_file(quarantine_path)
            if source_sha256 and quarantine_sha == source_sha256:
                payload = _record_payload(
                    status=_ALREADY_QUARANTINED,
                    blocking_reasons=[],
                    message="quarantine target already present with matching checksum",
                    source_path=source_path,
                    quarantine_path=quarantine_path,
                    source_kind=source_kind,
                    source_sha256=source_sha256,
                    quarantine_sha256=quarantine_sha,
                    source_move_executed=False,
                    source_retained=source_path.exists() and source_path.is_file(),
                    source_bytes=int(source_path.stat().st_size) if source_path.exists() else 0,
                    quarantine_bytes=int(quarantine_path.stat().st_size),
                )
                write_record_atomic(payload, policy=current_policy)
                ledger = append_ledger(_SUCCESS, int(quarantine_path.stat().st_size), None)
                return ledger, payload
            payload = _record_payload(
                status=_BLOCKED,
                blocking_reasons=["quarantine_target_exists_checksum_mismatch"],
                message="quarantine target already exists with checksum mismatch",
                source_path=source_path,
                quarantine_path=quarantine_path,
                source_kind=source_kind,
                source_sha256=source_sha256,
                quarantine_sha256=quarantine_sha,
                source_move_executed=False,
                source_retained=source_path.exists() and source_path.is_file(),
                source_bytes=int(source_path.stat().st_size) if source_path.exists() else 0,
                quarantine_bytes=int(quarantine_path.stat().st_size),
            )
            write_record_atomic(payload, policy=current_policy)
            ledger = append_ledger(_BLOCKED, int(quarantine_path.stat().st_size), "quarantine_target_exists_checksum_mismatch")
            return ledger, payload

        try:
            os.replace(str(source_path), str(quarantine_path))
        except OSError:
            shutil.move(str(source_path), str(quarantine_path))

        quarantine_sha = _sha256_file(quarantine_path)
        quarantine_bytes = int(quarantine_path.stat().st_size) if quarantine_path.exists() else 0
        if source_sha256 and quarantine_sha != source_sha256:
            # Best-effort rollback on checksum mismatch.
            try:
                shutil.move(str(quarantine_path), str(source_path))
            except Exception:
                pass
            payload = _record_payload(
                status=_FAILED,
                blocking_reasons=["post_move_checksum_mismatch"],
                message="checksum mismatch after move; rollback attempted",
                source_path=source_path,
                quarantine_path=quarantine_path,
                source_kind=source_kind,
                source_sha256=source_sha256,
                quarantine_sha256=quarantine_sha,
                source_move_executed=True,
                source_retained=source_path.exists() and source_path.is_file(),
                source_bytes=int(source_path.stat().st_size) if source_path.exists() else 0,
                quarantine_bytes=quarantine_bytes,
            )
            write_record_atomic(payload, policy=current_policy)
            ledger = append_ledger(_FAILED, quarantine_bytes, "post_move_checksum_mismatch")
            return ledger, payload

        payload = _record_payload(
            status=_SUCCESS,
            blocking_reasons=[],
            message="single-artifact quarantine completed",
            source_path=source_path,
            quarantine_path=quarantine_path,
            source_kind=source_kind,
            source_sha256=source_sha256,
            quarantine_sha256=quarantine_sha,
            source_move_executed=True,
            source_retained=False,
            source_bytes=source_bytes,
            quarantine_bytes=quarantine_bytes,
        )
        write_record_atomic(payload, policy=current_policy)
        ledger = append_ledger(_SUCCESS, quarantine_bytes, None)
        return ledger, payload
    except Exception as exc:
        payload = _record_payload(
            status=_FAILED,
            blocking_reasons=["quarantine_execution_error"],
            message=f"quarantine execution failed: {exc}",
            source_path=source_path,
            quarantine_path=quarantine_path,
            source_kind=source_kind,
            source_sha256=source_sha256,
            quarantine_sha256=_sha256_file(quarantine_path),
            source_move_executed=False,
            source_retained=source_path.exists() and source_path.is_file(),
            source_bytes=int(source_path.stat().st_size) if source_path.exists() else 0,
            quarantine_bytes=int(quarantine_path.stat().st_size) if quarantine_path.exists() else 0,
        )
        write_record_atomic(payload, policy=current_policy)
        ledger = append_ledger(_FAILED, 0, str(exc))
        return ledger, payload
