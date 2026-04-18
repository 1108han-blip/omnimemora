"""
Helpers for reading rotated OmniMemora JSONL event files.

Supports both legacy and current rotation styles:
- proxy_events.20260416120000.jsonl
- agent_events.jsonl.20260416120000
- compile_events.jsonl.bak
"""
from __future__ import annotations

from pathlib import Path
from typing import List


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
    lines: List[str] = []
    for path in list_jsonl_segments(base_path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                lines.extend(handle.readlines())
        except Exception:
            continue

    if max_lines is not None:
        return lines[-max_lines:]
    return lines
