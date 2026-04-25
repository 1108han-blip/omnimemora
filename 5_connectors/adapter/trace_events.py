"""
trace_events.py - structured request path trace persistence

Phase 0 goals:
- request-level JSONL evidence across entry/proxy/adapter/upstream/fallback/error
- independent from proxy_store / compile_store so Phase 0 does not disturb KPI surfaces
"""
from __future__ import annotations

import json
import os
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .log_segments import read_segment_lines


def _default_trace_events_path() -> str:
    base = os.path.expanduser("~/.omnimemora/adapter")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "trace_events.jsonl")


TRACE_EVENTS_PATH = os.getenv(
    "OMNIMEMORA_TRACE_EVENTS_PATH",
    _default_trace_events_path(),
)
MAX_FILE_SIZE_MB = int(os.getenv("OMNIMEMORA_TRACE_EVENTS_MAX_MB", "50"))
RETENTION_DAYS = int(os.getenv("OMNIMEMORA_TRACE_EVENTS_RETENTION_DAYS", "30"))


def append_trace_event(event: Dict[str, Any]) -> None:
    path = Path(TRACE_EVENTS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rotated = path.parent / f"{path.stem}.{timestamp}{path.suffix}"
        try:
            path.rename(rotated)
        except Exception:
            path.write_text("")

    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Observe-only mirror path; failures must not affect legacy source writes.
    try:
        segments = __import__(
            "5_connectors.adapter.data_lifecycle.raw_evidence_segments",
            fromlist=["append_event_dual_write_observe_only"],
        )
        segments.append_event_dual_write_observe_only(kind="trace_events", event=event)
    except Exception:
        pass


def read_recent_trace_events(limit: int = 200, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
    path = Path(TRACE_EVENTS_PATH)
    if not path.exists():
        return []

    cutoff = _time.time() - RETENTION_DAYS * 86400
    events: List[Dict[str, Any]] = []
    try:
        for line in read_segment_lines(path, max_lines=max(limit * 5, limit)):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("timestamp", 0) < cutoff:
                continue
            if trace_id and event.get("trace_id") != trace_id:
                continue
            events.append(event)
    except Exception:
        return []
    events.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
    return events[:limit]
