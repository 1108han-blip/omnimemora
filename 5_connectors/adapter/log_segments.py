"""
Helpers for reading rotated OmniMemora JSONL event files.

Supports both legacy and current rotation styles:
- proxy_events.20260416120000.jsonl
- agent_events.jsonl.20260416120000
- compile_events.jsonl.bak
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List


DEFAULT_INTERNAL_LOG_RETENTION_DAYS = int(os.getenv("OMNIMEMORA_INTERNAL_LOG_RETENTION_DAYS", "7"))
DEFAULT_INTERNAL_LOG_MAX_SEGMENTS = int(os.getenv("OMNIMEMORA_INTERNAL_LOG_MAX_SEGMENTS", "3"))
DEFAULT_INTERNAL_LOG_MAX_ACTIVE_LINES = int(os.getenv("OMNIMEMORA_INTERNAL_LOG_MAX_ACTIVE_LINES", "1000"))


def list_jsonl_segments(base_path: Path) -> List[Path]:
    """
    Return all known log segments for a base JSONL file in replay order.

    Replay order is oldest first, active base file last.
    """
    parent = base_path.parent
    stem = base_path.stem
    suffix = base_path.suffix
    name = base_path.name

    candidates = {base_path}
    for pattern in (
        f"{stem}.*{suffix}",
        f"{name}.*",
    ):
        for path in parent.glob(pattern):
            if path.is_file():
                candidates.add(path)

    existing = [path for path in candidates if path.exists() and path.is_file()]
    existing.sort(
        key=lambda path: (
            path.stat().st_mtime,
            1 if path == base_path else 0,
            path.name,
        )
    )
    return existing


def read_segment_lines(base_path: Path, max_lines: int | None = None) -> List[str]:
    """Read newline-delimited lines across all rotated segments."""
    segments = list_jsonl_segments(base_path)
    if max_lines is not None:
        collected: List[str] = []
        for path in reversed(segments):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    lines = handle.readlines()
            except Exception:
                continue
            collected[0:0] = lines
            if len(collected) >= max_lines:
                return collected[-max_lines:]
        return collected

    lines: List[str] = []
    for path in segments:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                lines.extend(handle.readlines())
        except Exception:
            continue

    return lines


def _timestamp_value(payload: dict) -> float | None:
    for key in ("timestamp", "completed_at", "started_at", "generated_at"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value)
            except ValueError:
                pass
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
            except Exception:
                pass
    return None


def _line_is_recent(line: str, cutoff_ts: float) -> bool:
    try:
        payload = json.loads(line)
    except Exception:
        return True
    if not isinstance(payload, dict):
        return True
    ts = _timestamp_value(payload)
    if ts is None:
        return True
    return ts >= cutoff_ts


def enforce_jsonl_retention(
    base_path: Path,
    *,
    retention_days: int = DEFAULT_INTERNAL_LOG_RETENTION_DAYS,
    max_segments: int = DEFAULT_INTERNAL_LOG_MAX_SEGMENTS,
    max_active_lines: int = DEFAULT_INTERNAL_LOG_MAX_ACTIVE_LINES,
) -> dict[str, int]:
    """Cap internal JSONL logs by age, rotated segment count, and active tail size."""
    base_path = Path(base_path).expanduser()
    cutoff_ts = time.time() - max(1, int(retention_days)) * 86400
    result = {"deleted_segments": 0, "rewritten_active": 0, "kept_segments": 0}
    segments = list_jsonl_segments(base_path)

    rotated = [path for path in segments if path != base_path]
    kept_rotated: list[Path] = []
    for path in sorted(rotated, key=lambda p: p.stat().st_mtime, reverse=True):
        if path.stat().st_mtime < cutoff_ts or len(kept_rotated) >= max(0, int(max_segments)):
            try:
                path.unlink()
                result["deleted_segments"] += 1
            except Exception:
                kept_rotated.append(path)
            continue
        kept_rotated.append(path)

    if base_path.exists() and base_path.is_file():
        try:
            lines = base_path.read_text(encoding="utf-8").splitlines(keepends=True)
            kept_lines = [line for line in lines if _line_is_recent(line, cutoff_ts)]
            if max_active_lines is not None:
                kept_lines = kept_lines[-max(1, int(max_active_lines)) :]
            if len(kept_lines) != len(lines):
                base_path.write_text("".join(kept_lines), encoding="utf-8")
                result["rewritten_active"] += 1
        except Exception:
            pass

    result["kept_segments"] = len(list_jsonl_segments(base_path))
    return result
