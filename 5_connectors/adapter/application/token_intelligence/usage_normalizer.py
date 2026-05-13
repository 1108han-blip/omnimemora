"""Provider usage normalization for Token Intelligence Lite."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .models import NormalizedUsage


def normalize_openai_compatible_usage(
    response_payload: Dict[str, Any],
    *,
    local_input_estimate: Optional[int] = None,
    local_output_estimate: Optional[int] = None,
    usage_source: str = "provider_reported",
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
            confidence="tokenizer_estimate" if total is not None else "rough_estimate",
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


def _sum_optional(*values: Optional[int]) -> Optional[int]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)
