"""Single-artifact reversible archive pilot executor (copy-only)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_transaction, state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_PILOT_RECORD_SCHEMA_VERSION = "dlp-archive-pilot-record-v1"
ARCHIVE_PILOT_RECORD_MODE = "copy_to_archive_only"
_ALLOWED_KINDS = {"compile_events", "proxy_events"}


def _pilot_root(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_pilot_root).expanduser()


def _pilot_record_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_pilot_record_file).expanduser()


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


def _load_gate_and_approval(policy: DataLifecyclePolicy) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_execution_gate")
    approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_approval")
    gate = gate_mod.read_gate(policy=policy)
    approval = approval_mod.read_approval(policy=policy)
    return gate, approval


def _select_candidate(preview: dict[str, Any]) -> Optional[dict[str, Any]]:
    items = preview.get("items")
    if not isinstance(items, list):
        return None
    eligible_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        if kind not in _ALLOWED_KINDS:
            continue
        source_path = str(item.get("source_path") or "").strip()
        source_bytes = int(item.get("source_bytes", 0) or 0)
        if not source_path:
            continue
        eligible_items.append(item)
    if not eligible_items:
        return None
    eligible_items.sort(key=lambda item: (int(item.get("source_bytes", 0) or 0), str(item.get("source_path") or "")))
    return eligible_items[0]


def _build_archive_path(*, policy: DataLifecyclePolicy, pilot_id: str, source_path: Path, source_sha256: str) -> Path:
    root = _pilot_root(policy)
    suffix = source_sha256[:12]
    return root / pilot_id / f"{source_path.name}.{suffix}.copy"


def _record_blocked(
    *,
    pilot_id: str,
    reason: str,
    gate: Optional[dict[str, Any]],
    candidate: Optional[dict[str, Any]],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "schema_version": ARCHIVE_PILOT_RECORD_SCHEMA_VERSION,
        "pilot_id": pilot_id,
        "generated_at": now.isoformat(),
        "mode": ARCHIVE_PILOT_RECORD_MODE,
        "status": "blocked",
        "message": reason,
        "gate_ref": {
            "gate_id": (gate or {}).get("gate_id"),
            "allowed": (gate or {}).get("allowed"),
            "status": (gate or {}).get("status"),
        },
        "source_path": (candidate or {}).get("source_path"),
        "source_kind": (candidate or {}).get("kind"),
        "source_bytes": int((candidate or {}).get("source_bytes", 0) or 0),
        "source_sha256": (candidate or {}).get("source_sha256"),
        "archive_path": None,
        "archive_bytes": 0,
        "archive_sha256": None,
        "checksum_match": False,
        "source_retained": True,
        "read_path_unchanged": True,
        "restore_key": (candidate or {}).get("restore_key"),
        "rollback_hint": "delete archive copy and keep source as-is",
    }


def write_pilot_record_atomic(record: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _pilot_record_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_pilot_", suffix=".tmp", dir=str(path.parent))
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


def read_latest_pilot_record(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _pilot_record_path(policy)
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _copy_file_atomic(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_copy_", suffix=".tmp", dir=str(dst.parent))
    try:
        os.close(fd)
        shutil.copyfile(str(src), tmp)
        with open(tmp, "rb") as fh:
            os.fsync(fh.fileno())
        os.replace(tmp, str(dst))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def copy_one_pilot(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    pilot_id = uuid4().hex[:12]
    gate, approval = _load_gate_and_approval(current_policy)
    preview = archive_transaction.read_preview(policy=current_policy)

    def append_record(status: str, bytes_scanned: int, error: Optional[str]) -> dict[str, Any]:
        completed_at = datetime.now(timezone.utc)
        rec = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_pilot_copy_one",
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            bytes_scanned=bytes_scanned,
            error=error,
        )
        state_store.append_state_record(rec, policy=current_policy)
        return rec

    if not isinstance(gate, dict) or not bool(gate.get("allowed")):
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="execution_gate_not_allowed",
            gate=gate,
            candidate=None,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "execution_gate_not_allowed")
        return rec, blocked

    approval_status = str((gate.get("approval") or {}).get("status") or "")
    if approval_status != "valid" or not isinstance(approval, dict):
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="approval_not_valid",
            gate=gate,
            candidate=None,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "approval_not_valid")
        return rec, blocked

    expires_at_dt = _parse_iso_utc(approval.get("expires_at"))
    if expires_at_dt is None or expires_at_dt <= datetime.now(timezone.utc):
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="approval_expired",
            gate=gate,
            candidate=None,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "approval_expired")
        return rec, blocked

    if not isinstance(preview, dict):
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="missing_transaction_preview",
            gate=gate,
            candidate=None,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "missing_transaction_preview")
        return rec, blocked

    candidate = _select_candidate(preview)
    if not isinstance(candidate, dict):
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="no_eligible_low_risk_candidate",
            gate=gate,
            candidate=None,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "no_eligible_low_risk_candidate")
        return rec, blocked

    source_path = Path(str(candidate.get("source_path") or "")).expanduser()
    expected_sha256 = str(candidate.get("source_sha256") or "")
    if not source_path.exists() or not source_path.is_file():
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="source_missing",
            gate=gate,
            candidate=candidate,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "source_missing")
        return rec, blocked

    actual_source_sha256 = _sha256_file(source_path)
    if not actual_source_sha256 or actual_source_sha256 != expected_sha256:
        blocked = _record_blocked(
            pilot_id=pilot_id,
            reason="preview_source_checksum_mismatch",
            gate=gate,
            candidate=candidate,
        )
        write_pilot_record_atomic(blocked, policy=current_policy)
        rec = append_record("blocked", 0, "preview_source_checksum_mismatch")
        return rec, blocked

    existing = read_latest_pilot_record(policy=current_policy)
    if isinstance(existing, dict):
        same_source = (
            str(existing.get("source_path") or "") == str(source_path)
            and str(existing.get("source_sha256") or "") == actual_source_sha256
        )
        existing_archive = Path(str(existing.get("archive_path") or "")).expanduser()
        if same_source and existing_archive.exists() and existing_archive.is_file():
            archive_sha = _sha256_file(existing_archive)
            if archive_sha == actual_source_sha256:
                rec = append_record("success", int(existing_archive.stat().st_size), None)
                existing_copy = dict(existing)
                existing_copy["status"] = "already_copied"
                existing_copy["message"] = "pilot copy already exists"
                return rec, existing_copy

    archive_path = _build_archive_path(
        policy=current_policy,
        pilot_id=pilot_id,
        source_path=source_path,
        source_sha256=actual_source_sha256,
    )

    try:
        _copy_file_atomic(source_path, archive_path)
        archive_sha = _sha256_file(archive_path)
        checksum_match = archive_sha == actual_source_sha256
        archive_bytes = int(archive_path.stat().st_size) if archive_path.exists() else 0

        record_payload = {
            "schema_version": ARCHIVE_PILOT_RECORD_SCHEMA_VERSION,
            "pilot_id": pilot_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": ARCHIVE_PILOT_RECORD_MODE,
            "status": "success" if checksum_match else "failed",
            "message": "pilot copy completed" if checksum_match else "pilot checksum mismatch after copy",
            "gate_ref": {
                "gate_id": gate.get("gate_id"),
                "allowed": gate.get("allowed"),
                "status": gate.get("status"),
            },
            "source_path": str(source_path),
            "source_kind": str(candidate.get("kind") or ""),
            "source_bytes": int(source_path.stat().st_size),
            "source_sha256": actual_source_sha256,
            "archive_path": str(archive_path),
            "archive_bytes": archive_bytes,
            "archive_sha256": archive_sha,
            "checksum_match": bool(checksum_match),
            "source_retained": source_path.exists() and source_path.is_file(),
            "read_path_unchanged": True,
            "restore_key": candidate.get("restore_key"),
            "rollback_hint": "delete archive copy file to rollback; source remains unchanged",
        }
        write_pilot_record_atomic(record_payload, policy=current_policy)
        rec = append_record(
            "success" if checksum_match else "failed",
            archive_bytes,
            None if checksum_match else "pilot_checksum_mismatch",
        )
        return rec, record_payload
    except Exception as exc:
        failed_record = {
            "schema_version": ARCHIVE_PILOT_RECORD_SCHEMA_VERSION,
            "pilot_id": pilot_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": ARCHIVE_PILOT_RECORD_MODE,
            "status": "failed",
            "message": str(exc),
            "gate_ref": {
                "gate_id": (gate or {}).get("gate_id"),
                "allowed": (gate or {}).get("allowed"),
                "status": (gate or {}).get("status"),
            },
            "source_path": str(source_path),
            "source_kind": str(candidate.get("kind") or ""),
            "source_bytes": int(source_path.stat().st_size) if source_path.exists() else 0,
            "source_sha256": actual_source_sha256,
            "archive_path": str(archive_path),
            "archive_bytes": int(archive_path.stat().st_size) if archive_path.exists() else 0,
            "archive_sha256": _sha256_file(archive_path) if archive_path.exists() else None,
            "checksum_match": False,
            "source_retained": source_path.exists() and source_path.is_file(),
            "read_path_unchanged": True,
            "restore_key": candidate.get("restore_key"),
            "rollback_hint": "delete archive copy file to rollback; source remains unchanged",
        }
        write_pilot_record_atomic(failed_record, policy=current_policy)
        rec = append_record("failed", 0, str(exc))
        return rec, failed_record
