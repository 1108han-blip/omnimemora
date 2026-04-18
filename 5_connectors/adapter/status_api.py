"""
status_api.py — OmniMemora LLM Proxy + Compile 狀態 API
========================================================
提供 /proxy/status、/proxy/events 和 Phase 3 /compile/status、/compile/events 端點。
"""
import importlib
from fastapi import APIRouter, Response

router = APIRouter(tags=["proxy"])


def _mark_diagnostic_surface(response: Response) -> None:
    response.headers["X-OmniMemora-Surface-Role"] = "diagnostic"
    response.headers["X-OmniMemora-KPI-Source"] = "/metrics/summary"


async def _build_system_status() -> dict:
    _main = importlib.import_module("5_connectors.adapter.main")
    _route_state = importlib.import_module("5_connectors.adapter.agent_routing_state")
    _track_b = importlib.import_module("5_connectors.adapter.track_b_status")

    per_agent_modes, _default_mode = _route_state.get_agent_modes_cache()
    routing_enabled = any(mode == "force_if_possible" for mode in per_agent_modes.values())
    backend_health = await _main._get_backend().health()
    return _track_b.build_track_b_status(
        backend_health=backend_health,
        routing_enabled=routing_enabled,
        override=_track_b.read_status_override(),
    )


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
