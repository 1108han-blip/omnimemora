"""
metrics_service.py - OmniMemora Metrics Aggregation Layer
==========================================================
Provides /metrics/summary and /metrics/recent_requests endpoints
by aggregating data from meter_store.

All metrics are computed from real running data - no mocks.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

# Lazy import to avoid circular imports
import importlib
_5_meter = importlib.import_module("5_connectors.adapter.meter_store")


def _collect_meters(tenant: str):
    _5_meter._ensure_persistence_loaded()
    if tenant == "all":
        return [m for tenant_meters in _5_meter._usage_aggregates.values() for m in tenant_meters]
    return _5_meter._usage_aggregates.get(tenant, [])


def compute_metrics_summary(tenant: str) -> Dict[str, Any]:
    """
    Compute the 4 hero metrics for the dashboard.

    Returns:
        {
            "token_saving_ratio": float,   # 0.0 - 1.0
            "tokens_saved": int,           # total saved tokens
            "request_count": int,          # total requests
            "avg_context_reduction": float # 0.0 - 1.0, mean((baseline-actual)/baseline)
        }
    """
    meters = _collect_meters(tenant)

    if not meters:
        return {
            "token_saving_ratio": 0.0,
            "tokens_saved": 0,
            "request_count": 0,
            "avg_context_reduction": 0.0,
        }

    total_requests = len(meters)
    baseline_total = sum(m.baseline_tokens_estimate for m in meters)
    actual_total = sum(m.actual_tokens_estimate for m in meters)
    saved_total = sum(m.saved_tokens_estimate for m in meters)
    avg_ratio = saved_total / baseline_total if baseline_total > 0 else 0.0

    # Compute avg_context_reduction: mean of (baseline - actual) / baseline per request
    reductions = []
    for m in meters:
        if m.baseline_tokens_estimate > 0:
            reduction = (m.baseline_tokens_estimate - m.actual_tokens_estimate) / m.baseline_tokens_estimate
            reductions.append(reduction)
    avg_reduction = sum(reductions) / len(reductions) if reductions else 0.0

    return {
        "token_saving_ratio": round(avg_ratio, 3),
        "tokens_saved": saved_total,
        "request_count": total_requests,
        "avg_context_reduction": round(avg_reduction, 3),
    }


def get_recent_requests(tenant: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get the most recent N requests for a tenant.

    Returns a list of lightweight request summaries suitable for the Live Flow module.
    """
    meters = _collect_meters(tenant)

    if not meters:
        return []

    # Sort by timestamp descending
    sorted_meters = sorted(meters, key=lambda m: m.timestamp, reverse=True)
    recent = sorted_meters[:limit]

    return [
        {
            "request_id": m.request_id,
            "agent": m.agent,
            "timestamp": m.timestamp,
            "task_type": getattr(m, "task_type", None) or "unknown",
            "bypass": m.context_bypass,
            "saved_tokens": m.saved_tokens_estimate,
            "savings_ratio": m.savings_ratio,
            "query": getattr(m, "query", "")[:80],
            "packed_memory_count": m.packed_memory_count,
            "local_cards_used": m.local_cards_used,
        }
        for m in recent
    ]


def list_tenants() -> List[str]:
    _5_meter._ensure_persistence_loaded()
    tenants = sorted([tenant for tenant, meters in _5_meter._usage_aggregates.items() if meters])
    return tenants
