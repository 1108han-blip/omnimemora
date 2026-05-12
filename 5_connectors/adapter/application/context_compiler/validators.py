"""Provider payload validators for structured compile."""

from __future__ import annotations

from typing import Any, Dict

from .anthropic_tool_graph import analyze_anthropic_tool_graph
from .anthropic_tool_schema import validate_anthropic_tool_schema


def validate_anthropic_payload_shape(payload: Dict[str, Any]) -> bool:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict):
            return False
        role = message.get("role")
        if role not in {"user", "assistant", "system"}:
            return False
        content = message.get("content")
        if not isinstance(content, (str, list)):
            return False
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    return False
                part_type = part.get("type")
                if part_type == "tool_use" and not part.get("id"):
                    return False
                if part_type == "tool_result" and not part.get("tool_use_id"):
                    return False
    return True


def validate_anthropic_compiled_payload(payload: Dict[str, Any]) -> bool:
    return (
        validate_anthropic_payload_shape(payload)
        and analyze_anthropic_tool_graph(payload).valid
        and validate_anthropic_tool_schema(payload)
    )
