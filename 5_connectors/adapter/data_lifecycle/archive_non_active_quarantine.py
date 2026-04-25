"""Single non-active archive-copy quarantine executor."""

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

from . import archive_non_active_execution_gate, archive_non_active_quarantine_readiness, state_store
from .policy import DataLifecyclePolicy, load_policy

NON_ACTIVE_QUARANTINE_RECORD_SCHEMA_VERSION = "dlp-non-active-copy-quarantine-record-v1"
NON_ACTIVE_QUARANTINE_MODE = "single_non_active_copy_quarantine_only"
NON_ACTIVE_QUARANTINE_TRIGGER = "archive_non_active_copy_quarantine_execute_one"

_SUCCESS = "success"
_BLOCKED = "blocked"
_FAILED = "failed"
_ALREADY_QUARANTINED = "already_quarantined"
_FORBIDDEN_SOURCE_BASENAMES = {
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
    "archive_non_active_candidate_report.json",
    "archive_non_active_quarantine_readiness_plan.json",
    "archive_non_active_execution_gate.json",
}


def _record_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
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


def _write_record_atomic(record: dict[str, Any], *, policy: DataLifecyclePolicy) -> Path:
    path = _record_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_non_active_quarantine_", suffix=".tmp", dir=str(path.parent))
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
    current = policy or load_policy()
    return _read_json_dict(_record_path(current))


def _is_path_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _append_ledger(
    *,
    policy: DataLifecyclePolicy,
    cycle_id: str,
    started_at: datetime,
    status: str,
    bytes_scanned: int,
    error: Optional[str],
) -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc)
    ledger = state_store.build_record(
        cycle_id=cycle_id,
        trigger=NON_ACTIVE_QUARANTINE_TRIGGER,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        bytes_scanned=bytes_scanned,
        error=error,
    )
    state_store.append_state_record(ledger, policy=policy)
    return ledger


def _record_payload(
    *,
    status: str,
    blocking_reasons: list[str],
    message: str,
    candidate_path: Optional[Path],
    quarantine_path: Optional[Path],
    source_sha256: Optional[str],
    quarantine_sha256: Optional[str],
    source_bytes: int,
    quarantine_bytes: int,
    readiness: Optional[dict[str, Any]],
    gate: Optional[dict[str, Any]],
) -> dict[str, Any]:
    selected = (readiness or {}).get("selected_candidate") if isinstance(readiness, dict) else {}
    selected = selected if isinstance(selected, dict) else {}
    source_path = str(selected.get("origin_source_path") or "")
    return {
        "schema_version": NON_ACTIVE_QUARANTINE_RECORD_SCHEMA_VERSION,
        "quarantine_id": uuid4().hex[:12],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": NON_ACTIVE_QUARANTINE_MODE,
        "status": status,
        "message": message,
        "blocking_reasons": blocking_reasons,
        "candidate_kind": selected.get("candidate_kind"),
        "candidate_path": str(candidate_path) if candidate_path else str(selected.get("candidate_path") or ""),
        "candidate_sha256": source_sha256,
        "candidate_bytes": int(max(0, source_bytes)),
        "origin_source_path": source_path or None,
        "origin_source_kind": selected.get("origin_source_kind"),
        "origin_source_sha256": selected.get("origin_source_sha256"),
        "production_source_path": source_path or None,
        "restore_key": selected.get("restore_key"),
        "pilot_id": selected.get("pilot_id"),
        "quarantine_path": str(quarantine_path) if quarantine_path else str(selected.get("planned_quarantine_path") or ""),
        "quarantine_copy_path": str(quarantine_path) if quarantine_path else None,
        "quarantine_sha256": quarantine_sha256,
        "quarantine_bytes": int(max(0, quarantine_bytes)),
        "checksum_match": bool(source_sha256 and quarantine_sha256 and source_sha256 == quarantine_sha256),
        "source_move_executed": False,
        "non_active_copy_move_executed": status in {_SUCCESS, _ALREADY_QUARANTINED},
        "delete_compress_executed": False,
        "production_read_path_unchanged": True,
        "source_retained": True,
        "archive_copy_retained": status != _SUCCESS,
        "quarantine_copy_retained": bool(quarantine_path and quarantine_path.exists() and quarantine_path.is_file()),
        "gate_ref": {
            "gate_id": (gate or {}).get("gate_id") if isinstance(gate, dict) else None,
            "allowed": bool((gate or {}).get("allowed", False)) if isinstance(gate, dict) else False,
            "status": (gate or {}).get("status") if isinstance(gate, dict) else None,
        },
        "readiness_ref": {
            "plan_id": (readiness or {}).get("plan_id") if isinstance(readiness, dict) else None,
            "status": (readiness or {}).get("status") if isinstance(readiness, dict) else None,
        },
        "summary": {
            "status": status,
            "blocking_count": len(blocking_reasons),
            "checksum_match": bool(source_sha256 and quarantine_sha256 and source_sha256 == quarantine_sha256),
            "source_move_executed": False,
            "non_active_copy_move_executed": status in {_SUCCESS, _ALREADY_QUARANTINED},
            "delete_compress_executed": False,
            "production_read_path_unchanged": True,
        },
    }


def execute_single_non_active_copy_quarantine(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    blocking_reasons: list[str] = []

    readiness = archive_non_active_quarantine_readiness.read_plan(policy=current_policy)
    gate = archive_non_active_execution_gate.read_gate(policy=current_policy)
    selected = readiness.get("selected_candidate") if isinstance(readiness, dict) else None
    selected = selected if isinstance(selected, dict) else {}

    if not isinstance(readiness, dict):
        blocking_reasons.append("missing_non_active_quarantine_readiness")
    else:
        if readiness.get("schema_version") != archive_non_active_quarantine_readiness.NON_ACTIVE_QUARANTINE_READINESS_SCHEMA_VERSION:
            blocking_reasons.append("non_active_quarantine_readiness_schema_mismatch")
        if readiness.get("status") != "ready_for_operator_approval":
            blocking_reasons.append("non_active_quarantine_readiness_not_ready")
        if readiness.get("mode") != archive_non_active_quarantine_readiness.READINESS_MODE:
            blocking_reasons.append("non_active_quarantine_readiness_mode_mismatch")

    if not isinstance(gate, dict):
        blocking_reasons.append("missing_non_active_execution_gate")
    else:
        if gate.get("schema_version") != archive_non_active_execution_gate.NON_ACTIVE_EXECUTION_GATE_SCHEMA_VERSION:
            blocking_reasons.append("non_active_execution_gate_schema_mismatch")
        if gate.get("mode") != archive_non_active_execution_gate.GATE_MODE:
            blocking_reasons.append("non_active_execution_gate_mode_mismatch")
        if gate.get("allowed") is not True:
            blocking_reasons.append("non_active_execution_gate_not_allowed")

    if selected.get("candidate_kind") != "archive_pilot_copy":
        blocking_reasons.append("selected_candidate_not_archive_pilot_copy")

    candidate_path = Path(str(selected.get("candidate_path") or "")).expanduser()
    quarantine_path = Path(str(selected.get("planned_quarantine_path") or "")).expanduser()
    if not str(candidate_path):
        blocking_reasons.append("selected_candidate_path_missing")
    if not str(quarantine_path):
        blocking_reasons.append("planned_quarantine_path_missing")

    if candidate_path.name in _FORBIDDEN_SOURCE_BASENAMES or (
        candidate_path.name.startswith("meters_") and candidate_path.name.endswith(".json")
    ):
        blocking_reasons.append("candidate_path_matches_active_or_control_basename")
    if str(candidate_path) and not _is_path_inside(candidate_path, Path(current_policy.archive_pilot_root).expanduser()):
        blocking_reasons.append("candidate_not_under_archive_pilot_root")
    if str(quarantine_path) and not _is_path_inside(
        quarantine_path,
        Path(current_policy.archive_quarantine_root).expanduser() / "non_active",
    ):
        blocking_reasons.append("quarantine_target_not_under_non_active_root")

    expected_sha = selected.get("sha256")
    if not blocking_reasons and quarantine_path.exists() and quarantine_path.is_file() and not candidate_path.exists():
        quarantine_sha = _sha256_file(quarantine_path)
        if expected_sha and quarantine_sha == str(expected_sha):
            record = _record_payload(
                status=_ALREADY_QUARANTINED,
                blocking_reasons=[],
                message="non-active copy already quarantined; no move executed",
                candidate_path=candidate_path,
                quarantine_path=quarantine_path,
                source_sha256=str(expected_sha),
                quarantine_sha256=quarantine_sha,
                source_bytes=int(selected.get("bytes", 0) or quarantine_path.stat().st_size),
                quarantine_bytes=int(quarantine_path.stat().st_size),
                readiness=readiness,
                gate=gate,
            )
            _write_record_atomic(record, policy=current_policy)
            ledger = _append_ledger(
                policy=current_policy,
                cycle_id=cycle_id,
                started_at=started_at,
                status=_SUCCESS,
                bytes_scanned=int(quarantine_path.stat().st_size),
                error=None,
            )
            return ledger, record

    candidate_exists = candidate_path.exists() and candidate_path.is_file() if str(candidate_path) else False
    candidate_sha = _sha256_file(candidate_path) if candidate_exists else None
    if not candidate_exists:
        blocking_reasons.append("selected_candidate_missing")
    if not candidate_sha:
        blocking_reasons.append("selected_candidate_checksum_missing")
    if expected_sha and candidate_sha and str(expected_sha) != candidate_sha:
        blocking_reasons.append("selected_candidate_checksum_mismatch")

    unique_blockers: list[str] = []
    for reason in blocking_reasons:
        if reason not in unique_blockers:
            unique_blockers.append(reason)
    blocking_reasons = unique_blockers

    source_bytes = int(candidate_path.stat().st_size) if candidate_exists else int(selected.get("bytes", 0) or 0)
    if blocking_reasons:
        record = _record_payload(
            status=_BLOCKED,
            blocking_reasons=blocking_reasons,
            message="non-active copy quarantine blocked by preconditions",
            candidate_path=candidate_path if str(candidate_path) else None,
            quarantine_path=quarantine_path if str(quarantine_path) else None,
            source_sha256=candidate_sha,
            quarantine_sha256=_sha256_file(quarantine_path),
            source_bytes=source_bytes,
            quarantine_bytes=int(quarantine_path.stat().st_size) if quarantine_path.exists() and quarantine_path.is_file() else 0,
            readiness=readiness,
            gate=gate,
        )
        _write_record_atomic(record, policy=current_policy)
        ledger = _append_ledger(
            policy=current_policy,
            cycle_id=cycle_id,
            started_at=started_at,
            status=_BLOCKED,
            bytes_scanned=source_bytes,
            error=",".join(blocking_reasons),
        )
        return ledger, record

    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    if quarantine_path.exists() and quarantine_path.is_file():
        quarantine_sha = _sha256_file(quarantine_path)
        if candidate_sha and quarantine_sha == candidate_sha:
            record = _record_payload(
                status=_ALREADY_QUARANTINED,
                blocking_reasons=[],
                message="non-active copy already quarantined; no move executed",
                candidate_path=candidate_path,
                quarantine_path=quarantine_path,
                source_sha256=candidate_sha,
                quarantine_sha256=quarantine_sha,
                source_bytes=source_bytes,
                quarantine_bytes=int(quarantine_path.stat().st_size),
                readiness=readiness,
                gate=gate,
            )
            _write_record_atomic(record, policy=current_policy)
            ledger = _append_ledger(
                policy=current_policy,
                cycle_id=cycle_id,
                started_at=started_at,
                status=_SUCCESS,
                bytes_scanned=int(quarantine_path.stat().st_size),
                error=None,
            )
            return ledger, record
        record = _record_payload(
            status=_BLOCKED,
            blocking_reasons=["quarantine_target_exists_checksum_mismatch"],
            message="quarantine target already exists with checksum mismatch",
            candidate_path=candidate_path,
            quarantine_path=quarantine_path,
            source_sha256=candidate_sha,
            quarantine_sha256=quarantine_sha,
            source_bytes=source_bytes,
            quarantine_bytes=int(quarantine_path.stat().st_size),
            readiness=readiness,
            gate=gate,
        )
        _write_record_atomic(record, policy=current_policy)
        ledger = _append_ledger(
            policy=current_policy,
            cycle_id=cycle_id,
            started_at=started_at,
            status=_BLOCKED,
            bytes_scanned=int(quarantine_path.stat().st_size),
            error="quarantine_target_exists_checksum_mismatch",
        )
        return ledger, record

    try:
        try:
            os.replace(str(candidate_path), str(quarantine_path))
        except OSError:
            shutil.move(str(candidate_path), str(quarantine_path))
        quarantine_sha = _sha256_file(quarantine_path)
        quarantine_bytes = int(quarantine_path.stat().st_size) if quarantine_path.exists() else 0
        if candidate_sha and quarantine_sha != candidate_sha:
            if quarantine_path.exists() and not candidate_path.exists():
                shutil.move(str(quarantine_path), str(candidate_path))
            record = _record_payload(
                status=_FAILED,
                blocking_reasons=["post_move_checksum_mismatch"],
                message="non-active copy quarantine failed checksum verification and was rolled back",
                candidate_path=candidate_path,
                quarantine_path=quarantine_path,
                source_sha256=candidate_sha,
                quarantine_sha256=quarantine_sha,
                source_bytes=source_bytes,
                quarantine_bytes=quarantine_bytes,
                readiness=readiness,
                gate=gate,
            )
            _write_record_atomic(record, policy=current_policy)
            ledger = _append_ledger(
                policy=current_policy,
                cycle_id=cycle_id,
                started_at=started_at,
                status=_FAILED,
                bytes_scanned=quarantine_bytes,
                error="post_move_checksum_mismatch",
            )
            return ledger, record

        record = _record_payload(
            status=_SUCCESS,
            blocking_reasons=[],
            message="single non-active archive copy quarantine completed",
            candidate_path=candidate_path,
            quarantine_path=quarantine_path,
            source_sha256=candidate_sha,
            quarantine_sha256=quarantine_sha,
            source_bytes=source_bytes,
            quarantine_bytes=quarantine_bytes,
            readiness=readiness,
            gate=gate,
        )
        _write_record_atomic(record, policy=current_policy)
        ledger = _append_ledger(
            policy=current_policy,
            cycle_id=cycle_id,
            started_at=started_at,
            status=_SUCCESS,
            bytes_scanned=quarantine_bytes,
            error=None,
        )
        return ledger, record
    except Exception as exc:
        record = _record_payload(
            status=_FAILED,
            blocking_reasons=["non_active_quarantine_execution_error"],
            message=f"non-active copy quarantine execution failed: {exc}",
            candidate_path=candidate_path,
            quarantine_path=quarantine_path,
            source_sha256=candidate_sha,
            quarantine_sha256=_sha256_file(quarantine_path),
            source_bytes=source_bytes,
            quarantine_bytes=int(quarantine_path.stat().st_size) if quarantine_path.exists() and quarantine_path.is_file() else 0,
            readiness=readiness,
            gate=gate,
        )
        _write_record_atomic(record, policy=current_policy)
        ledger = _append_ledger(
            policy=current_policy,
            cycle_id=cycle_id,
            started_at=started_at,
            status=_FAILED,
            bytes_scanned=source_bytes,
            error="non_active_quarantine_execution_error",
        )
        return ledger, record
