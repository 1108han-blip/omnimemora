"""Anthropic tool schema checks for structured compile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass(frozen=True)
class ToolSchemaIssue:
    code: str
    message_index: int = -1
    content_index: int = -1
    tool_name: str = ""
    detail: str = ""


@dataclass(frozen=True)
class ToolSchemaAnalysis:
    valid: bool
    issues: List[ToolSchemaIssue] = field(default_factory=list)


def analyze_anthropic_tool_schema(payload: Dict[str, Any]) -> ToolSchemaAnalysis:
    """Validate provided tool schemas against tool_use blocks.

    Anthropic-compatible clients may omit the top-level tools field when the
    provider already has session/tool context. When tools are provided, the
    compiler treats them as authoritative and refuses to rewrite payloads that
    reference undeclared tools.
    """
    tool_uses = _collect_tool_uses(payload)
    if not tool_uses:
        return ToolSchemaAnalysis(valid=True)

    if "tools" not in payload:
        return ToolSchemaAnalysis(valid=True)

    tools = payload.get("tools")
    if not isinstance(tools, list):
        return ToolSchemaAnalysis(
            valid=False,
            issues=[ToolSchemaIssue(code="invalid_tools_schema", detail="tools is not a list")],
        )

    issues: List[ToolSchemaIssue] = []
    declared_names: Set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict) or not tool.get("name"):
            issues.append(
                ToolSchemaIssue(
                    code="invalid_tool_definition",
                    detail=f"tools[{index}] has no name",
                )
            )
            continue
        declared_names.add(str(tool["name"]))

    for tool_use in tool_uses:
        name = tool_use.tool_name
        if not name:
            issues.append(
                ToolSchemaIssue(
                    code="missing_tool_use_name",
                    message_index=tool_use.message_index,
                    content_index=tool_use.content_index,
                )
            )
            continue
        if name not in declared_names:
            issues.append(
                ToolSchemaIssue(
                    code="undeclared_tool_use_name",
                    message_index=tool_use.message_index,
                    content_index=tool_use.content_index,
                    tool_name=name,
                )
            )

    return ToolSchemaAnalysis(valid=not issues, issues=issues)


def validate_anthropic_tool_schema(payload: Dict[str, Any]) -> bool:
    return analyze_anthropic_tool_schema(payload).valid


@dataclass(frozen=True)
class _ToolUseRef:
    message_index: int
    content_index: int
    tool_name: str


def _collect_tool_uses(payload: Dict[str, Any]) -> List[_ToolUseRef]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return []

    tool_uses: List[_ToolUseRef] = []
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for content_index, part in enumerate(content):
            if isinstance(part, dict) and part.get("type") == "tool_use":
                tool_uses.append(
                    _ToolUseRef(
                        message_index=message_index,
                        content_index=content_index,
                        tool_name=str(part.get("name") or ""),
                    )
                )
    return tool_uses
