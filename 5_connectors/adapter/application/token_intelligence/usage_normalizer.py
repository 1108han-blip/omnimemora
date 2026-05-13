"""Provider usage normalization for Token Intelligence Lite."""

from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Optional

from .models import NormalizedCost, NormalizedUsage


def normalize_openai_compatible_usage(
    response_payload: Dict[str, Any],
    *,
    local_input_estimate: Optional[int] = None,
    local_output_estimate: Optional[int] = None,
    usage_source: str = "provider_reported",
    local_estimate_confidence: str = "tokenizer_estimate",
) -> NormalizedUsage:
    """Normalize OpenAI-compatible usage fields.

    If upstream usage is absent, returns an explicitly estimated usage object.
    """
    raw_usage = response_payload.get("usage") if isinstance(response_payload, dict) else None
    if not isinstance(raw_usage, dict):
        input_estimate = _safe_int(local_input_estimate)
        output_estimate = _safe_int(local_output_estimate)
        total = _sum_optional(input_estimate, output_estimate)
        return NormalizedUsage(
            input_tokens=input_estimate,
            output_tokens=output_estimate,
            total_tokens=total,
            source="local_estimated",
            confidence=local_estimate_confidence if total is not None else "rough_estimate",
            raw_usage_present=False,
        )

    prompt_details = raw_usage.get("prompt_tokens_details")
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    completion_details = raw_usage.get("completion_tokens_details")
    if not isinstance(completion_details, dict):
        completion_details = {}

    return NormalizedUsage(
        input_tokens=_safe_int(raw_usage.get("prompt_tokens")),
        output_tokens=_safe_int(raw_usage.get("completion_tokens")),
        total_tokens=_safe_int(raw_usage.get("total_tokens")),
        cached_input_tokens=_safe_int(prompt_details.get("cached_tokens")),
        cache_write_tokens=_safe_int(prompt_details.get("cache_write_tokens")),
        reasoning_tokens=_safe_int(completion_details.get("reasoning_tokens")),
        image_tokens=_first_int(prompt_details.get("image_tokens"), completion_details.get("image_tokens")),
        audio_tokens=_first_int(prompt_details.get("audio_tokens"), completion_details.get("audio_tokens")),
        source=usage_source,
        confidence="official_usage",
        raw_usage_present=True,
    )


def estimate_openai_compatible_input_tokens(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    return _estimate_payload_tokens(payload)


def estimate_openai_compatible_output_tokens(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        return _estimate_payload_tokens({"choices": choices})
    output = payload.get("output")
    if output is not None:
        return _estimate_payload_tokens({"output": output})
    return None


def normalize_openai_compatible_cost(
    response_payload: Dict[str, Any],
    *,
    cost_source: str = "provider_reported",
) -> NormalizedCost:
    """Normalize provider/relay-reported OpenAI-compatible cost fields.

    This does not infer cost from a local price table. When no upstream cost is
    present, the returned object stays empty except for source/confidence labels.
    """
    if not isinstance(response_payload, dict):
        return NormalizedCost()
    raw_usage = response_payload.get("usage")
    usage_payload = raw_usage if isinstance(raw_usage, dict) else {}
    cost_value = _first_float(
        usage_payload.get("cost"),
        usage_payload.get("total_cost"),
        usage_payload.get("total_cost_usd"),
        response_payload.get("cost"),
        response_payload.get("total_cost"),
        response_payload.get("total_cost_usd"),
    )
    if cost_value is None:
        return NormalizedCost()
    pricing_version = _first_str(
        usage_payload.get("pricing_version"),
        usage_payload.get("price_version"),
        response_payload.get("pricing_version"),
        response_payload.get("price_version"),
    )
    return NormalizedCost(
        total_cost_usd=cost_value,
        source=cost_source,
        confidence="official_usage",
        pricing_version=pricing_version or "",
    )


def _estimate_payload_tokens(payload: Dict[str, Any]) -> Optional[int]:
    try:
        metrics = importlib.import_module("context_compiler.metrics")
        estimate = metrics.estimate_payload_tokens_detailed(payload)
        return max(1, int(estimate.tokens))
    except Exception:
        try:
            serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            serialized = str(payload)
        return max(1, int(len(serialized) / 4)) if serialized else None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return max(0, int(value))
    except Exception:
        return None


def _first_int(*values: Any) -> Optional[int]:
    for value in values:
        normalized = _safe_int(value)
        if normalized is not None:
            return normalized
    return None


def _first_float(*values: Any) -> Optional[float]:
    for value in values:
        normalized = _safe_float(value)
        if normalized is not None:
            return normalized
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = float(value)
    except Exception:
        return None
    return normalized if normalized >= 0 else None


def _first_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _sum_optional(*values: Optional[int]) -> Optional[int]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)
