"""SQLite audit ledger for Token Intelligence Lite."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .models import AuditEvent, NormalizedCost, NormalizedUsage
from .receipts import stable_hash

SCHEMA_VERSION = "token-intelligence-ledger-v1"
_SENSITIVE_METADATA_KEY_PARTS = {
    "content",
    "message",
    "messages",
    "prompt",
    "request",
    "response",
    "tool_output",
    "tool_result",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_sqlite_path() -> Path:
    return Path.home() / ".omnimemora" / "adapter" / "token_intelligence" / "audit.sqlite3"


def resolve_sqlite_path(path: Optional[str] = None) -> Path:
    explicit = (path or os.getenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", "")).strip()
    return Path(explicit).expanduser() if explicit else _default_sqlite_path()


def _connect(path: Optional[str] = None) -> sqlite3.Connection:
    sqlite_path = resolve_sqlite_path(path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(sqlite_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_schema(path: Optional[str] = None) -> None:
    with _connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                response_hash TEXT NOT NULL,
                upstream_base_url_hash TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_requested TEXT NOT NULL,
                model_reported TEXT NOT NULL,
                usage_json TEXT NOT NULL,
                cost_json TEXT NOT NULL,
                latency_ms INTEGER,
                status_code INTEGER,
                metadata_json TEXT NOT NULL,
                blocks_json TEXT NOT NULL DEFAULT '[]',
                opportunities_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(conn, "audit_events", "blocks_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "audit_events", "opportunities_json", "TEXT NOT NULL DEFAULT '[]'")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_request_id ON audit_events(request_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_model ON audit_events(model_requested);")
        _set_meta(conn, "schema_version", SCHEMA_VERSION)
        _set_meta(conn, "content_mode", "metadata_only")


def build_audit_event(
    *,
    request_id: str,
    request_payload: Any,
    response_payload: Any,
    upstream_base_url: str,
    provider: str,
    model_requested: str,
    usage: NormalizedUsage,
    cost: Optional[NormalizedCost] = None,
    model_reported: Optional[str] = None,
    latency_ms: Optional[int] = None,
    status_code: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    blocks: Optional[list[dict[str, Any]]] = None,
    opportunities: Optional[list[dict[str, Any]]] = None,
) -> AuditEvent:
    created_at = _utc_now_iso()
    return AuditEvent(
        audit_id=f"omni_audit_{uuid4().hex}",
        request_id=str(request_id or uuid4().hex),
        request_hash=stable_hash(request_payload),
        response_hash=stable_hash(response_payload),
        upstream_base_url_hash=stable_hash(str(upstream_base_url or "")),
        provider=str(provider or "unknown"),
        model_requested=str(model_requested or ""),
        model_reported=str(model_reported or model_requested or ""),
        usage=usage,
        cost=cost or NormalizedCost(),
        latency_ms=_safe_int(latency_ms),
        status_code=_safe_int(status_code),
        created_at=created_at,
        metadata=_sanitize_metadata(metadata or {}),
        blocks=_sanitize_blocks(blocks or []),
        opportunities=_sanitize_opportunities(opportunities or []),
    )


def record_audit_event(event: AuditEvent, *, path: Optional[str] = None) -> None:
    init_schema(path)
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO audit_events (
                audit_id,
                request_id,
                request_hash,
                response_hash,
                upstream_base_url_hash,
                provider,
                model_requested,
                model_reported,
                usage_json,
                cost_json,
                latency_ms,
                status_code,
                metadata_json,
                blocks_json,
                opportunities_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.audit_id,
                event.request_id,
                event.request_hash,
                event.response_hash,
                event.upstream_base_url_hash,
                event.provider,
                event.model_requested,
                event.model_reported,
                _json(event.usage.to_dict()),
                _json(event.cost.to_dict()),
                event.latency_ms,
                event.status_code,
                _json(event.metadata),
                _json_list(event.blocks),
                _json_list(event.opportunities),
                event.created_at,
            ),
        )


def get_audit_event(audit_id: str, *, path: Optional[str] = None) -> Optional[AuditEvent]:
    init_schema(path)
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM audit_events WHERE audit_id = ? LIMIT 1",
            (audit_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_event(row)


def delete_audit_event(audit_id: str, *, path: Optional[str] = None) -> bool:
    init_schema(path)
    with _connect(path) as conn:
        cursor = conn.execute("DELETE FROM audit_events WHERE audit_id = ?", (audit_id,))
    return int(cursor.rowcount or 0) > 0


def purge_audit_events_older_than(days: int, *, path: Optional[str] = None) -> int:
    bounded_days = max(1, min(int(days), 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=bounded_days)
    init_schema(path)
    with _connect(path) as conn:
        cursor = conn.execute("DELETE FROM audit_events WHERE created_at < ?", (cutoff.isoformat(),))
    return int(cursor.rowcount or 0)


def count_events(*, path: Optional[str] = None) -> int:
    init_schema(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM audit_events").fetchone()
    return int(row["c"] if row else 0)


def summarize_recent_events(*, path: Optional[str] = None, limit: int = 1000) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 1000))
    init_schema(path)
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT model_requested, usage_json, cost_json, status_code, latency_ms, blocks_json, opportunities_json, created_at
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()

    source_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    model_counts: dict[str, dict[str, Any]] = {}
    usage_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
    }
    total_cost_usd = 0.0
    cost_present = False
    latency_values: list[int] = []
    block_totals: dict[str, dict[str, Any]] = {}
    opportunity_totals: dict[str, dict[str, Any]] = {}

    for row in rows:
        usage = _loads(row["usage_json"])
        cost = _loads(row["cost_json"])
        model = str(row["model_requested"] or "")
        status = str(row["status_code"] if row["status_code"] is not None else "unknown")
        source = str(usage.get("source") or "unknown")
        confidence = str(usage.get("confidence") or "unknown")
        total_tokens = _safe_int(usage.get("total_tokens")) or 0

        source_counts[source] = source_counts.get(source, 0) + 1
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

        for key in usage_totals:
            usage_totals[key] += _safe_int(usage.get(key)) or 0

        cost_value = _safe_float(cost.get("total_cost_usd"))
        if cost_value is not None:
            total_cost_usd += cost_value
            cost_present = True

        if row["latency_ms"] is not None:
            latency_values.append(int(row["latency_ms"]))

        for block in _loads_list(row["blocks_json"]):
            block_type = str(_as_dict(block).get("block_type") or "unknown")
            token_estimate = _safe_int(_as_dict(block).get("token_estimate")) or 0
            block_entry = block_totals.setdefault(block_type, {"block_type": block_type, "token_estimate": 0})
            block_entry["token_estimate"] += token_estimate

        for opportunity in _loads_list(row["opportunities_json"]):
            category = str(_as_dict(opportunity).get("category") or "unknown")
            saving = _safe_int(_as_dict(opportunity).get("potential_saving_tokens")) or 0
            opp_entry = opportunity_totals.setdefault(
                category,
                {"category": category, "potential_saving_tokens": 0, "item_count": 0},
            )
            opp_entry["potential_saving_tokens"] += saving
            opp_entry["item_count"] += _safe_int(_as_dict(opportunity).get("item_count")) or 0

        model_entry = model_counts.setdefault(model, {"model": model, "request_count": 0, "total_tokens": 0})
        model_entry["request_count"] += 1
        model_entry["total_tokens"] += total_tokens

    top_models = sorted(
        model_counts.values(),
        key=lambda item: (-int(item["total_tokens"]), -int(item["request_count"]), str(item["model"])),
    )[:10]
    top_blocks = sorted(block_totals.values(), key=lambda item: (-int(item["token_estimate"]), str(item["block_type"])))
    top_opportunities = sorted(
        opportunity_totals.values(),
        key=lambda item: (-int(item["potential_saving_tokens"]), str(item["category"])),
    )
    return {
        "schema_version": "token-intelligence-summary-v1",
        "window": {"limit": bounded_limit, "bounded": True},
        "event_count": len(rows),
        "usage": usage_totals,
        "usage_sources": source_counts,
        "confidence": confidence_counts,
        "status_codes": status_counts,
        "top_models": top_models,
        "top_blocks": top_blocks,
        "top_opportunities": top_opportunities,
        "cost": {"total_cost_usd": round(total_cost_usd, 8)} if cost_present else {},
        "latency_ms": _latency_summary(latency_values),
    }


def _row_to_event(row: sqlite3.Row) -> AuditEvent:
    usage_payload = _loads(row["usage_json"])
    cost_payload = _loads(row["cost_json"])
    return AuditEvent(
        audit_id=str(row["audit_id"]),
        request_id=str(row["request_id"]),
        request_hash=str(row["request_hash"]),
        response_hash=str(row["response_hash"]),
        upstream_base_url_hash=str(row["upstream_base_url_hash"]),
        provider=str(row["provider"]),
        model_requested=str(row["model_requested"]),
        model_reported=str(row["model_reported"]),
        usage=NormalizedUsage(**usage_payload),
        cost=NormalizedCost(**cost_payload),
        latency_ms=row["latency_ms"],
        status_code=row["status_code"],
        created_at=str(row["created_at"]),
        metadata=_loads(row["metadata_json"]),
        blocks=_loads_list(_row_value(row, "blocks_json", "[]")),
        opportunities=_loads_list(_row_value(row, "opportunities_json", "[]")),
    )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(str(row["name"]) == column for row in rows):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO audit_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, _utc_now_iso()),
    )


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_list(payload: list[dict[str, Any]]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads(payload: str) -> dict[str, Any]:
    try:
        parsed = json.loads(payload or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _loads_list(payload: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(payload or "[]")
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [_as_dict(item) for item in parsed if isinstance(item, dict)]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _row_value(row: sqlite3.Row, key: str, default: Any) -> Any:
    return row[key] if key in row.keys() else default


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _latency_summary(values: list[int]) -> dict[str, int]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "max": ordered[-1],
        "avg": int(sum(ordered) / len(ordered)),
    }


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for raw_key, raw_value in metadata.items():
        key = str(raw_key)
        lowered = key.lower()
        if any(part in lowered for part in _SENSITIVE_METADATA_KEY_PARTS):
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            sanitized[key] = _cap_metadata_value(raw_value)
    return sanitized


def _sanitize_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for block in blocks:
        block_type = str(block.get("block_type") or "")
        if not block_type:
            continue
        sanitized.append(
            {
                "block_type": block_type,
                "token_estimate": max(0, _safe_int(block.get("token_estimate")) or 0),
                "item_count": max(0, _safe_int(block.get("item_count")) or 0),
                "source": str(block.get("source") or "local_estimated"),
                "confidence": str(block.get("confidence") or "compatible_estimate"),
            }
        )
    return sanitized


def _sanitize_opportunities(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for opportunity in opportunities:
        category = str(opportunity.get("category") or "")
        detector_id = str(opportunity.get("detector_id") or "")
        if not category or not detector_id:
            continue
        sanitized.append(
            {
                "detector_id": detector_id,
                "category": category,
                "reason_code": str(opportunity.get("reason_code") or ""),
                "token_estimate": max(0, _safe_int(opportunity.get("token_estimate")) or 0),
                "potential_saving_tokens": max(0, _safe_int(opportunity.get("potential_saving_tokens")) or 0),
                "item_count": max(0, _safe_int(opportunity.get("item_count")) or 0),
                "severity": str(opportunity.get("severity") or "low"),
                "source": str(opportunity.get("source") or "local_estimated"),
                "confidence": str(opportunity.get("confidence") or "compatible_estimate"),
            }
        )
    return sanitized


def _cap_metadata_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return value if len(value) <= 200 else value[:200] + "..."
