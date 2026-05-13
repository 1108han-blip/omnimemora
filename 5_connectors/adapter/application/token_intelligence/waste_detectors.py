"""Safe optimization opportunity detectors for Token Intelligence Lite."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .usage_normalizer import estimate_openai_compatible_input_tokens


_SPACE_RE = re.compile(r"\s+")


def detect_openai_compatible_waste(request_payload: Any, blocks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if not isinstance(request_payload, dict):
        return []
    opportunities: list[dict[str, Any]] = []
    messages = request_payload.get("messages")
    message_items = messages if isinstance(messages, list) else []
    _detect_duplicate_message_content(opportunities, message_items)
    _detect_long_tool_results(opportunities, message_items)
    _detect_high_tool_result_share(opportunities, blocks or [])
    return opportunities


def _detect_duplicate_message_content(opportunities: list[dict[str, Any]], messages: list[Any]) -> None:
    seen: dict[str, int] = {}
    repeated_tokens = 0
    repeated_count = 0
    for message in messages:
        content = _content_text(message)
        fingerprint = _fingerprint(content)
        if not fingerprint:
            continue
        tokens = _estimate_text_payload(content)
        if fingerprint in seen:
            repeated_tokens += tokens
            repeated_count += 1
        seen[fingerprint] = seen.get(fingerprint, 0) + 1
    if repeated_tokens <= 0:
        return
    opportunities.append(
        _opportunity(
            detector_id="duplicate_context_v1",
            category="duplicate_context",
            reason_code="repeated_message_content",
            token_estimate=repeated_tokens,
            potential_saving_tokens=repeated_tokens,
            item_count=repeated_count,
            severity="medium" if repeated_tokens < 500 else "high",
        )
    )


def _detect_long_tool_results(opportunities: list[dict[str, Any]], messages: list[Any]) -> None:
    total_tokens = 0
    item_count = 0
    for message in messages:
        if _role(message) not in {"tool", "function"}:
            continue
        tokens = _estimate_text_payload(_content_text(message))
        if tokens < 120:
            continue
        total_tokens += tokens
        item_count += 1
    if total_tokens <= 0:
        return
    opportunities.append(
        _opportunity(
            detector_id="long_tool_result_v1",
            category="long_tool_result",
            reason_code="tool_result_above_threshold",
            token_estimate=total_tokens,
            potential_saving_tokens=max(1, int(total_tokens * 0.5)),
            item_count=item_count,
            severity="medium" if total_tokens < 800 else "high",
        )
    )


def _detect_high_tool_result_share(opportunities: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> None:
    total = sum(_safe_int(block.get("token_estimate")) for block in blocks)
    tool_total = sum(
        _safe_int(block.get("token_estimate"))
        for block in blocks
        if str(block.get("block_type") or "") == "tool_results"
    )
    if total <= 0 or tool_total <= 0:
        return
    share = tool_total / total
    if share < 0.45:
        return
    opportunities.append(
        _opportunity(
            detector_id="tool_result_share_v1",
            category="tool_result_heavy_context",
            reason_code="tool_results_dominate_request_tokens",
            token_estimate=tool_total,
            potential_saving_tokens=max(1, int(tool_total * 0.35)),
            item_count=1,
            severity="medium" if share < 0.7 else "high",
        )
    )


def _opportunity(
    *,
    detector_id: str,
    category: str,
    reason_code: str,
    token_estimate: int,
    potential_saving_tokens: int,
    item_count: int,
    severity: str,
) -> dict[str, Any]:
    return {
        "detector_id": detector_id,
        "category": category,
        "reason_code": reason_code,
        "token_estimate": max(0, int(token_estimate)),
        "potential_saving_tokens": max(0, int(potential_saving_tokens)),
        "item_count": max(0, int(item_count)),
        "severity": severity,
        "source": "local_estimated",
        "confidence": "compatible_estimate",
    }


def _content_text(message: Any) -> str:
    payload = message if isinstance(message, dict) else {}
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return ""


def _fingerprint(text: str) -> str:
    normalized = _SPACE_RE.sub(" ", str(text or "").strip()).lower()
    if len(normalized) < 24:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _estimate_text_payload(text: str) -> int:
    if not text:
        return 0
    return estimate_openai_compatible_input_tokens({"content": text}) or 0


def _role(message: Any) -> str:
    payload = message if isinstance(message, dict) else {}
    return str(payload.get("role") or "")


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0
