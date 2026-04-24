"""Maintenance state ledger store for Data Lifecycle Plane."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .policy import DataLifecyclePolicy, load_policy


def _state_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.maintenance_state_file).expanduser()


def append_state_record(record: dict[str, Any], policy: Optional[DataLifecyclePolicy] = None) -> None:
    path = _state_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


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
