"""Legacy meter cleanup preview (read-only, no cleanup execution)."""

from __future__ import annotations

import glob
import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
_request_meter_read_resolver = importlib.import_module("5_connectors.adapter.application.request_meter_read_resolver")
_request_evidence_read_resolver = importlib.import_module(
    "5_connectors.adapter.application.request_evidence_meter_read_resolver"
)
_metrics_read_resolver = importlib.import_module("5_connectors.adapter.application.metrics_meter_read_resolver")
_status_read_resolver = importlib.import_module("5_connectors.adapter.application.status_read_model_meter_read_resolver")
_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")

METER_CLEANUP_PREVIEW_SCHEMA_VERSION = "res-legacy-meter-cleanup-preview-v1"
METER_CLEANUP_PREVIEW_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-preview-rebuild-v1"
METER_CLEANUP_PREVIEW_MODE = "preview_only"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _preview_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_preview_file).expanduser()


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


def _file_mtime(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _record_count(path: Path) -> Optional[int]:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            return int(len(payload))
        if isinstance(payload, list):
            return int(len(payload))
    except Exception:
        return None
    return None


def _safe_mode(env_name: str, default_mode: str, sqlite_first_mode: str, legacy_mode: str) -> str:
    mode = str(os.getenv(env_name, default_mode)).strip().lower()
    if mode not in {sqlite_first_mode, legacy_mode}:
        return sqlite_first_mode
    return mode


def _read_path_flags() -> dict[str, Any]:
    request_mode = _safe_mode(
        _request_meter_read_resolver.READ_PATH_ENV,
        _request_meter_read_resolver.MODE_SQLITE_FIRST,
        _request_meter_read_resolver.MODE_SQLITE_FIRST,
        _request_meter_read_resolver.MODE_LEGACY_ONLY,
    )
    request_evidence_mode = _safe_mode(
        _request_evidence_read_resolver.READ_PATH_ENV,
        _request_evidence_read_resolver.MODE_SQLITE_FIRST,
        _request_evidence_read_resolver.MODE_SQLITE_FIRST,
        _request_evidence_read_resolver.MODE_LEGACY_ONLY,
    )
    metrics_mode = _safe_mode(
        _metrics_read_resolver.READ_PATH_ENV,
        _metrics_read_resolver.MODE_SQLITE_FIRST,
        _metrics_read_resolver.MODE_SQLITE_FIRST,
        _metrics_read_resolver.MODE_LEGACY_ONLY,
    )
    status_mode = _safe_mode(
        _status_read_resolver.READ_PATH_ENV,
        _status_read_resolver.MODE_SQLITE_FIRST,
        _status_read_resolver.MODE_SQLITE_FIRST,
        _status_read_resolver.MODE_LEGACY_ONLY,
    )

    request_enabled = request_mode == _request_meter_read_resolver.MODE_SQLITE_FIRST
    request_evidence_enabled = request_evidence_mode == _request_evidence_read_resolver.MODE_SQLITE_FIRST
    metrics_enabled = metrics_mode == _metrics_read_resolver.MODE_SQLITE_FIRST
    status_enabled = status_mode == _status_read_resolver.MODE_SQLITE_FIRST
    fallback_enabled = request_enabled or request_evidence_enabled or metrics_enabled or status_enabled

    return {
        "request_meter_switch_enabled": request_enabled,
        "request_evidence_switch_enabled": request_evidence_enabled,
        "metrics_switch_enabled": metrics_enabled,
        "status_read_model_switch_enabled": status_enabled,
        "legacy_fallback_enabled": fallback_enabled,
        "request_meter_read_mode": request_mode,
        "request_evidence_read_mode": request_evidence_mode,
        "metrics_read_mode": metrics_mode,
        "status_read_model_read_mode": status_mode,
    }


def _legacy_meter_files() -> list[dict[str, Any]]:
    data_dir = Path(_meter_store._meter_data_dir()).expanduser()
    targets: list[Path] = []
    index_path = Path(_meter_store._meter_index_path()).expanduser()
    targets.append(index_path)

    if data_dir.exists() and data_dir.is_dir():
        for path_str in sorted(glob.glob(str(data_dir / "meters_*.json"))):
            path = Path(path_str).expanduser()
            if path.name == "meters_index.json":
                continue
            targets.append(path)

    output: list[dict[str, Any]] = []
    for path in targets:
        exists = path.exists() and path.is_file()
        size = int(path.stat().st_size) if exists else 0
        output.append(
            {
                "name": path.name,
                "path": str(path),
                "exists": bool(exists),
                "bytes": size,
                "record_count": _record_count(path),
                "sha256": _sha256_file(path),
                "mtime": _file_mtime(path),
                "fallback_dependency": True,
                "read_path_dependency": True,
                "parity_dependency": True,
                "cleanup_candidate": bool(exists),
            }
        )
    return output


def build_preview(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    now = _utc_now()
    legacy_files = _legacy_meter_files()
    parity = _meter_storage_v2.build_parity_report()
    read_path_flags = _read_path_flags()

    all_switches_enabled = (
        bool(read_path_flags.get("request_meter_switch_enabled"))
        and bool(read_path_flags.get("request_evidence_switch_enabled"))
        and bool(read_path_flags.get("metrics_switch_enabled"))
        and bool(read_path_flags.get("status_read_model_switch_enabled"))
    )
    parity_passed = str(parity.get("status") or "").lower() == "passed"
    critical_mismatch_count = int(parity.get("critical_mismatch_count") or 0)
    fallback_enabled = bool(read_path_flags.get("legacy_fallback_enabled"))

    blocking_reasons: list[str] = []
    if not parity_passed:
        blocking_reasons.append("parity_not_passed")
    if critical_mismatch_count != 0:
        blocking_reasons.append("critical_mismatch_nonzero")
    if not all_switches_enabled:
        blocking_reasons.append("not_all_sqlite_first_switches_enabled")
    if not fallback_enabled:
        blocking_reasons.append("legacy_fallback_not_enabled")
    blocking_reasons.append("backup_export_required")
    blocking_reasons.append("operator_approval_required")

    cleanup_candidates = [item for item in legacy_files if bool(item.get("cleanup_candidate"))]
    would_retain_files = [item for item in legacy_files if not bool(item.get("cleanup_candidate"))]
    estimated_reclaim_bytes = int(sum(int(item.get("bytes", 0) or 0) for item in cleanup_candidates))

    return {
        "schema_version": METER_CLEANUP_PREVIEW_SCHEMA_VERSION,
        "preview_id": state_store.new_cycle_id(),
        "generated_at": _to_iso(now),
        "mode": METER_CLEANUP_PREVIEW_MODE,
        "status": "blocked",
        "cleanup_allowed": False,
        "legacy_files": legacy_files,
        "would_cleanup_files": cleanup_candidates,
        "would_retain_files": would_retain_files,
        "estimated_reclaim_bytes": estimated_reclaim_bytes,
        "blocking_reasons": blocking_reasons,
        "backup_export_required": True,
        "operator_approval_required": True,
        "sqlite_parity": {
            "status": str(parity.get("status") or "unknown"),
            "critical_mismatch_count": critical_mismatch_count,
        },
        "read_path_flags": read_path_flags,
        "summary": {
            "legacy_file_count": int(len(legacy_files)),
            "candidate_file_count": int(len(cleanup_candidates)),
            "blocking_reasons_count": int(len(blocking_reasons)),
            "estimated_reclaim_bytes": estimated_reclaim_bytes,
        },
    }


def write_preview_atomic(preview: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _preview_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_preview_", suffix=".tmp", dir=str(path.parent))
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
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_preview(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = _utc_now()
    preview = build_preview(policy=current_policy)
    write_preview_atomic(preview, policy=current_policy)
    completed_at = _utc_now()

    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_cleanup_preview_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=int((preview.get("summary") or {}).get("estimated_reclaim_bytes", 0) or 0),
        error=None,
    )
    state_store.append_state_record(record, policy=current_policy)

    return {
        "schema_version": METER_CLEANUP_PREVIEW_REBUILD_SCHEMA_VERSION,
        "record": record,
        "preview": preview,
    }, preview
