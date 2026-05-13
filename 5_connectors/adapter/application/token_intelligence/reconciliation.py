"""Usage reconciliation between reported usage and local estimates."""

from __future__ import annotations

from typing import Any, Optional

from .models import NormalizedUsage
from .usage_normalizer import estimate_openai_compatible_input_tokens, estimate_openai_compatible_output_tokens


def reconcile_openai_compatible_usage(
    request_payload: Any,
    response_payload: Any,
    usage: NormalizedUsage,
) -> dict[str, Any]:
    local_input = estimate_openai_compatible_input_tokens(request_payload)
    local_output = estimate_openai_compatible_output_tokens(response_payload)
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


def _sum_optional(*values: Optional[int]) -> Optional[int]:
    present = [int(value) for value in values if value is not None]
    if not present:
        return None
    return sum(present)
