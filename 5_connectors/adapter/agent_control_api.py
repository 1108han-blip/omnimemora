from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import agent_metrics as _agent_metrics
from . import agent_routing_state as _route_state
from . import compile_store as _compile_store
from . import meter_store as _meter_store
from . import request_classifier as _rc
from .config import config

router = APIRouter()

_DISPLAY_NAMES = {
    "codex_cli": "Codex",
    "claude_code": "Claude Code",
    "cursor": "Cursor",
    "openclaw": "OpenClaw",
}


class UpstreamTruthSnapshot(BaseModel):
    """OpenClaw attach 時傳遞的上游真相快照。"""
    wire_api: str = "chat_completions"
    provider: str = "openai_compatible"
    base_url: str = ""
    auth_source: str = "runtime_authorization_header"
    model: str = ""
    config_layer: str = "env"


class AgentControlRequest(BaseModel):
    family_id: str
    upstream_truth: Optional[UpstreamTruthSnapshot] = None


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


def _build_integration_truth(card: Dict[str, Any]) -> str:
    """Derive integration_truth from installed + backup_available."""
    if not card.get("installed", False):
        return "detached"
    if card.get("backup_available", False):
        return "attached_with_backup"
    return "mcp_attached"


def _build_route_truth(routing_enabled: bool, health_state: str) -> str:
    """Derive route_truth from routing_enabled + health."""
    if not routing_enabled:
        return "off"
    if health_state == "healthy":
        return "effective"
    return "intent_on"


def _build_traffic_truth(family_id: str, window_minutes: int = 30) -> str:
    """
    Derive traffic_truth using dual evidence: compile_store + meter_store.

    Rules (priority order):
    1. real_request_observed: compile events exist AND corresponding real meter exists
    2. internal_only: compile events exist but no real meter evidence (bootstrap/ping only)
    3. no_recent_evidence: no compile events AND no real meter evidence

    This replaces the old single-source (compile_store only) logic that
    produced false positives when tiny pings triggered compile_success.
    """
    import time as _time

    compile_summary = _compile_store.summarize_compile_status(window_minutes=window_minutes)
    family_stats = compile_summary.get(family_id)

    # Get real meter evidence for this family in the window
    cutoff_ts = _time.time() - (window_minutes * 60)
    real_meter_count = _count_real_meters_in_window(family_id, cutoff_ts)

    if family_id == "openclaw":
        if not family_stats and real_meter_count == 0:
            return "no_recent_evidence"

        proxied = family_stats.get("proxied_requests", 0) if family_stats else 0

        if proxied > 0 and real_meter_count > 0:
            # Both compile evidence AND real meter evidence
            return "real_request_observed"
        elif proxied > 0:
            # Compile events exist but no real meter evidence
            return "internal_only"
        else:
            return "no_recent_evidence"

    # Non-openclaw families
    if family_stats and family_stats.get("proxied_requests", 0) > 0:
        return "internal_only"
    if real_meter_count > 0:
        return "real_request_observed"
    return "no_recent_evidence"


def _count_real_meters_in_window(family_id: str, cutoff_ts: float) -> int:
    """
    Count real (non-internal, non-tiny-ping) meter records for a family
    within a time window.

    Uses request_classifier for unified real/internal classification.
    """
    _meter_store._ensure_persistence_loaded()

    count = 0
    for tenant, meters in _meter_store._usage_aggregates.items():
        for m in meters:
            ts = getattr(m, "timestamp", None)
            if not ts:
                continue
            # Parse timestamp
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    continue
                if dt.timestamp() < cutoff_ts:
                    continue
            except Exception:
                continue

            # Normalize agent to family
            agent = getattr(m, "agent", "") or ""
            normalized = _normalize_agent_to_family(agent)
            if normalized != family_id:
                continue

            # Check if this request belongs to the default user-facing overview
            if not _rc.is_default_overview_request(m):
                continue

            # Check if tiny ping (baseline < 50 tokens)
            baseline = getattr(m, "baseline_tokens_estimate", 0)
            try:
                baseline = int(baseline)
            except (ValueError, TypeError):
                baseline = 0
            if baseline < 50:
                continue

            count += 1

    return count


def _normalize_agent_to_family(agent: str) -> str:
    """
    Normalize an agent identifier from meter records to its canonical family.
    """
    lower = agent.lower()
    if lower in {"openclaw", "openclaw-agent", "openclaw-bundle-mcp", "openclaw_bundle_mcp"}:
        return "openclaw"
    if lower in {"claude_code", "claude-code", "claude"}:
        return "claude_code"
    if lower in {"codex", "codex_cli", "codex-cli"}:
        return "codex_cli"
    if lower == "cursor":
        return "cursor"
    if lower == "test":
        return "test"
    return agent


def _build_observed_client_truth(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build observed_client_truth from runtime payload.
    Only observes; does not rename or productize.
    """
    base_url = raw.get("base_url", "") or ""
    base_url_class = "unknown"
    if "127.0.0.1" in base_url or "localhost" in base_url:
        base_url_class = "local"
    elif base_url.startswith("ws://") or base_url.startswith("wss://"):
        base_url_class = "remote_websocket"
    elif base_url.startswith("http://") or base_url.startswith("https://"):
        base_url_class = "remote_http"

    return {
        "provider": raw.get("provider", None),
        "model": raw.get("model", None),
        "base_url": base_url or None,
        "base_url_class": base_url_class,
    }


def _build_truth_message(card: Dict[str, Any], integration_truth: str, route_truth: str, traffic_truth: str) -> str:
    """Build user-facing truth_message from derived states."""
    installed = card.get("installed", False)
    routing_enabled = card.get("routing_enabled", False)

    if integration_truth == "detached":
        return "未接入 OmniMemora。點擊上方按鈕進行接入。"
    if integration_truth == "mcp_attached":
        if traffic_truth == "real_request_observed":
            return "已接入 MCP，的真實工作請求已進入 OmniMemora。"
        if traffic_truth == "internal_only":
            return "已接入 MCP，但當前僅看到內部握手，未證明主對話經 OmniMemora。"
        if routing_enabled:
            return "已接入 MCP，路由已開啟，等待真實工作請求。"
        return "已接入 MCP，當前無工作請求。"
    if integration_truth == "attached_with_backup":
        if traffic_truth == "real_request_observed":
            return "已接入並具備備份還原能力，真實工作請求已進入 OmniMemora。"
        if traffic_truth == "internal_only":
            return "已接入並具備備份還原能力，但當前僅看到內部握手。"
        if routing_enabled:
            return "已接入並具備備份還原能力，路由已開啟，等待真實工作請求。"
        return "已接入並具備備份還原能力，當前無工作請求。"
    return "ready"


async def _build_control_cards() -> List[Dict[str, Any]]:
    runtime_payload = await _runtime_request("GET", "/agents/control")
    health_state = await _runtime_health_state()
    metrics_index = _build_metrics_index()

    cards: List[Dict[str, Any]] = []
    for raw in runtime_payload.get("agents", []):
        family_id = str(raw.get("family_id") or "")
        metric = metrics_index.get(family_id, {})
        metrics_24h = _family_24h_metrics(family_id)

        integration_truth = _build_integration_truth(raw)
        route_truth = _build_route_truth(_route_state.routing_enabled(family_id), health_state)
        traffic_truth = _build_traffic_truth(family_id, window_minutes=30)
        observed_client_truth = _build_observed_client_truth(raw)
        truth_message = _build_truth_message(raw, integration_truth, route_truth, traffic_truth)

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
                # 24h benefit fields for overview unification
                "requests_24h": metrics_24h["requests_24h"],
                "saved_tokens_24h": metrics_24h["saved_tokens_24h"],
                "savings_ratio_24h": metrics_24h["savings_ratio_24h"],
                "last_request_at": metrics_24h["last_request_at"],
                # Truth surface fields (product boundary clarity)
                "integration_truth": integration_truth,
                "route_truth": route_truth,
                "traffic_truth": traffic_truth,
                "observed_client_truth": observed_client_truth,
                "truth_message": truth_message,
            }
        )

    cards.sort(key=lambda item: (not item["active"], item["display_name"].lower()))
    return cards


def _normalize_agent_to_family(agent: str) -> str:
    """
    Normalize an agent identifier from meter records to its canonical family.
    Only used for 24h收益聚合；不回寫原 meter。
    """
    lower = agent.lower()
    # openclaw family
    if lower in {"openclaw", "openclaw-agent", "openclaw-bundle-mcp", "openclaw_bundle_mcp"}:
        return "openclaw"
    # claude_code family
    if lower in {"claude_code", "claude-code", "claude"}:
        return "claude_code"
    # codex family
    if lower in {"codex", "codex_cli", "codex-cli"}:
        return "codex_cli"
    # cursor — no alias
    if lower == "cursor":
        return "cursor"
    # test — no alias
    if lower == "test":
        return "test"
    # Fallback: treat as given (supports unknown agents)
    return agent


def _family_24h_metrics(family_id: str) -> Dict[str, Any]:
    """
    Compute 24-hour metrics for a given family_id from meter_store.
    Agent identifiers are normalized via _normalize_agent_to_family before matching.
    Returns zeros if no meters found.
    """
    _meter_store._ensure_persistence_loaded()
    all_meters: List[Any] = []
    for tenant_meters in _meter_store._usage_aggregates.values():
        all_meters.extend(tenant_meters)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    family_meters = []
    for m in all_meters:
        try:
            m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if (
            m_time >= cutoff
            and _normalize_agent_to_family(m.agent) == family_id
            and _rc.is_default_overview_request(m)
        ):
            family_meters.append(m)

    family_meters = _rc.collapse_retry_bursts(family_meters)

    if not family_meters:
        return {"requests_24h": 0, "saved_tokens_24h": 0, "savings_ratio_24h": 0.0, "last_request_at": None}

    requests_24h = len(family_meters)
    saved_tokens_24h = sum(m.saved_tokens_estimate for m in family_meters)
    baseline_total = sum(m.baseline_tokens_estimate for m in family_meters)
    savings_ratio_24h = saved_tokens_24h / baseline_total if baseline_total > 0 else 0.0
    last_request_at = max((m.timestamp for m in family_meters), default=None)

    return {
        "requests_24h": requests_24h,
        "saved_tokens_24h": saved_tokens_24h,
        "savings_ratio_24h": round(savings_ratio_24h, 3),
        "last_request_at": last_request_at,
    }


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
        # Capture state before rescan to diff
        cards_before = await _build_control_cards()
        families_before = {c["family_id"] for c in cards_before}

        await _runtime_request("POST", "/agents/control/rescan", {})
        cards = await _build_control_cards()
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
    return {
        "agents": cards,
        "count": len(cards),
        "system_status": await _build_system_status(),
        "rescan_status": status_type,
        "rescan_message": status_message,
        "rescan_added": list(added),
        "rescan_removed": list(removed),
    }


@router.post("/agents/control/install")
async def install_agent_control(request: AgentControlRequest):
    # 保存 OpenClaw attach metadata upstream truth snapshot
    if request.family_id == "openclaw" and request.upstream_truth:
        _openclaw_attach = __import__(
            "5_connectors.adapter.openclaw_attach_state",
            fromlist=["dummy"]
        )
        _openclaw_attach.save_openclaw_attach_metadata(
            wire_api=request.upstream_truth.wire_api,
            provider=request.upstream_truth.provider,
            base_url=request.upstream_truth.base_url,
            auth_source=request.upstream_truth.auth_source,
            model=request.upstream_truth.model,
            config_layer=request.upstream_truth.config_layer,
        )

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
    # 清除 OpenClaw attach metadata
    if request.family_id == "openclaw":
        _openclaw_attach = __import__(
            "5_connectors.adapter.openclaw_attach_state",
            fromlist=["dummy"]
        )
        _openclaw_attach.clear_openclaw_attach_metadata()

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
            "requests_24h": 0,
            "saved_tokens_24h": 0,
            "savings_ratio_24h": 0.0,
            "last_request_at": None,
            # Truth surface fields
            "integration_truth": "detached",
            "route_truth": "off",
            "traffic_truth": "no_recent_evidence",
            "observed_client_truth": {"provider": None, "model": None, "base_url": None, "base_url_class": "unknown"},
            "truth_message": "未接入 OmniMemora。點擊上方按鈕進行接入。",
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
