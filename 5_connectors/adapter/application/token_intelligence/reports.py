"""Compact Token Intelligence reports."""

from __future__ import annotations

from typing import Any


def build_potential_savings_report(summary: dict[str, Any]) -> dict[str, Any]:
    opportunities = summary.get("top_opportunities") if isinstance(summary, dict) else []
    blocks = summary.get("top_blocks") if isinstance(summary, dict) else []
    models = summary.get("top_models") if isinstance(summary, dict) else []
    opportunity_items = opportunities if isinstance(opportunities, list) else []
    total_potential = sum(_safe_int(item.get("potential_saving_tokens")) for item in opportunity_items if isinstance(item, dict))
    return {
        "schema_version": "token-intelligence-potential-savings-report-v1",
        "event_count": _safe_int(summary.get("event_count")) if isinstance(summary, dict) else 0,
        "potential_saving_tokens": total_potential,
        "top_opportunities": opportunity_items[:10],
        "top_blocks": blocks[:10] if isinstance(blocks, list) else [],
        "top_models": models[:10] if isinstance(models, list) else [],
        "top_agents": _list_field(summary, "top_agents"),
        "top_workflows": _list_field(summary, "top_workflows"),
        "top_projects": _list_field(summary, "top_projects"),
        "source": "local_estimated",
        "confidence": "compatible_estimate" if total_potential > 0 else "rough_estimate",
        "advice": _advice(opportunity_items),
    }


def _advice(opportunities: list[Any]) -> list[dict[str, str]]:
    categories = {str(item.get("category") or "") for item in opportunities if isinstance(item, dict)}
    advice: list[dict[str, str]] = []
    if "duplicate_context" in categories:
        advice.append({"category": "duplicate_context", "action": "deduplicate repeated context before forwarding"})
    if "long_tool_result" in categories or "tool_result_heavy_context" in categories:
        advice.append({"category": "tool_results", "action": "compress long tool results before reuse"})
    return advice


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _list_field(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key) if isinstance(payload, dict) else []
    return value[:10] if isinstance(value, list) else []
