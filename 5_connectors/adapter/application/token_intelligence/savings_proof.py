"""Actual savings proof helpers."""

from __future__ import annotations

from typing import Any


def build_actual_savings_proof(payload: dict[str, Any]) -> dict[str, Any]:
    recommended = _safe_int(payload.get("recommended_saving_tokens"))
    baseline = _safe_int(payload.get("baseline_tokens"))
    actual = _safe_int(payload.get("actual_tokens"))
    realized = max(0, baseline - actual) if baseline > 0 else 0
    negative = max(0, actual - baseline) if baseline > 0 else 0
    ratio = round(realized / recommended, 4) if recommended > 0 else 0.0
    status = _status(recommended=recommended, realized=realized, negative=negative)
    return {
        "schema_version": "token-intelligence-actual-savings-proof-v1",
        "recommendation_id": str(payload.get("recommendation_id") or ""),
        "category": str(payload.get("category") or ""),
        "recommended_saving_tokens": recommended,
        "baseline_tokens": baseline,
        "actual_tokens": actual,
        "realized_saving_tokens": realized,
        "negative_saving_tokens": negative,
        "realization_ratio": ratio,
        "status": status,
        "source": "local_estimated",
        "confidence": "compatible_estimate",
    }


def _status(*, recommended: int, realized: int, negative: int) -> str:
    if negative > 0:
        return "negative_saving"
    if recommended <= 0:
        return "no_recommendation"
    if realized <= 0:
        return "no_saving"
    if realized >= recommended:
        return "realized"
    return "partial"


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0
