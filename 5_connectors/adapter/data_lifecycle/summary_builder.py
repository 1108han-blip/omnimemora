"""Pure summary-builder functions for family/window aggregation."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Iterable, Optional


_COMPILE_EMPTY_REASONS = {
    "empty_query",
    "no_messages",
    "no_user_message",
    "assistant_only_continuation",
}

_BYPASS_COMPILE_REASONS = {
    "agent_route_disabled",
    "codex_env_bypass",
}

_DEFAULT_FAMILIES = ["claude_code", "codex_cli", "openclaw", "cursor"]
_CLAUDE_CODE_PROFILE_ALIASES = {
    "cc-haha",
    "cc_haha",
    "claude-code-haha",
    "claude_code_haha",
}


def _resolve_canonical_agent_id(agent: str) -> str:
    try:
        identity_mod = importlib.import_module("5_connectors.adapter.agent_identity")
        return str(identity_mod.resolve_canonical_agent_id(agent or "") or "")
    except Exception:
        return str(agent or "")


def normalize_agent_to_family(agent: str) -> str:
    raw = str(agent or "")
    lower = raw.lower()
    canonical = _resolve_canonical_agent_id(raw).lower()
    if lower in {"openclaw", "openclaw-agent", "openclaw-bundle-mcp", "openclaw_bundle_mcp"}:
        return "openclaw"
    if lower in _CLAUDE_CODE_PROFILE_ALIASES:
        return "claude_code"
    if lower in {"claude_code", "claude-code", "claude"}:
        return "claude_code"
    if canonical in _CLAUDE_CODE_PROFILE_ALIASES:
        return "claude_code"
    if canonical in {"claude_code", "claude-code", "claude-code-cli", "claude"}:
        return "claude_code"
    if lower in {"codex", "codex_cli", "codex-cli"}:
        return "codex_cli"
    if canonical in {"codex", "codex_cli", "codex-cli"}:
        return "codex_cli"
    if lower == "cursor":
        return "cursor"
    if canonical == "cursor":
        return "cursor"
    if canonical in {"openclaw", "openclaw-agent", "openclaw-bundle-mcp", "openclaw_bundle_mcp"}:
        return "openclaw"
    return str(agent or "")


def _int_metric(meter: Any, name: str) -> int:
    try:
        return max(0, int(getattr(meter, name, 0) or 0))
    except Exception:
        return 0


def _compression_source_tokens(meter: Any) -> int:
    return _int_metric(meter, "compression_source_tokens") or _int_metric(meter, "baseline_tokens_estimate")


def _compression_output_tokens(meter: Any) -> int:
    return _int_metric(meter, "compression_output_tokens") or _int_metric(meter, "actual_tokens_estimate")


def _real_input_baseline_tokens(meter: Any) -> int:
    return _int_metric(meter, "baseline_payload_tokens")


def _real_input_saved_tokens(meter: Any) -> int:
    return _int_metric(meter, "real_input_saved_tokens")


def _parse_iso_to_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _epoch_to_iso(epoch_value: Optional[float]) -> Optional[str]:
    if not epoch_value:
        return None
    try:
        return datetime.fromtimestamp(float(epoch_value), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _clamp_ratio(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _parse_meter_ts(meter: Any) -> Optional[datetime]:
    return _parse_iso_to_dt(getattr(meter, "timestamp", None))


def _filter_last_24h(meters: Iterable[Any], *, now_utc: datetime) -> list[Any]:
    cutoff = now_utc - timedelta(hours=24)
    output: list[Any] = []
    for meter in meters:
        meter_dt = _parse_meter_ts(meter)
        if meter_dt is None:
            continue
        if meter_dt >= cutoff:
            output.append(meter)
    return output


def _default_overview_meters(
    meters: Iterable[Any],
    *,
    is_default_overview_request: Callable[[Any], bool],
    is_value_qualified: Callable[[Any], bool],
    collapse_retry_bursts: Callable[[Iterable[Any]], list[Any]],
    include_task_non_value: bool = False,
) -> list[Any]:
    filtered = [m for m in meters if is_default_overview_request(m)]
    collapsed = collapse_retry_bursts(filtered)
    if include_task_non_value:
        return sorted(list(collapsed), key=lambda m: getattr(m, "timestamp", ""), reverse=True)
    collapsed = [m for m in collapsed if is_value_qualified(m)]
    return sorted(list(collapsed), key=lambda m: getattr(m, "timestamp", ""), reverse=True)


def _build_metrics_summary_payload(meters: Iterable[Any]) -> dict[str, Any]:
    meter_list = list(meters)
    if not meter_list:
        return {
            "metric_contract_version": "real_input_v1",
            "token_saving_ratio": 0.0,
            "tokens_saved": 0,
            "request_count": 0,
            "avg_context_reduction": 0.0,
        }
    total_requests = len(meter_list)
    baseline_total = sum(_real_input_baseline_tokens(m) for m in meter_list)
    saved_total = sum(_real_input_saved_tokens(m) for m in meter_list)
    avg_ratio = (saved_total / baseline_total) if baseline_total > 0 else 0.0

    reductions: list[float] = []
    for meter in meter_list:
        baseline = _compression_source_tokens(meter)
        actual = _compression_output_tokens(meter)
        if baseline > 0:
            reductions.append((baseline - actual) / baseline)
    avg_reduction = (sum(reductions) / len(reductions)) if reductions else 0.0

    return {
        "metric_contract_version": "real_input_v1",
        "token_saving_ratio": round(avg_ratio, 3),
        "tokens_saved": int(saved_total),
        "request_count": int(total_requests),
        "avg_context_reduction": round(avg_reduction, 3),
    }


def _build_metrics_summary_24h_payload(meters_24h: Iterable[Any]) -> dict[str, Any]:
    payload = _build_metrics_summary_payload(meters_24h)
    payload["period"] = "24h"
    return payload


def _build_core_capabilities_24h_payload(
    observed_meters: Iterable[Any],
    *,
    is_value_qualified: Callable[[Any], bool],
    is_task_non_value: Callable[[Any], bool],
) -> dict[str, Any]:
    observed_list = list(observed_meters)
    value_qualified_meters = [m for m in observed_list if is_value_qualified(m)]
    task_non_value_count = sum(1 for m in observed_list if is_task_non_value(m))
    observed_count = len(observed_list)
    internal_or_wrapper_count = max(0, observed_count - task_non_value_count - len(value_qualified_meters))
    qualified_count = len(value_qualified_meters)
    qualified_ratio = (qualified_count / observed_count) if observed_count > 0 else 0.0

    if not value_qualified_meters:
        return {
            "period": "24h",
            "metric_contract_version": "real_input_v1",
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

    total_baseline = sum(_compression_source_tokens(m) for m in value_qualified_meters)
    total_actual = sum(_compression_output_tokens(m) for m in value_qualified_meters)
    compression_ratio = _clamp_ratio(1 - (total_actual / total_baseline)) if total_baseline > 0 else 0.0

    requests_with_memory = sum(
        1 for m in value_qualified_meters if int(getattr(m, "packed_memory_count", 0) or 0) > 0
    )
    memory_count_total = sum(int(getattr(m, "packed_memory_count", 0) or 0) for m in value_qualified_meters)
    memory_enhancement_rate = _clamp_ratio(requests_with_memory / qualified_count) if qualified_count > 0 else 0.0

    saved_total = sum(_real_input_saved_tokens(m) for m in value_qualified_meters)
    real_baseline_total = sum(_real_input_baseline_tokens(m) for m in value_qualified_meters)
    token_saving_ratio = _clamp_ratio(saved_total / real_baseline_total) if real_baseline_total > 0 else 0.0

    return {
        "period": "24h",
        "metric_contract_version": "real_input_v1",
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


def summarize_compile_rows_for_family(rows: Iterable[dict[str, Any]], family_id: str) -> dict[str, Any]:
    summary = {
        "proxied_requests": 0,
        "compile_empty": 0,
        "bypassed": 0,
        "last_event_ts": None,
    }
    for row in rows:
        normalized = normalize_agent_to_family(str(row.get("agent_id") or ""))
        if normalized != family_id:
            continue
        summary["proxied_requests"] += 1

        status = str(row.get("compile_status") or "").strip().lower()
        reason = str(row.get("compile_reason") or "").strip().lower()
        if status == "compile_skipped":
            if reason in _COMPILE_EMPTY_REASONS:
                summary["compile_empty"] += 1
            elif reason in _BYPASS_COMPILE_REASONS:
                summary["bypassed"] += 1

        ts = row.get("timestamp")
        if isinstance(ts, (int, float)):
            current = summary["last_event_ts"] or 0.0
            if float(ts) > current:
                summary["last_event_ts"] = float(ts)
    return summary


def derive_traffic_truth_from_counts(observed_count: int, compile_summary: dict[str, Any]) -> str:
    if observed_count > 0:
        return "real_request_observed"
    if int(compile_summary.get("bypassed", 0)) > 0:
        return "bypassed"
    if int(compile_summary.get("compile_empty", 0)) > 0:
        return "compile_empty"
    if int(compile_summary.get("proxied_requests", 0)) > 0:
        return "internal_only"
    return "no_recent_evidence"


def build_family_window_summary(
    *,
    meters: Iterable[Any],
    compile_rows_30m: Iterable[dict[str, Any]],
    compile_rows_24h: Iterable[dict[str, Any]],
    proxy_rows_30m: Iterable[dict[str, Any]] | None,
    now_utc: Optional[datetime] = None,
    is_default_overview_request: Optional[Callable[[Any], bool]] = None,
    is_value_qualified: Optional[Callable[[Any], bool]] = None,
    is_task_non_value: Optional[Callable[[Any], bool]] = None,
    collapse_retry_bursts: Optional[Callable[[Iterable[Any]], list[Any]]] = None,
    builder_version: str = "dlp-summary-builder-v3",
    degraded_reason: Optional[str] = None,
) -> dict[str, Any]:
    now = now_utc.astimezone(timezone.utc) if now_utc else datetime.now(timezone.utc)
    cutoff_30m = now - timedelta(minutes=30)
    cutoff_24h = now - timedelta(hours=24)

    overview_predicate = is_default_overview_request or (lambda _m: True)
    value_predicate = is_value_qualified or (lambda _m: False)
    task_non_value_predicate = is_task_non_value or (lambda _m: False)
    collapse = collapse_retry_bursts or (lambda items: list(items))

    family_candidates: set[str] = set(_DEFAULT_FAMILIES)
    meter_list = list(meters)
    compile_30_list = list(compile_rows_30m)
    compile_24_list = list(compile_rows_24h)
    proxy_30_list = list(proxy_rows_30m or [])

    for m in meter_list:
        family_candidates.add(normalize_agent_to_family(getattr(m, "agent", "")))
    for row in compile_24_list:
        family_candidates.add(normalize_agent_to_family(str(row.get("agent_id") or "")))
    for row in proxy_30_list:
        family_candidates.add(normalize_agent_to_family(str(row.get("agent_id") or "")))

    summary_families: dict[str, dict[str, Any]] = {}

    for family_id in sorted(f for f in family_candidates if f):
        observed_30m = []
        observed_24h = []
        qualified_24h = []

        for meter in meter_list:
            if normalize_agent_to_family(getattr(meter, "agent", "")) != family_id:
                continue
            meter_dt = _parse_iso_to_dt(getattr(meter, "timestamp", None))
            if meter_dt is None or meter_dt < cutoff_24h:
                continue
            if not overview_predicate(meter):
                continue
            baseline = _compression_source_tokens(meter)
            if baseline < 50:
                continue

            observed_24h.append(meter)
            if meter_dt >= cutoff_30m:
                observed_30m.append(meter)
            if value_predicate(meter):
                qualified_24h.append(meter)

        observed_30m = collapse(observed_30m)
        observed_24h = collapse(observed_24h)
        qualified_24h = collapse(qualified_24h)

        compile_30 = summarize_compile_rows_for_family(compile_30_list, family_id)
        compile_24 = summarize_compile_rows_for_family(compile_24_list, family_id)

        compile_last_request_at = _epoch_to_iso(compile_24.get("last_event_ts"))

        observed_last_request_at = None
        for meter in observed_24h:
            meter_dt = _parse_iso_to_dt(getattr(meter, "timestamp", None))
            if meter_dt is None:
                continue
            meter_ts = str(getattr(meter, "timestamp", ""))
            if observed_last_request_at is None or meter_dt > observed_last_request_at[0]:
                observed_last_request_at = (meter_dt, meter_ts)
        observed_last_request_at_str = observed_last_request_at[1] if observed_last_request_at else None

        requests_24h = len(qualified_24h)
        saved_tokens_24h = int(sum(_real_input_saved_tokens(m) for m in qualified_24h))
        baseline_total = int(sum(_real_input_baseline_tokens(m) for m in qualified_24h))
        savings_ratio_24h = (saved_tokens_24h / baseline_total) if baseline_total > 0 else 0.0
        qualified_last_request_at = max((getattr(m, "timestamp", None) for m in qualified_24h), default=None)

        metrics_24h = {
            "requests_24h": requests_24h,
            "saved_tokens_24h": saved_tokens_24h,
            "savings_ratio_24h": round(float(savings_ratio_24h), 3),
            "last_request_at": observed_last_request_at_str or compile_last_request_at or qualified_last_request_at,
            "observed_requests_24h": len(observed_24h),
        }

        proxy_requests_30m = 0
        for row in proxy_30_list:
            if normalize_agent_to_family(str(row.get("agent_id") or "")) != family_id:
                continue
            row_type = str(row.get("type") or "")
            if row_type in {"proxy_request", "proxy_response"}:
                proxy_requests_30m += 1

        summary_families[family_id] = {
            "traffic_truth_30m": derive_traffic_truth_from_counts(len(observed_30m), compile_30),
            "compile_30m": compile_30,
            "compile_24h": compile_24,
            "metrics_24h": metrics_24h,
            "observed_counts": {
                "observed_requests_30m": len(observed_30m),
                "observed_requests_24h": len(observed_24h),
                "qualified_requests_24h": len(qualified_24h),
            },
            "proxy_counts": {
                "proxy_requests_30m": proxy_requests_30m,
            },
        }

    payload: dict[str, Any] = {
        "schema_version": "dlp-family-window-summary-v1",
        "generated_at": now.timestamp(),
        "source_counts": {
            "meters": len(meter_list),
            "compile_rows_30m": len(compile_30_list),
            "compile_rows_24h": len(compile_24_list),
            "proxy_rows_30m": len(proxy_30_list),
        },
        "builder_version": builder_version,
        "metrics_summary_all": _build_metrics_summary_payload(
            _default_overview_meters(
                meter_list,
                is_default_overview_request=overview_predicate,
                is_value_qualified=value_predicate,
                collapse_retry_bursts=collapse,
            )
        ),
        "metrics_summary_24h": _build_metrics_summary_24h_payload(
            _default_overview_meters(
                _filter_last_24h(meter_list, now_utc=now),
                is_default_overview_request=overview_predicate,
                is_value_qualified=value_predicate,
                collapse_retry_bursts=collapse,
            )
        ),
        "core_capabilities_24h": _build_core_capabilities_24h_payload(
            _default_overview_meters(
                _filter_last_24h(meter_list, now_utc=now),
                is_default_overview_request=overview_predicate,
                is_value_qualified=value_predicate,
                collapse_retry_bursts=collapse,
                include_task_non_value=True,
            ),
            is_value_qualified=value_predicate,
            is_task_non_value=task_non_value_predicate,
        ),
        "families": summary_families,
    }
    if degraded_reason:
        payload["degraded_reason"] = str(degraded_reason)
    return payload
