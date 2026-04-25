"""Evidence/telemetry retention manifest (inventory only, non-destructive)."""

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

from .policy import DataLifecyclePolicy, load_policy
from . import state_store

RETENTION_MANIFEST_SCHEMA_VERSION = "dlp-retention-manifest-v1"
RETENTION_REBUILD_SCHEMA_VERSION = "dlp-retention-manifest-rebuild-v1"

TRACEABILITY_KEYS_BY_KIND = {
    "compile_events": ["request_id", "agent_id", "timestamp"],
    "proxy_events": ["request_id", "agent_id", "timestamp"],
    "trace_events": ["trace_id", "request_id", "timestamp"],
    "meter_index": ["request_id", "tenant", "agent", "timestamp"],
    "meter_tenant": ["request_id", "tenant", "agent", "timestamp"],
    "dlp_summary": ["family_id", "generated_at"],
    "dlp_ledger": ["cycle_id", "trigger", "status", "completed_at"],
}


def _manifest_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.retention_manifest_file).expanduser()


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


def _line_count_file(path: Path) -> Optional[int]:
    if not path.exists() or not path.is_file():
        return None
    count = 0
    with path.open("rb") as fh:
        for _line in fh:
            count += 1
    return count


def _file_mtime(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _artifact_entry(
    *,
    name: str,
    kind: str,
    path: Path,
    eligible_for_future_archive: bool = True,
) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    size = int(path.stat().st_size) if exists else 0
    sha256 = _sha256_file(path) if exists else None
    line_count = _line_count_file(path) if exists else None
    mtime = _file_mtime(path) if exists else None
    return {
        "name": name,
        "kind": kind,
        "path": str(path),
        "exists": bool(exists),
        "bytes": int(size),
        "sha256": sha256,
        "mtime": mtime,
        "line_count": line_count,
        "traceability_keys": list(TRACEABILITY_KEYS_BY_KIND.get(kind, [])),
        "eligible_for_future_archive": bool(eligible_for_future_archive),
    }


def _resolve_artifact_targets(policy: DataLifecyclePolicy) -> list[tuple[str, str, Path]]:
    compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")
    proxy_store = importlib.import_module("5_connectors.adapter.infrastructure.proxy_store")
    trace_events = importlib.import_module("5_connectors.adapter.trace_events")
    meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")

    summary_path = Path(policy.summary_file).expanduser()
    ledger_path = Path(policy.maintenance_state_file).expanduser()
    meter_index = Path(meter_store._meter_index_path()).expanduser()
    meter_data_dir = Path(meter_store._meter_data_dir()).expanduser()

    targets: list[tuple[str, str, Path]] = [
        ("compile_events", "compile_events", Path(compile_store.COMPILE_EVENTS_PATH).expanduser()),
        ("proxy_events", "proxy_events", Path(proxy_store.EVENTS_PATH).expanduser()),
        ("trace_events", "trace_events", Path(trace_events.TRACE_EVENTS_PATH).expanduser()),
        ("meter_index", "meter_index", meter_index),
        ("dlp_summary", "dlp_summary", summary_path),
        ("dlp_ledger", "dlp_ledger", ledger_path),
    ]

    if meter_data_dir.exists() and meter_data_dir.is_dir():
        tenant_files = sorted(meter_data_dir.glob("meters_*.json"))
        for path in tenant_files:
            if path.name == "meters_index.json":
                continue
            targets.append((f"meter_tenant:{path.stem}", "meter_tenant", path))
    return targets


def build_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    try:
        targets = _resolve_artifact_targets(current_policy)
    except Exception as exc:
        targets = []
        warnings.append({"code": "artifact_discovery_failed", "message": str(exc)})

    for name, kind, path in targets:
        try:
            entry = _artifact_entry(name=name, kind=kind, path=path)
            if not entry["exists"]:
                warnings.append(
                    {
                        "code": "artifact_missing",
                        "artifact": name,
                        "path": str(path),
                    }
                )
            artifacts.append(entry)
        except Exception as exc:
            artifacts.append(
                {
                    "name": name,
                    "kind": kind,
                    "path": str(path),
                    "exists": False,
                    "bytes": 0,
                    "sha256": None,
                    "mtime": None,
                    "line_count": None,
                    "traceability_keys": list(TRACEABILITY_KEYS_BY_KIND.get(kind, [])),
                    "eligible_for_future_archive": True,
                }
            )
            warnings.append(
                {
                    "code": "artifact_scan_error",
                    "artifact": name,
                    "path": str(path),
                    "message": str(exc),
                }
            )

    total_bytes = int(sum(int(item.get("bytes", 0) or 0) for item in artifacts))
    exists_count = int(sum(1 for item in artifacts if item.get("exists")))
    missing_count = int(len(artifacts) - exists_count)

    return {
        "schema_version": RETENTION_MANIFEST_SCHEMA_VERSION,
        "manifest_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": "inventory_only",
        "artifacts": artifacts,
        "summary": {
            "artifact_count": len(artifacts),
            "exists_count": exists_count,
            "missing_count": missing_count,
            "total_bytes": total_bytes,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_manifest_atomic(manifest: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _manifest_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_retention_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _manifest_path(policy)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    manifest: dict[str, Any]
    try:
        manifest = build_manifest(policy=current_policy)
        write_manifest_atomic(manifest, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="retention_manifest_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((manifest.get("summary") or {}).get("total_bytes", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, manifest
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="retention_manifest_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
