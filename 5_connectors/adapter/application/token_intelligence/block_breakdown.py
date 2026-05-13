"""Block-level token spend estimates for OpenAI-compatible payloads."""

from __future__ import annotations

import json
from typing import Any

from .usage_normalizer import estimate_openai_compatible_input_tokens, estimate_openai_compatible_output_tokens


def classify_openai_compatible_blocks(request_payload: Any, response_payload: Any = None) -> list[dict[str, Any]]:
    if not isinstance(request_payload, dict):
        return []
    blocks: list[dict[str, Any]] = []
    messages = request_payload.get("messages")
    message_items = messages if isinstance(messages, list) else []
    last_user_index = _last_role_index(message_items, "user")

    _append_block(
        blocks,
        "system_developer_instructions",
        [item for item in message_items if _role(item) in {"system", "developer"}],
    )
    _append_block(
        blocks,
        "current_user_intent",
        [message_items[last_user_index]] if last_user_index is not None else [],
    )
    _append_block(
        blocks,
        "conversation_history",
        [
            item
            for index, item in enumerate(message_items)
            if _role(item) in {"user", "assistant"} and index != last_user_index and "tool_calls" not in _as_dict(item)
        ],
    )
    _append_block(
        blocks,
        "tool_schemas",
        _selected_top_level(request_payload, ["tools", "functions"]),
    )
    _append_block(
        blocks,
        "tool_calls",
        [item for item in message_items if _role(item) == "assistant" and "tool_calls" in _as_dict(item)]
        + _selected_top_level(request_payload, ["tool_choice", "function_call"]),
    )
    _append_block(
        blocks,
        "tool_results",
        [item for item in message_items if _role(item) in {"tool", "function"}],
    )
    _append_block(
        blocks,
        "memory_context_injection",
        _memory_context_items(request_payload),
    )
    _append_provider_output(blocks, response_payload)
    return blocks


def _append_block(blocks: list[dict[str, Any]], block_type: str, items: list[Any]) -> None:
    items = [item for item in items if item is not None]
    if not items:
        return
    tokens = _estimate_tokens({"items": items})
    if tokens <= 0:
        return
    blocks.append(
        {
            "block_type": block_type,
            "token_estimate": tokens,
            "item_count": len(items),
            "source": "local_estimated",
            "confidence": "compatible_estimate",
        }
    )


def _append_provider_output(blocks: list[dict[str, Any]], response_payload: Any) -> None:
    tokens = estimate_openai_compatible_output_tokens(response_payload)
    if not tokens:
        return
    blocks.append(
        {
            "block_type": "provider_output",
            "token_estimate": tokens,
            "item_count": _provider_output_count(response_payload),
            "source": "local_estimated",
            "confidence": "compatible_estimate",
        }
    )


def _estimate_tokens(payload: dict[str, Any]) -> int:
    estimate = estimate_openai_compatible_input_tokens(payload)
    if estimate is not None:
        return estimate
    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        serialized = str(payload)
    return max(1, int(len(serialized) / 4)) if serialized else 0


def _selected_top_level(payload: dict[str, Any], keys: list[str]) -> list[Any]:
    selected = []
    for key in keys:
        value = payload.get(key)
        if value is not None:
            selected.append({key: value})
    return selected


def _memory_context_items(payload: dict[str, Any]) -> list[Any]:
    selected = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if key == "messages":
            continue
        if "memory" in lowered or "context" in lowered:
            selected.append({key: value})
    return selected


def _last_role_index(messages: list[Any], role: str) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if _role(messages[index]) == role:
            return index
    return None


def _role(item: Any) -> str:
    return str(_as_dict(item).get("role") or "")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _provider_output_count(response_payload: Any) -> int:
    if not isinstance(response_payload, dict):
        return 0
    choices = response_payload.get("choices")
    if isinstance(choices, list):
        return len(choices)
    output = response_payload.get("output")
    if isinstance(output, list):
        return len(output)
    return 1
