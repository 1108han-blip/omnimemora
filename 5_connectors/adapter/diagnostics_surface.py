import importlib
import inspect as _inspect
import os
import sys
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException, Response

router = APIRouter()

_config = None
_get_backend_fn: Optional[Callable[[], Any]] = None
_get_dedup_cache_fn: Optional[Callable[[], Any]] = None
_rate_limiter = None
_adapter_hostname = ""
_adapter_started_at = ""
_agent_metrics_module = None
_agent_identity_module = None
_get_meter_fn: Optional[Callable[[str], Any]] = None
_support_schema_version = ""
_support_error_catalog: Dict[str, Dict[str, Any]] = {}


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
    global _config, _get_backend_fn, _get_dedup_cache_fn, _rate_limiter
    global _adapter_hostname, _adapter_started_at, _agent_metrics_module, _agent_identity_module
    global _get_meter_fn, _support_schema_version, _support_error_catalog
    _config = config_obj
    _get_backend_fn = get_backend_fn
    _get_dedup_cache_fn = get_dedup_cache_fn
    _rate_limiter = rate_limiter
    _adapter_hostname = adapter_hostname
    _adapter_started_at = adapter_started_at
    _agent_metrics_module = agent_metrics_module
    _agent_identity_module = agent_identity_module
    _get_meter_fn = get_meter_fn
    _support_schema_version = support_schema_version
    _support_error_catalog = support_error_catalog


@router.get("/")
async def root():
    result = {
        "service": "Memory Adapter v2.2",
        "version": "2.2.0",
        "support_schema_version": _support_schema_version,
        "dedup_stats": _get_dedup_cache_fn().get_stats(),
        "rate_limit": {
            "max_per_minute": _config.rate_limit_per_minute,
            "current": _rate_limiter.get_current_count(),
        },
    }
    if _config.viking_url:
        result["viking_url"] = _config.viking_url
    return result


@router.get("/health")
async def health(mode: str = "full"):
    if mode == "local":
        return {
            "status": "healthy",
            "mode": "local",
            "interface_policy": {
                "product_entry_port": 18011,
                "mcp_endpoint": "/mcp",
                "internal_backend_port": 8765,
                "note": "External agents must connect to 18011. Port 8765 is internal only.",
            },
            "dedup_stats": _get_dedup_cache_fn().get_stats(),
            "rate_limit": {
                "enabled": _config.enable_rate_limit,
                "max_per_minute": _config.rate_limit_per_minute,
                "current": _rate_limiter.get_current_count(),
            },
        }

    backend_health = await _get_backend_fn().health()
    route_state = importlib.import_module("5_connectors.adapter.agent_routing_state")
    track_b_orchestrator = importlib.import_module("5_connectors.adapter.track_b_orchestrator")
    per_agent_modes, _default_mode = route_state.get_agent_modes_cache()
    system_status = track_b_orchestrator.build_system_status_from_backend_health(
        backend_health=backend_health,
        per_agent_modes=per_agent_modes,
    )
    return {
        "status": "healthy" if backend_health.healthy else "degraded",
        "mode": "full",
        "interface_policy": {
            "product_entry_port": 18011,
            "mcp_endpoint": "/mcp",
            "internal_backend_port": 8765,
            "note": "External agents must connect to 18011. Port 8765 is internal only.",
        },
        "memory_backend": {
            "type": backend_health.backend_type,
            "healthy": backend_health.healthy,
            "details": backend_health.details,
        },
        "system_status": system_status,
        "timeout_profile": {
            "connect_seconds": _config.viking_connect_timeout_seconds,
            "health_seconds": _config.viking_health_timeout_seconds,
            "search_seconds": _config.viking_search_timeout_seconds,
            "read_seconds": _config.viking_read_timeout_seconds,
            "delete_seconds": _config.viking_delete_timeout_seconds,
            "snapshot_seconds": _config.viking_snapshot_timeout_seconds,
            "upload_seconds": _config.viking_upload_timeout_seconds,
            "commit_seconds": _config.viking_commit_timeout_seconds,
            "resolve_seconds": _config.viking_resolve_timeout_seconds,
            "retry_attempts": _config.viking_retry_attempts,
            "retry_backoff_seconds": _config.viking_retry_backoff_seconds,
            "slow_request_threshold_ms": _config.slow_request_threshold_ms,
        },
        "path_policy": {
            "agent_segment_sanitized": True,
            "namespace_prepare_on_write": True,
            "missing_namespace_returns_empty": True,
        },
        "error_policy": {
            "schema_version": _support_schema_version,
            "request_id_header": "X-Request-ID",
            "catalog_endpoint": "/support/error-codes",
            "structured_http_errors": True,
            "write_error_fields": ["reason", "error_code", "request_id", "support"],
        },
        "dedup_stats": _get_dedup_cache_fn().get_stats(),
        "rate_limit": {
            "enabled": _config.enable_rate_limit,
            "max_per_minute": _config.rate_limit_per_minute,
            "current": _rate_limiter.get_current_count(),
        },
    }


@router.get("/debug/runtime_fingerprint")
async def runtime_fingerprint():
    live_5m = _agent_metrics_module.get_live_agents(window_minutes=5)
    live_24h = _agent_metrics_module.get_live_agents(window_minutes=1440)
    key_modules = [
        "5_connectors.adapter.main",
        "5_connectors.adapter.metrics_aggregator",
        "5_connectors.adapter.agent_identity",
        "5_connectors.adapter.agent_metrics",
    ]
    code_source = {}
    for name in key_modules:
        try:
            mod = importlib.import_module(name)
            code_source[name] = _inspect.getfile(mod)
        except Exception as exc:
            code_source[name] = f"import failed: {exc}"

    return {
        "service": "Memory Adapter v2.2",
        "version": "2.2.0",
        "pid": os.getpid(),
        "hostname": _adapter_hostname,
        "started_at": _adapter_started_at,
        "python": sys.version.split(" ")[0],
        "config": {
            "adapter_host": _config.adapter_host,
            "adapter_port": _config.adapter_port,
            "memory_backend_type": _config.memory_backend.backend_type,
            "memory_backend_url": _config.memory_backend.base_url,
            "agent_events_path": _config.agent_events_path,
        },
        "code_source": code_source,
        "live_counts": {
            "window_5m": len(live_5m),
            "window_24h": len(live_24h),
        },
        "interface_policy": {
            "product_entry_port": 18011,
            "mcp_endpoint": "/mcp",
            "internal_backend_port": 8765,
            "note": "External agents must connect to 18011. Port 8765 is internal only.",
        },
    }


@router.get("/support/error-codes")
async def support_error_codes():
    return {
        "schema_version": _support_schema_version,
        "count": len(_support_error_catalog),
        "error_codes": [
            {
                "code": code,
                "category": meta["category"],
                "severity": meta["severity"],
                "retryable": meta["retryable"],
                "suggested_action": meta["suggested_action"],
            }
            for code, meta in sorted(_support_error_catalog.items())
        ],
    }


@router.get("/metrics/summary")
async def get_metrics_summary(response: Response, tenant: str = "all"):
    del tenant
    aggregator = importlib.import_module("5_connectors.adapter.metrics_aggregator")
    response.headers["X-OmniMemora-Surface-Role"] = "kpi"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"
    return aggregator.compute_unified_summary()


@router.get("/metrics/debug/sources")
async def get_metrics_debug_sources():
    aggregator = importlib.import_module("5_connectors.adapter.metrics_aggregator")
    return aggregator.get_metrics_debug_sources()


@router.get("/metrics/recent_requests")
async def get_recent_requests(tenant: str = "default", limit: int = 20):
    metrics_service = importlib.import_module("5_connectors.adapter.metrics_service")
    requests = metrics_service.get_recent_requests(tenant, limit)
    return {"tenant": tenant, "requests": requests}


@router.get("/metrics/tenants")
async def get_metric_tenants():
    metrics_service = importlib.import_module("5_connectors.adapter.metrics_service")
    return {"tenants": metrics_service.list_tenants()}


@router.get("/debug/context_diff")
async def get_context_diff(request_id: str):
    meter = _get_meter_fn(request_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter not found for request_id={request_id}")

    meter_dict = meter.to_dict()
    candidate_memories = meter_dict.get("candidate_memories", [])
    dropped_memories = meter_dict.get("dropped_memories", [])
    dropped_content_set = {m.get("content", "").strip() for m in dropped_memories}
    selected_memories = [
        m for m in candidate_memories if m.get("content", "").strip() not in dropped_content_set
    ]
    return {
        "request_id": request_id,
        "before_tokens": meter_dict.get("baseline_tokens_estimate", 0),
        "after_tokens": meter_dict.get("actual_tokens_estimate", 0),
        "selected_memories": selected_memories,
        "dropped_memories": dropped_memories,
    }


@router.get("/debug/call_chain")
async def get_call_chain(request_id: str):
    trace_store = importlib.import_module("5_connectors.adapter.trace_store")
    chain_dict = trace_store.get_trace_dict(request_id)
    if not chain_dict:
        raise HTTPException(status_code=404, detail=f"Trace not found for request_id={request_id}")
    return chain_dict


@router.get("/agents/live")
async def get_agents_live(response: Response, window_minutes: int = 30):
    live = _agent_metrics_module.get_live_agents(window_minutes=window_minutes)
    response.headers["X-OmniMemora-Surface-Role"] = "diagnostic"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"
    return {
        "surface_role": "diagnostic",
        "kpi_source": "/metrics/summary",
        "diagnostic_scope": "agent session snapshots reconstructed from agent_events JSONL",
        "agents": live,
        "count": len(live),
    }


@router.get("/agents/metrics")
async def get_agent_metrics_get(
    response: Response,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    canonical_id = None
    if agent_id:
        canonical_id = _agent_identity_module.resolve_canonical_agent_id(agent_id)
    metrics = _agent_metrics_module.get_agent_metrics(agent_id=canonical_id, session_id=session_id)
    response.headers["X-OmniMemora-Surface-Role"] = "diagnostic"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"
    return {
        "surface_role": "diagnostic",
        "kpi_source": "/metrics/summary",
        "diagnostic_scope": "agent/session aggregates replayed from agent_events JSONL",
        "metrics": [m.dict() for m in metrics],
        "count": len(metrics),
    }
