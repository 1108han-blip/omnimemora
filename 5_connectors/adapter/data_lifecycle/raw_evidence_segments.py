"""Observe-only raw evidence segmentation for compile/proxy/trace JSONL streams."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

RAW_EVIDENCE_SEGMENTS_MANIFEST_SCHEMA_VERSION = "dlp-raw-evidence-segments-manifest-v1"
RAW_EVIDENCE_SEGMENTS_REBUILD_SCHEMA_VERSION = "dlp-raw-evidence-segments-rebuild-v1"
RAW_EVIDENCE_SEGMENTS_MODE = "dual_write_observe_only"
SUPPORTED_KINDS = {"compile_events", "proxy_events", "trace_events"}
_LOCK_BY_KIND = {kind: threading.Lock() for kind in SUPPORTED_KINDS}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _manifest_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.raw_evidence_segments_manifest_file).expanduser()


def _segments_root(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.raw_evidence_segments_root).expanduser()


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


def _line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    count = 0
    with path.open("rb") as fh:
        for _line in fh:
            count += 1
    return count


def _new_segment_id(kind: str, now: datetime) -> str:
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    return f"{kind}-{ts}-{uuid.uuid4().hex[:8]}"


def _segment_path(kind: str, segment_id: str, *, policy: DataLifecyclePolicy) -> Path:
    return _segments_root(policy) / kind / f"{segment_id}.jsonl"


def _new_manifest(*, now: datetime) -> dict[str, Any]:
    return {
        "schema_version": RAW_EVIDENCE_SEGMENTS_MANIFEST_SCHEMA_VERSION,
        "manifest_id": uuid.uuid4().hex[:16],
        "generated_at": _to_iso(now),
        "mode": RAW_EVIDENCE_SEGMENTS_MODE,
        "segments": [],
        "summary": {
            "total_segments": 0,
            "active_segments": 0,
            "sealed_segments": 0,
            "total_bytes": 0,
            "warnings_count": 0,
        },
        "warnings": [],
    }


def _read_manifest_raw(policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def _render_summary(manifest: dict[str, Any]) -> dict[str, int]:
    segments = manifest.get("segments") or []
    active = 0
    sealed = 0
    total_bytes = 0
    for item in segments:
        if str(item.get("state") or "") == "active":
            active += 1
        if str(item.get("state") or "") == "sealed":
            sealed += 1
        total_bytes += int(item.get("bytes", 0) or 0)
    warnings = manifest.get("warnings") or []
    return {
        "total_segments": len(segments),
        "active_segments": active,
        "sealed_segments": sealed,
        "total_bytes": total_bytes,
        "warnings_count": len(warnings),
    }


def _normalize_manifest(manifest: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    output = dict(manifest)
    output["schema_version"] = RAW_EVIDENCE_SEGMENTS_MANIFEST_SCHEMA_VERSION
    output["mode"] = RAW_EVIDENCE_SEGMENTS_MODE
    output["generated_at"] = _to_iso(now)
    output["segments"] = list(manifest.get("segments") or [])
    output["warnings"] = list(manifest.get("warnings") or [])
    output["summary"] = _render_summary(output)
    return output


def write_manifest_atomic(manifest: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _manifest_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_raw_evidence_segments_", suffix=".tmp", dir=str(path.parent))
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
    payload = _read_manifest_raw(policy)
    if not isinstance(payload, dict):
        return None
    return _normalize_manifest(payload, now=_utc_now())


def _active_segment_entry(manifest: dict[str, Any], *, kind: str) -> Optional[dict[str, Any]]:
    for item in reversed(manifest.get("segments") or []):
        if item.get("kind") == kind and item.get("state") == "active":
            return item
    return None


def _segment_events_window(path: Path) -> tuple[Optional[str], Optional[str]]:
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    if not path.exists() or not path.is_file():
        return None, None
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                text = raw.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except Exception:
                    continue
                value = payload.get("timestamp")
                if not isinstance(value, (int, float)):
                    continue
                iso = datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
                if first_ts is None:
                    first_ts = iso
                last_ts = iso
    except Exception:
        return None, None
    return first_ts, last_ts


def _record_degraded(*, kind: str, error: str, policy: DataLifecyclePolicy) -> None:
    started_at = _utc_now()
    completed_at = _utc_now()
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="raw_evidence_segments_dual_write",
        started_at=started_at,
        completed_at=completed_at,
        status="degraded",
        bytes_scanned=0,
        error=error,
    )
    record["kind"] = kind
    state_store.append_state_record(record, policy=policy)


def append_event_dual_write_observe_only(
    *,
    kind: str,
    event: dict[str, Any],
    policy: Optional[DataLifecyclePolicy] = None,
) -> None:
    current = policy or load_policy()
    if str(current.raw_evidence_segments_mode or "").strip() != RAW_EVIDENCE_SEGMENTS_MODE:
        return
    if kind not in SUPPORTED_KINDS:
        return

    lock = _LOCK_BY_KIND[kind]
    now = _utc_now()
    line = json.dumps(event, ensure_ascii=False) + "\n"
    try:
        with lock:
            manifest = _read_manifest_raw(current)
            if not isinstance(manifest, dict):
                manifest = _new_manifest(now=now)
            if not isinstance(manifest.get("segments"), list):
                manifest["segments"] = []

            segment = _active_segment_entry(manifest, kind=kind)
            if segment is None:
                segment_id = _new_segment_id(kind, now)
                segment_path = _segment_path(kind, segment_id, policy=current)
                segment = {
                    "kind": kind,
                    "segment_id": segment_id,
                    "state": "active",
                    "path": str(segment_path),
                    "bytes": 0,
                    "line_count": 0,
                    "sha256": None,
                    "created_at": _to_iso(now),
                    "sealed_at": None,
                    "first_event_at": None,
                    "last_event_at": None,
                }
                manifest["segments"].append(segment)

            segment_path = Path(str(segment.get("path") or "")).expanduser()
            segment_path.parent.mkdir(parents=True, exist_ok=True)
            with segment_path.open("a", encoding="utf-8") as fh:
                fh.write(line)

            segment["bytes"] = int(segment_path.stat().st_size)
            segment["line_count"] = int(segment.get("line_count", 0) or 0) + 1
            event_ts = event.get("timestamp")
            if isinstance(event_ts, (int, float)):
                event_iso = datetime.fromtimestamp(float(event_ts), tz=timezone.utc).isoformat()
            else:
                event_iso = _to_iso(now)
            if not segment.get("first_event_at"):
                segment["first_event_at"] = event_iso
            segment["last_event_at"] = event_iso

            created_at = datetime.fromisoformat(str(segment.get("created_at")).replace("Z", "+00:00"))
            age_seconds = max(0.0, (now - created_at).total_seconds())
            if (
                int(segment.get("bytes", 0) or 0) >= int(current.raw_evidence_segment_max_bytes)
                or age_seconds >= int(current.raw_evidence_segment_max_age_seconds)
            ):
                segment["state"] = "sealed"
                segment["sealed_at"] = _to_iso(now)
                segment["sha256"] = _sha256_file(segment_path)
                next_segment_id = _new_segment_id(kind, now)
                next_segment_path = _segment_path(kind, next_segment_id, policy=current)
                manifest["segments"].append(
                    {
                        "kind": kind,
                        "segment_id": next_segment_id,
                        "state": "active",
                        "path": str(next_segment_path),
                        "bytes": 0,
                        "line_count": 0,
                        "sha256": None,
                        "created_at": _to_iso(now),
                        "sealed_at": None,
                        "first_event_at": None,
                        "last_event_at": None,
                    }
                )

            normalized = _normalize_manifest(manifest, now=now)
            write_manifest_atomic(normalized, policy=current)
    except Exception as exc:
        _record_degraded(kind=kind, error=str(exc), policy=current)


def _scan_segments(policy: DataLifecyclePolicy) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = _segments_root(policy)
    warnings: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    previous = _read_manifest_raw(policy) or {}
    previous_map: dict[str, dict[str, Any]] = {}
    for item in previous.get("segments") or []:
        p = str(item.get("path") or "")
        if p:
            previous_map[p] = item

    for kind in sorted(SUPPORTED_KINDS):
        kind_dir = root / kind
        if not kind_dir.exists():
            continue
        files = sorted(kind_dir.glob("*.jsonl"))
        if not files:
            continue
        latest_path = max(files, key=lambda path: path.stat().st_mtime if path.exists() else 0)
        for path in files:
            try:
                size = int(path.stat().st_size)
                line_count = _line_count(path)
                first_event_at, last_event_at = _segment_events_window(path)
                previous_entry = previous_map.get(str(path), {})
                previous_state = str(previous_entry.get("state") or "")
                if previous_state == "sealed":
                    state = "sealed"
                else:
                    state = "active" if path == latest_path else "sealed"
                created_at = previous_entry.get("created_at")
                if not isinstance(created_at, str) or not created_at:
                    created_at = datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc).isoformat()
                sealed_at = previous_entry.get("sealed_at")
                if state == "sealed" and not sealed_at:
                    sealed_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
                if state == "active":
                    sealed_at = None
                segments.append(
                    {
                        "kind": kind,
                        "segment_id": path.stem,
                        "state": state,
                        "path": str(path),
                        "bytes": size,
                        "line_count": line_count,
                        "sha256": _sha256_file(path),
                        "created_at": created_at,
                        "sealed_at": sealed_at,
                        "first_event_at": first_event_at,
                        "last_event_at": last_event_at,
                    }
                )
            except Exception as exc:
                warnings.append(
                    {
                        "code": "segment_scan_error",
                        "kind": kind,
                        "path": str(path),
                        "message": str(exc),
                    }
                )
    return segments, warnings


def build_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = _utc_now()
    segments, warnings = _scan_segments(current)
    manifest = _new_manifest(now=now)
    manifest["segments"] = segments
    manifest["warnings"] = warnings
    manifest["summary"] = _render_summary(manifest)
    return manifest


def rebuild_manifest(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    cycle_id = state_store.new_cycle_id()
    manifest: dict[str, Any]
    try:
        manifest = build_manifest(policy=current)
        write_manifest_atomic(manifest, policy=current)
        completed_at = _utc_now()
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="raw_evidence_segments_manifest_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((manifest.get("summary") or {}).get("total_bytes", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, manifest
    except Exception as exc:
        completed_at = _utc_now()
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="raw_evidence_segments_manifest_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise
