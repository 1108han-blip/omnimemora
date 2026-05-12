"""Structured compile IR for provider payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CompileBlock:
    """A provider payload segment classified for future compile decisions."""

    block_type: str
    role: str
    message_index: Optional[int]
    content_index: Optional[int]
    content: Any
    protected: bool = False
    tool_use_id: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompileIR:
    """Provider payload parsed into blocks without changing the payload."""

    protocol: str
    payload: Dict[str, Any]
    messages: List[Dict[str, Any]]
    blocks: List[CompileBlock]

    @property
    def has_tool_graph(self) -> bool:
        return any(block.block_type in {"tool_call", "tool_result_recent"} for block in self.blocks)


def parse_anthropic_payload(payload: Dict[str, Any]) -> CompileIR:
    """Parse an Anthropic-compatible payload into compile blocks.

    The parser is deliberately conservative: it preserves the original payload
    object as data and only emits analysis blocks for later compiler stages.
    """
    messages = payload.get("messages") or []
    blocks: List[CompileBlock] = []

    if payload.get("system"):
        blocks.append(
            CompileBlock(
                block_type="system_policy",
                role="system",
                message_index=None,
                content_index=None,
                content=payload.get("system"),
                protected=True,
            )
        )

    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        content = message.get("content")

        if isinstance(content, str):
            blocks.append(
                CompileBlock(
                    block_type=_text_block_type(role, message_index, messages),
                    role=role,
                    message_index=message_index,
                    content_index=None,
                    content=content,
                    protected=role in {"system"},
                )
            )
            continue

        if not isinstance(content, list):
            continue

        for content_index, part in enumerate(content):
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "")
            if part_type == "tool_use":
                blocks.append(
                    CompileBlock(
                        block_type="tool_call",
                        role=role,
                        message_index=message_index,
                        content_index=content_index,
                        content=part,
                        protected=True,
                        tool_use_id=_string_or_none(part.get("id")),
                        tool_name=_string_or_none(part.get("name")),
                    )
                )
            elif part_type == "tool_result":
                blocks.append(
                    CompileBlock(
                        block_type="tool_result_recent",
                        role=role,
                        message_index=message_index,
                        content_index=content_index,
                        content=part,
                        protected=True,
                        tool_use_id=_string_or_none(part.get("tool_use_id")),
                    )
                )
            elif part_type == "text":
                blocks.append(
                    CompileBlock(
                        block_type=_text_block_type(role, message_index, messages),
                        role=role,
                        message_index=message_index,
                        content_index=content_index,
                        content=part.get("text", ""),
                        protected=role in {"system"},
                        metadata={"source_type": "text"},
                    )
                )

    return CompileIR(protocol="anthropic", payload=payload, messages=messages, blocks=blocks)


def _text_block_type(role: str, message_index: int, messages: List[Dict[str, Any]]) -> str:
    if role == "user" and message_index == _last_user_message_index(messages):
        return "current_user_intent"
    if role == "assistant":
        return "assistant_state"
    if role == "system":
        return "system_policy"
    return "conversation_history"


def _last_user_message_index(messages: List[Dict[str, Any]]) -> Optional[int]:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if isinstance(message, dict) and message.get("role") == "user":
            return index
    return None


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

