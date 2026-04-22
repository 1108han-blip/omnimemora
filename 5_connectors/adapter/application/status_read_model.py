"""
status_read_model.py — Status / Diagnostics Read Model
=========================================================
職責：只讀聚合事實面，不承擔 action execution。

只讀聚合的事實面：
- control state
- runtime health
- metrics truth surface
- verification/governance evidence
- usage/log projection

禁止：
- 不進入 compile 主鏈
- 不執行 installation/routing 動作
- 不做 truth resolution 或 compile decision
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import httpx

_DISPLAY_NAMES = {
    "codex_cli": "Codex",
    "claude_code": "Claude Code",
    "cursor": "Cursor",
    "openclaw": "OpenClaw",
}


def _get_agent_metrics():
    return __import__("5_connectors.adapter.agent_metrics", fromlist=["dummy"])

def _get_agent_routing_state():
    return __import__("5_connectors.adapter.agent_routing_state", fromlist=["dummy"])

def _get_compile_store():
    return __import__("5_connectors.adapter.compile_store", fromlist=["dummy"])

def _get_meter_store():
    return __import__("5_connectors.adapter.meter_store", fromlist=["dummy"])

def _get_request_classifier():
    return __import__("5_connectors.adapter.request_classifier", fromlist=["dummy"])

def _get_config():
    return __import__("5_connectors.adapter.config", fromlist=["dummy"]).config


# ============================================================================
# Runtime Health & System Status
# ============================================================================

async def _runtime_request(method: str, path: str, payload: Optional[dict] = None) -> Dict[str, Any]:
    cfg = _get_config()
    base_url = str(cfg.memory_backend.base_url).rstrip("/")
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


async def build_system_status() -> Dict[str, Any]:
    """
    Build system_status from runtime health and per-agent routing modes.
    This is a read-model aggregation, not an action executor.
    """
    _track_b_orchestrator = __import__("5_connectors.adapter.track_b_orchestrator", fromlist=["dummy"])
    route_state = _get_agent_routing_state()
    health_state = await _runtime_health_state()
    per_agent_modes, _default_mode = route_state.get_agent_modes_cache()
    return _track_b_orchestrator.build_system_status_from_runtime_health(
        runtime_health_state=health_state,
        per_agent_modes=per_agent_modes,
    )


# ============================================================================
# Metrics Index (compile_store + agent_metrics dual source)
# ============================================================================

def _parse_iso(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def build_metrics_index() -> dict[str, dict[str, Any]]:
    """
    Build per-family metrics index from compile_store (primary) and agent_metrics (fallback).
    """
    agent_metrics = _get_agent_metrics()
    compile_store = _get_compile_store()

    live = agent_metrics.get_live_agents(window_minutes=30)
    all_metrics = agent_metrics.get_agent_metrics()
    by_family: dict[str, dict[str, Any]] = {}

    compile_summary = compile_store.summarize_compile_status(window_minutes=30)
    for family, stat in compile_summary.items():
        by_family[family] = {
            "active": True,
            "last_seen_at": datetime.fromtimestamp(stat["last_seen"], tz=timezone.utc).isoformat()
            if stat.get("last_seen")
            else None,
            "subagent_count_active": 0,
            "subagent_count_total_visible": 0,
        }

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
        if family not in compile_summary:
            state["active"] = True
            if ts > current_ts:
                state["last_seen_at"] = item.get("last_seen_at")

    return by_family


# ============================================================================
# Agent Normalization
# ============================================================================

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


# ============================================================================
# Truth Surface Derivation (read-only projection, not action)
# ============================================================================

def derive_integration_truth(card: Dict[str, Any]) -> str:
    """Derive integration_truth from installed + backup_available."""
    if not card.get("installed", False):
        return "detached"
    if card.get("backup_available", False):
        return "attached_with_backup"
    return "mcp_attached"


def derive_route_truth(routing_enabled: bool, health_state: str) -> str:
    """Derive route_truth from routing_enabled + health."""
    if not routing_enabled:
        return "off"
    if health_state == "healthy":
        return "effective"
    return "intent_on"


def _count_real_meters_in_window(family_id: str, cutoff_ts: float) -> int:
    """
    Count real (non-internal, non-tiny-ping) meter records for a family
    within a time window.
    """
    meter_store = _get_meter_store()
    request_classifier = _get_request_classifier()

    meter_store._ensure_persistence_loaded()

    count = 0
    for tenant, meters in meter_store._usage_aggregates.items():
        for m in meters:
            ts = getattr(m, "timestamp", None)
            if not ts:
                continue
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    continue
                if dt.timestamp() < cutoff_ts:
                    continue
            except Exception:
                continue

            agent = getattr(m, "agent", "") or ""
            normalized = _normalize_agent_to_family(agent)
            if normalized != family_id:
                continue

            if not request_classifier.is_default_overview_request(m):
                continue

            baseline = getattr(m, "baseline_tokens_estimate", 0)
            try:
                baseline = int(baseline)
            except (ValueError, TypeError):
                baseline = 0
            if baseline < 50:
                continue

            count += 1

    return count


def derive_traffic_truth(family_id: str, window_minutes: int = 30) -> str:
    """
    Derive traffic_truth using dual evidence: compile_store + meter_store.
    """
    import time as _time

    compile_store = _get_compile_store()

    compile_summary = compile_store.summarize_compile_status(window_minutes=window_minutes)
    family_stats = compile_summary.get(family_id)

    cutoff_ts = _time.time() - (window_minutes * 60)
    real_meter_count = _count_real_meters_in_window(family_id, cutoff_ts)

    if family_id == "openclaw":
        if not family_stats and real_meter_count == 0:
            return "no_recent_evidence"

        proxied = family_stats.get("proxied_requests", 0) if family_stats else 0

        if proxied > 0 and real_meter_count > 0:
            return "real_request_observed"
        elif proxied > 0:
            return "internal_only"
        else:
            return "no_recent_evidence"

    if family_stats and family_stats.get("proxied_requests", 0) > 0:
        return "internal_only"
    if real_meter_count > 0:
        return "real_request_observed"
    return "no_recent_evidence"


def derive_observed_client_truth(raw: Dict[str, Any]) -> Dict[str, Any]:
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


def derive_truth_message(card: Dict[str, Any], integration_truth: str, route_truth: str, traffic_truth: str) -> str:
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


# ============================================================================
# 24h Metrics Computation
# ============================================================================

def compute_family_24h_metrics(family_id: str) -> Dict[str, Any]:
    """
    Compute 24-hour metrics for a given family_id from meter_store.
    Primary KPI fields (requests_24h, saved_tokens_24h, savings_ratio_24h) are
    computed from value_qualified requests only. observed_requests_24h captures
    all task requests including task_non_value for diagnostics.
    """
    meter_store = _get_meter_store()
    request_classifier = _get_request_classifier()

    meter_store._ensure_persistence_loaded()
    all_meters: List[Any] = []
    for tenant_meters in meter_store._usage_aggregates.values():
        all_meters.extend(tenant_meters)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    observed_family_meters = []
    qualified_family_meters = []
    for m in all_meters:
        try:
            m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if m_time >= cutoff and _normalize_agent_to_family(m.agent) == family_id:
            if request_classifier.is_default_overview_request(m):
                observed_family_meters.append(m)
            if request_classifier.is_value_qualified(m):
                qualified_family_meters.append(m)

    observed_family_meters = request_classifier.collapse_retry_bursts(observed_family_meters)
    qualified_family_meters = request_classifier.collapse_retry_bursts(qualified_family_meters)

    if not qualified_family_meters:
        return {
            "requests_24h": 0,
            "saved_tokens_24h": 0,
            "savings_ratio_24h": 0.0,
            "last_request_at": None,
            "observed_requests_24h": len(observed_family_meters),
        }

    requests_24h = len(qualified_family_meters)
    saved_tokens_24h = sum(m.saved_tokens_estimate for m in qualified_family_meters)
    baseline_total = sum(m.baseline_tokens_estimate for m in qualified_family_meters)
    savings_ratio_24h = saved_tokens_24h / baseline_total if baseline_total > 0 else 0.0
    last_request_at = max((m.timestamp for m in qualified_family_meters), default=None)

    return {
        "requests_24h": requests_24h,
        "saved_tokens_24h": saved_tokens_24h,
        "savings_ratio_24h": round(savings_ratio_24h, 3),
        "last_request_at": last_request_at,
        "observed_requests_24h": len(observed_family_meters),
    }


# ============================================================================
# Control Cards Aggregation (Read Model)
# ============================================================================

async def build_control_cards() -> List[Dict[str, Any]]:
    """
    Build control cards aggregation from runtime payload, metrics index, and truth surfaces.
    This is the primary read-model output for the control plane.
    """
    route_state = _get_agent_routing_state()

    runtime_payload = await _runtime_request("GET", "/agents/control")
    health_state = await _runtime_health_state()
    metrics_index = build_metrics_index()

    cards: List[Dict[str, Any]] = []
    for raw in runtime_payload.get("agents", []):
        family_id = str(raw.get("family_id") or "")
        metric = metrics_index.get(family_id, {})
        metrics_24h = compute_family_24h_metrics(family_id)

        integration_truth = derive_integration_truth(raw)
        route_truth = derive_route_truth(route_state.routing_enabled(family_id), health_state)
        traffic_truth = derive_traffic_truth(family_id, window_minutes=30)
        observed_client_truth = derive_observed_client_truth(raw)
        truth_message = derive_truth_message(raw, integration_truth, route_truth, traffic_truth)

        cards.append(
            {
                "family_id": family_id,
                "display_name": raw.get("display_name") or _DISPLAY_NAMES.get(family_id, family_id),
                "installed": bool(raw.get("installed")),
                "routing_enabled": route_state.routing_enabled(family_id),
                "detected": bool(raw.get("detected", True)),
                "active": bool(metric.get("active", False)),
                "last_seen_at": metric.get("last_seen_at"),
                "health_state": health_state,
                "backup_available": bool(raw.get("backup_available")),
                "subagent_count_active": int(metric.get("subagent_count_active", 0)),
                "subagent_count_total_visible": int(metric.get("subagent_count_total_visible", 0)),
                "message": raw.get("message", ""),
                # 24h benefit fields
                "requests_24h": metrics_24h["requests_24h"],
                "saved_tokens_24h": metrics_24h["saved_tokens_24h"],
                "savings_ratio_24h": metrics_24h["savings_ratio_24h"],
                "last_request_at": metrics_24h["last_request_at"],
                "observed_requests_24h": metrics_24h["observed_requests_24h"],
                # Truth surface fields
                "integration_truth": integration_truth,
                "route_truth": route_truth,
                "traffic_truth": traffic_truth,
                "observed_client_truth": observed_client_truth,
                "truth_message": truth_message,
            }
        )

    cards.sort(key=lambda item: (not item["active"], item["display_name"].lower()))
    return cards