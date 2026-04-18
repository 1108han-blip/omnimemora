"""
status_api.py — OmniMemora LLM Proxy + Compile 狀態 API
========================================================
提供 /proxy/status、/proxy/events 和 Phase 3 /compile/status、/compile/events 端點。
"""
import importlib
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(tags=["proxy"])


class TrackBStatusOverrideRequest(BaseModel):
    status: Optional[str] = None
    status_source: Optional[str] = None
    transition_reason: Optional[str] = None
    gateway_health: Optional[str] = None
    capability_health: Optional[str] = None
    routing_requested: Optional[bool] = None
    routing_effective: Optional[bool] = None
    user_action_required: Optional[bool] = None
    recommended_action: Optional[str] = None
    error_code: Optional[str] = None


def _mark_diagnostic_surface(response: Response) -> None:
    response.headers["X-OmniMemora-Surface-Role"] = "diagnostic"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"


async def _build_system_status() -> dict:
    _main = importlib.import_module("5_connectors.adapter.main")
    _route_state = importlib.import_module("5_connectors.adapter.agent_routing_state")
    _track_b_orchestrator = importlib.import_module("5_connectors.adapter.track_b_orchestrator")

    per_agent_modes, _default_mode = _route_state.get_agent_modes_cache()
    backend_health = await _main._get_backend().health()
    return _track_b_orchestrator.build_system_status_from_backend_health(
        backend_health=backend_health,
        per_agent_modes=per_agent_modes,
    )


def _require_internal_service_token(request: Request) -> None:
    internal_token = request.headers.get("X-Internal-Token", "")
    expected_token = os.getenv("OMNIMEMORA_INTERNAL_API_TOKEN", "")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Internal API token not configured on adapter.")
    if not internal_token or internal_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid internal service token.")


# ============================================================================
# Proxy Status（Phase 2）
# ============================================================================

@router.get("/proxy/status")
async def proxy_status(response: Response, window_minutes: int = 30, include_system: bool = False):
    """
    返回每個 Agent 的代理接入狀態。

    響應格式：
    {
      "claude_code": {
        "connected": true,
        "last_seen": 1710000000,
        "proxied_requests": 8,
        "failed_requests": 0
      },
      ...
    }
    """
    _ps = importlib.import_module("5_connectors.adapter.proxy_store")
    _mark_diagnostic_surface(response)
    agents = _ps.summarize_agent_status(window_minutes=window_minutes)
    if not include_system:
        return agents
    return {
        "system_status": await _build_system_status(),
        "agents": agents,
    }


@router.get("/proxy/system-status")
async def proxy_system_status(response: Response):
    _mark_diagnostic_surface(response)
    return await _build_system_status()


@router.post("/proxy/system-status/override")
async def set_proxy_system_status_override(
    payload: TrackBStatusOverrideRequest,
    request: Request,
    response: Response,
):
    _track_b = importlib.import_module("5_connectors.adapter.track_b_status")
    _require_internal_service_token(request)
    try:
        _track_b.write_status_override(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _mark_diagnostic_surface(response)
    return await _build_system_status()


@router.delete("/proxy/system-status/override")
async def clear_proxy_system_status_override(request: Request, response: Response):
    _track_b = importlib.import_module("5_connectors.adapter.track_b_status")
    _require_internal_service_token(request)
    _track_b.clear_status_override()
    _mark_diagnostic_surface(response)
    return await _build_system_status()


@router.get("/proxy/events")
async def proxy_events(response: Response, limit: int = 50):
    """返回最近的代理事件日誌。"""
    _ps = importlib.import_module("5_connectors.adapter.proxy_store")
    _mark_diagnostic_surface(response)
    return {"events": _ps.read_recent_events(limit=limit)}


# ============================================================================
# Compile Status（Phase 3）
# ============================================================================

@router.get("/compile/status")
async def compile_status(response: Response, window_minutes: int = 30):
    """
    返回每個 Agent 的 Gateway Compile 統計。

    響應格式：
    {
      "claude_code": {
        "proxied_requests": 20,
        "compile_success": 18,
        "compile_skipped": 1,
        "compile_failed": 1,
        "avg_compression_ratio": 0.68,
        "avg_selected_memories": 3.2,
        "last_seen": 1710000000
      },
      ...
    }
    """
    _cs = importlib.import_module("5_connectors.adapter.compile_store")
    _mark_diagnostic_surface(response)
    return _cs.summarize_compile_status(window_minutes=window_minutes)


@router.get("/compile/events")
async def compile_events(response: Response, limit: int = 50, window_minutes: int = None):
    """
    返回最近的 Compile 事件日誌。

    Args:
        limit: 最大返回條目數
        window_minutes: 可選，限定時間窗口
    """
    _cs = importlib.import_module("5_connectors.adapter.compile_store")
    kw = {"limit": limit}
    if window_minutes is not None:
        kw["window_minutes"] = window_minutes
    _mark_diagnostic_surface(response)
    return {"events": _cs.read_recent_compile_events(**kw)}


@router.get("/trace/events")
async def trace_events(response: Response, limit: int = 50, trace_id: str = None):
    _ts = importlib.import_module("5_connectors.adapter.trace_events")
    _mark_diagnostic_surface(response)
    return {"events": _ts.read_recent_trace_events(limit=limit, trace_id=trace_id)}


@router.get("/path/registry")
async def path_registry(response: Response):
    _pr = importlib.import_module("5_connectors.adapter.path_registry")
    _mark_diagnostic_surface(response)
    return {
        "path_mode": importlib.import_module("5_connectors.adapter.config").config.path_mode,
        "primary_ratio": importlib.import_module("5_connectors.adapter.config").config.primary_ratio,
        "paths": _pr.get_registry_snapshot(),
    }
