"""
agent_control_api.py — Control Plane Action API
=================================================
職責：執行 control action，不承擔 read-model 聚合。

Action 分類：
- integration_action: install, uninstall, rescan
- routing_action: enable, disable

禁止：
- 不做 read-model 聚合（委託給 status_read_model.py）
- 不做 metrics 計算
- 不做 truth surface 構建
"""

from __future__ import annotations

import copy
import importlib
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import agent_routing_state as _route_state
from .config import config

_srm = importlib.import_module("5_connectors.adapter.application.status_read_model")
_snapshot_cache = importlib.import_module("5_connectors.adapter.application.control_snapshot_cache")

router = APIRouter()

_AGENTS_CONTROL_CACHE_TTL_SECONDS = float(_snapshot_cache.DEFAULT_TTL_SECONDS)

_DISPLAY_NAMES = {
    "codex_cli": "Codex",
    "claude_code": "Claude Code",
    "cursor": "Cursor",
    "openclaw": "OpenClaw",
}


class AgentControlRequest(BaseModel):
    family_id: str
    upstream_truth: Optional[dict] = None


async def _runtime_request(method: str, path: str, payload: Optional[dict] = None) -> dict:
    base_url = str(config.memory_backend.base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
        response = await client.request(method, f"{base_url}{path}", json=payload)
    response.raise_for_status()
    return response.json()


def _find_card(cards, family_id):
    for card in cards:
        if card["family_id"] == family_id:
            return card
    return None


def _invalidate_agents_control_snapshot() -> None:
    _snapshot_cache.invalidate_agents_control_snapshot()


def _load_cached_agents_control_snapshot() -> Optional[dict]:
    return _snapshot_cache.load_cached_agents_control_snapshot()


def _store_agents_control_snapshot(payload: dict, ttl_seconds: float = _AGENTS_CONTROL_CACHE_TTL_SECONDS) -> None:
    _snapshot_cache.store_agents_control_snapshot(payload, ttl_seconds=ttl_seconds)


async def _build_agents_control_payload() -> dict:
    cards = await _srm.build_control_cards()
    system_status = await _srm.build_system_status()
    return {"agents": cards, "count": len(cards), "system_status": system_status}


# ============================================================================
# Read Model Proxy (delegates to status_read_model.py)
# ============================================================================

@router.get("/agents/control")
async def get_agents_control():
    """
    Read model endpoint — delegates to status_read_model.
    Kept here for API surface stability.
    """
    cached = _load_cached_agents_control_snapshot()
    if cached is not None:
        return cached

    try:
        payload = await _build_agents_control_payload()
        _store_agents_control_snapshot(payload)
        return copy.deepcopy(payload)
    except httpx.HTTPError as exc:
        # Failures are not cached; keep next read eligible for rebuild.
        _invalidate_agents_control_snapshot()
        raise HTTPException(status_code=503, detail=f"runtime control unavailable: {exc}") from exc


@router.post("/agents/control/rescan")
async def rescan_agents_control():
    """
    integration_action: rescan agents.
    Reads state before/after to report diff, but does not own read-model.
    """
    _invalidate_agents_control_snapshot()
    try:
        cards_before = await _srm.build_control_cards()
        families_before = {c["family_id"] for c in cards_before}

        await _runtime_request("POST", "/agents/control/rescan", {})
        cards = await _srm.build_control_cards()
        families_after = {c["family_id"] for c in cards}

        added = families_after - families_before
        removed = families_before - families_after

        if added:
            status_message = f"扫描完成：发现 {len(added)} 个新应用 ({', '.join(sorted(added))})"
            status_type = "added"
        elif removed:
            status_message = f"扫描完成：{len(removed)} 个应用已消失 ({', '.join(sorted(removed))})"
            status_type = "removed"
        else:
            status_message = "扫描完成，暂未发现新的应用"
            status_type = "no_change"

    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime rescan unavailable: {exc}") from exc

    _invalidate_agents_control_snapshot()
    system_status = await _srm.build_system_status()
    return {
        "agents": cards,
        "count": len(cards),
        "system_status": system_status,
        "rescan_status": status_type,
        "rescan_message": status_message,
        "rescan_added": list(added),
        "rescan_removed": list(removed),
    }


# ============================================================================
# integration_action: install / uninstall
# ============================================================================

@router.post("/agents/control/install")
async def install_agent_control(request: AgentControlRequest):
    """
    integration_action: install an agent.
    """
    _invalidate_agents_control_snapshot()
    # 保存 OpenClaw attach metadata upstream truth snapshot
    if request.family_id == "openclaw" and request.upstream_truth:
        _openclaw_attach = __import__(
            "5_connectors.adapter.openclaw_attach_state",
            fromlist=["dummy"]
        )
        _openclaw_attach.save_openclaw_attach_metadata(
            wire_api=request.upstream_truth.get("wire_api", "chat_completions"),
            provider=request.upstream_truth.get("provider", "openai_compatible"),
            base_url=request.upstream_truth.get("base_url", ""),
            auth_source=request.upstream_truth.get("auth_source", "runtime_authorization_header"),
            model=request.upstream_truth.get("model", ""),
            config_layer=request.upstream_truth.get("config_layer", "env"),
        )

    try:
        await _runtime_request("POST", "/agents/control/install", {"family_id": request.family_id})
        cards = await _srm.build_control_cards()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime install unavailable: {exc}") from exc

    _invalidate_agents_control_snapshot()
    card = _find_card(cards, request.family_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"family not found after install: {request.family_id}")
    return card


@router.post("/agents/control/uninstall")
async def uninstall_agent_control(request: AgentControlRequest):
    """
    integration_action: uninstall an agent.
    Note: routing_state is cleared here as part of the uninstall contract,
    not as a separate routing_action.
    """
    _invalidate_agents_control_snapshot()
    # 清除 OpenClaw attach metadata
    if request.family_id == "openclaw":
        _openclaw_attach = __import__(
            "5_connectors.adapter.openclaw_attach_state",
            fromlist=["dummy"]
        )
        _openclaw_attach.clear_openclaw_attach_metadata()

    try:
        # Clear routing state as part of uninstall contract
        _route_state.set_family_routing_enabled(request.family_id, False)
        await _runtime_request("POST", "/agents/control/uninstall", {"family_id": request.family_id})
        cards = await _srm.build_control_cards()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"runtime uninstall unavailable: {exc}") from exc

    _invalidate_agents_control_snapshot()
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
            "requests_24h": 0,
            "saved_tokens_24h": 0,
            "savings_ratio_24h": 0.0,
            "last_request_at": None,
            "integration_truth": "detached",
            "route_truth": "off",
            "traffic_truth": "no_recent_evidence",
            "observed_client_truth": {"provider": None, "model": None, "base_url": None, "base_url_class": "unknown"},
            "truth_message": "未接入 OmniMemora。點擊上方按鈕進行接入。",
        }
    card["routing_enabled"] = False
    return card


# ============================================================================
# routing_action: enable / disable
# ============================================================================

@router.post("/agents/control/enable")
async def enable_agent_control(request: AgentControlRequest):
    """
    routing_action: enable routing for an installed agent.
    """
    _invalidate_agents_control_snapshot()
    cards = await _srm.build_control_cards()
    card = _find_card(cards, request.family_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"family not found: {request.family_id}")
    if not card["installed"]:
        raise HTTPException(status_code=409, detail="agent must be installed before enabling routing")
    if card["health_state"] != "healthy":
        raise HTTPException(status_code=409, detail="OmniMemora is not healthy enough to enable routing")

    _route_state.set_family_routing_enabled(request.family_id, True)
    refreshed = await _srm.build_control_cards()
    updated = _find_card(refreshed, request.family_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"family not found after enable: {request.family_id}")
    updated["message"] = "routing enabled"
    _invalidate_agents_control_snapshot()
    return updated


@router.post("/agents/control/disable")
async def disable_agent_control(request: AgentControlRequest):
    """
    routing_action: disable routing for an agent.
    """
    _invalidate_agents_control_snapshot()
    _route_state.set_family_routing_enabled(request.family_id, False)
    refreshed = await _srm.build_control_cards()
    updated = _find_card(refreshed, request.family_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"family not found after disable: {request.family_id}")
    updated["message"] = "routing disabled"
    _invalidate_agents_control_snapshot()
    return updated
