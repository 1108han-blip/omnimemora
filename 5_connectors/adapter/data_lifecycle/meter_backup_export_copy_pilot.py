"""Single copy-only backup export pilot for legacy meter files."""

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

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
_execution_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate")

METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION = "res-legacy-meter-backup-export-copy-pilot-v1"
METER_BACKUP_EXPORT_COPY_PILOT_MODE = "single_copy_pilot_only"


def _record_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_copy_pilot_record_file).expanduser()


def _pilot_root(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_copy_pilot_root).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _is_legacy_meter_file(path: Path) -> bool:
    name = path.name
    return name == "meters_index.json" or (name.startswith("meters_") and name.endswith(".json"))


def _manifest_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("files")
    if not isinstance(raw, list):
        raw = manifest.get("would_export_files")
    files: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, dict):
            files.append(item)
    return files


def _normalize_manifest_entry(entry: dict[str, Any]) -> dict[str, Any]:
    p = Path(str(entry.get("path") or "")).expanduser()
    exists = p.exists() and p.is_file()
    size = int(entry.get("bytes", 0) or 0)
    if exists:
        size = int(p.stat().st_size)
    return {
        "name": str(entry.get("name") or p.name),
        "path": str(p),
        "bytes": size,
        "exists": bool(exists),
        "sha256": str(entry.get("sha256") or "") or _sha256_file(p),
    }


def _select_candidate(manifest: dict[str, Any]) -> tuple[Optional[dict[str, Any]], list[str]]:
    blocking: list[str] = []
    candidates = [_normalize_manifest_entry(item) for item in _manifest_files(manifest)]
    if not candidates:
        blocking.append("backup_export_package_manifest_empty")
        return None, blocking
    legacy_candidates = []
    for item in candidates:
        p = Path(item["path"])
        if _is_legacy_meter_file(p):
            legacy_candidates.append(item)
    if not legacy_candidates:
        blocking.append("no_legacy_meter_candidate_in_manifest")
        return None, blocking
    existing_legacy = [c for c in legacy_candidates if c["exists"]]
    if not existing_legacy:
        blocking.append("selected_source_missing")
        return None, blocking
    existing_legacy.sort(key=lambda x: (int(x.get("bytes", 0) or 0), str(x.get("path") or "")))
    return existing_legacy[0], blocking


def _copy_file(src: Path, dst: Path) -> None:
    shutil.copyfile(str(src), str(dst))


def _deterministic_target_name(source_path: Path, source_sha256: str) -> str:
    safe_name = source_path.name
    return f"{safe_name}.{source_sha256[:16]}.pilotcopy"


def _write_record_atomic(record: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _record_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_backup_export_copy_pilot_", suffix=".tmp", dir=str(path.parent))
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


def _build_blocked_record(
    *,
    policy: DataLifecyclePolicy,
    gate: Optional[dict[str, Any]],
    package_manifest: Optional[dict[str, Any]],
    blocking_reasons: list[str],
    pilot_scope_override: bool,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    gate_ref = {
        "schema_version": _execution_gate.METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION,
        "status": "missing",
        "allowed": False,
        "artifact_hash": None,
    }
    if isinstance(gate, dict):
        gate_ref = {
            "schema_version": str(gate.get("schema_version") or _execution_gate.METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION),
            "status": str(gate.get("status") or "blocked"),
            "allowed": bool(gate.get("allowed") is True),
            "artifact_hash": _json_hash(gate),
        }
    manifest_ref = {
        "schema_version": _package_manifest.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION,
        "status": "missing",
        "artifact_hash": None,
    }
    if isinstance(package_manifest, dict):
        manifest_ref = {
            "schema_version": str(
                package_manifest.get("schema_version")
                or _package_manifest.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION
            ),
            "status": str(package_manifest.get("status") or "present"),
            "artifact_hash": _json_hash(package_manifest),
        }
    return {
        "schema_version": METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION,
        "pilot_id": uuid4().hex[:16],
        "executed_at": now.isoformat(),
        "mode": METER_BACKUP_EXPORT_COPY_PILOT_MODE,
        "status": "blocked",
        "pilot_scope_override": bool(pilot_scope_override),
        "full_export_allowed": bool(gate_ref.get("allowed") is True),
        "gate_ref": gate_ref,
        "package_manifest_ref": manifest_ref,
        "selected_candidate": None,
        "target_path": None,
        "copied_bytes": 0,
        "source_sha256": None,
        "copied_sha256": None,
        "checksum_match": False,
        "source_retained": True,
        "cleanup_started": False,
        "read_path_unchanged": True,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": "blocked",
            "source_retained": True,
            "checksum_match": False,
            "cleanup_started": False,
            "read_path_unchanged": True,
            "pilot_scope_override": bool(pilot_scope_override),
            "blocking_count": len(blocking_reasons),
        },
    }


def run_one_copy_pilot(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        gate = _execution_gate.read_gate(policy=current)
        package_manifest = _package_manifest.read_package_manifest(policy=current)
        blocking: list[str] = []
        pilot_scope_override = False

        if not isinstance(gate, dict):
            blocking.append("execution_gate_missing")
        else:
            gate_allowed = bool(gate.get("allowed") is True)
            gate_blocking = list(gate.get("blocking_reasons") or [])
            if not gate_allowed:
                if "missing_operator_approval" in gate_blocking:
                    if bool(current.meter_backup_export_copy_pilot_allow_override):
                        pilot_scope_override = True
                    else:
                        blocking.append("blocked_missing_operator_approval")
                else:
                    blocking.append("execution_gate_blocked")
                if not pilot_scope_override:
                    blocking.extend(gate_blocking)

        if not isinstance(package_manifest, dict):
            blocking.append("backup_export_package_manifest_missing")

        selected_candidate: Optional[dict[str, Any]] = None
        if isinstance(package_manifest, dict):
            selected_candidate, select_blocking = _select_candidate(package_manifest)
            blocking.extend(select_blocking)

        dedup: list[str] = []
        seen = set()
        for reason in blocking:
            if reason not in seen:
                seen.add(reason)
                dedup.append(reason)
        blocking = dedup

        if blocking or selected_candidate is None:
            pilot = _build_blocked_record(
                policy=current,
                gate=gate if isinstance(gate, dict) else None,
                package_manifest=package_manifest if isinstance(package_manifest, dict) else None,
                blocking_reasons=blocking or ["copy_pilot_blocked"],
                pilot_scope_override=pilot_scope_override,
            )
            _write_record_atomic(pilot, policy=current)
            completed_at = datetime.now(timezone.utc)
            record = state_store.build_record(
                cycle_id=cycle_id,
                trigger="meter_backup_export_copy_pilot_run_one",
                started_at=started_at,
                completed_at=completed_at,
                status="success",
                bytes_scanned=0,
                error=None,
            )
            state_store.append_state_record(record, policy=current)
            return record, pilot

        source_path = Path(str(selected_candidate["path"])).expanduser()
        source_sha = _sha256_file(source_path)
        if not source_sha:
            pilot = _build_blocked_record(
                policy=current,
                gate=gate,
                package_manifest=package_manifest,
                blocking_reasons=["selected_source_missing"],
                pilot_scope_override=pilot_scope_override,
            )
            _write_record_atomic(pilot, policy=current)
            completed_at = datetime.now(timezone.utc)
            record = state_store.build_record(
                cycle_id=cycle_id,
                trigger="meter_backup_export_copy_pilot_run_one",
                started_at=started_at,
                completed_at=completed_at,
                status="success",
                bytes_scanned=0,
                error=None,
            )
            state_store.append_state_record(record, policy=current)
            return record, pilot

        root = _pilot_root(current)
        root.mkdir(parents=True, exist_ok=True)
        target_name = _deterministic_target_name(source_path, source_sha)
        target_path = root / target_name

        copied_status = "copied"
        copied_bytes = int(source_path.stat().st_size)
        if target_path.exists():
            existing_sha = _sha256_file(target_path)
            if existing_sha == source_sha:
                copied_status = "already_copied"
            else:
                pilot = _build_blocked_record(
                    policy=current,
                    gate=gate,
                    package_manifest=package_manifest,
                    blocking_reasons=["target_conflict"],
                    pilot_scope_override=pilot_scope_override,
                )
                pilot["selected_candidate"] = selected_candidate
                pilot["target_path"] = str(target_path)
                pilot["source_sha256"] = source_sha
                pilot["copied_sha256"] = existing_sha
                _write_record_atomic(pilot, policy=current)
                completed_at = datetime.now(timezone.utc)
                record = state_store.build_record(
                    cycle_id=cycle_id,
                    trigger="meter_backup_export_copy_pilot_run_one",
                    started_at=started_at,
                    completed_at=completed_at,
                    status="success",
                    bytes_scanned=0,
                    error=None,
                )
                state_store.append_state_record(record, policy=current)
                return record, pilot
        else:
            _copy_file(source_path, target_path)

        copied_sha = _sha256_file(target_path)
        checksum_match = copied_sha == source_sha
        status = "success" if checksum_match else "blocked"
        blocking_reasons = [] if checksum_match else ["checksum_mismatch"]
        now = datetime.now(timezone.utc)
        pilot = {
            "schema_version": METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION,
            "pilot_id": uuid4().hex[:16],
            "executed_at": now.isoformat(),
            "mode": METER_BACKUP_EXPORT_COPY_PILOT_MODE,
            "status": copied_status if checksum_match and copied_status == "already_copied" else status,
            "pilot_scope_override": bool(pilot_scope_override),
            "full_export_allowed": bool((gate or {}).get("allowed") is True),
            "gate_ref": {
                "schema_version": str(
                    (gate or {}).get("schema_version") or _execution_gate.METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION
                ),
                "status": str((gate or {}).get("status") or "missing"),
                "allowed": bool((gate or {}).get("allowed") is True),
                "artifact_hash": _json_hash(gate),
            },
            "package_manifest_ref": {
                "schema_version": str(
                    (package_manifest or {}).get("schema_version")
                    or _package_manifest.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION
                ),
                "status": str((package_manifest or {}).get("status") or "missing"),
                "artifact_hash": _json_hash(package_manifest),
            },
            "selected_candidate": selected_candidate,
            "target_path": str(target_path),
            "copied_bytes": copied_bytes,
            "source_sha256": source_sha,
            "copied_sha256": copied_sha,
            "checksum_match": bool(checksum_match),
            "source_retained": True,
            "cleanup_started": False,
            "read_path_unchanged": True,
            "blocking_reasons": blocking_reasons,
            "summary": {
                "status": copied_status if checksum_match and copied_status == "already_copied" else status,
                "source_retained": True,
                "checksum_match": bool(checksum_match),
                "cleanup_started": False,
                "read_path_unchanged": True,
                "pilot_scope_override": bool(pilot_scope_override),
                "blocking_count": len(blocking_reasons),
            },
        }
        _write_record_atomic(pilot, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_backup_export_copy_pilot_run_one",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=copied_bytes,
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, pilot
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_backup_export_copy_pilot_run_one",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise


def read_latest_copy_pilot(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _record_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None
