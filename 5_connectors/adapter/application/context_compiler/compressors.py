"""Deterministic text block compressors for structured compile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


IMPORTANT_LINE_RE = re.compile(
    r"("
    r"error|exception|traceback|failed|failure|warning|timeout|denied|"
    r"request_id|status=|exit code|"
    r"[A-Za-z0-9_./-]+\.(py|ts|tsx|js|go|rs|md):\d+"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CompressionResult:
    text: str
    changed: bool
    original_chars: int
    compressed_chars: int
    reason: str


def compress_tool_result_text(
    text: str,
    *,
    max_chars: int = 1200,
    head_lines: int = 12,
    tail_lines: int = 8,
    important_limit: int = 24,
) -> CompressionResult:
    """Compress long tool output with extractive rules only."""
    source = str(text or "")
    original_chars = len(source)
    if original_chars <= max_chars:
        return CompressionResult(
            text=source,
            changed=False,
            original_chars=original_chars,
            compressed_chars=original_chars,
            reason="under_budget",
        )

    lines = source.splitlines()
    selected: List[str] = []

    selected.extend(lines[:head_lines])

    important = [line for line in lines if IMPORTANT_LINE_RE.search(line)]
    for line in important[:important_limit]:
        selected.append(line)

    selected.extend(lines[-tail_lines:])
    selected = _dedupe_preserve_order(selected)

    body = "\n".join(selected).strip()
    marker = (
        f"[omnimemora structured compile: deterministic tool_result compression; "
        f"original_chars={original_chars}; retained_lines={len(selected)}]"
    )
    compressed = f"{marker}\n{body}" if body else marker

    if len(compressed) >= original_chars:
        return CompressionResult(
            text=source,
            changed=False,
            original_chars=original_chars,
            compressed_chars=original_chars,
            reason="no_gain",
        )

    if len(compressed) > max_chars:
        compressed = compressed[: max_chars - 64].rstrip() + "\n[omnimemora structured compile: truncated]"

    return CompressionResult(
        text=compressed,
        changed=True,
        original_chars=original_chars,
        compressed_chars=len(compressed),
        reason="deterministic_extract",
    )


def _dedupe_preserve_order(lines: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for line in lines:
        key = line.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out

