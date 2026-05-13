"""Opt-in MCP JSON-RPC companion for Token Intelligence Lite."""

from __future__ import annotations

import json
from typing import Any, Optional

from .ledger import list_top_requests, summarize_recent_events
from .reports import build_potential_savings_report


def mcp_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "transport": "http-jsonrpc",
        "message_endpoint": "/mcp",
        "mode": "candidate_local_companion",
    }


def dispatch_mcp_jsonrpc(body: Any, *, audit_db_path: Optional[str] = None) -> Optional[dict[str, Any]]:
    if not isinstance(body, dict):
        return _mcp_error(None, -32600, "invalid request")
    method = str(body.get("method") or "")
    msg_id = body.get("id")
    if method == "initialize":
        return _mcp_result(msg_id, _initialize_payload())
    if method in {"notifications/initialized"}:
        return None
    if method == "ping":
        return _mcp_result(msg_id, {})
    if method == "tools/list":
        return _mcp_result(msg_id, _tools_payload())
    if method == "tools/call":
        params = body.get("params")
        if not isinstance(params, dict):
            return _mcp_error(msg_id, -32602, "invalid params")
        return _mcp_result(msg_id, {"content": _call_tool(params, audit_db_path=audit_db_path)})
    return _mcp_error(msg_id, -32601, f"method not found: {method}")


def _initialize_payload() -> dict[str, Any]:
    return {
        "protocolVersion": "2025-03-26",
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": "omnimemora-token-intelligence-lite",
            "version": "0.1.0-dev",
        },
    }


def _tools_payload() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "token_intelligence.summary",
                "description": "Read bounded local Token Intelligence audit summary. This is not a request capture path.",
                "inputSchema": _limit_schema(),
            },
            {
                "name": "token_intelligence.potential_savings",
                "description": "Read bounded local potential token-savings report. This does not run automatic optimization.",
                "inputSchema": _limit_schema(),
            },
            {
                "name": "token_intelligence.top_requests",
                "description": "Read bounded highest-token and highest-cost local audit request summaries.",
                "inputSchema": _limit_schema(),
            },
        ]
    }


def _limit_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
            }
        },
    }


def _call_tool(params: dict[str, Any], *, audit_db_path: Optional[str]) -> list[dict[str, str]]:
    name = str(params.get("name") or "")
    arguments = params.get("arguments")
    args = arguments if isinstance(arguments, dict) else {}
    limit = _limit(args.get("limit"))
    if name == "token_intelligence.summary":
        payload = summarize_recent_events(path=audit_db_path, limit=limit)
        return [_json_text(payload)]
    if name == "token_intelligence.potential_savings":
        summary = summarize_recent_events(path=audit_db_path, limit=limit)
        return [_json_text(build_potential_savings_report(summary))]
    if name == "token_intelligence.top_requests":
        return [_json_text(list_top_requests(path=audit_db_path, limit=limit))]
    return [{"type": "text", "text": f"error: unknown tool: {name}"}]


def _json_text(payload: dict[str, Any]) -> dict[str, str]:
    return {"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}


def _limit(value: Any) -> int:
    try:
        return max(1, min(int(value), 1000))
    except Exception:
        return 1000


def _mcp_result(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _mcp_error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
