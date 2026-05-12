"""Structured compiler orchestration for Anthropic-compatible payloads."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .anthropic_tool_graph import analyze_anthropic_tool_graph
from .anthropic_tool_schema import analyze_anthropic_tool_schema
from .compressors import compress_tool_result_text
from .metrics import compression_ratio, estimate_payload_tokens_detailed
from .validators import validate_anthropic_compiled_payload


@dataclass(frozen=True)
class StructuredCompileResult:
    status: str
    payload: Dict[str, Any]
    original_token_estimate: int
    compiled_token_estimate: int
    compression_ratio: float
    token_estimator_name: str = ""
    token_estimator_confidence: str = ""
    changed_blocks: int = 0
    reason: str = ""
    issues: List[str] = field(default_factory=list)


def compile_anthropic_tool_context(
    payload: Dict[str, Any],
    *,
    max_tool_result_chars: int = 1200,
) -> StructuredCompileResult:
    """Compile eligible Anthropic tool results while preserving graph structure."""
    before_estimate = estimate_payload_tokens_detailed(payload)
    before_tokens = before_estimate.tokens
    analysis = analyze_anthropic_tool_graph(payload)
    if not analysis.valid:
        return _passthrough(payload, before_estimate, "invalid_tool_graph", _issue_codes(analysis.issues))
    if not analysis.has_tool_graph:
        return _passthrough(payload, before_estimate, "no_tool_graph", [])

    schema_analysis = analyze_anthropic_tool_schema(payload)
    if not schema_analysis.valid:
        return _passthrough(
            payload,
            before_estimate,
            "invalid_tool_schema",
            _issue_codes(schema_analysis.issues),
        )

    latest_result_location = _latest_tool_result_location(analysis.ir.messages)
    if latest_result_location is None:
        return _passthrough(payload, before_estimate, "no_tool_result", [])

    compiled = deepcopy(payload)
    changed_blocks = 0
    reasons: List[str] = []

    messages = compiled.get("messages") or []
    for message_index, message in enumerate(messages):
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for content_index, part in enumerate(content):
            if not isinstance(part, dict) or part.get("type") != "tool_result":
                continue
            if (message_index, content_index) == latest_result_location:
                continue
            text, replace_mode = _tool_result_text(part)
            compressed = compress_tool_result_text(text, max_chars=max_tool_result_chars)
            if not compressed.changed:
                continue
            if replace_mode == "content_list_text":
                part["content"] = [{"type": "text", "text": compressed.text}]
            else:
                part["content"] = compressed.text
            changed_blocks += 1
            reasons.append(compressed.reason)

    if changed_blocks == 0:
        return _passthrough(payload, before_estimate, "no_eligible_tool_result", [])

    if not validate_anthropic_compiled_payload(compiled):
        return _passthrough(payload, before_estimate, "compiled_payload_invalid", [])

    after_estimate = estimate_payload_tokens_detailed(compiled)
    after_tokens = after_estimate.tokens
    if after_tokens >= before_tokens:
        return _passthrough(payload, before_estimate, "no_token_gain", [])

    return StructuredCompileResult(
        status="structured_compile_success",
        payload=compiled,
        original_token_estimate=before_tokens,
        compiled_token_estimate=after_tokens,
        compression_ratio=compression_ratio(before_tokens, after_tokens),
        token_estimator_name=before_estimate.estimator_name,
        token_estimator_confidence=before_estimate.estimator_confidence,
        changed_blocks=changed_blocks,
        reason=",".join(sorted(set(reasons))) or "deterministic_extract",
    )


def _passthrough(
    payload: Dict[str, Any],
    before_estimate: Any,
    reason: str,
    issues: List[str],
) -> StructuredCompileResult:
    return StructuredCompileResult(
        status="structured_compile_passthrough",
        payload=payload,
        original_token_estimate=before_estimate.tokens,
        compiled_token_estimate=before_estimate.tokens,
        compression_ratio=0.0,
        token_estimator_name=before_estimate.estimator_name,
        token_estimator_confidence=before_estimate.estimator_confidence,
        changed_blocks=0,
        reason=reason,
        issues=issues,
    )


def _latest_tool_result_location(messages: List[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
    latest: Optional[Tuple[int, int]] = None
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for content_index, part in enumerate(content):
            if isinstance(part, dict) and part.get("type") == "tool_result":
                latest = (message_index, content_index)
    return latest


def _tool_result_text(part: Dict[str, Any]) -> Tuple[str, str]:
    content = part.get("content", "")
    if isinstance(content, list):
        texts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(text for text in texts if text), "content_list_text"
    return str(content or ""), "content_string"


def _issue_codes(issues: List[Any]) -> List[str]:
    return [str(getattr(issue, "code", "unknown")) for issue in issues]
