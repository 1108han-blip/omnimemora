"""Anthropic tool graph analysis for structured compile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .ir import CompileIR, parse_anthropic_payload


@dataclass(frozen=True)
class ToolGraphIssue:
    code: str
    message_index: int
    content_index: int
    tool_use_id: str = ""
    detail: str = ""


@dataclass(frozen=True)
class ToolGraphAnalysis:
    ir: CompileIR
    valid: bool
    issues: List[ToolGraphIssue] = field(default_factory=list)

    @property
    def has_tool_graph(self) -> bool:
        return self.ir.has_tool_graph


def analyze_anthropic_tool_graph(payload: Dict[str, Any]) -> ToolGraphAnalysis:
    """Parse and validate an Anthropic-compatible tool graph."""
    ir = parse_anthropic_payload(payload)
    issues = _validate_tool_graph(ir)
    return ToolGraphAnalysis(ir=ir, valid=not issues, issues=issues)


def validate_anthropic_tool_graph(payload: Dict[str, Any]) -> bool:
    """Return true when the Anthropic tool graph is valid or absent."""
    return analyze_anthropic_tool_graph(payload).valid


def _validate_tool_graph(ir: CompileIR) -> List[ToolGraphIssue]:
    issues: List[ToolGraphIssue] = []
    seen_tool_ids: Set[str] = set()
    result_ids: Set[str] = set()

    for block in ir.blocks:
        message_index = block.message_index if block.message_index is not None else -1
        content_index = block.content_index if block.content_index is not None else -1
        if block.block_type == "tool_call":
            if not block.tool_use_id:
                issues.append(
                    ToolGraphIssue(
                        code="missing_tool_use_id",
                        message_index=message_index,
                        content_index=content_index,
                        detail="tool_use block has no id",
                    )
                )
                continue
            if block.tool_use_id in seen_tool_ids:
                issues.append(
                    ToolGraphIssue(
                        code="duplicate_tool_use_id",
                        message_index=message_index,
                        content_index=content_index,
                        tool_use_id=block.tool_use_id,
                    )
                )
            seen_tool_ids.add(block.tool_use_id)

        if block.block_type == "tool_result_recent":
            if not block.tool_use_id:
                issues.append(
                    ToolGraphIssue(
                        code="missing_tool_result_id",
                        message_index=message_index,
                        content_index=content_index,
                        detail="tool_result block has no tool_use_id",
                    )
                )
                continue
            if block.tool_use_id not in seen_tool_ids:
                issues.append(
                    ToolGraphIssue(
                        code="unknown_tool_result_id",
                        message_index=message_index,
                        content_index=content_index,
                        tool_use_id=block.tool_use_id,
                    )
                )
            result_ids.add(block.tool_use_id)

    for tool_use_id in sorted(seen_tool_ids - result_ids):
        call_block = next(
            block
            for block in ir.blocks
            if block.block_type == "tool_call" and block.tool_use_id == tool_use_id
        )
        issues.append(
            ToolGraphIssue(
                code="missing_tool_result",
                message_index=call_block.message_index if call_block.message_index is not None else -1,
                content_index=call_block.content_index if call_block.content_index is not None else -1,
                tool_use_id=tool_use_id,
            )
        )

    return issues

