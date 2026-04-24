"""
Meter 持久化层 - 负责 meter artifact 的内存缓存与磁盘读写
只属于 adapter 运行时，不属于 core 逻辑
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
import glob as _glob
import os
import tempfile
import time

# 兼容数字开头包：用 importlib 动态导入
import importlib
_4_core = importlib.import_module("4_core.logic.v2_compute")
TokenSavingsMeter = _4_core.TokenSavingsMeter


# In-memory storage for meter artifacts — backed by local persistence.
_meter_store: Dict[str, TokenSavingsMeter] = {}
_usage_aggregates: Dict[str, List[TokenSavingsMeter]] = {}
_persistence_loaded = False
_pending_persist: List[TokenSavingsMeter] = []
_last_persist_ts: float = 0.0
_persist_interval_seconds: float = float(os.getenv("OMNIMEMORA_METER_PERSIST_INTERVAL_SECONDS", "3"))


# ------------------------------------------------------------------
# Path resolution — derives data dir relative to THIS file, not relative
# to the logic layer.  This keeps path knowledge in adapter.
# ------------------------------------------------------------------

def _meter_index_path() -> str:
    """Absolute path to the shared meter index file."""
    return os.path.join(_meter_data_dir(), "meters_index.json")


def _tenant_aggregate_path(tenant: str) -> str:
    """Absolute path to a per-tenant aggregate file.

    Tenant segment is sanitised (alphanumeric / dash / underscore only) to
    prevent path-traversal attacks.
    """
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (tenant or "unknown"))
    return os.path.join(_meter_data_dir(), f"meters_{safe}.json")


def _meter_data_dir() -> str:
    """
    Resolve meter persistence directory.

    Priority:
    1) OMNIMEMORA_METER_DATA_DIR (explicit external data dir)
    2) adapter/data (legacy default for backward compatibility)
    """
    env_dir = os.getenv("OMNIMEMORA_METER_DATA_DIR", "").strip()
    if env_dir:
        return os.path.abspath(env_dir)
    adapter_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(adapter_dir, "data")


def _atomic_write_json(path: str, data: Any) -> None:
    """
    Atomically serialise *data* as JSON to *path* using the
    write-to-temp-then-atomic-replace pattern.
    """
    import json
    target = os.path.abspath(path)
    target_dir = os.path.dirname(target)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="v2meters_", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _safe_read_json(path: str) -> Any:
    """Return the deserialised JSON at *path*, or None if missing / malformed."""
    import json
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def persist_meter(meter: TokenSavingsMeter) -> None:
    """Persist a single meter to the shared index atomically."""
    idx_path = _meter_index_path()
    index: Dict[str, Any] = _safe_read_json(idx_path) or {}
    index[meter.request_id] = meter.to_dict()
    _atomic_write_json(idx_path, index)


def persist_tenant_aggregate(tenant: str, meter: TokenSavingsMeter) -> None:
    """Append a meter to the per-tenant aggregate list atomically."""
    agg_path = _tenant_aggregate_path(tenant)
    agg_list: List[Dict[str, Any]] = _safe_read_json(agg_path) or []
    agg_list.append(meter.to_dict())
    _atomic_write_json(agg_path, agg_list)


def _flush_pending_persistence() -> None:
    """
    Flush pending meter updates in one batch.
    This avoids per-request full-file read+rewrite amplification.
    """
    global _pending_persist
    if not _pending_persist:
        return

    pending = _pending_persist
    _pending_persist = []

    idx_path = _meter_index_path()
    index: Dict[str, Any] = _safe_read_json(idx_path) or {}
    tenant_buffers: Dict[str, List[Dict[str, Any]]] = {}

    touched_tenants: set[str] = set()
    for meter in pending:
        meter_dict = meter.to_dict()
        index[meter.request_id] = meter_dict
        touched_tenants.add(meter.tenant)

    for tenant in touched_tenants:
        agg_path = _tenant_aggregate_path(tenant)
        tenant_buffers[tenant] = _safe_read_json(agg_path) or []

    for meter in pending:
        tenant_buffers[meter.tenant].append(meter.to_dict())

    _atomic_write_json(idx_path, index)
    for tenant, rows in tenant_buffers.items():
        _atomic_write_json(_tenant_aggregate_path(tenant), rows)


def load_meter(request_id: str) -> Optional[Dict[str, Any]]:
    """Load a single meter dict from the shared index (lazy disk fallback)."""
    index: Dict[str, Any] = _safe_read_json(_meter_index_path()) or {}
    return index.get(request_id)


def load_persisted_state() -> tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Load all persisted state from disk on process startup.

    Returns:
        (meters_index: dict request_id→dict,
         tenant_aggregates: dict tenant_slug→list[dict])
    """
    index: Dict[str, Dict[str, Any]] = _safe_read_json(_meter_index_path()) or {}
    tenant_aggregates: Dict[str, List[Dict[str, Any]]] = {}

    data_dir = os.path.dirname(_meter_index_path())
    for path in _glob.glob(os.path.join(data_dir, "meters_*.json")):
        basename = os.path.basename(path)
        if basename == "meters_index.json":
            continue
        slug = basename[len("meters_"):-len(".json")]
        loaded: List[Dict[str, Any]] = _safe_read_json(path) or []
        tenant_aggregates[slug] = loaded

    return index, tenant_aggregates


def _ensure_persistence_loaded() -> None:
    """Load persisted state from disk into in-memory stores (idempotent)."""
    global _persistence_loaded
    if _persistence_loaded:
        return
    _persistence_loaded = True

    try:
        persisted_meters, persisted_aggregates = load_persisted_state()
        for rid, meter_dict in persisted_meters.items():
            try:
                _meter_store[rid] = TokenSavingsMeter(**meter_dict)
            except Exception:
                pass  # skip malformed records

        for tenant_id, agg_list in persisted_aggregates.items():
            if tenant_id not in _usage_aggregates:
                _usage_aggregates[tenant_id] = []
            for meter_dict in agg_list:
                try:
                    _usage_aggregates[tenant_id].append(TokenSavingsMeter(**meter_dict))
                except Exception:
                    pass  # skip malformed records
    except Exception:
        pass


def store_meter(meter: Union[TokenSavingsMeter, Dict[str, Any]]) -> None:
    """
    Store meter artifact in memory and persist to disk atomically.
    Accepts either a TokenSavingsMeter dataclass or a dict (e.g. from engine result).
    """
    _ensure_persistence_loaded()

    # Normalize dict to TokenSavingsMeter if needed
    if isinstance(meter, dict):
        try:
            meter = TokenSavingsMeter(**meter)
        except Exception:
            return  # skip malformed records

    request_id = meter.request_id
    tenant = meter.tenant
    _meter_store[request_id] = meter
    if tenant not in _usage_aggregates:
        _usage_aggregates[tenant] = []
    _usage_aggregates[tenant].append(meter)

    global _last_persist_ts
    try:
        _pending_persist.append(meter)
        now = time.time()
        if _persist_interval_seconds <= 0 or (now - _last_persist_ts) >= _persist_interval_seconds:
            _flush_pending_persistence()
            _last_persist_ts = now
    except Exception:
        pass  # best-effort


def get_meter(request_id: str) -> Optional[TokenSavingsMeter]:
    """Get meter artifact by request ID. Checks in-memory store first, then disk."""
    _ensure_persistence_loaded()
    if request_id in _meter_store:
        return _meter_store[request_id]

    try:
        meter_dict = load_meter(request_id)
        if meter_dict:
            meter = TokenSavingsMeter(**meter_dict)
            _meter_store[request_id] = meter
            return meter
    except Exception:
        pass
    return None


def _token_savings_by_period(meters: List[TokenSavingsMeter]) -> Dict[str, int]:
    """Compute saved_tokens totals for today/week/month windows."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)  # last 7 days including today
    month_start = today_start - timedelta(days=29)  # last 30 days

    today_total = 0
    week_total = 0
    month_total = 0

    for m in meters:
        try:
            m_time = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        saved = m.saved_tokens_estimate
        if m_time >= today_start:
            today_total += saved
        if m_time >= week_start:
            week_total += saved
        if m_time >= month_start:
            month_total += saved

    return {
        "today": today_total,
        "week": week_total,
        "month": month_total,
    }


def get_tenant_usage(
    tenant: str,
    agent: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get aggregated usage for a tenant with period_breakdown and by_workspace."""
    _ensure_persistence_loaded()
    if tenant == "all":
        meters = [m for tenant_meters in _usage_aggregates.values() for m in tenant_meters]
    else:
        meters = _usage_aggregates.get(tenant, [])

    if start_time:
        meters = [m for m in meters if datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")) >= start_time]
    if end_time:
        meters = [m for m in meters if datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")) <= end_time]
    if agent:
        meters = [m for m in meters if m.agent == agent]

    if not meters:
        return {
            "tenant": tenant,
            "request_count": 0,
            "total_requests": 0,
            "saved_tokens_estimate_total": 0,
            "actual_tokens_estimate_total": 0,
            "baseline_tokens_total": 0,
            "actual_tokens_total": 0,
            "saved_tokens_total": 0,
            "average_savings_ratio": 0.0,
            "last_request_at": None,
            "current_period_usage": 0,
            "by_agent": [],
            "by_workspace": [],
            "period_breakdown": {"today": 0, "week": 0, "month": 0},
            "recent_requests": [],
        }

    sorted_meters = sorted(meters, key=lambda m: m.timestamp, reverse=True)

    total_requests = len(meters)
    baseline_total = sum(m.baseline_tokens_estimate for m in meters)
    actual_total = sum(m.actual_tokens_estimate for m in meters)
    saved_total = sum(m.saved_tokens_estimate for m in meters)
    avg_ratio = saved_total / baseline_total if baseline_total > 0 else 0.0
    last_request_at = sorted_meters[0].timestamp if sorted_meters else None

    # By agent
    agent_map: Dict[str, List[TokenSavingsMeter]] = {}
    for m in meters:
        if m.agent not in agent_map:
            agent_map[m.agent] = []
        agent_map[m.agent].append(m)

    by_agent = []
    for agent_id, agent_meters in agent_map.items():
        agent_saved = sum(m.saved_tokens_estimate for m in agent_meters)
        agent_baseline = sum(m.baseline_tokens_estimate for m in agent_meters)
        agent_ratio = agent_saved / agent_baseline if agent_baseline > 0 else 0.0
        agent_last = max((m.timestamp for m in agent_meters), default=None)
        by_agent.append({
            "agent": agent_id,
            "requests": len(agent_meters),
            "saved_tokens": agent_saved,
            "savings_ratio": round(agent_ratio, 3),
            "last_request_at": agent_last,
        })

    # By workspace — use user field as workspace_id proxy (meter_store records user as workspace scope)
    # Note: workspace_id field in meter is not populated by current adapter, so aggregate by user as proxy
    workspace_map: Dict[str, List[TokenSavingsMeter]] = {}
    for m in meters:
        # Use tenant as workspace proxy when workspace_id is not explicitly set
        ws_key = getattr(m, 'workspace_id', None) or m.tenant or "unknown"
        if ws_key not in workspace_map:
            workspace_map[ws_key] = []
        workspace_map[ws_key].append(m)

    by_workspace = []
    for ws_id, ws_meters in workspace_map.items():
        ws_saved = sum(m.saved_tokens_estimate for m in ws_meters)
        ws_baseline = sum(m.baseline_tokens_estimate for m in ws_meters)
        ws_ratio = ws_saved / ws_baseline if ws_baseline > 0 else 0.0
        by_workspace.append({
            "workspace_id": ws_id,
            "requests": len(ws_meters),
            "saved_tokens": ws_saved,
            "savings_ratio": round(ws_ratio, 3),
        })

    # Period breakdown
    period_breakdown = _token_savings_by_period(meters)

    recent_requests = []
    for m in sorted_meters[:10]:
        recent_requests.append({
            "request_id": m.request_id,
            "tenant": m.tenant,
            "user": m.user,
            "agent": m.agent,
            "timestamp": m.timestamp,
            "query": getattr(m, "query", ""),
            "baseline_tokens": m.baseline_tokens_estimate,
            "actual_tokens": m.actual_tokens_estimate,
            "saved_tokens": m.saved_tokens_estimate,
            "savings_ratio": m.savings_ratio,
            "baseline_chars": m.baseline_chars,
            "actual_chars": m.actual_chars,
            "saved_chars": m.saved_chars,
            "local_cards_used": m.local_cards_used,
            "remote_candidates_considered": m.remote_candidates_considered,
            "remote_candidates_skipped": m.remote_candidates_skipped,
            "skipped_remote_reason": m.skipped_remote_reason,
            "packing_enabled": m.packing_enabled,
            "dedup_applied": m.dedup_applied,
        })

    return {
        "tenant": tenant,
        "request_count": total_requests,
        "total_requests": total_requests,
        "saved_tokens_estimate_total": saved_total,
        "actual_tokens_estimate_total": actual_total,
        "baseline_tokens_total": baseline_total,
        "actual_tokens_total": actual_total,
        "saved_tokens_total": saved_total,
        "average_savings_ratio": round(avg_ratio, 3),
        "last_request_at": last_request_at,
        "current_period_usage": actual_total,
        "by_agent": by_agent,
        "by_workspace": by_workspace,
        "period_breakdown": period_breakdown,
        "recent_requests": recent_requests,
    }


def get_trend_data(tenant: str, days: int = 7) -> Dict[str, Any]:
    """Get trend data for the last N days. Supports tenant=all."""
    from datetime import timedelta

    _ensure_persistence_loaded()
    if tenant == "all":
        meters = [m for tenant_meters in _usage_aggregates.values() for m in tenant_meters]
    else:
        meters = _usage_aggregates.get(tenant, [])
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)

    date_map: Dict[str, List[TokenSavingsMeter]] = {}
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_key = date.isoformat()
        date_map[date_key] = []

    for m in meters:
        m_date = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).date()
        date_key = m_date.isoformat()
        if date_key in date_map:
            date_map[date_key].append(m)

    trend = []
    for date_key in sorted(date_map.keys()):
        day_meters = date_map[date_key]
        requests = len(day_meters)
        saved_tokens = sum(m.saved_tokens_estimate for m in day_meters)
        baseline_total = sum(m.baseline_tokens_estimate for m in day_meters)
        savings_ratio = saved_tokens / baseline_total if baseline_total > 0 else 0.0

        trend.append({
            "date": date_key,
            "requests": requests,
            "saved_tokens": saved_tokens,
            "savings_ratio": round(savings_ratio, 3),
        })

    return {
        "tenant": tenant,
        "days": days,
        "trend": trend,
    }


def get_tenant_current_usage(tenant: str) -> int:
    """Get current period usage (total actual_tokens) for a tenant. Convenience for quota checks."""
    _ensure_persistence_loaded()
    meters = _usage_aggregates.get(tenant, [])
    return sum(m.actual_tokens_estimate for m in meters)
