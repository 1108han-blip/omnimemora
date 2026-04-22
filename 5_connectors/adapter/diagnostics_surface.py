import importlib
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException, Response

router = APIRouter()
_srm = importlib.import_module("5_connectors.adapter.application.status_read_model")


def configure_diagnostics_surface(
    *,
    config_obj: Any,
    get_backend_fn: Callable[[], Any],
    get_dedup_cache_fn: Callable[[], Any],
    rate_limiter: Any,
    adapter_hostname: str,
    adapter_started_at: str,
    agent_metrics_module: Any,
    agent_identity_module: Any,
    get_meter_fn: Callable[[str], Any],
    support_schema_version: str,
    support_error_catalog: Dict[str, Dict[str, Any]],
) -> None:
    """Surface config only: pass dependencies into application read-model."""
    _srm.configure_diagnostics_read_model(
        config_obj=config_obj,
        get_backend_fn=get_backend_fn,
        get_dedup_cache_fn=get_dedup_cache_fn,
        rate_limiter=rate_limiter,
        adapter_hostname=adapter_hostname,
        adapter_started_at=adapter_started_at,
        agent_metrics_module=agent_metrics_module,
        agent_identity_module=agent_identity_module,
        get_meter_fn=get_meter_fn,
        support_schema_version=support_schema_version,
        support_error_catalog=support_error_catalog,
    )


@router.get("/")
async def root():
    return _srm.build_root_payload()


@router.get("/health")
async def health(mode: str = "full"):
    return await _srm.build_health_payload(mode=mode)


@router.get("/debug/runtime_fingerprint")
async def runtime_fingerprint():
    return _srm.build_runtime_fingerprint_payload()


@router.get("/support/error-codes")
async def support_error_codes():
    return _srm.build_support_error_codes_payload()


@router.get("/metrics/summary")
async def get_metrics_summary(response: Response, tenant: str = "all"):
    response.headers["X-OmniMemora-Surface-Role"] = "kpi"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"
    return _srm.build_metrics_summary_payload(tenant)


@router.get("/metrics/summary_24h")
async def get_metrics_summary_24h(response: Response, tenant: str = "all"):
    response.headers["X-OmniMemora-Surface-Role"] = "kpi"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary_24h"
    return _srm.build_metrics_summary_24h_payload(tenant)


@router.get("/metrics/debug/sources")
async def get_metrics_debug_sources():
    return _srm.build_metrics_debug_sources_payload()


@router.get("/metrics/recent_requests")
async def get_recent_requests(
    tenant: str = "default",
    limit: int = 20,
    include_internal: bool = False,
    value_qualified_only: bool = True,
):
    return _srm.build_recent_requests_payload(
        tenant=tenant,
        limit=limit,
        include_internal=include_internal,
        value_qualified_only=value_qualified_only,
    )


@router.get("/metrics/tenants")
async def get_metric_tenants():
    return _srm.build_metric_tenants_payload()


@router.get("/metrics/core_capabilities")
async def get_core_capabilities(response: Response, tenant: str = "all"):
    response.headers["X-OmniMemora-Surface-Role"] = "kpi"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/core_capabilities"
    return _srm.build_core_capabilities_payload(tenant)


@router.get("/metrics/core_capabilities/trend")
async def get_core_capabilities_trend(response: Response, tenant: str = "all", days: int = 7):
    response.headers["X-OmniMemora-Surface-Role"] = "kpi"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/core_capabilities/trend"
    return _srm.build_core_capabilities_trend_payload(tenant, days)


@router.get("/debug/context_diff")
async def get_context_diff(request_id: str):
    try:
        return _srm.build_context_diff_payload(request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/debug/call_chain")
async def get_call_chain(request_id: str):
    try:
        return _srm.build_call_chain_payload(request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/debug/request_evidence")
async def get_request_evidence(request_id: str):
    try:
        return _srm.build_request_evidence_payload(request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/agents/live")
async def get_agents_live(response: Response, window_minutes: int = 30):
    response.headers["X-OmniMemora-Surface-Role"] = "diagnostic"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"
    return _srm.build_agents_live_payload(window_minutes=window_minutes)


@router.get("/agents/metrics")
async def get_agent_metrics_get(
    response: Response,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    response.headers["X-OmniMemora-Surface-Role"] = "diagnostic"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"
    return _srm.build_agent_metrics_payload(agent_id=agent_id, session_id=session_id)
