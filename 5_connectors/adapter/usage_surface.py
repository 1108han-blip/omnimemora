from datetime import datetime
import importlib
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Response

from .access import get_tenant_registry_entry
from .application import request_meter_read_resolver as _request_meter_resolver

router = APIRouter()
_metrics_service = importlib.import_module("5_connectors.adapter.metrics_service")

_config = None
_get_tenant_usage_fn: Optional[Callable[..., Any]] = None
_get_trend_data_fn: Optional[Callable[..., Any]] = None
_get_meter_fn: Optional[Callable[[str], Any]] = None


def configure_usage_surface(
    *,
    config_obj: Any,
    get_tenant_usage_fn: Callable[..., Any],
    get_trend_data_fn: Callable[..., Any],
    get_meter_fn: Callable[[str], Any],
) -> None:
    global _config, _get_tenant_usage_fn, _get_trend_data_fn, _get_meter_fn
    _config = config_obj
    _get_tenant_usage_fn = get_tenant_usage_fn
    _get_trend_data_fn = get_trend_data_fn
    _get_meter_fn = get_meter_fn


def _fast_all_usage_payload(tenant: str) -> Optional[dict[str, Any]]:
    if tenant != "all":
        return None
    summary = _metrics_service.compute_metrics_summary("all")
    if not isinstance(summary, dict):
        return None
    request_count = int(summary.get("request_count") or 0)
    tokens_saved = int(summary.get("tokens_saved") or 0)
    savings_ratio = float(summary.get("token_saving_ratio") or 0.0)
    return {
        "tenant": tenant,
        "request_count": request_count,
        "total_requests": request_count,
        "saved_tokens_estimate_total": tokens_saved,
        "actual_tokens_estimate_total": 0,
        "baseline_tokens_total": 0,
        "actual_tokens_total": 0,
        "saved_tokens_total": tokens_saved,
        "average_savings_ratio": savings_ratio,
        "last_request_at": None,
        "current_period_usage": 0,
        "by_agent": [],
        "by_workspace": [],
        "period_breakdown": {"today": 0, "week": 0, "month": 0},
        "recent_requests": [],
        "read_mode": "summary_first",
    }


@router.get("/usage/token-savings")
async def get_token_savings(
    tenant: str,
    agent: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    start_dt = datetime.fromisoformat(start_time) if start_time else None
    end_dt = datetime.fromisoformat(end_time) if end_time else None

    usage = None
    if agent is None and start_dt is None and end_dt is None:
        usage = _fast_all_usage_payload(tenant)
    if usage is None:
        usage = _get_tenant_usage_fn(tenant, agent=agent, start_time=start_dt, end_time=end_dt)
    registry_entry = get_tenant_registry_entry(_config.omnimemora_access_registry_path, tenant)
    monthly_quota_tokens = None
    plan = None
    status = None
    quota_status = "untracked"
    if registry_entry:
        plan = registry_entry.get("plan")
        status = registry_entry.get("status")
        raw_quota = registry_entry.get("monthly_quota_tokens")
        if raw_quota not in (None, ""):
            try:
                monthly_quota_tokens = int(raw_quota)
            except (TypeError, ValueError):
                monthly_quota_tokens = None

    current_period_usage = usage.get("current_period_usage", 0)
    if monthly_quota_tokens is not None:
        quota_status = "over_quota" if current_period_usage > monthly_quota_tokens else "within_quota"

    usage["plan"] = plan
    usage["status"] = status
    usage["monthly_quota_tokens"] = monthly_quota_tokens
    usage["quota_status"] = quota_status
    return usage


@router.get("/usage/token-savings/trend")
async def get_token_savings_trend(tenant: str, agent: Optional[str] = None, days: int = 7):
    trend_data = _get_trend_data_fn(tenant, days)
    trend_data["agent"] = agent
    return trend_data


@router.get("/requests/{request_id}/meter")
async def get_request_meter(request_id: str, response: Response):
    resolved = _request_meter_resolver.resolve_request_meter(
        request_id,
        legacy_get_meter_fn=_get_meter_fn,
    )
    response.headers["x-omnimemora-meter-read-mode"] = resolved.mode
    response.headers["x-omnimemora-meter-read-source"] = resolved.source
    if not resolved.meter:
        raise HTTPException(status_code=404, detail=f"Meter not found for request_id={request_id}")
    return resolved.meter.to_dict()
