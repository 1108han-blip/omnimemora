from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import agent_metrics as _agent_metrics
from . import agent_routing_state as _route_state
from . import compile_store as _compile_store
from .config import config

router = APIRouter()

_DISPLAY_NAMES = {
    "codex_cli": "Codex",
    "claude_code": "Claude Code",
    "cursor": "Cursor",
    "openclaw": "OpenClaw",
}


class AgentControlRequest(BaseModel):
    family_id: str


def _parse_iso(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


async def _runtime_request(method: str, path: str, payload: Optional[dict] = None) -> Dict[str, Any]:
    base_url = str(config.memory_backend.base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
        response = await client.request(method, f"{base_url}{path}", json=payload)
    response.raise_for_status()
    return response.json()


async def _runtime_health_state() -> str:
    try:
        payload = await _runtime_request("GET", "/health")
    except Exception:
        return "unreachable"
    status = str(payload.get("status") or "").strip().lower()
    return "healthy" if status in {"healthy", "ok"} else "degraded"


async def _build_system_status() -> Dict[str, Any]:
    _track_b_orchestrator = __import__("5_connectors.adapter.track_b_orchestrator", fromlist=["dummy"])
    health_state = await _runtime_health_state()
    per_agent_modes, _default_mode = _route_state.get_agent_modes_cache()
    return _track_b_orchestrator.build_system_status_from_runtime_health(
        runtime_health_state=health_state,
        per_agent_modes=per_agent_modes,
    )


def _build_metrics_index() -> dict[str, dict[str, Any]]:
    live = _agent_metrics.get_live_agents(window_minutes=30)
    all_metrics = _agent_metrics.get_agent_metrics()
    by_family: dict[str, dict[str, Any]] = {}

    # Phase 1: Primary activity source — compile/request-level product activity
    # compile events reflect真实产品请求进入 18011, taking precedence over subagent metrics
    compile_summary = _compile_store.summarize_compile_status(window_minutes=30)
    for family, stat in compile_summary.items():
        by_family[family] = {
            "active": True,
            "last_seen_at": datetime.fromtimestamp(stat["last_seen"], tz=timezone.utc).isoformat()
            if stat.get("last_seen")
            else None,
            "subagent_count_active": 0,
            "subagent_count_total_visible": 0,
        }

    # Phase 2: Fallback — agent_metrics only for families NOT already set by compile
    # compile sets active/last_seen_at; metrics fills subagent_count and provides fallback truth
    for item in all_metrics:
        family = item.agent_id
        state = by_family.setdefault(
            family,
            {
                "active": False,
                "last_seen_at": None,
                "subagent_count_active": 0,
                "subagent_count_total_visible": 0,
            },
        )
        state["subagent_count_total_visible"] += 1
        ts = _parse_iso(item.last_seen_at)
        current_ts = _parse_iso(state["last_seen_at"])
        # Only override if compile hasn't already set truth for this family
        if family not in compile_summary:
            if ts > current_ts:
                state["last_seen_at"] = item.last_seen_at
            if ts > 0:
                state["active"] = True

    for item in live:
        family = str(item.get("agent_id") or "unknown")
        state = by_family.setdefault(
            family,
            {
                "active": False,
                "last_seen_at": None,
                "subagent_count_active": 0,
                "subagent_count_total_visible": 0,
            },
        )
        state["subagent_count_active"] += 1
        ts = _parse_iso(item.get("last_seen_at"))
        current_ts = _parse_iso(state["last_seen_at"])
        # Only override if compile hasn't already set truth for this family
        if family not in compile_summary:
            state["active"] = True
            if ts > current_ts:
                state["last_seen_at"] = item.get("last_seen_at")

    return by_family


async def _build_control_cards() -> List[Dict[str, Any]]:
    runtime_payload = await _runtime_request("GET", "/agents/control")
    health_state = await _runtime_health_state()
    metrics_index = _build_metrics_index()

    cards: List[Dict[str, Any]] = []
    for raw in runtime_payload.get("agents", []):
        family_id = str(raw.get("family_id") or "")
        metric = metrics_index.get(family_id, {})
        cards.append(
            {
                "family_id": family_id,
                "display_name": raw.get("display_name") or _DISPLAY_NAMES.get(family_id, family_id),
                "installed": bool(raw.get("installed")),
                "routing_enabled": _route_state.routing_enabled(family_id),
                "detected": bool(raw.get("detected", True)),
                "active": bool(metric.get("active", False)),
                "last_seen_at": metric.get("last_seen_at"),
                "health_state": health_state,
                "backup_available": bool(raw.get("backup_available")),
                "subagent_count_active": int(metric.get("subagent_count_active", 0)),
                "subagent_count_total_visible": int(metric.get("subagent_count_total_visible", 0)),
                "message": raw.get("message", ""),
            }
        )

    cards.sort(key=lambda item: (not item["active"], item["display_name"].lower()))
    return cards


def _find_card(cards: List[Dict[str, Any]], family_id: str) -> Optional[Dict[str, Any]]:
    for card in cards:
        if card["family_id"] == family_id:
            return card
    return None


@router.get("/agents/control")
async def get_agents_control():
    try:
        cards = await _build_control_cards()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime control unavailable: {exc}") from exc
    return {"agents": cards, "count": len(cards), "system_status": await _build_system_status()}


@router.post("/agents/control/rescan")
async def rescan_agents_control():
    try:
        await _runtime_request("POST", "/agents/control/rescan", {})
        cards = await _build_control_cards()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime rescan unavailable: {exc}") from exc
    return {"agents": cards, "count": len(cards), "system_status": await _build_system_status()}


@router.post("/agents/control/install")
async def install_agent_control(request: AgentControlRequest):
    try:
        await _runtime_request("POST", "/agents/control/install", request.model_dump())
        cards = await _build_control_cards()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime install unavailable: {exc}") from exc

    card = _find_card(cards, request.family_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"family not found after install: {request.family_id}")
    return card


@router.post("/agents/control/uninstall")
async def uninstall_agent_control(request: AgentControlRequest):
    try:
        _route_state.set_family_routing_enabled(request.family_id, False)
        await _runtime_request("POST", "/agents/control/uninstall", request.model_dump())
        cards = await _build_control_cards()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime uninstall unavailable: {exc}") from exc

    card = _find_card(cards, request.family_id)
    if not card:
        return {
            "family_id": request.family_id,
            "display_name": _DISPLAY_NAMES.get(request.family_id, request.family_id),
            "installed": False,
            "routing_enabled": False,
            "detected": False,
            "active": False,
            "last_seen_at": None,
            "health_state": "unreachable",
            "backup_available": False,
            "subagent_count_active": 0,
            "subagent_count_total_visible": 0,
            "message": "agent no longer detected after uninstall",
        }
    card["routing_enabled"] = False
    return card


@router.post("/agents/control/enable")
async def enable_agent_control(request: AgentControlRequest):
    cards = await _build_control_cards()
    card = _find_card(cards, request.family_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"family not found: {request.family_id}")
    if not card["installed"]:
        raise HTTPException(status_code=409, detail="agent must be installed before enabling routing")
    if card["health_state"] != "healthy":
        raise HTTPException(status_code=409, detail="OmniMemora is not healthy enough to enable routing")

    _route_state.set_family_routing_enabled(request.family_id, True)
    refreshed = await _build_control_cards()
    updated = _find_card(refreshed, request.family_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"family not found after enable: {request.family_id}")
    updated["message"] = "routing enabled"
    return updated


@router.post("/agents/control/disable")
async def disable_agent_control(request: AgentControlRequest):
    _route_state.set_family_routing_enabled(request.family_id, False)
    refreshed = await _build_control_cards()
    updated = _find_card(refreshed, request.family_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"family not found after disable: {request.family_id}")
    updated["message"] = "routing disabled"
    return updated
