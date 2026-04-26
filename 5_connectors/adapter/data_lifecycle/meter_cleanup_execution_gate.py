"""Legacy meter cleanup execution gate (gate-only, cleanup execution forbidden by default)."""

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
_backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
_backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
_backup_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
_backup_copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")
_restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
_operator_approval = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval")
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")

METER_CLEANUP_EXECUTION_GATE_SCHEMA_VERSION = "res-legacy-meter-cleanup-execution-gate-v1"
METER_CLEANUP_EXECUTION_GATE_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-execution-gate-rebuild-v1"
METER_CLEANUP_EXECUTION_GATE_MODE = "cleanup_gate_only"


def _gate_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_execution_gate_file).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_running_revision() -> tuple[Optional[str], str]:
    for key in ("OMNIMEMORA_RUNNING_REVISION", "OMNIMEMORA_ADAPTER_RUNNING_REVISION"):
        value = str(os.getenv(key, "")).strip()
        if value:
            return value, f"env:{key}"
    marker_override = str(os.getenv("OMNIMEMORA_PROMOTION_STATE_FILE", "")).strip()
    if marker_override:
        marker_candidates = [marker_override]
    else:
        marker_candidates = [
            str(Path("~/.omnimemora/service/current/.omnimemora_promotion_state.json").expanduser()),
        ]
    for raw_path in marker_candidates:
        if not raw_path:
            continue
        marker_path = Path(raw_path).expanduser()
        if not marker_path.exists() or not marker_path.is_file():
            continue
        try:
            marker_payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(marker_payload, dict):
            continue
        revision = str(marker_payload.get("repo_revision") or "").strip()
        if revision:
            return revision, f"marker:{marker_path}"
    return None, "missing"


def _source_file_hashes(cleanup_preview: Optional[dict[str, Any]]) -> dict[str, str]:
    if not isinstance(cleanup_preview, dict):
        return {}
    result: dict[str, str] = {}
    for item in cleanup_preview.get("would_cleanup_files") or []:
        if not isinstance(item, dict):
            continue
        source_path = str(item.get("path") or "").strip()
        sha256 = str(item.get("sha256") or "").strip()
        if source_path and sha256:
            result[source_path] = sha256
    return result


def build_execution_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    blocking_reasons: list[str] = []

    cleanup_preview = _cleanup_preview.read_preview(policy=current)
    backup_copy_pilot = _backup_copy_pilot.read_latest_copy_pilot(policy=current)
    restore_readback = _restore_readback.read_restore_readback_report(policy=current)
    parity = _meter_storage_v2.build_parity_report()
    backup_plan = _backup_plan.read_plan(policy=current)
    backup_readiness = _backup_readiness.read_readiness(policy=current)
    backup_manifest = _backup_manifest.read_package_manifest(policy=current)
    operator_approval = _operator_approval.read_operator_approval(policy=current)

    cleanup_preview_hash = _json_hash(cleanup_preview)
    backup_readiness_hash = _json_hash(backup_readiness)
    backup_plan_hash = _json_hash(backup_plan)
    backup_manifest_hash = _json_hash(backup_manifest)
    source_file_hashes = _source_file_hashes(cleanup_preview)
    running_revision, running_revision_source = _resolve_running_revision()

    if not isinstance(cleanup_preview, dict):
        blocking_reasons.append("cleanup_preview_missing")
    if not isinstance(backup_copy_pilot, dict):
        blocking_reasons.append("backup_copy_pilot_missing")
    else:
        if str(backup_copy_pilot.get("status") or "") not in {"success", "already_copied"}:
            blocking_reasons.append("backup_copy_pilot_not_success")
        if not bool(backup_copy_pilot.get("source_retained", False)):
            blocking_reasons.append("backup_copy_source_not_retained")
        if not bool(backup_copy_pilot.get("checksum_match", False)):
            blocking_reasons.append("backup_copy_checksum_mismatch")
        if bool(backup_copy_pilot.get("cleanup_started", False)):
            blocking_reasons.append("backup_copy_cleanup_started")
    if not isinstance(restore_readback, dict):
        blocking_reasons.append("restore_readback_missing")
    else:
        if str(restore_readback.get("status") or "") != "passed":
            blocking_reasons.append("restore_readback_not_passed")
        if not bool(restore_readback.get("source_retained", False)):
            blocking_reasons.append("restore_readback_source_not_retained")
        if not bool(restore_readback.get("checksum_match", False)):
            blocking_reasons.append("restore_readback_checksum_mismatch")
        if bool(restore_readback.get("production_restore_started", False)):
            blocking_reasons.append("restore_readback_production_restore_started")
        if bool(restore_readback.get("cleanup_started", False)):
            blocking_reasons.append("restore_readback_cleanup_started")
    if str(parity.get("status") or "").lower() != "passed":
        blocking_reasons.append("parity_not_passed")
    if int(parity.get("critical_mismatch_count", 0) or 0) != 0:
        blocking_reasons.append("critical_mismatch_nonzero")
    if not running_revision:
        blocking_reasons.append("running_revision_missing")

    expected_destination_path = str(((backup_plan or {}).get("destination_status") or {}).get("path") or "")
    approval_validation = _operator_approval.validate_operator_approval(
        approval=operator_approval,
        expected_plan_hash=backup_plan_hash,
        expected_package_manifest_hash=backup_manifest_hash,
        expected_readiness_hash=backup_readiness_hash,
        expected_cleanup_preview_hash=cleanup_preview_hash,
        expected_destination_path=expected_destination_path or None,
        now=now,
    )
    blocking_reasons.extend(list(approval_validation.get("blocking_reasons") or []))

    # RES-020 contract: default deny cleanup execution even if every prerequisite is satisfied.
    blocking_reasons.append("cleanup_execution_not_enabled_in_res020")

    dedup: list[str] = []
    seen = set()
    for reason in blocking_reasons:
        if reason not in seen:
            seen.add(reason)
            dedup.append(reason)
    blocking_reasons = dedup

    return {
        "schema_version": METER_CLEANUP_EXECUTION_GATE_SCHEMA_VERSION,
        "gate_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_EXECUTION_GATE_MODE,
        "cleanup_gate_status": "blocked",
        "cleanup_allowed": False,
        "rollback_required": True,
        "blocking_reasons": blocking_reasons,
        "required_approval_hashes": {
            "approved_plan_hash": backup_plan_hash,
            "approved_package_manifest_hash": backup_manifest_hash,
            "approved_readiness_hash": backup_readiness_hash,
            "approved_cleanup_preview_hash": cleanup_preview_hash,
        },
        "source_file_hashes": source_file_hashes,
        "running_revision": running_revision,
        "running_revision_source": running_revision_source,
        "input_refs": {
            "cleanup_preview_hash": cleanup_preview_hash,
            "backup_copy_pilot_hash": _json_hash(backup_copy_pilot),
            "restore_readback_hash": _json_hash(restore_readback),
            "parity_hash": _json_hash(parity),
        },
        "summary": {
            "cleanup_gate_status": "blocked",
            "cleanup_allowed": False,
            "rollback_required": True,
            "blocking_count": int(len(blocking_reasons)),
            "source_file_count": int(len(source_file_hashes)),
        },
    }


def write_gate_atomic(gate: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _gate_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_execution_gate_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(gate, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _gate_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_gate(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    gate = build_execution_gate(policy=current)
    write_gate_atomic(gate, policy=current)
    completed_at = datetime.now(timezone.utc)
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_cleanup_execution_gate_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((gate.get("summary") or {}).get("source_file_count", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, gate
