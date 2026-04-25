"""SQLite mirror store for meter persistence (observe-only dual-write mode)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

METER_STORE_V2_SCHEMA_VERSION = "meter-store-v2-schema-1"
METER_STORE_V2_MODE = "dual_write_observe_only"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_sqlite_path() -> Path:
    return Path.home() / ".omnimemora" / "adapter" / "meter_store_v2" / "meter_store.sqlite3"


def resolve_sqlite_path(path: Optional[str] = None) -> Path:
    explicit = (path or os.getenv("OMNIMEMORA_METER_STORE_V2_FILE", "")).strip()
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
            CREATE TABLE IF NOT EXISTS meter_records (
                request_id TEXT PRIMARY KEY,
                tenant TEXT,
                agent TEXT,
                family_id TEXT,
                timestamp TEXT,
                task_type TEXT,
                context_state TEXT,
                baseline_tokens_estimate INTEGER,
                actual_tokens_estimate INTEGER,
                saved_tokens_estimate INTEGER,
                savings_ratio REAL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meter_store_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meter_write_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_records_request_id ON meter_records(request_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_records_tenant_ts ON meter_records(tenant, timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_records_family_ts ON meter_records(family_id, timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_records_agent_ts ON meter_records(agent, timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_records_timestamp ON meter_records(timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_write_errors_created_at ON meter_write_errors(created_at);")
        set_meta("schema_version", METER_STORE_V2_SCHEMA_VERSION, path=path)
        set_meta("mode", METER_STORE_V2_MODE, path=path)


def set_meta(key: str, value: str, *, path: Optional[str] = None) -> None:
    now_iso = _utc_now_iso()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO meter_store_meta (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now_iso),
        )


def get_meta(*, path: Optional[str] = None) -> dict[str, str]:
    init_schema(path)
    with _connect(path) as conn:
        rows = conn.execute("SELECT key, value FROM meter_store_meta").fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def _normalized_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _int_field(payload: dict[str, Any], key: str) -> Optional[int]:
    value = payload.get(key)
    if value is None:
        return None
    return int(value)


def _float_field(payload: dict[str, Any], key: str) -> Optional[float]:
    value = payload.get(key)
    if value is None:
        return None
    return float(value)


def upsert_meter(payload: dict[str, Any], *, path: Optional[str] = None) -> None:
    init_schema(path)
    request_id = str(payload.get("request_id") or "").strip()
    if not request_id:
        raise ValueError("request_id is required")
    if "timestamp" in payload and payload.get("timestamp") is not None and not isinstance(payload.get("timestamp"), str):
        raise ValueError("timestamp must be string when present")

    now_iso = _utc_now_iso()
    payload_json = _normalized_payload_json(payload)
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO meter_records (
                request_id,
                tenant,
                agent,
                family_id,
                timestamp,
                task_type,
                context_state,
                baseline_tokens_estimate,
                actual_tokens_estimate,
                saved_tokens_estimate,
                savings_ratio,
                payload_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                tenant = excluded.tenant,
                agent = excluded.agent,
                family_id = excluded.family_id,
                timestamp = excluded.timestamp,
                task_type = excluded.task_type,
                context_state = excluded.context_state,
                baseline_tokens_estimate = excluded.baseline_tokens_estimate,
                actual_tokens_estimate = excluded.actual_tokens_estimate,
                saved_tokens_estimate = excluded.saved_tokens_estimate,
                savings_ratio = excluded.savings_ratio,
                payload_json = excluded.payload_json
            """,
            (
                request_id,
                payload.get("tenant"),
                payload.get("agent"),
                payload.get("family_id"),
                payload.get("timestamp"),
                payload.get("task_type"),
                payload.get("context_state"),
                _int_field(payload, "baseline_tokens_estimate"),
                _int_field(payload, "actual_tokens_estimate"),
                _int_field(payload, "saved_tokens_estimate"),
                _float_field(payload, "savings_ratio"),
                payload_json,
                now_iso,
            ),
        )


def record_write_error(
    *,
    request_id: Optional[str],
    error_type: str,
    error_message: str,
    payload: Optional[dict[str, Any]] = None,
    path: Optional[str] = None,
) -> None:
    init_schema(path)
    payload_json = None if payload is None else _normalized_payload_json(payload)
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO meter_write_errors (
                request_id,
                error_type,
                error_message,
                payload_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, error_type, error_message, payload_json, _utc_now_iso()),
        )


def get_meter(request_id: str, *, path: Optional[str] = None) -> Optional[dict[str, Any]]:
    init_schema(path)
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM meter_records WHERE request_id = ? LIMIT 1",
            (request_id,),
        ).fetchone()
    if row is None:
        return None
    payload_text = row["payload_json"]
    try:
        payload = json.loads(payload_text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def query_recent(
    *,
    limit: int = 50,
    tenant: Optional[str] = None,
    family_id: Optional[str] = None,
    agent: Optional[str] = None,
    since_iso: Optional[str] = None,
    path: Optional[str] = None,
) -> list[dict[str, Any]]:
    init_schema(path)
    clauses: list[str] = []
    params: list[Any] = []
    if tenant:
        clauses.append("tenant = ?")
        params.append(tenant)
    if family_id:
        clauses.append("family_id = ?")
        params.append(family_id)
    if agent:
        clauses.append("agent = ?")
        params.append(agent)
    if since_iso:
        clauses.append("timestamp >= ?")
        params.append(since_iso)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    bounded_limit = max(1, min(int(limit), 100000))
    params.append(bounded_limit)
    sql = (
        "SELECT payload_json FROM meter_records "
        f"{where_sql} "
        "ORDER BY timestamp DESC, created_at DESC "
        "LIMIT ?"
    )
    with _connect(path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    output: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            continue
        if isinstance(payload, dict):
            output.append(payload)
    return output


def query_window(
    *,
    since_iso: str,
    limit: int = 1000,
    tenant: Optional[str] = None,
    path: Optional[str] = None,
) -> list[dict[str, Any]]:
    return query_recent(
        limit=limit,
        tenant=tenant,
        since_iso=since_iso,
        path=path,
    )


def list_tenants(*, path: Optional[str] = None, limit: int = 1000) -> list[str]:
    init_schema(path)
    bounded_limit = max(1, min(int(limit), 100000))
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT tenant
            FROM meter_records
            WHERE tenant IS NOT NULL AND tenant != ''
            ORDER BY tenant ASC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    tenants: list[str] = []
    for row in rows:
        tenant = row["tenant"]
        if isinstance(tenant, str) and tenant.strip():
            tenants.append(tenant.strip())
    return tenants


def count_records(*, path: Optional[str] = None) -> int:
    init_schema(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM meter_records").fetchone()
    return int(row["c"] if row else 0)


def count_write_errors(*, path: Optional[str] = None) -> int:
    init_schema(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM meter_write_errors").fetchone()
    return int(row["c"] if row else 0)


def latest_write_error(*, path: Optional[str] = None) -> Optional[dict[str, Any]]:
    init_schema(path)
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT id, request_id, error_type, error_message, payload_json, created_at
            FROM meter_write_errors
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    payload = None
    if row["payload_json"]:
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = None
    return {
        "id": int(row["id"]),
        "request_id": row["request_id"],
        "error_type": row["error_type"],
        "error_message": row["error_message"],
        "payload": payload,
        "created_at": row["created_at"],
    }
