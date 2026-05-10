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

import importlib
import inspect as _inspect
import os
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import httpx

_DISPLAY_NAMES = {
    "codex_cli": "Codex",
    "claude_code": "Claude Code",
    "cursor": "Cursor",
    "openclaw": "OpenClaw",
}


# ============================================================================
# Diagnostics Read-Model Configuration
# ============================================================================

_diag_config = None
_diag_get_backend_fn = None
_diag_get_dedup_cache_fn = None
_diag_rate_limiter = None
_diag_adapter_hostname = ""
_diag_adapter_started_at = ""
_diag_agent_metrics_module = None
_diag_agent_identity_module = None
_diag_get_meter_fn = None
_diag_support_schema_version = ""
_diag_support_error_catalog: Dict[str, Dict[str, Any]] = {}
_diag_last_degraded_record_ts = 0.0
_diag_degraded_record_lock = threading.Lock()
_status_meter_read_resolver = importlib.import_module(
    "5_connectors.adapter.application.status_read_model_meter_read_resolver"
)


def configure_diagnostics_read_model(
    *,
    config_obj: Any,
    get_backend_fn: Any,
    get_dedup_cache_fn: Any,
    rate_limiter: Any,
    adapter_hostname: str,
    adapter_started_at: str,
    agent_metrics_module: Any,
    agent_identity_module: Any,
    get_meter_fn: Any,
    support_schema_version: str,
    support_error_catalog: Dict[str, Dict[str, Any]],
) -> None:
    """Configure diagnostics read-model dependencies from adapter main assembly."""
    global _diag_config, _diag_get_backend_fn, _diag_get_dedup_cache_fn, _diag_rate_limiter
    global _diag_adapter_hostname, _diag_adapter_started_at, _diag_agent_metrics_module, _diag_agent_identity_module
    global _diag_get_meter_fn, _diag_support_schema_version, _diag_support_error_catalog
    _diag_config = config_obj
    _diag_get_backend_fn = get_backend_fn
    _diag_get_dedup_cache_fn = get_dedup_cache_fn
    _diag_rate_limiter = rate_limiter
    _diag_adapter_hostname = adapter_hostname
    _diag_adapter_started_at = adapter_started_at
    _diag_agent_metrics_module = agent_metrics_module
    _diag_agent_identity_module = agent_identity_module
    _diag_get_meter_fn = get_meter_fn
    _diag_support_schema_version = support_schema_version
    _diag_support_error_catalog = support_error_catalog


def _require_diag_config() -> None:
    if _diag_config is None:
        raise RuntimeError("diagnostics read-model is not configured")


def _diag_agent_metrics():
    return _diag_agent_metrics_module or _get_agent_metrics()


def _diag_agent_identity():
    if _diag_agent_identity_module is not None:
        return _diag_agent_identity_module
    return __import__("5_connectors.adapter.agent_identity", fromlist=["dummy"])


def _get_agent_metrics():
    return __import__("5_connectors.adapter.agent_metrics", fromlist=["dummy"])

def _get_agent_routing_state():
    return __import__("5_connectors.adapter.agent_routing_state", fromlist=["dummy"])

def _get_compile_store():
    return __import__("5_connectors.adapter.infrastructure.compile_store", fromlist=["dummy"])

def _get_meter_store():
    return __import__("5_connectors.adapter.infrastructure.meter_store", fromlist=["dummy"])

def _get_request_classifier():
    return __import__("5_connectors.adapter.request_classifier", fromlist=["dummy"])

def _get_config():
    return __import__("5_connectors.adapter.config", fromlist=["dummy"]).config


def _get_data_lifecycle_policy():
    return __import__("5_connectors.adapter.data_lifecycle.policy", fromlist=["dummy"])


def _get_data_lifecycle_summary_store():
    return __import__("5_connectors.adapter.data_lifecycle.summary_store", fromlist=["dummy"])


def _get_data_lifecycle_state_store():
    return __import__("5_connectors.adapter.data_lifecycle.state_store", fromlist=["dummy"])


def _get_data_lifecycle_summary_builder():
    return __import__("5_connectors.adapter.data_lifecycle.summary_builder", fromlist=["dummy"])


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


def _epoch_to_iso(epoch_value: Optional[float]) -> Optional[str]:
    if not epoch_value:
        return None
    try:
        return datetime.fromtimestamp(float(epoch_value), tz=timezone.utc).isoformat()
    except Exception:
        return None


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
    """Normalize an agent identifier to its canonical family."""
    summary_builder = _get_data_lifecycle_summary_builder()
    normalized = summary_builder.normalize_agent_to_family(agent)
    if normalized == str(agent or "") and str(agent or "").lower() == "test":
        return "test"
    return normalized


def _is_meter_family_match(meter: Any, family_id: str) -> bool:
    agent = getattr(meter, "agent", "") or ""
    return _normalize_agent_to_family(agent) == family_id


# ============================================================================
# Truth Surface Derivation (read-only projection, not action)
# ============================================================================

def derive_integration_truth(card: Dict[str, Any]) -> str:
    """Derive integration_truth from installed + backup_available."""
    if not card.get("installed", False):
        return "detached"
    if card.get("family_id") == "codex_cli" and not card.get("backup_available", False):
        return "managed_ready"
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


def _filter_observed_family_candidates(
    candidates: List[Any],
    *,
    family_id: str,
    window_minutes: int,
) -> List[Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    request_classifier = _get_request_classifier()

    observed: List[Any] = []
    seen_request_ids: set[str] = set()

    def _maybe_add_meter(m: Any) -> None:
        request_id = str(getattr(m, "request_id", "") or "")
        if request_id and request_id in seen_request_ids:
            return

        ts = getattr(m, "timestamp", None)
        if not ts:
            return
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
            else:
                return
            if dt < cutoff:
                return
        except Exception:
            return

        if not _is_meter_family_match(m, family_id):
            return

        if not request_classifier.is_default_overview_request(m):
            return

        baseline = getattr(m, "baseline_tokens_estimate", 0)
        try:
            baseline = int(baseline)
        except (ValueError, TypeError):
            baseline = 0
        if baseline < 50:
            return

        observed.append(m)
        if request_id:
            seen_request_ids.add(request_id)
    for m in candidates:
        _maybe_add_meter(m)
    return request_classifier.collapse_retry_bursts(observed)


def _collect_observed_family_meters_legacy(family_id: str, window_minutes: int = 30) -> List[Any]:
    """
    Legacy family-scoped observed task meter collection.
    Kept as fallback implementation for sqlite-first resolver.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    cutoff_epoch = cutoff.timestamp()
    meter_store = _get_meter_store()
    meter_store._ensure_persistence_loaded()

    candidates: List[Any] = []

    # Primary source: in-memory tenant aggregates
    for meters in meter_store._usage_aggregates.values():
        candidates.extend(meters)

    # Secondary fallback: recent proxy request IDs resolved through in-memory meter index.
    # Keep this path memory-only to avoid per-request disk replay under load.
    try:
        proxy_store = __import__("5_connectors.adapter.infrastructure.proxy_store", fromlist=["dummy"])
        recent_events = proxy_store.read_recent_events(limit=1000)
    except Exception:
        recent_events = []
    meter_memory_index = getattr(meter_store, "_meter_store", None)
    meter_getter = _diag_get_meter_fn if callable(_diag_get_meter_fn) else getattr(meter_store, "get_meter", None)
    if isinstance(meter_memory_index, dict) or callable(meter_getter):
        if len(recent_events) == 0 and isinstance(meter_memory_index, dict):
            for event in recent_events:
                try:
                    if event.get("type") != "proxy_request":
                        continue
                    ts = float(event.get("timestamp") or 0)
                    if ts < cutoff_epoch:
                        continue
                    agent_id = str(event.get("agent_id") or "")
                    if _normalize_agent_to_family(agent_id) != family_id:
                        continue
                    request_id = str(event.get("request_id") or "")
                    if not request_id:
                        continue
                    meter_obj = meter_memory_index.get(request_id) if isinstance(meter_memory_index, dict) else None
                    if meter_obj is None and callable(meter_getter) and not isinstance(meter_memory_index, dict):
                        meter_obj = meter_getter(request_id)
                    if meter_obj is None:
                        continue
                    candidates.append(meter_obj)
                except Exception:
                    continue
        else:
            # No proxy events — directly iterate _meter_store dict values as fallback.
            # Each value must be a dict with request_id + baseline_tokens_estimate >= 50.
            if isinstance(meter_memory_index, dict):
                for request_id, meter_dict in meter_memory_index.items():
                    if not isinstance(meter_dict, dict):
                        continue
                    # Construct a lightweight object that _maybe_add_meter can inspect
                    meter_obj = type("Meter", (), meter_dict)()
                    candidates.append(meter_obj)

    return _filter_observed_family_candidates(
        candidates,
        family_id=family_id,
        window_minutes=window_minutes,
    )


def _collect_observed_family_meters(family_id: str, window_minutes: int = 30) -> List[Any]:
    """
    Collect family-scoped observed task meters for control/read-model truth.

    Inclusion criteria (fixed contract):
    - family_id matches after normalization
    - timestamp falls within window
    - request_classifier.is_default_overview_request(m) is True
    - baseline_tokens_estimate >= 50
    """
    resolution = _status_meter_read_resolver.resolve_status_read_model_meters(
        family_id=family_id,
        window_minutes=window_minutes,
        legacy_collect_fn=_collect_observed_family_meters_legacy,
        family_match_fn=_is_meter_family_match,
    )
    if resolution.degraded and resolution.degraded_reason:
        _record_degraded_path(resolution.degraded_reason)
    return _filter_observed_family_candidates(
        resolution.meters,
        family_id=family_id,
        window_minutes=window_minutes,
    )


def _collect_family_window_meters_legacy(family_id: str, window_minutes: int) -> List[Any]:
    meter_store = _get_meter_store()
    meter_store._ensure_persistence_loaded()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    output: List[Any] = []
    for tenant_meters in meter_store._usage_aggregates.values():
        for m in tenant_meters:
            try:
                m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                continue
            if m_time >= cutoff and _is_meter_family_match(m, family_id):
                output.append(m)
    return output


def _summarize_family_compile_events(
    family_id: str,
    window_minutes: int = 30,
    preloaded_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if preloaded_rows is None:
        compile_store = _get_compile_store()
        rows = compile_store.read_recent_compile_events(limit=5000, window_minutes=window_minutes)
    else:
        rows = preloaded_rows
    summary_builder = _get_data_lifecycle_summary_builder()
    return summary_builder.summarize_compile_rows_for_family(rows, family_id)


def derive_traffic_truth(
    family_id: str,
    window_minutes: int = 30,
    observed_meters: Optional[List[Any]] = None,
    compile_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Derive traffic_truth using running-reality-first evidence.

    Priority:
    1) real request observed (meter-backed)
    2) bypassed compile route observed
    3) compile_empty observed
    4) internal compile evidence only
    5) no recent evidence
    """
    if observed_meters is None:
        observed_meters = _collect_observed_family_meters(family_id, window_minutes=window_minutes)
    family_compile = compile_summary or _summarize_family_compile_events(family_id, window_minutes=window_minutes)
    summary_builder = _get_data_lifecycle_summary_builder()
    return summary_builder.derive_traffic_truth_from_counts(len(observed_meters), family_compile)


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


def _activity_state_from_metric_and_process(
    metric: Dict[str, Any],
    *,
    process_running: bool,
) -> Dict[str, Any]:
    if process_running:
        return {
            "active": True,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "active": bool(metric.get("active", False)),
        "last_seen_at": metric.get("last_seen_at"),
    }


def derive_truth_message(
    card: Dict[str, Any],
    integration_truth: str,
    route_truth: str,
    traffic_truth: str,
    metrics_24h: Optional[Dict[str, Any]] = None,
) -> str:
    """Build user-facing truth_message from derived states."""
    installed = card.get("installed", False)
    routing_enabled = card.get("routing_enabled", False)
    metrics_24h = metrics_24h or {}
    has_24h_value = int(metrics_24h.get("requests_24h") or 0) > 0 or int(metrics_24h.get("saved_tokens_24h") or 0) > 0

    if integration_truth == "detached":
        return "未接入 OmniMemora。點擊上方按鈕進行接入。"
    if integration_truth == "mcp_attached":
        if traffic_truth == "real_request_observed":
            return "已接入 MCP，的真實工作請求已進入 OmniMemora。"
        if traffic_truth == "internal_only":
            if has_24h_value:
                return "已接入 MCP，24 小時內已有真實請求收益；最近 30 分鐘僅看到內部握手。"
            return "已接入 MCP，但當前僅看到內部握手，未證明主對話經 OmniMemora。"
        if traffic_truth == "no_recent_evidence" and has_24h_value:
            return "已接入 MCP，24 小時內已有真實請求收益；最近 30 分鐘暫無工作請求。"
        if card.get("running"):
            return "已接入 MCP，檢測到客戶端正在運行，等待真實工作請求。"
        if routing_enabled:
            return "已接入 MCP，路由已開啟，等待真實工作請求。"
        return "已接入 MCP，當前無工作請求。"
    if integration_truth == "managed_ready":
        if traffic_truth == "real_request_observed":
            return "已準備 OmniMemora 管理入口，真實工作請求已進入 OmniMemora。"
        if traffic_truth == "internal_only":
            if has_24h_value:
                return "已準備 OmniMemora 管理入口，24 小時內已有真實請求收益；最近 30 分鐘僅看到內部握手。"
            return "已準備 OmniMemora 管理入口，但當前僅看到內部握手。"
        if traffic_truth == "no_recent_evidence" and has_24h_value:
            return "已準備 OmniMemora 管理入口，24 小時內已有真實請求收益；最近 30 分鐘暫無工作請求。"
        if routing_enabled:
            return "已準備 OmniMemora 管理入口，路由已開啟，等待受管 Codex 工作請求。"
        return "已準備 OmniMemora 管理入口，原 Codex 配置保持不變。"
    if integration_truth == "attached_with_backup":
        if traffic_truth == "real_request_observed":
            return "已接入並具備備份還原能力，真實工作請求已進入 OmniMemora。"
        if traffic_truth == "internal_only":
            if has_24h_value:
                return "已接入並具備備份還原能力，24 小時內已有真實請求收益；最近 30 分鐘僅看到內部握手。"
            return "已接入並具備備份還原能力，但當前僅看到內部握手。"
        if traffic_truth == "no_recent_evidence" and has_24h_value:
            return "已接入並具備備份還原能力，24 小時內已有真實請求收益；最近 30 分鐘暫無工作請求。"
        if card.get("running"):
            return "已接入並具備備份還原能力，檢測到客戶端正在運行，等待真實工作請求。"
        if routing_enabled:
            return "已接入並具備備份還原能力，路由已開啟，等待真實工作請求。"
        return "已接入並具備備份還原能力，當前無工作請求。"
    return "ready"


def _derive_scope_note(family_id: str) -> Optional[str]:
    """
    Derive scope_note for control cards.
    All control cards default to family scope.
    claude_code gets an explicit note clarifying the family-aggregate nature.
    """
    if family_id == "claude_code":
        return (
            "此卡僅表達 Claude family 的聚合 truth。獨立 profile（如 cc-haha）不會作為單獨控制卡出現。"
            "獨立 profile 的驗證應查看 request evidence / 驗證記錄，不看是否出現第二張卡。"
        )
    return None


def compute_family_24h_metrics(
    family_id: str,
    observed_family_meters: Optional[List[Any]] = None,
    compile_24h_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute 24-hour metrics for a given family_id from meter_store.
    Primary KPI fields (requests_24h, saved_tokens_24h, savings_ratio_24h) are
    computed from value_qualified requests only. observed_requests_24h captures
    all task requests including task_non_value for diagnostics.
    """
    request_classifier = _get_request_classifier()
    if observed_family_meters is None:
        observed_family_meters = _collect_observed_family_meters(family_id, window_minutes=24 * 60)

    all_meters_resolution = _status_meter_read_resolver.resolve_status_read_model_meters(
        family_id=family_id,
        window_minutes=24 * 60,
        legacy_collect_fn=_collect_family_window_meters_legacy,
        family_match_fn=_is_meter_family_match,
    )
    if all_meters_resolution.degraded and all_meters_resolution.degraded_reason:
        _record_degraded_path(all_meters_resolution.degraded_reason)
    all_meters = all_meters_resolution.meters

    qualified_family_meters = []
    for m in all_meters:
        if request_classifier.is_value_qualified(m):
            qualified_family_meters.append(m)

    qualified_family_meters = request_classifier.collapse_retry_bursts(qualified_family_meters)

    compile_24h = compile_24h_summary or _summarize_family_compile_events(family_id, window_minutes=24 * 60)
    compile_last_request_at = _epoch_to_iso(compile_24h.get("last_event_ts"))
    observed_last_request_at = None
    for m in observed_family_meters:
        ts = getattr(m, "timestamp", None)
        if not isinstance(ts, str):
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if observed_last_request_at is None:
            observed_last_request_at = (dt, ts)
            continue
        if dt > observed_last_request_at[0]:
            observed_last_request_at = (dt, ts)
    observed_last_request_at_str = observed_last_request_at[1] if observed_last_request_at else None

    if not qualified_family_meters:
        return {
            "requests_24h": 0,
            "saved_tokens_24h": 0,
            "savings_ratio_24h": 0.0,
            "last_request_at": observed_last_request_at_str or compile_last_request_at,
            "observed_requests_24h": len(observed_family_meters),
        }

    requests_24h = len(qualified_family_meters)
    saved_tokens_24h = sum(m.saved_tokens_estimate for m in qualified_family_meters)
    baseline_total = sum(m.baseline_tokens_estimate for m in qualified_family_meters)
    savings_ratio_24h = saved_tokens_24h / baseline_total if baseline_total > 0 else 0.0
    qualified_last_request_at = max((m.timestamp for m in qualified_family_meters), default=None)
    last_request_at = observed_last_request_at_str or compile_last_request_at or qualified_last_request_at

    return {
        "requests_24h": requests_24h,
        "saved_tokens_24h": saved_tokens_24h,
        "savings_ratio_24h": round(savings_ratio_24h, 3),
        "last_request_at": last_request_at,
        "observed_requests_24h": len(observed_family_meters),
    }


def _is_valid_summary_contract(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    required_keys = {
        "schema_version",
        "generated_at",
        "source_counts",
        "builder_version",
        "families",
    }
    if not required_keys.issubset(set(payload.keys())):
        return False
    if payload.get("schema_version") != "dlp-family-window-summary-v1":
        return False
    if not isinstance(payload.get("generated_at"), (int, float)):
        return False
    if not isinstance(payload.get("source_counts"), dict):
        return False
    if not isinstance(payload.get("builder_version"), str):
        return False
    if not isinstance(payload.get("families"), dict):
        return False
    degraded_reason = payload.get("degraded_reason")
    if degraded_reason is not None and not isinstance(degraded_reason, str):
        return False
    return True


def _read_family_window_summary() -> tuple[Optional[Dict[str, Dict[str, Any]]], str, Optional[str]]:
    """
    Read family/window summary from Data Lifecycle Plane.
    Order: fresh summary -> stale-but-usable summary -> None.
    """
    try:
        policy_mod = _get_data_lifecycle_policy()
        summary_store = _get_data_lifecycle_summary_store()
        policy = policy_mod.load_policy()
        payload = summary_store.read_fresh_summary(policy=policy)
        source = "fresh"
        if payload is None:
            payload = summary_store.read_stale_usable_summary(policy=policy)
            source = "stale"
    except Exception:
        return None, "none", "summary_read_error"

    if payload is None:
        return None, "none", "summary_missing"
    if not _is_valid_summary_contract(payload):
        return None, "none", "summary_contract_invalid"
    families = payload.get("families")
    return families, source, None


def _record_degraded_path(reason: str) -> None:
    global _diag_last_degraded_record_ts
    now_ts = time.time()
    with _diag_degraded_record_lock:
        if (now_ts - _diag_last_degraded_record_ts) < 60.0:
            return
        _diag_last_degraded_record_ts = now_ts
    try:
        state_store = _get_data_lifecycle_state_store()
        now = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=state_store.new_cycle_id(),
            trigger="read_model_degraded",
            started_at=now,
            completed_at=now,
            status="degraded",
            bytes_scanned=0,
            error=reason,
        )
        state_store.append_state_record(record)
    except Exception:
        pass


def _safe_family_summary(
    summary_families: Optional[Dict[str, Dict[str, Any]]],
    family_id: str,
) -> Optional[Dict[str, Any]]:
    if not summary_families:
        return None
    payload = summary_families.get(family_id)
    if isinstance(payload, dict):
        return payload
    return None


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
    summary_families, _summary_source, degraded_reason = _read_family_window_summary()
    compile_rows_30m = None
    compile_rows_24h = None
    using_legacy_fallback = summary_families is None
    if summary_families is None:
        # Degraded compatibility path when DLP summary contract cannot be used.
        compile_store = _get_compile_store()
        compile_rows_30m = compile_store.read_recent_compile_events(limit=5000, window_minutes=30)
        compile_rows_24h = compile_store.read_recent_compile_events(limit=5000, window_minutes=24 * 60)

    cards: List[Dict[str, Any]] = []
    for raw in runtime_payload.get("agents", []):
        family_id = str(raw.get("family_id") or "")
        metric = metrics_index.get(family_id, {})
        family_summary = _safe_family_summary(summary_families, family_id)
        if family_summary is not None:
            compile_30m = family_summary.get("compile_30m") or {
                "proxied_requests": 0,
                "compile_empty": 0,
                "bypassed": 0,
                "last_event_ts": None,
            }
            compile_24h = family_summary.get("compile_24h") or {
                "proxied_requests": 0,
                "compile_empty": 0,
                "bypassed": 0,
                "last_event_ts": None,
            }
            metrics_24h = family_summary.get("metrics_24h") or {
                "requests_24h": 0,
                "saved_tokens_24h": 0,
                "savings_ratio_24h": 0.0,
                "last_request_at": None,
                "observed_requests_24h": 0,
            }
            observed_30m = []
            traffic_truth = str(family_summary.get("traffic_truth_30m") or "").strip().lower()
            if not traffic_truth:
                traffic_truth = derive_traffic_truth(
                    family_id,
                    window_minutes=30,
                    observed_meters=[],
                    compile_summary=compile_30m,
                )
        else:
            observed_30m = _collect_observed_family_meters(family_id, window_minutes=30)
            compile_30m = _summarize_family_compile_events(
                family_id,
                window_minutes=30,
                preloaded_rows=compile_rows_30m,
            )
            observed_24h = _collect_observed_family_meters(family_id, window_minutes=24 * 60)
            compile_24h = _summarize_family_compile_events(
                family_id,
                window_minutes=24 * 60,
                preloaded_rows=compile_rows_24h,
            )
            metrics_24h = compute_family_24h_metrics(
                family_id,
                observed_family_meters=observed_24h,
                compile_24h_summary=compile_24h,
            )
            traffic_truth = derive_traffic_truth(
                family_id,
                window_minutes=30,
                observed_meters=observed_30m,
                compile_summary=compile_30m,
            )

        integration_truth = derive_integration_truth(raw)
        route_truth = derive_route_truth(route_state.routing_enabled(family_id), health_state)
        observed_client_truth = derive_observed_client_truth(raw)
        process_running = bool(raw.get("running", False))
        activity_state = _activity_state_from_metric_and_process(metric, process_running=process_running)
        truth_message = derive_truth_message(raw, integration_truth, route_truth, traffic_truth, metrics_24h)

        cards.append(
            {
                "family_id": family_id,
                "display_name": raw.get("display_name") or _DISPLAY_NAMES.get(family_id, family_id),
                "installed": bool(raw.get("installed")),
                "routing_enabled": route_state.routing_enabled(family_id),
                "detected": bool(raw.get("detected", True)),
                "active": activity_state["active"],
                "last_seen_at": activity_state["last_seen_at"],
                "health_state": health_state,
                "process_running": process_running,
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
                "drifted": bool(raw.get("detected", True)) and bool(raw.get("backup_available")) and not bool(raw.get("installed")),
                "drift_reason": "config_overwritten_after_attach" if (bool(raw.get("detected", True)) and bool(raw.get("backup_available")) and not bool(raw.get("installed"))) else None,
                # Scope identity fields
                "identity_scope": "family",
                "scope_note": _derive_scope_note(family_id),
            }
        )
    if using_legacy_fallback:
        _record_degraded_path(degraded_reason or "legacy_fallback_path")

    cards.sort(key=lambda item: (not item["active"], item["display_name"].lower()))
    return cards


# ============================================================================
# Diagnostics Surface Projections (Read Model Only)
# ============================================================================

def build_root_payload() -> Dict[str, Any]:
    _require_diag_config()
    result = {
        "service": "Memory Adapter v2.2",
        "version": "2.2.0",
        "support_schema_version": _diag_support_schema_version,
        "dedup_stats": _diag_get_dedup_cache_fn().get_stats(),
        "rate_limit": {
            "max_per_minute": _diag_config.rate_limit_per_minute,
            "current": _diag_rate_limiter.get_current_count(),
        },
    }
    if _diag_config.memory_backend_url:
        result["memory_backend_url"] = _diag_config.memory_backend_url
    return result


async def build_health_payload(mode: str = "local") -> Dict[str, Any]:
    _require_diag_config()
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
            "dedup_stats": _diag_get_dedup_cache_fn().get_stats(),
            "rate_limit": {
                "enabled": _diag_config.enable_rate_limit,
                "max_per_minute": _diag_config.rate_limit_per_minute,
                "current": _diag_rate_limiter.get_current_count(),
            },
        }

    backend_health = await _diag_get_backend_fn().health()
    route_state = _get_agent_routing_state()
    track_b_orchestrator = __import__("5_connectors.adapter.track_b_orchestrator", fromlist=["dummy"])
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
            "connect_seconds": _diag_config.memory_backend_connect_timeout_seconds,
            "health_seconds": _diag_config.memory_backend_health_timeout_seconds,
            "search_seconds": _diag_config.memory_backend_search_timeout_seconds,
            "read_seconds": _diag_config.memory_backend_read_timeout_seconds,
            "delete_seconds": _diag_config.memory_backend_delete_timeout_seconds,
            "snapshot_seconds": _diag_config.memory_backend_snapshot_timeout_seconds,
            "upload_seconds": _diag_config.memory_backend_upload_timeout_seconds,
            "commit_seconds": _diag_config.memory_backend_commit_timeout_seconds,
            "resolve_seconds": _diag_config.memory_backend_resolve_timeout_seconds,
            "retry_attempts": _diag_config.memory_backend_retry_attempts,
            "retry_backoff_seconds": _diag_config.memory_backend_retry_backoff_seconds,
            "slow_request_threshold_ms": _diag_config.slow_request_threshold_ms,
        },
        "path_policy": {
            "agent_segment_sanitized": True,
            "namespace_prepare_on_write": True,
            "missing_namespace_returns_empty": True,
        },
        "error_policy": {
            "schema_version": _diag_support_schema_version,
            "request_id_header": "X-Request-ID",
            "catalog_endpoint": "/support/error-codes",
            "structured_http_errors": True,
            "write_error_fields": ["reason", "error_code", "request_id", "support"],
        },
        "dedup_stats": _diag_get_dedup_cache_fn().get_stats(),
        "rate_limit": {
            "enabled": _diag_config.enable_rate_limit,
            "max_per_minute": _diag_config.rate_limit_per_minute,
            "current": _diag_rate_limiter.get_current_count(),
        },
    }


def build_runtime_fingerprint_payload() -> Dict[str, Any]:
    _require_diag_config()
    agent_metrics = _diag_agent_metrics()
    live_5m = agent_metrics.get_live_agents(window_minutes=5)
    live_24h = agent_metrics.get_live_agents(window_minutes=1440)
    key_modules = [
        "5_connectors.adapter.main",
        "5_connectors.adapter.metrics_service",
        "5_connectors.adapter.agent_identity",
        "5_connectors.adapter.agent_metrics",
    ]
    code_source: Dict[str, str] = {}
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
        "hostname": _diag_adapter_hostname,
        "started_at": _diag_adapter_started_at,
        "python": sys.version.split(" ")[0],
        "config": {
            "adapter_host": _diag_config.adapter_host,
            "adapter_port": _diag_config.adapter_port,
            "memory_backend_type": _diag_config.memory_backend.backend_type,
            "memory_backend_url": _diag_config.memory_backend.base_url,
            "agent_events_path": _diag_config.agent_events_path,
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


def build_support_error_codes_payload() -> Dict[str, Any]:
    return {
        "schema_version": _diag_support_schema_version,
        "count": len(_diag_support_error_catalog),
        "error_codes": [
            {
                "code": code,
                "category": meta["category"],
                "severity": meta["severity"],
                "retryable": meta["retryable"],
                "suggested_action": meta["suggested_action"],
            }
            for code, meta in sorted(_diag_support_error_catalog.items())
        ],
    }


def build_metrics_summary_payload(tenant: str = "all") -> Dict[str, Any]:
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    return metrics_service.compute_metrics_summary(tenant)


def build_metrics_summary_24h_payload(tenant: str = "all") -> Dict[str, Any]:
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    return metrics_service.compute_metrics_summary_24h(tenant)


def build_metrics_debug_sources_payload() -> Dict[str, Any]:
    _require_diag_config()
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    return {
        "summary_source": "5_connectors.adapter.metrics_service.compute_metrics_summary",
        "recent_requests_source": "5_connectors.adapter.metrics_service.get_recent_requests",
        "tenant_source": "5_connectors.adapter.metrics_service.list_tenants",
        "module_file": _inspect.getfile(metrics_service),
        "agent_events_path": _diag_config.agent_events_path,
    }


def build_recent_requests_payload(
    tenant: str = "default",
    limit: int = 20,
    include_internal: bool = False,
    value_qualified_only: bool = True,
    per_agent_limit: Optional[int] = None,
) -> Dict[str, Any]:
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    requests = metrics_service.get_recent_requests(
        tenant,
        limit,
        include_internal=include_internal,
        value_qualified_only=value_qualified_only,
        per_agent_limit=per_agent_limit,
    )
    return {"tenant": tenant, "requests": requests}


def build_metric_tenants_payload() -> Dict[str, Any]:
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    return {"tenants": metrics_service.list_tenants()}


def build_core_capabilities_payload(tenant: str = "all") -> Dict[str, Any]:
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    return metrics_service.compute_core_capabilities(tenant)


def build_core_capabilities_trend_payload(tenant: str = "all", days: int = 7) -> Dict[str, Any]:
    metrics_service = __import__("5_connectors.adapter.metrics_service", fromlist=["dummy"])
    return metrics_service.compute_core_capabilities_trend(tenant, days)


def build_context_diff_payload(request_id: str) -> Dict[str, Any]:
    if _diag_get_meter_fn is None:
        raise LookupError(f"Meter not found for request_id={request_id}")
    meter = _diag_get_meter_fn(request_id)
    if not meter:
        raise LookupError(f"Meter not found for request_id={request_id}")

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


def build_call_chain_payload(request_id: str) -> Dict[str, Any]:
    trace_store = __import__("5_connectors.adapter.infrastructure.trace_store", fromlist=["dummy"])
    chain_dict = trace_store.get_trace_dict(request_id)
    if not chain_dict:
        raise LookupError(f"Trace not found for request_id={request_id}")
    return chain_dict


def _derive_product_nodes(meter_dict: Dict[str, Any], chain_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    bypass = meter_dict.get("context_bypass", False)
    selected_count = len(meter_dict.get("candidate_memories", []))
    packed_count = meter_dict.get("packed_memory_count", 0)
    savings_ratio = meter_dict.get("savings_ratio", 0.0)
    task_type = meter_dict.get("task_type", "unknown")

    def _stage_duration(*names: str) -> float:
        if not chain_dict or "stages" not in chain_dict:
            return 0.0
        total = 0.0
        for stage in chain_dict["stages"]:
            if stage["name"] in names:
                total += stage.get("duration_ms", 0)
        return round(total, 3)

    def _status(success_cond: bool, warn_cond: bool = False) -> str:
        if success_cond:
            return "success"
        if warn_cond:
            return "warning"
        return "not_used"

    return [
        {"id": "app_request", "label": "App Request", "status": "success", "duration_ms": 0, "note": "request received"},
        {"id": "entry_18011", "label": "Entry 18011", "status": "success", "duration_ms": 0, "note": "adapter entry"},
        {
            "id": "route_decision",
            "label": "Route Decision",
            "status": _status(task_type != "unknown"),
            "duration_ms": _stage_duration("route_score"),
            "note": f"task_type={task_type}",
        },
        {
            "id": "memory_recall",
            "label": "Memory Recall",
            "status": _status(selected_count > 0, selected_count == 0 and task_type != "unknown"),
            "duration_ms": _stage_duration("filter", "dedup"),
            "note": f"{selected_count} candidates",
        },
        {
            "id": "context_pack",
            "label": "Context Pack",
            "status": _status(packed_count > 0, packed_count == 0 and selected_count > 0),
            "duration_ms": _stage_duration("select", "pack"),
            "note": f"{packed_count} packed",
        },
        {
            "id": "compile_or_bypass",
            "label": "Compile / Bypass",
            "status": "bypassed" if bypass else _status(savings_ratio > 0),
            "duration_ms": _stage_duration("meter", "policy_eval"),
            "note": "bypassed" if bypass else f"savings={savings_ratio:.2%}",
        },
        {
            "id": "upstream_forward",
            "label": "Upstream Forward",
            "status": "not_used",
            "duration_ms": 0,
            "note": "local-first v1: no upstream forwarding",
        },
        {
            "id": "response_recorded",
            "label": "Response Recorded",
            "status": "success",
            "duration_ms": _stage_duration("engine_total"),
            "note": "response sent",
        },
    ]


def _classify_meter_request(meter: Any) -> Dict[str, Any]:
    request_classifier = _get_request_classifier()
    description = request_classifier.describe_request_value(meter)

    return {
        "request_class": description["request_class"],
        "value_path": description["value_paths"],
        "value_paths": description["value_paths"],
        "qualification_reason": description["qualification_reason"],
        "user_visible_query": description["user_visible_query"],
        "diagnostic_label": description["diagnostic_label"],
        "packed_memory_count": getattr(meter, "packed_memory_count", 0) or 0,
        "local_cards_used": getattr(meter, "local_cards_used", 0) or 0,
        "remote_used_count": getattr(meter, "remote_used_count", 0) or 0,
    }


def _infer_request_status(meter_dict: Dict[str, Any], chain_dict: Dict[str, Any]) -> Dict[str, Any]:
    bypass = meter_dict.get("context_bypass", False)
    savings_ratio = meter_dict.get("savings_ratio", 0.0)
    packed_memory_count = meter_dict.get("packed_memory_count", 0)
    local_cards_used = meter_dict.get("local_cards_used", 0)
    remote_used_count = meter_dict.get("remote_used_count", 0)

    failure_stage = None
    failure_reason = None
    if chain_dict and "stages" in chain_dict:
        for stage in chain_dict["stages"]:
            metadata = stage.get("metadata", {})
            if metadata.get("error") or metadata.get("failed"):
                failure_stage = stage["name"]
                failure_reason = metadata.get("error_reason", "stage failed")
                break

    value_qualified = (packed_memory_count > 0) or (local_cards_used > 0) or (remote_used_count > 0)

    if failure_stage:
        request_status = "failed"
    elif bypass:
        request_status = "bypassed"
    elif not value_qualified:
        if savings_ratio > 0:
            request_status = "warning"
        else:
            request_status = "not_used"
    elif savings_ratio > 0.5:
        request_status = "success"
    elif savings_ratio > 0:
        request_status = "warning"
    else:
        request_status = "not_used"

    return {
        "request_status": request_status,
        "bypass": bypass,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "value_qualified": value_qualified,
    }


def _normalize_skill_suggestions(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "skill_id": item.get("skill_id", ""),
                "title": item.get("title", ""),
                "reason": item.get("reason", ""),
                "confidence": item.get("confidence", 0.0),
                "source": item.get("source", ""),
            }
        )
    return normalized


def _project_skill_suggestions(request_id: str) -> List[Dict[str, Any]]:
    """
    Read-only projection from persisted compile events.
    Never recomputes suggestions.
    """
    compile_store = _get_compile_store()
    try:
        events = compile_store.read_recent_compile_events(limit=5000)
    except Exception:
        return []

    for event in events:
        if event.get("request_id") == request_id:
            return _normalize_skill_suggestions(event.get("skill_suggestions", []))
    return []


def _project_skill_policy_metadata(request_id: str) -> Dict[str, str]:
    """
    Read-only projection for skill policy metadata from persisted compile events.
    Never recomputes recommendation policy.
    """
    compile_store = _get_compile_store()
    try:
        events = compile_store.read_recent_compile_events(limit=5000)
    except Exception:
        return {
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "fallback",
        }

    for event in events:
        if event.get("request_id") == request_id:
            def _val(key: str, default: str) -> str:
                value = event.get(key)
                if value is None or value == "":
                    return default
                return str(value)

            return {
                "skill_policy_name": _val("skill_policy_name", "local_fallback"),
                "skill_policy_version": _val("skill_policy_version", "static_catalog_v1"),
                "skill_policy_source": _val("skill_policy_source", "local_builtin"),
                "skill_policy_status": _val("skill_policy_status", "fallback"),
            }

    return {
        "skill_policy_name": "local_fallback",
        "skill_policy_version": "static_catalog_v1",
        "skill_policy_source": "local_builtin",
        "skill_policy_status": "fallback",
    }


def _project_task_type(request_id: str, meter_dict: Dict[str, Any]) -> str:
    """
    Prefer persisted compile event task_type; fallback to meter task_type;
    fallback to continuation.
    """
    compile_store = _get_compile_store()
    try:
        events = compile_store.read_recent_compile_events(limit=5000)
    except Exception:
        events = []

    for event in events:
        if event.get("request_id") == request_id:
            value = event.get("task_type")
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"implementation", "decision", "continuation"}:
                    return normalized
            break

    meter_task_type = meter_dict.get("task_type")
    if isinstance(meter_task_type, str):
        normalized = meter_task_type.strip().lower()
        if normalized in {"implementation", "decision", "continuation"}:
            return normalized
    return "continuation"


def _build_request_evidence_payload_from_meter(request_id: str, meter: Any) -> Dict[str, Any]:
    meter_dict = meter.to_dict()
    trace_store = __import__("5_connectors.adapter.infrastructure.trace_store", fromlist=["dummy"])
    chain_dict = trace_store.get_trace_dict(request_id)

    before_tokens = meter_dict.get("baseline_tokens_estimate", 0)
    after_tokens = meter_dict.get("actual_tokens_estimate", 0)
    saved_tokens = before_tokens - after_tokens
    savings_ratio = meter_dict.get("savings_ratio", 0.0)
    compression_source_tokens = int(meter_dict.get("compression_source_tokens") or before_tokens or 0)
    compression_output_tokens = int(meter_dict.get("compression_output_tokens") or after_tokens or 0)
    compression_saved_tokens = max(0, int(meter_dict.get("compression_saved_tokens") or (compression_source_tokens - compression_output_tokens)))
    compression_ratio = float(
        meter_dict.get("compression_ratio")
        if meter_dict.get("compression_ratio") is not None
        else ((compression_saved_tokens / compression_source_tokens) if compression_source_tokens > 0 else 0.0)
    )
    baseline_payload_tokens = int(meter_dict.get("baseline_payload_tokens") or 0)
    forwarded_payload_tokens = int(meter_dict.get("forwarded_payload_tokens") or 0)
    real_input_saved_tokens = int(meter_dict.get("real_input_saved_tokens") or 0)
    real_input_savings_ratio = float(
        meter_dict.get("real_input_savings_ratio")
        if meter_dict.get("real_input_savings_ratio") is not None
        else ((real_input_saved_tokens / baseline_payload_tokens) if baseline_payload_tokens > 0 else 0.0)
    )
    candidate_memories = meter_dict.get("candidate_memories", [])
    dropped_memories = meter_dict.get("dropped_memories", [])
    dropped_content_set = {m.get("content", "").strip() for m in dropped_memories}
    selected_memories = [
        m for m in candidate_memories if m.get("content", "").strip() not in dropped_content_set
    ]

    raw_agent_id = meter_dict.get("raw_agent_id") or meter_dict.get("agent", "unknown")
    agent_identity = _diag_agent_identity()
    agent_family = meter_dict.get("family_id") or agent_identity.resolve_canonical_agent_id(raw_agent_id)
    identity_spine = meter_dict.get("identity_spine", {}) if isinstance(meter_dict.get("identity_spine"), dict) else {}
    if not identity_spine:
        identity_spine = {
            "tenant_id": meter_dict.get("tenant_id") or meter_dict.get("tenant"),
            "family_id": meter_dict.get("family_id") or agent_family,
            "instance_id": meter_dict.get("instance_id"),
            "window_id": meter_dict.get("window_id"),
            "session_id": meter_dict.get("session_id"),
            "request_id": request_id,
            "raw_agent_id": raw_agent_id,
        }

    access_plan = meter_dict.get("access_plan", {}) if isinstance(meter_dict.get("access_plan"), dict) else {}
    if not access_plan:
        access_plan = {
            "identity": identity_spine,
            "read_domains": meter_dict.get("read_domains") or [],
            "primary_write_domain": meter_dict.get("primary_write_domain"),
            "secondary_write_domains": meter_dict.get("secondary_write_domains") or [],
            "sharing_policy_source": meter_dict.get("sharing_policy_source") or "legacy_meter_projection",
        }
    enforcement_trace = (
        meter_dict.get("enforcement_trace")
        if isinstance(meter_dict.get("enforcement_trace"), dict)
        else None
    )
    if enforcement_trace is None and isinstance(meter_dict.get("actual_enforcement"), dict):
        enforcement_trace = meter_dict.get("actual_enforcement")
    actual_enforcement: Dict[str, Any]
    if isinstance(enforcement_trace, dict):
        actual_enforcement = enforcement_trace
    else:
        actual_enforcement = {
            "status": "unavailable",
            "reason": "runtime_enforcement_trace_unavailable",
        }

    status = _infer_request_status(meter_dict, chain_dict)
    nodes = _derive_product_nodes(meter_dict, chain_dict)
    skill_suggestions = _project_skill_suggestions(request_id)
    policy_meta = _project_skill_policy_metadata(request_id)
    task_type = _project_task_type(request_id, meter_dict)

    if savings_ratio > 0 and not status["bypass"]:
        context_state = "optimized_visible"
    elif status["bypass"]:
        context_state = "bypass_or_not_applicable"
    else:
        context_state = "traffic_but_no_optimization"

    return {
        "request": {
            "request_id": request_id,
            "timestamp": meter_dict.get("timestamp", ""),
            "raw_agent_id": raw_agent_id,
            "agent_family": agent_family,
            "identity": identity_spine,
            "task_type": task_type,
            "query_summary": meter_dict.get("query", "")[:100],
        },
        "access_plan": access_plan,
        "enforcement_trace": enforcement_trace,
        "actual_enforcement": actual_enforcement,
        "request_class": _classify_meter_request(meter),
        "status": status,
        "context": {
            "before_tokens": before_tokens,
            "after_tokens": after_tokens,
            "saved_tokens": max(0, saved_tokens),
            "savings_ratio": savings_ratio,
            "compression": {
                "source_tokens": compression_source_tokens,
                "output_tokens": compression_output_tokens,
                "saved_tokens": compression_saved_tokens,
                "ratio": round(compression_ratio, 4),
            },
            "real_input": {
                "baseline_payload_tokens": baseline_payload_tokens,
                "forwarded_payload_tokens": forwarded_payload_tokens,
                "saved_tokens": max(0, real_input_saved_tokens),
                "savings_ratio": round(real_input_savings_ratio, 4),
                "omni_added_tokens": int(meter_dict.get("omni_added_tokens") or 0),
                "omni_removed_tokens": int(meter_dict.get("omni_removed_tokens") or 0),
                "metric_confidence": meter_dict.get("metric_confidence") or "legacy_compression_only",
                "quality_gate_status": meter_dict.get("quality_gate_status") or "unverified",
            },
            "selected_memory_count": len(selected_memories),
            "dropped_memory_count": len(dropped_memories),
            "selected_memories": selected_memories,
            "dropped_memories": dropped_memories,
            "context_state": context_state,
        },
        "chain": {
            "nodes": nodes,
            "trace_id": chain_dict.get("trace_id") if chain_dict else request_id,
        },
        "skill_suggestions": skill_suggestions,
        "skill_policy_name": policy_meta["skill_policy_name"],
        "skill_policy_version": policy_meta["skill_policy_version"],
        "skill_policy_source": policy_meta["skill_policy_source"],
        "skill_policy_status": policy_meta["skill_policy_status"],
    }


def build_request_evidence_payload(request_id: str) -> Dict[str, Any]:
    if _diag_get_meter_fn is None:
        raise LookupError(f"Meter not found for request_id={request_id}")
    meter = _diag_get_meter_fn(request_id)
    if not meter:
        raise LookupError(f"Meter not found for request_id={request_id}")
    return _build_request_evidence_payload_from_meter(request_id, meter)


def _request_evidence_shadow_core_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return {
        "identity": (payload.get("request") or {}).get("identity"),
        "access_plan": payload.get("access_plan"),
        "actual_enforcement": payload.get("actual_enforcement"),
        "tokens": {
            "before_tokens": context.get("before_tokens"),
            "after_tokens": context.get("after_tokens"),
            "saved_tokens": context.get("saved_tokens"),
            "savings_ratio": context.get("savings_ratio"),
        },
        "request_class": payload.get("request_class"),
        "status": payload.get("status"),
    }


def build_request_evidence_payload_resolved(request_id: str) -> Dict[str, Any]:
    if _diag_get_meter_fn is None:
        raise LookupError(f"Meter not found for request_id={request_id}")

    resolver = __import__(
        "5_connectors.adapter.application.request_evidence_meter_read_resolver",
        fromlist=["dummy"],
    )
    resolution = resolver.resolve_request_evidence_meter(
        request_id,
        legacy_get_meter_fn=_diag_get_meter_fn,
    )
    if resolution.selected_meter is None:
        raise LookupError(f"Meter not found for request_id={request_id}")

    selected_payload = _build_request_evidence_payload_from_meter(request_id, resolution.selected_meter)
    selected_payload["request_evidence_meter_read"] = {
        "mode": resolution.mode,
        "source": resolution.selected_source,
        "degraded": resolution.degraded,
        "degraded_reason": resolution.degraded_reason,
    }

    shadow_status = "degraded"
    mismatch_fields: List[str] = []

    if resolution.sqlite_meter is not None and resolution.legacy_meter is not None:
        sqlite_payload = _build_request_evidence_payload_from_meter(request_id, resolution.sqlite_meter)
        legacy_payload = _build_request_evidence_payload_from_meter(request_id, resolution.legacy_meter)
        sqlite_core = _request_evidence_shadow_core_fields(sqlite_payload)
        legacy_core = _request_evidence_shadow_core_fields(legacy_payload)
        for key in sqlite_core.keys():
            if sqlite_core.get(key) != legacy_core.get(key):
                mismatch_fields.append(key)
        shadow_status = "passed" if len(mismatch_fields) == 0 else "degraded"
    else:
        if resolution.sqlite_meter is None:
            mismatch_fields.append("sqlite_meter_missing")
        if resolution.legacy_meter is None:
            mismatch_fields.append("legacy_meter_missing")

    selected_payload["request_evidence_meter_shadow"] = {
        "status": shadow_status,
        "mode": resolution.mode,
        "read_source": resolution.selected_source,
        "mismatch_fields": mismatch_fields,
    }
    return selected_payload


def build_agents_live_payload(window_minutes: int = 30) -> Dict[str, Any]:
    agent_metrics = _diag_agent_metrics()
    live = agent_metrics.get_live_agents(window_minutes=window_minutes)
    return {
        "surface_role": "diagnostic",
        "kpi_source": "/metrics/summary",
        "diagnostic_scope": "agent session snapshots reconstructed from agent_events JSONL",
        "agents": live,
        "count": len(live),
    }


def build_agent_metrics_payload(agent_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    agent_metrics = _diag_agent_metrics()
    canonical_id = None
    if agent_id:
        canonical_id = _diag_agent_identity().resolve_canonical_agent_id(agent_id)
    metrics = agent_metrics.get_agent_metrics(agent_id=canonical_id, session_id=session_id)
    return {
        "surface_role": "diagnostic",
        "kpi_source": "/metrics/summary",
        "diagnostic_scope": "agent/session aggregates replayed from agent_events JSONL",
        "metrics": [m.dict() for m in metrics],
        "count": len(metrics),
    }
