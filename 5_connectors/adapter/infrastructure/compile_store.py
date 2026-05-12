"""
compile_store.py — Compile Telemetry Persistence
=================================================
Phase 3 Task D: Persists structured compile telemetry.

Format: JSONL at ~/.omnimemora/adapter/compile_events.jsonl
File rotates when exceeding 50MB.
Events older than 7 days are auto-pruned; reads use bounded recent tails.
"""
from __future__ import annotations

import json
import os
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import loguru

from ..log_segments import enforce_jsonl_retention, read_segment_lines


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

MAX_FILE_SIZE_MB = int(os.getenv("OMNIMEMORA_COMPILE_EVENTS_MAX_MB", "10"))
RETENTION_DAYS = int(os.getenv("OMNIMEMORA_COMPILE_EVENTS_RETENTION_DAYS", os.getenv("OMNIMEMORA_INTERNAL_LOG_RETENTION_DAYS", "7")))
MAX_RECENT_READ_LINES = int(os.getenv("OMNIMEMORA_COMPILE_EVENTS_MAX_READ_LINES", "1000"))


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
    enforce_jsonl_retention(path, retention_days=RETENTION_DAYS, max_active_lines=MAX_RECENT_READ_LINES)

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
        enforce_jsonl_retention(path, retention_days=RETENTION_DAYS, max_active_lines=MAX_RECENT_READ_LINES)
    except Exception as e:
        loguru.logger.warning(f"[COMPILE_STORE] append failed: {e}")
        return


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
        for line in read_segment_lines(path, max_lines=max(min(MAX_RECENT_READ_LINES, limit * 5), limit)):
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
                "structured_compile_success": int,
                "structured_compile_passthrough": int,
                "compile_skipped": int,
                "compile_failed": int,
                "status_counts": dict,
                "status_shares": dict,
                "compile_token_savings": dict,
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
                "structured_compile_success": 0,
                "structured_compile_passthrough": 0,
                "compile_skipped": 0,
                "compile_failed": 0,
                "status_counts": {},
                "compression_ratios": [],
                "selected_counts": [],
                "original_token_total": 0,
                "compiled_token_total": 0,
                "saved_token_total": 0,
                "last_seen": None,
            }

        s = stats[agent]
        s["proxied_requests"] += 1
        status = event.get("compile_status", "")
        if not status:
            status = "unknown"
        s["status_counts"][status] = s["status_counts"].get(status, 0) + 1
        if status == "compile_success":
            s["compile_success"] += 1
        elif status == "structured_compile_success":
            s["structured_compile_success"] += 1
        elif status == "structured_compile_passthrough":
            s["structured_compile_passthrough"] += 1
        elif status == "compile_skipped":
            s["compile_skipped"] += 1
        elif status == "compile_failed":
            s["compile_failed"] += 1

        original_tokens = _safe_int(event.get("original_token_estimate", 0))
        compiled_tokens = _safe_int(event.get("compiled_token_estimate", 0))
        if status not in {"compile_success", "structured_compile_success"} or compiled_tokens <= 0:
            compiled_tokens = original_tokens
        saved_tokens = max(0, original_tokens - compiled_tokens)
        s["original_token_total"] += original_tokens
        s["compiled_token_total"] += compiled_tokens
        s["saved_token_total"] += saved_tokens

        ratio = _safe_float(event.get("compression_ratio", 0.0))
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
        proxied_requests = int(s["proxied_requests"])
        status_counts = dict(sorted(s["status_counts"].items()))
        status_shares = {
            status: round(count / proxied_requests, 4) if proxied_requests > 0 else 0.0
            for status, count in status_counts.items()
        }
        original_total = int(s["original_token_total"])
        compiled_total = int(s["compiled_token_total"])
        saved_total = int(s["saved_token_total"])
        savings_ratio = round(saved_total / original_total, 4) if original_total > 0 else 0.0
        result[agent] = {
            "proxied_requests": proxied_requests,
            "compile_success": s["compile_success"],
            "structured_compile_success": s["structured_compile_success"],
            "structured_compile_passthrough": s["structured_compile_passthrough"],
            "compile_skipped": s["compile_skipped"],
            "compile_failed": s["compile_failed"],
            "status_counts": status_counts,
            "status_shares": status_shares,
            "structured_compile": {
                "success": s["structured_compile_success"],
                "passthrough": s["structured_compile_passthrough"],
                "success_share": status_shares.get("structured_compile_success", 0.0),
                "passthrough_share": status_shares.get("structured_compile_passthrough", 0.0),
            },
            "compile_token_savings": {
                "original_token_estimate": original_total,
                "compiled_token_estimate": compiled_total,
                "saved_token_estimate": saved_total,
                "savings_ratio": savings_ratio,
            },
            "avg_compression_ratio": round(sum(ratios) / len(ratios), 3) if ratios else 0.0,
            "avg_selected_memories": round(sum(counts) / len(counts), 1) if counts else 0.0,
            "last_seen": s["last_seen"],
        }

    return result


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except Exception:
        return 0.0


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
