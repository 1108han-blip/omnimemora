"""Lightweight token estimates for structured compile."""

from __future__ import annotations

import json
from typing import Any, Dict


def estimate_text_tokens(text: str) -> int:
    return max(0, int(len(text or "") / 3))


def estimate_payload_tokens(payload: Dict[str, Any]) -> int:
    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        serialized = str(payload)
    return max(1, estimate_text_tokens(serialized))


def compression_ratio(before_tokens: int, after_tokens: int) -> float:
    if before_tokens <= 0 or after_tokens <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (after_tokens / before_tokens)))

