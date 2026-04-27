"""
metrics_service.py - OmniMemora Metrics Aggregation Layer
==========================================================
Provides KPI-facing aggregation for:
  - /metrics/summary
  - /metrics/summary_24h
  - /metrics/core_capabilities

Hot-read path is summary-first through Data Lifecycle Plane (DLP) summary.
Legacy meter aggregation remains as degraded fallback only.
"""

from __future__ import annotations

import importlib
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

_5_meter = importlib.import_module("5_connectors.adapter.meter_store")
_5_rc = importlib.import_module("5_connectors.adapter.request_classifier")
_metrics_read_resolver = importlib.import_module("5_connectors.adapter.application.metrics_meter_read_resolver")

_diag_metrics_degraded_lock = threading.Lock()
_diag_last_metrics_degraded_record_ts = 0.0
_METRICS_DEGRADED_RECORD_INTERVAL_SECONDS = 60.0


def _clamp_ratio(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _get_data_lifecycle_policy():
    return importlib.import_module("5_connectors.adapter.data_lifecycle.policy")


def _get_data_lifecycle_summary_store():
    return importlib.import_module("5_connectors.adapter.data_lifecycle.summary_store")


def _get_data_lifecycle_state_store():
    return importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")


def _collect_meters_legacy(tenant: str):
    _5_meter._ensure_persistence_loaded()
    if tenant == "all":
        return [m for tenant_meters in _5_meter._usage_aggregates.values() for m in tenant_meters]
    return _5_meter._usage_aggregates.get(tenant, [])


def _legacy_list_tenants() -> List[str]:
    _5_meter._ensure_persistence_loaded()
    return sorted([tenant for tenant, meters in _5_meter._usage_aggregates.items() if meters])


def _collect_meters(
    tenant: str,
    *,
    since_utc: Optional[datetime] = None,
    limit: int = 100000,
):
    result = _metrics_read_resolver.resolve_metrics_meters(
        tenant=tenant,
        since_utc=since_utc,
        limit=limit,
        legacy_collect_fn=_collect_meters_legacy,
    )
    if result.degraded and result.degraded_reason:
        _record_metrics_degraded_path(result.degraded_reason)
    return result.meters


def _collect_meters_24h(tenant: str):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    meters = _collect_meters(tenant, since_utc=cutoff)
    filtered = []
    for m in meters:
        try:
            m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if m_time >= cutoff:
            filtered.append(m)
    return filtered


def _default_overview_meters(
    meters: Iterable[Any],
    include_internal: bool = False,
    include_task_non_value: bool = False,
) -> List[Any]:
    filtered = [m for m in meters if not _5_rc.is_operator_verification_request(m)]
    collapsed = _5_rc.collapse_retry_bursts(filtered)
    if not include_internal:
        collapsed = [m for m in collapsed if not _5_rc.is_internal_request(m)]
    if not include_task_non_value:
        collapsed = [m for m in collapsed if _5_rc.is_value_qualified(m)]
    return sorted(collapsed, key=lambda m: m.timestamp, reverse=True)


def _is_valid_dlp_kpi_contract(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    required_keys = {
        "schema_version",
        "generated_at",
        "source_counts",
        "builder_version",
        "families",
        "metrics_summary_all",
        "metrics_summary_24h",
        "core_capabilities_24h",
    }
    if not required_keys.issubset(set(payload.keys())):
        return False
    if payload.get("schema_version") != "dlp-family-window-summary-v1":
        return False
    if not isinstance(payload.get("generated_at"), (int, float)):
        return False
    if not isinstance(payload.get("source_counts"), dict):
        return False
    if not isinstance(payload.get("builder_version"), str):
        return False
    if not isinstance(payload.get("families"), dict):
        return False
    if not isinstance(payload.get("metrics_summary_all"), dict):
        return False
    if not isinstance(payload.get("metrics_summary_24h"), dict):
        return False
    if not isinstance(payload.get("core_capabilities_24h"), dict):
        return False
    return True


def _read_dlp_kpi_summary_payload() -> tuple[Optional[dict[str, Any]], str, Optional[str]]:
    try:
        policy_mod = _get_data_lifecycle_policy()
        summary_store = _get_data_lifecycle_summary_store()
        policy = policy_mod.load_policy()
        payload = summary_store.read_fresh_summary(policy=policy)
        if payload is not None:
            if _is_valid_dlp_kpi_contract(payload):
                return payload, "fresh", None
            return None, "none", "summary_contract_invalid"

        payload = summary_store.read_stale_usable_summary(policy=policy)
        if payload is not None:
            if _is_valid_dlp_kpi_contract(payload):
                return payload, "stale_usable", None
            return None, "none", "summary_contract_invalid"

        raw_payload = summary_store.read_summary(policy=policy)
        if raw_payload is None:
            return None, "none", "summary_missing"
        if not _is_valid_dlp_kpi_contract(raw_payload):
            return None, "none", "summary_contract_invalid"
        return None, "none", "summary_expired"
    except Exception:
        return None, "none", "summary_read_error"


def _record_metrics_degraded_path(reason: str) -> None:
    global _diag_last_metrics_degraded_record_ts
    now_ts = time.time()
    with _diag_metrics_degraded_lock:
        if (now_ts - _diag_last_metrics_degraded_record_ts) < _METRICS_DEGRADED_RECORD_INTERVAL_SECONDS:
            return
        _diag_last_metrics_degraded_record_ts = now_ts
    try:
        state_store = _get_data_lifecycle_state_store()
        now = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=state_store.new_cycle_id(),
            trigger="metrics_read_degraded",
            started_at=now,
            completed_at=now,
            status="degraded",
            bytes_scanned=0,
            error=reason,
        )
        state_store.append_state_record(record)
    except Exception:
        pass


def _extract_summary_kpi_block(tenant: str, key: str) -> Optional[dict[str, Any]]:
    if tenant != "all":
        return None
    payload, _source, degraded_reason = _read_dlp_kpi_summary_payload()
    if payload is None:
        if degraded_reason:
            _record_metrics_degraded_path(degraded_reason)
        return None
    block = payload.get(key)
    if not isinstance(block, dict):
        _record_metrics_degraded_path("summary_kpi_block_invalid")
        return None
    return dict(block)


def _compute_metrics_summary_legacy(tenant: str) -> Dict[str, Any]:
    meters = _default_overview_meters(_collect_meters(tenant))

    if not meters:
        return {
            "token_saving_ratio": 0.0,
            "tokens_saved": 0,
            "request_count": 0,
            "avg_context_reduction": 0.0,
        }

    baseline_total = sum(m.baseline_tokens_estimate for m in meters)
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
        "tokens_saved": int(saved_total),
        "request_count": int(len(meters)),
        "avg_context_reduction": round(avg_reduction, 3),
    }


def compute_metrics_summary(tenant: str) -> Dict[str, Any]:
    summary_block = _extract_summary_kpi_block(tenant, "metrics_summary_all")
    if summary_block is not None:
        return summary_block
    return _compute_metrics_summary_legacy(tenant)


def get_recent_requests(
    tenant: str,
    limit: int = 20,
    include_internal: bool = False,
    value_qualified_only: bool = True,
) -> List[Dict[str, Any]]:
    meters = _collect_meters_24h(tenant)

    if not meters:
        return []

    sorted_meters = sorted(meters, key=lambda m: m.timestamp, reverse=True)
    if not include_internal:
        sorted_meters = [m for m in sorted_meters if not _5_rc.is_internal_request(m)]
    if value_qualified_only:
        sorted_meters = [m for m in sorted_meters if _5_rc.is_value_qualified(m)]

    recent = sorted_meters[:limit]

    recent_payload = []
    for m in recent:
        value_description = _5_rc.describe_request_value(m)
        raw_query = getattr(m, "query", "") or ""
        recent_payload.append(
            {
                "request_id": m.request_id,
                "agent": m.agent,
                "timestamp": m.timestamp,
                "task_type": getattr(m, "task_type", None) or "unknown",
                "bypass": m.context_bypass,
                "saved_tokens": m.saved_tokens_estimate,
                "savings_ratio": m.savings_ratio,
                "query": value_description["user_visible_query"][:160],
                "raw_query": raw_query,
                "user_visible_query": value_description["user_visible_query"][:240],
                "packed_memory_count": m.packed_memory_count,
                "local_cards_used": m.local_cards_used,
                "remote_used_count": getattr(m, "remote_used_count", 0),
                "request_class": value_description["request_class"],
                "qualification_reason": value_description["qualification_reason"],
                "value_paths": value_description["value_paths"],
                "diagnostic_label": value_description["diagnostic_label"],
                "display_savings_as_value": value_description["request_class"] == "value_qualified",
            }
        )
    return recent_payload


def list_tenants() -> List[str]:
    result = _metrics_read_resolver.resolve_metrics_tenants(
        legacy_list_tenants_fn=_legacy_list_tenants,
    )
    if result.degraded and result.degraded_reason:
        _record_metrics_degraded_path(result.degraded_reason)
    return result.tenants


def _compute_metrics_summary_24h_legacy(tenant: str) -> Dict[str, Any]:
    meters = _default_overview_meters(_collect_meters_24h(tenant))

    if not meters:
        return {
            "token_saving_ratio": 0.0,
            "tokens_saved": 0,
            "request_count": 0,
            "avg_context_reduction": 0.0,
            "period": "24h",
        }

    baseline_total = sum(m.baseline_tokens_estimate for m in meters)
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
        "tokens_saved": int(saved_total),
        "request_count": int(len(meters)),
        "avg_context_reduction": round(avg_reduction, 3),
        "period": "24h",
    }


def compute_metrics_summary_24h(tenant: str) -> Dict[str, Any]:
    summary_block = _extract_summary_kpi_block(tenant, "metrics_summary_24h")
    if summary_block is not None:
        return summary_block
    return _compute_metrics_summary_24h_legacy(tenant)


def _is_real_request(meter: Any) -> bool:
    return _5_rc.is_real_request(meter)


def _compute_core_capabilities_legacy(tenant: str) -> Dict[str, Any]:
    meters = _collect_meters_24h(tenant)
    observed_meters = _default_overview_meters(meters, include_internal=True, include_task_non_value=True)
    value_qualified_meters = [m for m in observed_meters if _5_rc.is_value_qualified(m)]
    task_non_value_count = sum(1 for m in observed_meters if _5_rc.is_task_non_value(m))
    internal_or_wrapper_count = sum(1 for m in observed_meters if _5_rc.is_internal_request(m))
    observed_count = len(observed_meters)
    qualified_count = len(value_qualified_meters)
    qualified_ratio = qualified_count / observed_count if observed_count > 0 else 0.0

    if not value_qualified_meters:
        return {
            "period": "24h",
            "observed_request_count": observed_count,
            "non_value_count": task_non_value_count,
            "internal_or_wrapper_count": internal_or_wrapper_count,
            "cards": {
                "real_requests": {"count": 0, "ratio": 0.0},
                "context_compression": {"ratio": 0.0, "baseline_tokens": 0, "actual_tokens": 0},
                "memory_enhancement": {"rate": 0.0, "memory_count": 0},
                "token_savings": {"ratio": 0.0, "saved_tokens": 0},
            },
        }

    total_baseline = sum(m.baseline_tokens_estimate for m in value_qualified_meters)
    total_actual = sum(m.actual_tokens_estimate for m in value_qualified_meters)
    compression_ratio = _clamp_ratio(1 - (total_actual / total_baseline)) if total_baseline > 0 else 0.0

    requests_with_memory = sum(1 for m in value_qualified_meters if (m.packed_memory_count or 0) > 0)
    memory_count_total = sum(m.packed_memory_count or 0 for m in value_qualified_meters)
    memory_enhancement_rate = _clamp_ratio(requests_with_memory / qualified_count) if qualified_count > 0 else 0.0

    saved_total = sum(m.saved_tokens_estimate for m in value_qualified_meters)
    token_saving_ratio = _clamp_ratio(saved_total / total_baseline) if total_baseline > 0 else 0.0

    return {
        "period": "24h",
        "observed_request_count": observed_count,
        "non_value_count": task_non_value_count,
        "internal_or_wrapper_count": internal_or_wrapper_count,
        "cards": {
            "real_requests": {"count": qualified_count, "ratio": round(qualified_ratio, 4)},
            "context_compression": {
                "ratio": round(compression_ratio, 4),
                "baseline_tokens": total_baseline,
                "actual_tokens": total_actual,
            },
            "memory_enhancement": {"rate": round(memory_enhancement_rate, 4), "memory_count": memory_count_total},
            "token_savings": {"ratio": round(token_saving_ratio, 4), "saved_tokens": saved_total},
        },
    }


def compute_core_capabilities(tenant: str) -> Dict[str, Any]:
    summary_block = _extract_summary_kpi_block(tenant, "core_capabilities_24h")
    if summary_block is not None:
        return summary_block
    return _compute_core_capabilities_legacy(tenant)


def compute_core_capabilities_trend(tenant: str, days: int = 7) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    meters = _default_overview_meters(
        _collect_meters(tenant, since_utc=cutoff),
        include_internal=True,
        include_task_non_value=True,
    )

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
        value_qualified_meters = [m for m in day_meters if _5_rc.is_value_qualified(m)]
        task_non_value_count = sum(1 for m in day_meters if _5_rc.is_task_non_value(m))
        internal_or_wrapper_count = sum(1 for m in day_meters if _5_rc.is_internal_request(m))
        observed_count = len(day_meters)
        qualified_count = len(value_qualified_meters)
        qualified_ratio = qualified_count / observed_count if observed_count > 0 else 0.0

        if not value_qualified_meters:
            trend.append(
                {
                    "date": day_str,
                    "observed_request_count": observed_count,
                    "non_value_count": task_non_value_count,
                    "internal_or_wrapper_count": internal_or_wrapper_count,
                    "real_requests": {"count": 0, "ratio": 0.0},
                    "context_compression": {"ratio": 0.0, "baseline_tokens": 0, "actual_tokens": 0},
                    "memory_enhancement": {"rate": 0.0, "memory_count": 0},
                    "token_savings": {"ratio": 0.0, "saved_tokens": 0},
                }
            )
            continue

        total_baseline = sum(m.baseline_tokens_estimate for m in value_qualified_meters)
        total_actual = sum(m.actual_tokens_estimate for m in value_qualified_meters)
        compression_ratio = _clamp_ratio(1 - (total_actual / total_baseline)) if total_baseline > 0 else 0.0

        requests_with_memory = sum(1 for m in value_qualified_meters if (m.packed_memory_count or 0) > 0)
        memory_count_total = sum(m.packed_memory_count or 0 for m in value_qualified_meters)
        memory_enhancement_rate = _clamp_ratio(requests_with_memory / qualified_count) if qualified_count > 0 else 0.0

        saved_total = sum(m.saved_tokens_estimate for m in value_qualified_meters)
        token_saving_ratio = _clamp_ratio(saved_total / total_baseline) if total_baseline > 0 else 0.0

        trend.append(
            {
                "date": day_str,
                "observed_request_count": observed_count,
                "non_value_count": task_non_value_count,
                "internal_or_wrapper_count": internal_or_wrapper_count,
                "real_requests": {"count": qualified_count, "ratio": round(qualified_ratio, 4)},
                "context_compression": {
                    "ratio": round(compression_ratio, 4),
                    "baseline_tokens": total_baseline,
                    "actual_tokens": total_actual,
                },
                "memory_enhancement": {"rate": round(memory_enhancement_rate, 4), "memory_count": memory_count_total},
                "token_savings": {"ratio": round(token_saving_ratio, 4), "saved_tokens": saved_total},
            }
        )

    return {"days": days, "trend": trend}
