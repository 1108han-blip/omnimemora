"""Maintenance state ledger store for Data Lifecycle Plane."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from ..log_segments import enforce_jsonl_retention, read_segment_lines
from .policy import DataLifecyclePolicy, load_policy


RETENTION_DAYS = int(os.getenv("OMNIMEMORA_MAINTENANCE_STATE_RETENTION_DAYS", os.getenv("OMNIMEMORA_INTERNAL_LOG_RETENTION_DAYS", "7")))
MAX_RECENT_READ_LINES = int(os.getenv("OMNIMEMORA_MAINTENANCE_STATE_MAX_READ_LINES", "1000"))


def _state_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.maintenance_state_file).expanduser()


def append_state_record(record: dict[str, Any], policy: Optional[DataLifecyclePolicy] = None) -> None:
    path = _state_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    enforce_jsonl_retention(path, retention_days=RETENTION_DAYS, max_active_lines=MAX_RECENT_READ_LINES)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _normalize_filter_values(value: Optional[str | Iterable[str]]) -> Optional[set[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return {normalized} if normalized else None
    result = {str(item).strip() for item in value if str(item).strip()}
    return result or None


def _read_records_raw(policy: Optional[DataLifecyclePolicy] = None) -> list[dict[str, Any]]:
    path = _state_path(policy)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        for line in read_segment_lines(path, max_lines=MAX_RECENT_READ_LINES):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def read_recent_records(
    limit: int = 20,
    *,
    trigger: Optional[str | Iterable[str]] = None,
    status: Optional[str | Iterable[str]] = None,
    policy: Optional[DataLifecyclePolicy] = None,
) -> list[dict[str, Any]]:
    trigger_filter = _normalize_filter_values(trigger)
    status_filter = _normalize_filter_values(status)
    records = _read_records_raw(policy)
    output: list[dict[str, Any]] = []
    for record in reversed(records):
        if trigger_filter is not None:
            trigger_value = str(record.get("trigger") or "").strip()
            if trigger_value not in trigger_filter:
                continue
        if status_filter is not None:
            status_value = str(record.get("status") or "").strip()
            if status_value not in status_filter:
                continue
        output.append(record)
        if len(output) >= max(1, int(limit)):
            break
    return output


def latest_record(
    *,
    trigger: Optional[str | Iterable[str]] = None,
    status: Optional[str | Iterable[str]] = None,
    policy: Optional[DataLifecyclePolicy] = None,
) -> Optional[dict[str, Any]]:
    records = read_recent_records(limit=1, trigger=trigger, status=status, policy=policy)
    if not records:
        return None
    return records[0]


def new_cycle_id() -> str:
    return uuid.uuid4().hex[:12]


def build_record(
    *,
    cycle_id: str,
    trigger: str,
    started_at: datetime,
    completed_at: datetime,
    status: str,
    bytes_scanned: int,
    error: Optional[str],
) -> dict[str, Any]:
    return {
        "cycle_id": cycle_id,
        "trigger": trigger,
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "completed_at": completed_at.astimezone(timezone.utc).isoformat(),
        "status": status,
        "bytes_scanned": int(max(0, bytes_scanned)),
        "error": error,
    }
