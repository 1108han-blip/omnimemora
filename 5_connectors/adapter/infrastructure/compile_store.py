"""
compile_store.py — Compile Telemetry Persistence
=================================================
Phase 3 Task D: Persists structured compile telemetry.

Format: JSONL at ~/.omnimemora/adapter/compile_events.jsonl
File rotates when exceeding 50MB.
Events older than 30 days are auto-pruned on read.
"""
from __future__ import annotations

import json
import os
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import loguru

from ..log_segments import read_segment_lines


# ============================================================================
# Path Configuration
# ============================================================================

def _default_compile_events_path() -> str:
    base = os.path.expanduser("~/.omnimemora/adapter")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "compile_events.jsonl")


COMPILE_EVENTS_PATH = os.getenv(
    "OMNIMEMORA_COMPILE_EVENTS_PATH",
    _default_compile_events_path(),
)

MAX_FILE_SIZE_MB = int(os.getenv("OMNIMEMORA_COMPILE_EVENTS_MAX_MB", "50"))
RETENTION_DAYS = int(os.getenv("OMNIMEMORA_COMPILE_EVENTS_RETENTION_DAYS", "30"))


# ============================================================================
# Core Append
# ============================================================================

def append_compile_event(event: Dict[str, Any]) -> None:
    """
    Append a single compile event to the JSONL file.
    Handles file rotation when exceeding MAX_FILE_SIZE_MB.
    """
    path = Path(COMPILE_EVENTS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Auto-rotate if file too large
    if path.exists() and path.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        timestamp = datetime_utc_compact()
        rotated = path.parent / f"{path.stem}.{timestamp}{path.suffix}"
        try:
            path.rename(rotated)
            loguru.logger.info(f"[COMPILE_STORE] rotated {path} → {rotated}")
        except Exception as e:
            loguru.logger.warning(f"[COMPILE_STORE] rotate failed: {e}, overwriting")
            path.write_text("")

    # Append event
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        loguru.logger.warning(f"[COMPILE_STORE] append failed: {e}")
        return

    # Observe-only mirror path; failures must not affect legacy source writes.
    try:
        segments = __import__(
            "5_connectors.adapter.data_lifecycle.raw_evidence_segments",
            fromlist=["append_event_dual_write_observe_only"],
        )
        segments.append_event_dual_write_observe_only(kind="compile_events", event=event)
    except Exception as e:
        loguru.logger.warning(f"[COMPILE_STORE] segment mirror failed (non-fatal): {e}")


# ============================================================================
# Read Recent Events
# ============================================================================

def read_recent_compile_events(
    limit: int = 200,
    window_minutes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Read recent compile events from JSONL.

    Args:
        limit: Maximum number of events to return (most recent first)
        window_minutes: If set, only return events within this window
    """
    path = Path(COMPILE_EVENTS_PATH)

    cutoff = 0.0
    if window_minutes is not None:
        cutoff = _time.time() - window_minutes * 60

    events: List[Dict[str, Any]] = []
    cutoff_time = cutoff

    try:
        for line in read_segment_lines(path):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                # Prune old events (older than retention window)
                ts = event.get("timestamp", 0)
                age_days = (_time.time() - ts) / 86400
                if age_days > RETENTION_DAYS:
                    continue
                if window_minutes is not None and ts < cutoff_time:
                    continue
                events.append(event)
            except json.JSONDecodeError:
                continue
    except Exception as e:
        loguru.logger.warning(f"[COMPILE_STORE] read failed: {e}")

    # Most recent first, then limit
    events.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return events[:limit]


# ============================================================================
# Summarize Per-Agent Compile Status
# ============================================================================

def summarize_compile_status(window_minutes: int = 30) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate compile telemetry per agent.

    Returns:
        {
            "claude_code": {
                "proxied_requests": int,
                "compile_success": int,
                "compile_skipped": int,
                "compile_failed": int,
                "avg_compression_ratio": float,
                "avg_selected_memories": float,
                "last_seen": float | None,
            },
            ...
        }
    """
    events = read_recent_compile_events(limit=2000, window_minutes=window_minutes)

    # Collect per-agent stats
    stats: Dict[str, Dict[str, Any]] = {}

    for event in events:
        agent = event.get("agent_id", "unknown")
        if agent not in stats:
            stats[agent] = {
                "proxied_requests": 0,
                "compile_success": 0,
                "compile_skipped": 0,
                "compile_failed": 0,
                "compression_ratios": [],
                "selected_counts": [],
                "last_seen": None,
            }

        s = stats[agent]
        s["proxied_requests"] += 1
        status = event.get("compile_status", "")
        if status == "compile_success":
            s["compile_success"] += 1
        elif status == "compile_skipped":
            s["compile_skipped"] += 1
        elif status == "compile_failed":
            s["compile_failed"] += 1

        ratio = event.get("compression_ratio", 0.0)
        if ratio > 0:
            s["compression_ratios"].append(ratio)

        sel = event.get("selected_memory_count", 0)
        if sel > 0:
            s["selected_counts"].append(sel)

        ts = event.get("timestamp", 0)
        if ts > (s["last_seen"] or 0):
            s["last_seen"] = ts

    # Compute averages
    result = {}
    for agent, s in stats.items():
        ratios = s["compression_ratios"]
        counts = s["selected_counts"]
        result[agent] = {
            "proxied_requests": s["proxied_requests"],
            "compile_success": s["compile_success"],
            "compile_skipped": s["compile_skipped"],
            "compile_failed": s["compile_failed"],
            "avg_compression_ratio": round(sum(ratios) / len(ratios), 3) if ratios else 0.0,
            "avg_selected_memories": round(sum(counts) / len(counts), 1) if counts else 0.0,
            "last_seen": s["last_seen"],
        }

    return result


# ============================================================================
# Reset (for testing)
# ============================================================================

def reset_compile_events() -> None:
    """Clear all compile events (use only in testing)."""
    path = Path(COMPILE_EVENTS_PATH)
    if path.exists():
        path.unlink()
    loguru.logger.info("[COMPILE_STORE] events reset")


def datetime_utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
