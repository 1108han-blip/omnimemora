"""Single-file reversible quarantine pilot for legacy meter cleanup (RES-023)."""

from __future__ import annotations

import errno
import hashlib
import importlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
_cleanup_txn = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_transaction_preview")
_cleanup_rollback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")
_backup_copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")
_backup_restore_readback = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback"
)
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")

METER_CLEANUP_SELECTED_CANDIDATE_SCHEMA_VERSION = "res-legacy-meter-cleanup-selected-candidate-v1"
METER_CLEANUP_SELECTED_CANDIDATE_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-selected-candidate-rebuild-v1"
METER_CLEANUP_SELECTED_CANDIDATE_MODE = "single_candidate_record_only"

METER_CLEANUP_PILOT_APPROVAL_TEMPLATE_SCHEMA_VERSION = "res-legacy-meter-cleanup-pilot-approval-template-v1"
METER_CLEANUP_PILOT_APPROVAL_TEMPLATE_MODE = "approval_template_only"

METER_CLEANUP_PILOT_OPERATOR_APPROVAL_SCHEMA_VERSION = "res-legacy-meter-cleanup-pilot-operator-approval-v1"

METER_CLEANUP_PILOT_SCHEMA_VERSION = "res-legacy-meter-cleanup-pilot-record-v1"
METER_CLEANUP_PILOT_MODE = "single_reversible_quarantine_only"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: Optional[datetime]) -> Optional[str]:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).isoformat()


def _stable_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_for_artifact_hash(payload: Any) -> Any:
    volatile_keys = {
        "generated_at",
        "executed_at",
        "approved_at",
        "selection_id",
        "preview_id",
        "report_id",
        "record_id",
        "cycle_id",
        "transaction_id",
        "gate_id",
        "pilot_id",
        "template_id",
    }
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if key in volatile_keys:
                continue
            out[str(key)] = _normalize_for_artifact_hash(value)
        return out
    if isinstance(payload, list):
        return [_normalize_for_artifact_hash(item) for item in payload]
    return payload


def _artifact_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    normalized = _normalize_for_artifact_hash(payload)
    text = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _selected_candidate_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_selected_candidate_file).expanduser()


def _approval_template_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_pilot_approval_template_file).expanduser()


def _operator_approval_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_pilot_operator_approval_file).expanduser()


def _pilot_record_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_pilot_record_file).expanduser()


def _quarantine_root(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_quarantine_root).expanduser()


def _write_json_atomic(path: Path, payload: dict[str, Any], *, tmp_prefix: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=tmp_prefix, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _is_legacy_tenant_meter_file(path: Path) -> bool:
    return path.name.startswith("meters_") and path.name.endswith(".json") and path.name != "meters_index.json"


def _is_forbidden_candidate_path(path: Path) -> bool:
    lower_path = str(path).lower()
    if lower_path.endswith(".sqlite") or lower_path.endswith(".sqlite3") or lower_path.endswith(".db"):
        return True
    forbidden_tokens = [
        "/data_lifecycle/",
        "/backup_export/",
        "/quarantine/",
        "/restore/",
    ]
    return any(token in lower_path for token in forbidden_tokens)


def _planned_quarantine_path(source_path: Path, source_sha256: str, *, policy: DataLifecyclePolicy) -> Path:
    root = _quarantine_root(policy)
    return root / f"{source_path.name}.{source_sha256[:16]}.quarantine"


def _resolve_running_revision() -> tuple[Optional[str], str]:
    for key in ("OMNIMEMORA_RUNNING_REVISION", "OMNIMEMORA_ADAPTER_RUNNING_REVISION"):
        value = str(os.getenv(key, "")).strip()
        if value:
            return value, f"env:{key}"

    marker_override = str(os.getenv("OMNIMEMORA_PROMOTION_STATE_FILE", "")).strip()
    marker_path = (
        Path(marker_override).expanduser()
        if marker_override
        else Path("~/.omnimemora/service/current/.omnimemora_promotion_state.json").expanduser()
    )
    if marker_path.exists() and marker_path.is_file():
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            revision = str(payload.get("repo_revision") or "").strip()
            if revision:
                return revision, f"marker:{marker_path}"

    return None, "missing"


def _find_txn_item_by_source_path(txn_preview: Optional[dict[str, Any]], source_path: str) -> Optional[dict[str, Any]]:
    if not isinstance(txn_preview, dict):
        return None
    for item in txn_preview.get("items") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or {}
        if isinstance(source, dict) and str(source.get("path") or "") == source_path:
            return item
    return None


def build_selected_candidate(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = _utc_now()
    blocking_reasons: list[str] = []

    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    copy_pilot = _backup_copy_pilot.read_latest_copy_pilot(policy=current)
    restore_readback = _backup_restore_readback.read_restore_readback_report(policy=current)
    parity = _meter_storage_v2.build_parity_report()
    txn_preview = _cleanup_txn.read_preview(policy=current)
    rollback_drill = _cleanup_rollback.read_rollback_drill_report(policy=current)

    preview_hash = _artifact_hash(cleanup_preview)
    copy_pilot_hash = _artifact_hash(copy_pilot)
    restore_hash = _artifact_hash(restore_readback)
    parity_hash = _artifact_hash(parity)
    txn_hash = _artifact_hash(txn_preview)
    rollback_hash = _artifact_hash(rollback_drill)

    selected_path: Optional[Path] = None
    selected_preview_item: Optional[dict[str, Any]] = None
    backup_copy_path: Optional[Path] = None
    txn_item: Optional[dict[str, Any]] = None

    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
    if not isinstance(copy_pilot, dict):
        blocking_reasons.append("backup_copy_pilot_missing")
    else:
        if str(copy_pilot.get("status") or "") not in {"success", "already_copied"}:
            blocking_reasons.append("backup_copy_pilot_not_success")
        if not bool(copy_pilot.get("source_retained", False)):
            blocking_reasons.append("backup_copy_source_not_retained")
        if not bool(copy_pilot.get("checksum_match", False)):
            blocking_reasons.append("backup_copy_checksum_mismatch")
        selected = copy_pilot.get("selected_candidate") or {}
        raw_source = str(selected.get("path") or "").strip()
        if raw_source:
            selected_path = Path(raw_source).expanduser()
        else:
            blocking_reasons.append("backup_copy_selected_source_missing")
        raw_backup_copy = str(copy_pilot.get("target_path") or "").strip()
        if raw_backup_copy:
            backup_copy_path = Path(raw_backup_copy).expanduser()
        else:
            blocking_reasons.append("backup_copy_target_missing")

    if selected_path is None:
        blocking_reasons.append("selected_source_missing")

    if selected_path is not None:
        if selected_path.name == "meters_index.json":
            blocking_reasons.append("selected_source_is_meters_index")
        if not _is_legacy_tenant_meter_file(selected_path):
            blocking_reasons.append("selected_source_not_legacy_tenant_meter")
        if _is_forbidden_candidate_path(selected_path):
            blocking_reasons.append("selected_source_in_forbidden_path")

    if isinstance(cleanup_preview, dict) and selected_path is not None:
        for item in cleanup_preview.get("would_cleanup_files") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("path") or "") == str(selected_path):
                selected_preview_item = item
                break
        if selected_preview_item is None:
            blocking_reasons.append("selected_source_not_in_cleanup_preview")

    source_exists = bool(selected_path and selected_path.exists() and selected_path.is_file())
    source_sha256 = _sha256_file(selected_path) if selected_path else None
    source_mtime = _mtime_iso(selected_path) if selected_path else None
    source_bytes = int(selected_path.stat().st_size) if source_exists and selected_path else 0

    preview_source_sha256 = str((selected_preview_item or {}).get("sha256") or "") or None
    preview_source_mtime = str((selected_preview_item or {}).get("mtime") or "") or None

    if selected_path is not None and not source_exists:
        blocking_reasons.append("selected_source_not_readable")
    if source_exists and preview_source_sha256 and source_sha256 and source_sha256 != preview_source_sha256:
        blocking_reasons.append("source_hash_drift")
    if source_exists and preview_source_mtime and source_mtime and source_mtime != preview_source_mtime:
        blocking_reasons.append("source_mtime_drift")

    backup_copy_exists = bool(backup_copy_path and backup_copy_path.exists() and backup_copy_path.is_file())
    backup_copy_sha256 = _sha256_file(backup_copy_path) if backup_copy_path else None
    if backup_copy_path is not None and not backup_copy_exists:
        blocking_reasons.append("backup_copy_not_readable")
    expected_backup_sha = str(copy_pilot.get("copied_sha256") or "") if isinstance(copy_pilot, dict) else ""
    if backup_copy_exists and expected_backup_sha and backup_copy_sha256 and backup_copy_sha256 != expected_backup_sha:
        blocking_reasons.append("backup_copy_hash_drift")

    if not isinstance(restore_readback, dict):
        blocking_reasons.append("restore_readback_missing")
    else:
        if str(restore_readback.get("status") or "") != "passed":
            blocking_reasons.append("restore_readback_not_passed")
        if not bool(restore_readback.get("checksum_match", False)):
            blocking_reasons.append("restore_readback_checksum_mismatch")
        if str(restore_readback.get("source_path") or "") != str(selected_path or ""):
            blocking_reasons.append("restore_readback_source_mismatch")
        if str(restore_readback.get("backup_copy_path") or "") != str(backup_copy_path or ""):
            blocking_reasons.append("restore_readback_backup_copy_mismatch")

    if str(parity.get("status") or "").lower() != "passed":
        blocking_reasons.append("parity_not_passed")
    if int(parity.get("critical_mismatch_count", 0) or 0) != 0:
        blocking_reasons.append("critical_mismatch_nonzero")

    if not isinstance(txn_preview, dict):
        blocking_reasons.append("cleanup_transaction_preview_missing")
    else:
        txn_item = _find_txn_item_by_source_path(txn_preview, str(selected_path or ""))
        if txn_item is None:
            blocking_reasons.append("cleanup_transaction_preview_candidate_missing")

    if not isinstance(rollback_drill, dict):
        blocking_reasons.append("rollback_drill_missing")
    else:
        if str(rollback_drill.get("status") or "") != "passed":
            blocking_reasons.append("rollback_drill_not_passed")
        if not bool(rollback_drill.get("staging_restore_readable", False)):
            blocking_reasons.append("rollback_drill_staging_restore_not_readable")
        if not bool(rollback_drill.get("checksum_match", False)):
            blocking_reasons.append("rollback_drill_checksum_mismatch")

    if selected_path is None or source_sha256 is None:
        planned_quarantine_path = None
    else:
        planned_quarantine_path = str(_planned_quarantine_path(selected_path, source_sha256, policy=current))

    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    status = "ready_for_operator_approval" if not blocking_reasons else "blocked"
    txn_operation = str((txn_item or {}).get("operation") or "unknown")

    return {
        "schema_version": METER_CLEANUP_SELECTED_CANDIDATE_SCHEMA_VERSION,
        "selection_id": state_store.new_cycle_id(),
        "generated_at": _to_iso(now),
        "mode": METER_CLEANUP_SELECTED_CANDIDATE_MODE,
        "status": status,
        "selected_candidate": {
            "path": str(selected_path) if selected_path else None,
            "name": selected_path.name if selected_path else None,
            "bytes": source_bytes,
            "sha256": source_sha256,
            "mtime": source_mtime,
            "txn_operation": txn_operation,
        },
        "backup_copy": {
            "path": str(backup_copy_path) if backup_copy_path else None,
            "sha256": backup_copy_sha256,
        },
        "planned_quarantine_path": planned_quarantine_path,
        "artifact_hashes": {
            "cleanup_preview_hash": preview_hash,
            "backup_copy_pilot_hash": copy_pilot_hash,
            "restore_readback_report_hash": restore_hash,
            "parity_report_hash": parity_hash,
            "transaction_preview_hash": txn_hash,
            "rollback_drill_hash": rollback_hash,
        },
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "blocking_count": len(blocking_reasons),
            "selected_candidate_present": selected_path is not None,
            "source_hash_mtime_stable": bool(
                source_exists
                and preview_source_sha256
                and preview_source_mtime
                and source_sha256 == preview_source_sha256
                and source_mtime == preview_source_mtime
            ),
            "backup_copy_readable": backup_copy_exists,
        },
    }


def write_selected_candidate(selected_candidate: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    return _write_json_atomic(
        _selected_candidate_path(policy),
        selected_candidate,
        tmp_prefix="meter_cleanup_selected_candidate_",
    )


def read_selected_candidate(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    return _read_json(_selected_candidate_path(policy))


def rebuild_selected_candidate(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    selected_candidate = build_selected_candidate(policy=current)
    write_selected_candidate(selected_candidate, policy=current)
    completed_at = _utc_now()
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_cleanup_selected_candidate_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((selected_candidate.get("selected_candidate") or {}).get("bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, selected_candidate


def build_approval_template(*, selected_candidate: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    expires_at = now + timedelta(hours=24)
    hashes = (selected_candidate.get("artifact_hashes") or {}) if isinstance(selected_candidate, dict) else {}
    candidate = (selected_candidate.get("selected_candidate") or {}) if isinstance(selected_candidate, dict) else {}
    backup_copy = (selected_candidate.get("backup_copy") or {}) if isinstance(selected_candidate, dict) else {}
    planned_quarantine_path = (selected_candidate.get("planned_quarantine_path") if isinstance(selected_candidate, dict) else None)
    blocking_reasons = list(selected_candidate.get("blocking_reasons") or []) if isinstance(selected_candidate, dict) else []
    if str(selected_candidate.get("status") or "") != "ready_for_operator_approval":
        blocking_reasons.append("selected_candidate_not_ready")
    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    status = "ready_for_operator_approval" if not blocking_reasons else "blocked"

    return {
        "schema_version": METER_CLEANUP_PILOT_APPROVAL_TEMPLATE_SCHEMA_VERSION,
        "template_id": state_store.new_cycle_id(),
        "generated_at": _to_iso(now),
        "mode": METER_CLEANUP_PILOT_APPROVAL_TEMPLATE_MODE,
        "status": status,
        "approval_valid": False,
        "expires_at": _to_iso(expires_at),
        "required_bindings": {
            "source_path": candidate.get("path"),
            "source_sha256": candidate.get("sha256"),
            "source_mtime": candidate.get("mtime"),
            "backup_copy_path": backup_copy.get("path"),
            "backup_copy_sha256": backup_copy.get("sha256"),
            "restore_readback_report_hash": hashes.get("restore_readback_report_hash"),
            "parity_report_hash": hashes.get("parity_report_hash"),
            "transaction_preview_hash": hashes.get("transaction_preview_hash"),
            "target_quarantine_path": planned_quarantine_path,
        },
        "required_schema_version": METER_CLEANUP_PILOT_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "blocking_count": len(blocking_reasons),
        },
    }


def write_approval_template(template: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    return _write_json_atomic(
        _approval_template_path(policy),
        template,
        tmp_prefix="meter_cleanup_pilot_approval_template_",
    )


def read_approval_template(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    return _read_json(_approval_template_path(policy))


def read_operator_approval(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    return _read_json(_operator_approval_path(policy))


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def validate_operator_approval(
    *,
    approval: Optional[dict[str, Any]],
    selected_candidate: dict[str, Any],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    check_now = (now or _utc_now()).astimezone(timezone.utc)
    candidate = selected_candidate.get("selected_candidate") or {}
    backup_copy = selected_candidate.get("backup_copy") or {}
    hashes = selected_candidate.get("artifact_hashes") or {}
    target_quarantine_path = selected_candidate.get("planned_quarantine_path")
    blocking_reasons: list[str] = []

    if not isinstance(approval, dict):
        return {
            "status": "missing",
            "approval_hash": None,
            "operator_id": None,
            "expires_at": None,
            "blocking_reasons": ["missing_cleanup_pilot_operator_approval"],
        }

    if str(approval.get("schema_version") or "") != METER_CLEANUP_PILOT_OPERATOR_APPROVAL_SCHEMA_VERSION:
        blocking_reasons.append("operator_approval_schema_mismatch")
    operator_id = str(approval.get("operator_id") or "").strip()
    if not operator_id:
        blocking_reasons.append("operator_approval_operator_id_missing")

    approved_at = _parse_iso_utc(approval.get("approved_at"))
    expires_at = _parse_iso_utc(approval.get("expires_at"))
    if approved_at is None:
        blocking_reasons.append("operator_approval_approved_at_invalid")
    if expires_at is None:
        blocking_reasons.append("operator_approval_expires_at_invalid")
    elif expires_at <= check_now:
        blocking_reasons.append("operator_approval_expired")

    field_map = {
        "source_path": candidate.get("path"),
        "source_sha256": candidate.get("sha256"),
        "source_mtime": candidate.get("mtime"),
        "backup_copy_path": backup_copy.get("path"),
        "backup_copy_sha256": backup_copy.get("sha256"),
        "restore_readback_report_hash": hashes.get("restore_readback_report_hash"),
        "parity_report_hash": hashes.get("parity_report_hash"),
        "transaction_preview_hash": hashes.get("transaction_preview_hash"),
        "target_quarantine_path": target_quarantine_path,
    }
    hash_mismatch = False
    for key, expected in field_map.items():
        actual = approval.get(key)
        if str(actual or "") != str(expected or ""):
            blocking_reasons.append(f"operator_approval_{key}_mismatch")
            if key.endswith("_hash") or key.endswith("_sha256"):
                hash_mismatch = True
    if hash_mismatch:
        blocking_reasons.append("operator_approval_artifact_hash_mismatch")

    status = "valid" if not blocking_reasons else "invalid"
    return {
        "status": status,
        "approval_hash": _stable_hash(approval),
        "operator_id": operator_id or None,
        "expires_at": approval.get("expires_at"),
        "blocking_reasons": blocking_reasons,
    }


def _build_blocked_record(
    *,
    selected_candidate: dict[str, Any],
    approval_validation: dict[str, Any],
    running_revision: Optional[str],
    running_revision_source: str,
) -> dict[str, Any]:
    candidate = selected_candidate.get("selected_candidate") or {}
    blocking_reasons = list(selected_candidate.get("blocking_reasons") or [])
    blocking_reasons.extend(list(approval_validation.get("blocking_reasons") or []))
    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    return {
        "schema_version": METER_CLEANUP_PILOT_SCHEMA_VERSION,
        "pilot_id": uuid4().hex[:16],
        "executed_at": _to_iso(_utc_now()),
        "mode": METER_CLEANUP_PILOT_MODE,
        "status": "blocked",
        "original_path": candidate.get("path"),
        "quarantine_path": selected_candidate.get("planned_quarantine_path"),
        "source_sha256_before": candidate.get("sha256"),
        "quarantine_sha256_after": None,
        "bytes": int(candidate.get("bytes", 0) or 0),
        "mtime": candidate.get("mtime"),
        "approval_hash": approval_validation.get("approval_hash"),
        "rollback_instruction": "Move quarantine file back to original path and verify sha256",
        "source_move_executed": False,
        "delete_executed": False,
        "compress_executed": False,
        "truncate_executed": False,
        "batch_cleanup_executed": False,
        "checksum_match": False,
        "running_revision": running_revision,
        "running_revision_source": running_revision_source,
        "artifact_hashes": selected_candidate.get("artifact_hashes"),
        "approval_status": approval_validation.get("status"),
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": "blocked",
            "source_move_executed": False,
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
            "blocking_count": len(blocking_reasons),
        },
    }


def execute_single_file_quarantine(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    cycle_id = state_store.new_cycle_id()

    selected_candidate = build_selected_candidate(policy=current)
    write_selected_candidate(selected_candidate, policy=current)
    approval_template = build_approval_template(selected_candidate=selected_candidate)
    write_approval_template(approval_template, policy=current)

    approval = read_operator_approval(policy=current)
    approval_validation = validate_operator_approval(approval=approval, selected_candidate=selected_candidate)
    running_revision, running_revision_source = _resolve_running_revision()

    selected_status = str(selected_candidate.get("status") or "")
    if selected_status != "ready_for_operator_approval" or str(approval_validation.get("status") or "") != "valid":
        pilot = _build_blocked_record(
            selected_candidate=selected_candidate,
            approval_validation=approval_validation,
            running_revision=running_revision,
            running_revision_source=running_revision_source,
        )
        _write_json_atomic(_pilot_record_path(current), pilot, tmp_prefix="meter_cleanup_pilot_record_")
        completed_at = _utc_now()
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_quarantine_pilot_quarantine_one",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=0,
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, pilot

    candidate = selected_candidate.get("selected_candidate") or {}
    source_path = Path(str(candidate.get("path") or "")).expanduser()
    source_sha256 = str(candidate.get("sha256") or "")
    source_mtime = str(candidate.get("mtime") or "")
    quarantine_path = Path(str(selected_candidate.get("planned_quarantine_path") or "")).expanduser()

    source_current_sha = _sha256_file(source_path)
    source_current_mtime = _mtime_iso(source_path)
    precheck_blocking: list[str] = []
    if source_current_sha != source_sha256:
        precheck_blocking.append("candidate_source_hash_drift")
    if source_current_mtime != source_mtime:
        precheck_blocking.append("candidate_source_mtime_drift")
    if quarantine_path.exists():
        precheck_blocking.append("quarantine_target_already_exists")
    if precheck_blocking:
        approval_validation = dict(approval_validation)
        approval_validation["blocking_reasons"] = list(approval_validation.get("blocking_reasons") or []) + precheck_blocking
        pilot = _build_blocked_record(
            selected_candidate=selected_candidate,
            approval_validation=approval_validation,
            running_revision=running_revision,
            running_revision_source=running_revision_source,
        )
        _write_json_atomic(_pilot_record_path(current), pilot, tmp_prefix="meter_cleanup_pilot_record_")
        completed_at = _utc_now()
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_quarantine_pilot_quarantine_one",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=0,
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, pilot

    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = quarantine_path.parent / f".{quarantine_path.name}.{uuid4().hex[:12]}.tmp"

    try:
        shutil.copyfile(str(source_path), str(tmp_path))
        tmp_sha256 = _sha256_file(tmp_path)
        if tmp_sha256 != source_sha256:
            raise RuntimeError("quarantine_temp_checksum_mismatch")

        move_method = "rename"
        try:
            os.replace(str(source_path), str(quarantine_path))
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                move_method = "cross_device_move"
                shutil.move(str(source_path), str(quarantine_path))
            else:
                raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    quarantine_sha256 = _sha256_file(quarantine_path)
    source_exists_after = source_path.exists()
    checksum_match = bool(quarantine_sha256 and source_sha256 and quarantine_sha256 == source_sha256)
    status = "success" if checksum_match and not source_exists_after else "blocked"
    blocking_reasons: list[str] = []
    if source_exists_after:
        blocking_reasons.append("source_still_exists_after_move")
    if not checksum_match:
        blocking_reasons.append("quarantine_checksum_mismatch")

    pilot = {
        "schema_version": METER_CLEANUP_PILOT_SCHEMA_VERSION,
        "pilot_id": uuid4().hex[:16],
        "executed_at": _to_iso(_utc_now()),
        "mode": METER_CLEANUP_PILOT_MODE,
        "status": status,
        "original_path": str(source_path),
        "quarantine_path": str(quarantine_path),
        "source_sha256_before": source_sha256,
        "quarantine_sha256_after": quarantine_sha256,
        "bytes": int(candidate.get("bytes", 0) or 0),
        "mtime": source_mtime,
        "approval_hash": approval_validation.get("approval_hash"),
        "rollback_instruction": f"Move {quarantine_path} back to {source_path} and verify sha256={source_sha256}",
        "source_move_executed": status == "success",
        "delete_executed": False,
        "compress_executed": False,
        "truncate_executed": False,
        "batch_cleanup_executed": False,
        "checksum_match": checksum_match,
        "move_method": move_method,
        "running_revision": running_revision,
        "running_revision_source": running_revision_source,
        "artifact_hashes": selected_candidate.get("artifact_hashes"),
        "approval_status": approval_validation.get("status"),
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "source_move_executed": status == "success",
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
            "blocking_count": len(blocking_reasons),
        },
    }
    _write_json_atomic(_pilot_record_path(current), pilot, tmp_prefix="meter_cleanup_pilot_record_")

    completed_at = _utc_now()
    record = state_store.build_record(
        cycle_id=cycle_id,
        trigger="meter_cleanup_quarantine_pilot_quarantine_one",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int(candidate.get("bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, pilot


def read_latest_pilot(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    return _read_json(_pilot_record_path(policy))
