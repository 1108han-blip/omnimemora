"""Minimal structured compile failure samples.

Collection is disabled by default and intentionally stores no raw request,
tool output, memory content, prompt text, or provider response body.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ...log_segments import enforce_jsonl_retention, read_segment_lines


SCHEMA_VERSION = "structured_compile_failure_sample_v1"
RETENTION_DAYS = int(
    os.getenv(
        "OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLE_RETENTION_DAYS",
        os.getenv("OMNIMEMORA_INTERNAL_LOG_RETENTION_DAYS", "7"),
    )
)
MAX_RECENT_READ_LINES = int(os.getenv("OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLE_MAX_READ_LINES", "1000"))
FAILURE_SAMPLES_PATH = os.getenv(
    "OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLES_PATH",
    os.path.expanduser("~/.omnimemora/adapter/structured_compile_failure_samples.jsonl"),
)


def sampling_enabled() -> bool:
    return os.getenv("OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def record_failure_sample(
    *,
    status: str,
    reason: str,
    issues: Iterable[str],
    protocol: str,
    agent_family: str,
    original_token_estimate: int,
    compiled_token_estimate: int,
    token_estimator_name: Optional[str] = None,
    token_estimator_confidence: Optional[str] = None,
    changed_blocks: int = 0,
) -> bool:
    if not sampling_enabled():
        return False
    sample = build_failure_sample(
        status=status,
        reason=reason,
        issues=issues,
        protocol=protocol,
        agent_family=agent_family,
        original_token_estimate=original_token_estimate,
        compiled_token_estimate=compiled_token_estimate,
        token_estimator_name=token_estimator_name,
        token_estimator_confidence=token_estimator_confidence,
        changed_blocks=changed_blocks,
    )
    append_failure_sample(sample)
    return True


def build_failure_sample(
    *,
    status: str,
    reason: str,
    issues: Iterable[str],
    protocol: str,
    agent_family: str,
    original_token_estimate: int,
    compiled_token_estimate: int,
    token_estimator_name: Optional[str] = None,
    token_estimator_confidence: Optional[str] = None,
    changed_blocks: int = 0,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": time.time(),
        "compile_status": str(status or "unknown"),
        "compile_reason": str(reason or ""),
        "issue_codes": [str(issue) for issue in issues if str(issue)],
        "protocol": str(protocol or "unknown"),
        "agent_family": str(agent_family or "unknown"),
        "original_token_estimate": _safe_int(original_token_estimate),
        "compiled_token_estimate": _safe_int(compiled_token_estimate),
        "token_estimator_name": str(token_estimator_name or ""),
        "token_estimator_confidence": str(token_estimator_confidence or ""),
        "changed_blocks": _safe_int(changed_blocks),
    }


def append_failure_sample(sample: Dict[str, Any]) -> None:
    path = Path(FAILURE_SAMPLES_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    enforce_jsonl_retention(path, retention_days=RETENTION_DAYS, max_active_lines=MAX_RECENT_READ_LINES)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
    enforce_jsonl_retention(path, retention_days=RETENTION_DAYS, max_active_lines=MAX_RECENT_READ_LINES)


def read_recent_failure_samples(limit: int = 100) -> list[Dict[str, Any]]:
    path = Path(FAILURE_SAMPLES_PATH).expanduser()
    rows: list[Dict[str, Any]] = []
    for line in read_segment_lines(path, max_lines=max(1, min(MAX_RECENT_READ_LINES, limit))):
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("schema_version") == SCHEMA_VERSION:
            rows.append(payload)
    rows.sort(key=lambda row: float(row.get("timestamp") or 0), reverse=True)
    return rows[:limit]


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0
