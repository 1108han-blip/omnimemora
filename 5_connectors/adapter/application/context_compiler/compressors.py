"""Deterministic text block compressors for structured compile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


DIFF_LINE_RE = re.compile(r"^(diff --git|index |@@ |\+\+\+ |--- |\+[^+]|-[^-])")
FILE_READ_LINE_RE = re.compile(r"^\s*(class |def |async def |function |export |import |from |package |func )")
IMPORTANT_LINE_RE = re.compile(
    r"("
    r"error|exception|traceback|failed|failure|warning|timeout|denied|"
    r"request_id|status=|exit code|"
    r"[A-Za-z0-9_./-]+\.(py|ts|tsx|js|go|rs|md):\d+"
    r")",
    re.IGNORECASE,
)
LOG_LINE_RE = re.compile(r"(\bERROR\b|\bWARN(?:ING)?\b|\bINFO\b|\bDEBUG\b|\bTRACE\b|\d{4}-\d{2}-\d{2}[T ]\d{2}:)", re.IGNORECASE)
SEVERE_LOG_LINE_RE = re.compile(r"(\bERROR\b|\bWARN(?:ING)?\b|exception|traceback|timeout|denied)", re.IGNORECASE)
SEARCH_LINE_RE = re.compile(r"([A-Za-z0-9_./-]+\.(py|ts|tsx|js|go|rs|md):\d+|https?://|rg:|grep:)", re.IGNORECASE)
TEST_LINE_RE = re.compile(
    r"(FAILED|ERROR|AssertionError|Traceback|passed|failed|xfailed|xpassed|collected|"
    r"^=+ .* =+$|^_{3,} .* _{3,}$)",
    re.IGNORECASE,
)
TEST_FAILURE_RE = re.compile(r"(FAILED|ERROR|AssertionError|Traceback)", re.IGNORECASE)
TEST_SUMMARY_RE = re.compile(r"(passed|failed|xfailed|xpassed|collected|^=+ .* =+$)", re.IGNORECASE)


@dataclass(frozen=True)
class CompressionResult:
    text: str
    changed: bool
    original_chars: int
    compressed_chars: int
    reason: str
    output_type: str = "generic"


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
            output_type=classify_tool_result_text(source),
        )

    lines = source.splitlines()
    output_type = classify_tool_result_text(source)
    selected: List[str] = []

    selected.extend(_select_lines_by_type(lines, output_type, head_lines, tail_lines, important_limit))
    selected = _dedupe_preserve_order(selected)

    body = "\n".join(selected).strip()
    marker = (
        f"[omnimemora structured compile: deterministic {output_type} compression; "
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
            output_type=output_type,
        )

    if len(compressed) > max_chars:
        compressed = compressed[: max_chars - 64].rstrip() + "\n[omnimemora structured compile: truncated]"

    return CompressionResult(
        text=compressed,
        changed=True,
        original_chars=original_chars,
        compressed_chars=len(compressed),
        reason=f"deterministic_extract_{output_type}",
        output_type=output_type,
    )


def classify_tool_result_text(text: str) -> str:
    source = str(text or "")
    lines = source.splitlines()
    if not lines:
        return "generic"

    diff_hits = sum(1 for line in lines if DIFF_LINE_RE.search(line))
    test_hits = sum(1 for line in lines if TEST_LINE_RE.search(line))
    search_hits = sum(1 for line in lines if SEARCH_LINE_RE.search(line))
    log_hits = sum(1 for line in lines if LOG_LINE_RE.search(line))
    file_read_hits = sum(1 for line in lines if FILE_READ_LINE_RE.search(line))

    if diff_hits >= 3:
        return "diff"
    if log_hits >= max(3, int(len(lines) * 0.25)):
        return "log"
    if test_hits >= 2:
        return "test_output"
    if search_hits >= max(3, int(len(lines) * 0.25)):
        return "search_result"
    if file_read_hits >= 2:
        return "file_read"
    return "generic"


def _select_lines_by_type(
    lines: List[str],
    output_type: str,
    head_lines: int,
    tail_lines: int,
    important_limit: int,
) -> List[str]:
    selected: List[str] = []

    if output_type == "diff":
        selected.extend(_sample_lines([line for line in lines if DIFF_LINE_RE.search(line)], important_limit))
    elif output_type == "test_output":
        selected.extend([line for line in lines if TEST_FAILURE_RE.search(line)][:important_limit])
        selected.extend([line for line in lines if TEST_SUMMARY_RE.search(line)][:important_limit])
        selected.extend([line for line in lines if IMPORTANT_LINE_RE.search(line)][:important_limit])
    elif output_type == "log":
        selected.extend([line for line in lines if SEVERE_LOG_LINE_RE.search(line)][:important_limit])
        selected.extend(
            _sample_lines(
                [line for line in lines if LOG_LINE_RE.search(line) or IMPORTANT_LINE_RE.search(line)],
                important_limit,
            )
        )
    elif output_type == "search_result":
        selected.extend(
            _sample_lines(
                [line for line in lines if SEARCH_LINE_RE.search(line) or IMPORTANT_LINE_RE.search(line)],
                important_limit,
            )
        )
    elif output_type == "file_read":
        selected.extend([line for line in lines if FILE_READ_LINE_RE.search(line) or IMPORTANT_LINE_RE.search(line)][:important_limit])
    else:
        selected.extend([line for line in lines if IMPORTANT_LINE_RE.search(line)][:important_limit])

    selected.extend(lines[:head_lines])
    selected.extend(lines[-tail_lines:])
    return selected


def _sample_lines(lines: List[str], limit: int) -> List[str]:
    if limit <= 0 or len(lines) <= limit:
        return lines

    first_count = max(1, limit // 3)
    middle_count = max(1, limit // 3)
    last_count = max(1, limit - first_count - middle_count)
    middle_start = max(0, (len(lines) // 2) - (middle_count // 2))
    middle_end = min(len(lines), middle_start + middle_count)
    return lines[:first_count] + lines[middle_start:middle_end] + lines[-last_count:]


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
