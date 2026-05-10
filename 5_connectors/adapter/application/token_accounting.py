"""
Token accounting helpers.

Separates two metrics that used to be conflated:
- compression metrics: how much OmniMemora can compact selected context
- real input savings: full upstream payload delta after OmniMemora routing
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


def estimate_payload_tokens(payload: Any) -> int:
    """Estimate complete payload tokens from the serialized upstream request."""
    if payload is None:
        return 0
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        text = str(payload)
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def build_token_accounting(
    *,
    original_payload: Optional[dict],
    forwarded_payload: Optional[dict],
    compression_source_tokens: int,
    compression_output_tokens: int,
    metric_confidence: str = "estimated_payload",
) -> Dict[str, Any]:
    """Build conservative token-value fields for a meter payload."""
    baseline_payload_tokens = estimate_payload_tokens(original_payload)
    forwarded_payload_tokens = estimate_payload_tokens(forwarded_payload)
    real_input_saved_tokens = max(0, baseline_payload_tokens - forwarded_payload_tokens)
    real_input_savings_ratio = (
        real_input_saved_tokens / baseline_payload_tokens
        if baseline_payload_tokens > 0
        else 0.0
    )

    compression_source_tokens = max(0, int(compression_source_tokens or 0))
    compression_output_tokens = max(0, int(compression_output_tokens or 0))
    compression_saved_tokens = max(0, compression_source_tokens - compression_output_tokens)
    compression_ratio = (
        compression_saved_tokens / compression_source_tokens
        if compression_source_tokens > 0
        else 0.0
    )

    return {
        "baseline_payload_tokens": baseline_payload_tokens,
        "forwarded_payload_tokens": forwarded_payload_tokens,
        "real_input_saved_tokens": real_input_saved_tokens,
        "real_input_savings_ratio": round(real_input_savings_ratio, 4),
        "omni_added_tokens": max(0, forwarded_payload_tokens - baseline_payload_tokens),
        "omni_removed_tokens": real_input_saved_tokens,
        "compression_source_tokens": compression_source_tokens,
        "compression_output_tokens": compression_output_tokens,
        "compression_saved_tokens": compression_saved_tokens,
        "compression_ratio": round(compression_ratio, 4),
        "metric_confidence": metric_confidence,
    }
