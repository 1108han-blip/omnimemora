"""
metrics_service.py - OmniMemora Metrics Aggregation Layer
==========================================================
Provides /metrics/summary and /metrics/recent_requests endpoints
by aggregating data from meter_store.

All metrics are computed from real running data - no mocks.

Public interfaces for core capabilities (首页四卡):
  - compute_core_capabilities(tenant)     -> 24h four-card summary
  - compute_core_capabilities_trend(...)  -> multi-day trend
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

# Lazy import to avoid circular imports
import importlib
_5_meter = importlib.import_module("5_connectors.adapter.meter_store")
_5_rc = importlib.import_module("5_connectors.adapter.request_classifier")


def _clamp_ratio(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _collect_meters(tenant: str):
    _5_meter._ensure_persistence_loaded()
    if tenant == "all":
        return [m for tenant_meters in _5_meter._usage_aggregates.values() for m in tenant_meters]
    return _5_meter._usage_aggregates.get(tenant, [])


def _collect_meters_24h(tenant: str):
    """Collect meters within the last 24 hours."""
    meters = _collect_meters(tenant)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    filtered = []
    for m in meters:
        try:
            m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if m_time >= cutoff:
            filtered.append(m)
    return filtered


def _default_overview_meters(meters: List[Any], include_internal: bool = False) -> List[Any]:
    """
    Normalize the default user-facing request set for overview surfaces.

    Rules:
    1. Drop operator verification traffic so default overview reflects user use.
    2. Collapse short retry bursts for the same prompt into one request.
    3. Optionally keep internal events for coverage denominators.
    """
    filtered = [m for m in meters if not _5_rc.is_operator_verification_request(m)]
    collapsed = _5_rc.collapse_retry_bursts(filtered)
    if not include_internal:
        collapsed = [m for m in collapsed if _5_rc.is_real_request(m)]
    return sorted(collapsed, key=lambda m: m.timestamp, reverse=True)


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
    meters = _default_overview_meters(_collect_meters(tenant))

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


def get_recent_requests(tenant: str, limit: int = 20, include_internal: bool = False) -> List[Dict[str, Any]]:
    """
    Get the most recent N requests for a tenant.

    Args:
        tenant: Tenant identifier
        limit: Maximum number of requests to return
        include_internal: If False (default), excludes bootstrap/handshake/internal requests.
                         If True, includes all requests for diagnostics.

    Returns a list of lightweight request summaries suitable for the Live Flow module.
    """
    meters = _collect_meters_24h(tenant)

    if not meters:
        return []

    sorted_meters = _default_overview_meters(meters, include_internal=include_internal)

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


def compute_metrics_summary_24h(tenant: str) -> Dict[str, Any]:
    """
    Compute the 4 hero metrics for the dashboard, restricted to the last 24 hours.
    Used for HeroMetrics正面 (default view).

    Returns:
        {
            "token_saving_ratio": float,
            "tokens_saved": int,
            "request_count": int,
            "avg_context_reduction": float,
            "period": "24h",
        }
    """
    meters = _default_overview_meters(_collect_meters_24h(tenant))

    if not meters:
        return {
            "token_saving_ratio": 0.0,
            "tokens_saved": 0,
            "request_count": 0,
            "avg_context_reduction": 0.0,
            "period": "24h",
        }

    total_requests = len(meters)
    baseline_total = sum(m.baseline_tokens_estimate for m in meters)
    actual_total = sum(m.actual_tokens_estimate for m in meters)
    saved_total = sum(m.saved_tokens_estimate for m in meters)
    avg_ratio = saved_total / baseline_total if baseline_total > 0 else 0.0

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
        "period": "24h",
    }


# =============================================================================
# Internal/bootstrap filtering — now delegates to request_classifier
# =============================================================================

def _is_real_request(meter: Any) -> bool:
    """
    Return True if this meter represents a real user-facing request.
    Excludes internal/bootstrap events like session handshakes.

    Delegates to request_classifier.is_real_request() for unified logic.
    """
    return _5_rc.is_real_request(meter)


# =============================================================================
# Core Capabilities — 首页四卡专用聚合（过滤 internal/bootstrap）
# =============================================================================

def compute_core_capabilities(tenant: str) -> Dict[str, Any]:
    """
    Compute the four-card 24h summary for the homepage.

    Card 1: Real Requests — count + ratio
    Card 2: Context Compression — ratio + tokens
    Card 3: Memory Enhancement — rate + memory_count
    Card 4: Token Savings — ratio + saved_tokens

    Only real requests are included; internal/bootstrap events are excluded.
    """
    meters = _collect_meters_24h(tenant)
    observed_meters = _default_overview_meters(meters, include_internal=True)
    real_meters = [m for m in observed_meters if _is_real_request(m)]
    observed_count = len(observed_meters)
    real_count = len(real_meters)
    real_ratio = real_count / observed_count if observed_count > 0 else 0.0

    if not real_meters:
        return {
            "period": "24h",
            "observed_request_count": observed_count,
            "cards": {
                "real_requests": {"count": 0, "ratio": 0.0},
                "context_compression": {"ratio": 0.0, "baseline_tokens": 0, "actual_tokens": 0},
                "memory_enhancement": {"rate": 0.0, "memory_count": 0},
                "token_savings": {"ratio": 0.0, "saved_tokens": 0},
            },
        }

    # Card 2: context compression (compression_ratio = 1 - actual/baseline)
    total_baseline = sum(m.baseline_tokens_estimate for m in real_meters)
    total_actual = sum(m.actual_tokens_estimate for m in real_meters)
    compression_ratio = _clamp_ratio(1 - (total_actual / total_baseline)) if total_baseline > 0 else 0.0

    # Card 3: memory enhancement (requests with packed_memory_count > 0)
    requests_with_memory = sum(1 for m in real_meters if (m.packed_memory_count or 0) > 0)
    memory_count_total = sum(m.packed_memory_count or 0 for m in real_meters)
    memory_enhancement_rate = _clamp_ratio(requests_with_memory / real_count) if real_count > 0 else 0.0

    # Card 4: token saving (saved_tokens / baseline)
    saved_total = sum(m.saved_tokens_estimate for m in real_meters)
    token_saving_ratio = _clamp_ratio(saved_total / total_baseline) if total_baseline > 0 else 0.0

    return {
        "period": "24h",
        "observed_request_count": observed_count,
        "cards": {
            "real_requests": {"count": real_count, "ratio": round(real_ratio, 4)},
            "context_compression": {
                "ratio": round(compression_ratio, 4),
                "baseline_tokens": total_baseline,
                "actual_tokens": total_actual,
            },
            "memory_enhancement": {
                "rate": round(memory_enhancement_rate, 4),
                "memory_count": memory_count_total,
            },
            "token_savings": {
                "ratio": round(token_saving_ratio, 4),
                "saved_tokens": saved_total,
            },
        },
    }


def compute_core_capabilities_trend(tenant: str, days: int = 7) -> Dict[str, Any]:
    """
    Compute per-day trend for the four cards over `days`.
    Returns one data point per day, oldest first.
    """
    meters = _default_overview_meters(_collect_meters(tenant), include_internal=True)

    # Build day buckets (key = YYYY-MM-DD, naive date for grouping)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    buckets: Dict[str, List[Any]] = {}
    for m in meters:
        try:
            m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if m_time < cutoff:
            continue
        day_key = m_time.strftime("%Y-%m-%d")
        buckets.setdefault(day_key, []).append(m)

    trend = []
    for day_str in sorted(buckets.keys()):
        day_meters = buckets[day_str]
        real_meters = [m for m in day_meters if _is_real_request(m)]
        observed_count = len(day_meters)
        real_count = len(real_meters)
        real_ratio = real_count / observed_count if observed_count > 0 else 0.0

        if not real_meters:
            trend.append({
                "date": day_str,
                "observed_request_count": observed_count,
                "real_requests": {"count": 0, "ratio": 0.0},
                "context_compression": {"ratio": 0.0, "baseline_tokens": 0, "actual_tokens": 0},
                "memory_enhancement": {"rate": 0.0, "memory_count": 0},
                "token_savings": {"ratio": 0.0, "saved_tokens": 0},
            })
            continue

        total_baseline = sum(m.baseline_tokens_estimate for m in real_meters)
        total_actual = sum(m.actual_tokens_estimate for m in real_meters)
        compression_ratio = _clamp_ratio(1 - (total_actual / total_baseline)) if total_baseline > 0 else 0.0

        requests_with_memory = sum(1 for m in real_meters if (m.packed_memory_count or 0) > 0)
        memory_count_total = sum(m.packed_memory_count or 0 for m in real_meters)
        memory_enhancement_rate = _clamp_ratio(requests_with_memory / real_count) if real_count > 0 else 0.0

        saved_total = sum(m.saved_tokens_estimate for m in real_meters)
        token_saving_ratio = _clamp_ratio(saved_total / total_baseline) if total_baseline > 0 else 0.0

        trend.append({
            "date": day_str,
            "observed_request_count": observed_count,
            "real_requests": {"count": real_count, "ratio": round(real_ratio, 4)},
            "context_compression": {
                "ratio": round(compression_ratio, 4),
                "baseline_tokens": total_baseline,
                "actual_tokens": total_actual,
            },
            "memory_enhancement": {
                "rate": round(memory_enhancement_rate, 4),
                "memory_count": memory_count_total,
            },
            "token_savings": {
                "ratio": round(token_saving_ratio, 4),
                "saved_tokens": saved_total,
            },
        })

    return {"days": days, "trend": trend}
