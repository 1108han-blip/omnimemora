"""Legacy meter cleanup transaction preview (file-level preview only, never executes cleanup)."""

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

_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
_cleanup_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_execution_gate")
_copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")
_restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")

METER_CLEANUP_TRANSACTION_PREVIEW_SCHEMA_VERSION = "res-legacy-meter-cleanup-transaction-preview-v1"
METER_CLEANUP_TRANSACTION_PREVIEW_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-transaction-preview-rebuild-v1"
METER_CLEANUP_TRANSACTION_PREVIEW_MODE = "cleanup_transaction_preview_only"


def _preview_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_transaction_preview_file).expanduser()


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


def _mtime_iso(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _build_item(
    *,
    candidate: dict[str, Any],
    parity_ok: bool,
    copy_pilot: Optional[dict[str, Any]],
    restore_readback: Optional[dict[str, Any]],
    gate: Optional[dict[str, Any]],
) -> dict[str, Any]:
    source_path = Path(str(candidate.get("path") or "")).expanduser()
    source_exists = source_path.exists() and source_path.is_file()
    current_sha256 = _sha256_file(source_path) if source_exists else None
    current_mtime = _mtime_iso(source_path) if source_exists else None
    source_bytes = int(source_path.stat().st_size) if source_exists else int(candidate.get("bytes", 0) or 0)

    expected_sha256 = str(candidate.get("sha256") or "")
    expected_mtime = str(candidate.get("mtime") or "")
    drift_reasons: list[str] = []
    if not source_exists:
        drift_reasons.append("source_missing")
    if source_exists and expected_sha256 and current_sha256 and expected_sha256 != current_sha256:
        drift_reasons.append("source_hash_drift")
    if source_exists and expected_mtime and current_mtime and expected_mtime != current_mtime:
        drift_reasons.append("source_mtime_drift")

    copy_ref = {
        "status": "missing",
        "target_path": None,
        "checksum_match": False,
    }
    if isinstance(copy_pilot, dict):
        selected = copy_pilot.get("selected_candidate") or {}
        selected_path = str(selected.get("path") or "")
        if selected_path == str(source_path):
            copy_ref = {
                "status": str(copy_pilot.get("status") or "unknown"),
                "target_path": copy_pilot.get("target_path"),
                "checksum_match": bool(copy_pilot.get("checksum_match", False)),
            }
        else:
            copy_ref["status"] = "not_selected_for_copy_pilot"

    restore_ref = {
        "status": "missing",
        "checksum_match": False,
        "source_retained": False,
    }
    if isinstance(restore_readback, dict):
        restore_ref = {
            "status": str(restore_readback.get("status") or "unknown"),
            "checksum_match": bool(restore_readback.get("checksum_match", False)),
            "source_retained": bool(restore_readback.get("source_retained", False)),
        }

    reasons: list[str] = []
    reasons.extend(drift_reasons)
    if not parity_ok:
        reasons.append("parity_not_passed")
    if not isinstance(restore_readback, dict):
        reasons.append("restore_readback_missing")
    elif str(restore_readback.get("status") or "") != "passed":
        reasons.append("restore_readback_not_passed")
    if not isinstance(gate, dict):
        reasons.append("cleanup_gate_missing")
    else:
        gate_reasons = list(gate.get("blocking_reasons") or [])
        if "missing_operator_approval" in gate_reasons:
            reasons.append("missing_operator_approval")
        if "operator_approval_artifact_hash_mismatch" in gate_reasons:
            reasons.append("operator_approval_artifact_hash_mismatch")

    operation = "eligible_for_future_cleanup"
    rollback_instruction = "restore backup copy to staging path; verify checksum; keep source retained"
    if source_path.name == "meters_index.json":
        operation = "retain"
        reasons.append("core_index_retained_for_future_explicit_scope")
        rollback_instruction = "retain index file; no cleanup candidate action in this stage"
    if reasons:
        operation = "blocked" if operation != "retain" else "retain"

    return {
        "candidate_id": str(candidate.get("name") or source_path.name),
        "operation": operation,
        "source": {
            "path": str(source_path),
            "bytes": source_bytes,
            "mtime": current_mtime,
            "sha256": current_sha256,
            "expected_mtime": expected_mtime or None,
            "expected_sha256": expected_sha256 or None,
        },
        "sqlite_parity_ref": {
            "status": "passed" if parity_ok else "degraded",
        },
        "backup_copy_ref": copy_ref,
        "restore_readback_ref": restore_ref,
        "rollback_instruction": rollback_instruction,
        "blocking_reasons": list(dict.fromkeys(reasons)),
    }


def build_transaction_preview(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    cleanup_gate = _cleanup_gate.read_gate(policy=current)
    copy_pilot = _copy_pilot.read_latest_copy_pilot(policy=current)
    restore_readback = _restore_readback.read_restore_readback_report(policy=current)
    parity = _meter_storage_v2.build_parity_report()
    parity_ok = str(parity.get("status") or "").lower() == "passed" and int(
        parity.get("critical_mismatch_count", 0) or 0
    ) == 0

    candidates = []
    if isinstance(cleanup_preview, dict):
        for item in cleanup_preview.get("would_cleanup_files") or []:
            if isinstance(item, dict):
                candidates.append(item)

    items = [
        _build_item(
            candidate=item,
            parity_ok=parity_ok,
            copy_pilot=copy_pilot if isinstance(copy_pilot, dict) else None,
            restore_readback=restore_readback if isinstance(restore_readback, dict) else None,
            gate=cleanup_gate if isinstance(cleanup_gate, dict) else None,
        )
        for item in candidates
    ]
    operation_counts = {
        "retain": 0,
        "eligible_for_future_cleanup": 0,
        "blocked": 0,
    }
    blocked_candidates = 0
    for item in items:
        op = str(item.get("operation") or "blocked")
        if op not in operation_counts:
            op = "blocked"
        operation_counts[op] += 1
        if op == "blocked":
            blocked_candidates += 1

    blocking_reasons: list[str] = []
    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
    if not isinstance(cleanup_gate, dict):
        blocking_reasons.append("cleanup_gate_missing")
    if not isinstance(restore_readback, dict):
        blocking_reasons.append("restore_readback_missing")
    if not parity_ok:
        blocking_reasons.append("parity_not_passed")
    if blocked_candidates > 0:
        blocking_reasons.append("blocked_candidates_present")
    # RES-021 contract: preview only, never execution.
    blocking_reasons.append("execution_not_enabled_in_res021")
    blocking_reasons = list(dict.fromkeys(blocking_reasons))

    return {
        "schema_version": METER_CLEANUP_TRANSACTION_PREVIEW_SCHEMA_VERSION,
        "transaction_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_TRANSACTION_PREVIEW_MODE,
        "status": "blocked",
        "execution_allowed": False,
        "items": items,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": "blocked",
            "execution_allowed": False,
            "candidate_count": int(len(items)),
            "retain_count": int(operation_counts["retain"]),
            "eligible_for_future_cleanup_count": int(operation_counts["eligible_for_future_cleanup"]),
            "blocked_count": int(operation_counts["blocked"]),
            "blocking_reasons_count": int(len(blocking_reasons)),
        },
    }


def write_preview_atomic(preview: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _preview_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_transaction_preview_", suffix=".tmp", dir=str(path.parent))
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
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    preview = build_transaction_preview(policy=current)
    write_preview_atomic(preview, policy=current)
    completed_at = datetime.now(timezone.utc)
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_cleanup_transaction_preview_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((preview.get("summary") or {}).get("candidate_count", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, preview

