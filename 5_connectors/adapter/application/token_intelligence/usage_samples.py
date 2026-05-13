"""Unified LLM usage sample recording for product ingress."""

from __future__ import annotations

import json
from typing import Any, Optional

from .block_breakdown import classify_openai_compatible_blocks
from .ledger import build_audit_event, record_audit_event
from .models import AuditEvent, NormalizedUsage
from .reconciliation import reconcile_openai_compatible_usage
from .usage_normalizer import (
    estimate_anthropic_compatible_output_tokens,
    estimate_openai_compatible_input_tokens,
    estimate_openai_compatible_output_tokens,
    normalize_anthropic_compatible_usage,
    normalize_openai_compatible_cost,
    normalize_openai_compatible_usage,
)
from .waste_detectors import detect_openai_compatible_waste


SCHEMA_VERSION = "llm-usage-sample-v1"


def record_openai_usage_sample(
    *,
    request_id: str,
    route: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    upstream_base_url: str,
    provider: str,
    model_requested: str,
    latency_ms: Optional[int] = None,
    status_code: Optional[int] = None,
    agent_id: Optional[str] = None,
    workflow_tag: Optional[str] = None,
    project_id: Optional[str] = None,
    workspace_tag: Optional[str] = None,
    path: Optional[str] = None,
) -> AuditEvent:
    """Record a metadata-only OpenAI-compatible usage sample."""
    local_input = estimate_openai_compatible_input_tokens(request_payload)
    local_output = estimate_openai_compatible_output_tokens(response_payload)
    usage = normalize_openai_compatible_usage(
        response_payload,
        local_input_estimate=local_input,
        local_output_estimate=local_output,
    )
    reconciliation = reconcile_openai_compatible_usage(request_payload, response_payload, usage)
    blocks = classify_openai_compatible_blocks(request_payload, response_payload)
    opportunities = detect_openai_compatible_waste(request_payload, blocks)
    event = _build_usage_event(
        protocol="openai_chat_completions",
        route=route,
        request_id=request_id,
        request_payload=request_payload,
        response_payload=response_payload,
        upstream_base_url=upstream_base_url,
        provider=provider,
        model_requested=model_requested,
        usage=usage,
        local_input=local_input,
        local_output=local_output,
        latency_ms=latency_ms,
        status_code=status_code,
        agent_id=agent_id,
        workflow_tag=workflow_tag,
        project_id=project_id,
        workspace_tag=workspace_tag,
        finish_reason=_openai_finish_reason(response_payload),
        model_reported=_string_field(response_payload, "model") or model_requested,
        reconciliation=reconciliation,
        blocks=blocks,
        opportunities=opportunities,
    )
    record_audit_event(event, path=path)
    return event


def record_anthropic_usage_sample(
    *,
    request_id: str,
    route: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    upstream_base_url: str,
    provider: str,
    model_requested: str,
    latency_ms: Optional[int] = None,
    status_code: Optional[int] = None,
    agent_id: Optional[str] = None,
    workflow_tag: Optional[str] = None,
    project_id: Optional[str] = None,
    workspace_tag: Optional[str] = None,
    path: Optional[str] = None,
) -> AuditEvent:
    """Record a metadata-only Anthropic Messages usage sample."""
    local_input = estimate_openai_compatible_input_tokens(request_payload)
    local_output = estimate_anthropic_compatible_output_tokens(response_payload)
    usage = normalize_anthropic_compatible_usage(
        response_payload,
        local_input_estimate=local_input,
        local_output_estimate=local_output,
    )
    reconciliation = _reconcile_usage(
        usage=usage,
        local_input=local_input,
        local_output=local_output,
    )
    blocks = classify_openai_compatible_blocks(request_payload, response_payload)
    opportunities = detect_openai_compatible_waste(request_payload, blocks)
    event = _build_usage_event(
        protocol="anthropic_messages",
        route=route,
        request_id=request_id,
        request_payload=request_payload,
        response_payload=response_payload,
        upstream_base_url=upstream_base_url,
        provider=provider,
        model_requested=model_requested,
        usage=usage,
        local_input=local_input,
        local_output=local_output,
        latency_ms=latency_ms,
        status_code=status_code,
        agent_id=agent_id,
        workflow_tag=workflow_tag,
        project_id=project_id,
        workspace_tag=workspace_tag,
        finish_reason=_string_field(response_payload, "stop_reason"),
        model_reported=_string_field(response_payload, "model") or model_requested,
        reconciliation=reconciliation,
        blocks=blocks,
        opportunities=opportunities,
    )
    record_audit_event(event, path=path)
    return event


def _build_usage_event(
    *,
    protocol: str,
    route: str,
    request_id: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    upstream_base_url: str,
    provider: str,
    model_requested: str,
    usage: NormalizedUsage,
    local_input: Optional[int],
    local_output: Optional[int],
    latency_ms: Optional[int],
    status_code: Optional[int],
    agent_id: Optional[str],
    workflow_tag: Optional[str],
    project_id: Optional[str],
    workspace_tag: Optional[str],
    finish_reason: Optional[str],
    model_reported: str,
    reconciliation: dict[str, Any],
    blocks: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
) -> AuditEvent:
    metadata = _drop_none(
        {
            "schema_version": SCHEMA_VERSION,
            "route": route,
            "protocol": protocol,
            "provider": provider,
            "agent_id": _safe_tag(agent_id),
            "workflow_tag": _safe_tag(workflow_tag),
            "project_id": _safe_tag(project_id),
            "workspace_tag": _safe_tag(workspace_tag),
            "provider_event_id": _safe_tag(_string_field(response_payload, "id")),
            "input_chars": _serialized_len(request_payload),
            "output_chars": _output_chars(protocol, response_payload),
            "local_estimated_input_tokens": local_input,
            "local_estimated_output_tokens": local_output,
            "provider_input_tokens": usage.input_tokens,
            "provider_output_tokens": usage.output_tokens,
            "provider_total_tokens": usage.total_tokens,
            "cache_read_tokens": usage.cached_input_tokens,
            "cache_write_tokens": usage.cache_write_tokens,
            "reasoning_tokens": usage.reasoning_tokens,
            "finish_reason": _safe_tag(finish_reason),
            "usage_source": usage.source,
            "usage_confidence": usage.confidence,
            "verification_status": _verification_status(usage, reconciliation),
            "reported_to_estimated_ratio": _reported_to_estimated_ratio(usage.total_tokens, local_input, local_output),
            "stream_observation_status": "complete",
        }
    )
    return build_audit_event(
        request_id=request_id,
        request_payload=request_payload,
        response_payload=response_payload,
        upstream_base_url=upstream_base_url,
        provider=provider,
        model_requested=model_requested,
        model_reported=model_reported,
        usage=usage,
        cost=normalize_openai_compatible_cost(response_payload),
        latency_ms=latency_ms,
        status_code=status_code,
        metadata=metadata,
        blocks=blocks,
        opportunities=opportunities,
        reconciliation=reconciliation,
    )


def _reconcile_usage(
    *,
    usage: NormalizedUsage,
    local_input: Optional[int],
    local_output: Optional[int],
) -> dict[str, Any]:
    local_total = _sum_optional(local_input, local_output)
    reported_total = usage.total_tokens
    delta = None
    delta_ratio = None
    status = "not_applicable"
    if reported_total is not None and local_total is not None and local_total > 0:
        delta = max(0, int(reported_total) - int(local_total))
        delta_ratio = round(delta / local_total, 4)
        status = _status(delta_ratio)
    elif usage.source == "local_estimated":
        status = "estimated_only"
    return {
        "schema_version": "token-intelligence-usage-reconciliation-v1",
        "reported_total_tokens": reported_total,
        "local_total_estimate": local_total,
        "local_input_estimate": local_input,
        "local_output_estimate": local_output,
        "delta_tokens": delta,
        "delta_ratio": delta_ratio,
        "status": status,
        "source": "local_estimated",
        "confidence": "compatible_estimate" if local_total is not None else "rough_estimate",
    }


def _status(delta_ratio: Optional[float]) -> str:
    if delta_ratio is None:
        return "not_applicable"
    if delta_ratio <= 0.25:
        return "normal"
    if delta_ratio <= 1.0:
        return "warning"
    return "unexplained_delta"


def _verification_status(usage: NormalizedUsage, reconciliation: dict[str, Any]) -> str:
    if usage.raw_usage_present is False:
        return "estimated_only"
    status = str(reconciliation.get("status") or "")
    if status in {"normal", "warning", "unexplained_delta"}:
        return status
    return "not_applicable"


def _reported_to_estimated_ratio(
    reported_total: Optional[int],
    local_input: Optional[int],
    local_output: Optional[int],
) -> Optional[float]:
    local_total = _sum_optional(local_input, local_output)
    if reported_total is None or local_total is None or local_total <= 0:
        return None
    return round(float(reported_total) / float(local_total), 4)


def _openai_finish_reason(payload: dict[str, Any]) -> Optional[str]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0] if isinstance(choices[0], dict) else {}
    return _safe_tag(first.get("finish_reason"))


def _output_chars(protocol: str, payload: dict[str, Any]) -> int:
    if protocol == "anthropic_messages":
        return _anthropic_output_chars(payload)
    return _openai_output_chars(payload)


def _openai_output_chars(payload: dict[str, Any]) -> int:
    chars = 0
    choices = payload.get("choices")
    for choice in choices if isinstance(choices, list) else []:
        message = choice.get("message") if isinstance(choice, dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            chars += len(content) if isinstance(content, str) else _serialized_len(content)
    return chars or _serialized_len(payload)


def _anthropic_output_chars(payload: dict[str, Any]) -> int:
    chars = 0
    content = payload.get("content")
    for part in content if isinstance(content, list) else []:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        thinking = part.get("thinking")
        if isinstance(text, str):
            chars += len(text)
        if isinstance(thinking, str):
            chars += len(thinking)
    return chars or _serialized_len(payload)


def _serialized_len(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        return len(str(value or ""))


def _string_field(payload: Any, key: str) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return str(value) if value is not None else None


def _safe_tag(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped[:120] if stripped else None


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _sum_optional(*values: Optional[int]) -> Optional[int]:
    present = [int(value) for value in values if value is not None]
    if not present:
        return None
    return sum(present)
