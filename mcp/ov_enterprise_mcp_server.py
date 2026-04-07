"""
Reference MCP stdio server for OmniMemora.

This is a minimal reference implementation demonstrating the OmniMemora tool interface.
It is intended for integration reference only — it does not contain production logic.

For production deployments, use the full OmniMemora adapter service.

Usage:
    python ov_enterprise_mcp_server.py

Environment:
    OMNIMEMORA_API_KEY       Your OmniMemora API key
    OMNIMEMORA_ADAPTER_URL   Base URL of the OmniMemora adapter (default: https://api.doloclaw.com)
"""

from __future__ import annotations

import json
import os
import sys
import httpx
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "omnimemora-mcp", "version": "1.0.0"}

ADAPTER_URL = os.getenv("OMNIMEMORA_ADAPTER_URL", "https://api.doloclaw.com")
API_KEY = os.getenv("OMNIMEMORA_API_KEY", "")
TIMEOUT = 30.0


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-OmniMemora-Key"] = API_KEY
    return headers


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()
    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        return None
    body = sys.stdin.buffer.read(content_length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(content: list[dict], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": content,
        "isError": is_error,
    }


def _text_content(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def _call_adapter(method: str, path: str, json_body: dict | None = None) -> httpx.Response:
    url = f"{ADAPTER_URL}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        return client.request(method, url, headers=_headers(), json=json_body)


def _handle_tools_list() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "memory_write",
                "description": "Store important information in the agent's long-term memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string", "description": "Agent identifier"},
                        "type": {"type": "string", "description": "Memory category (general, decision, preference, etc.)"},
                        "content": {"type": "string", "description": "The memory content to store"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                        "memory_type": {"type": "string", "description": "Explicit memory type override"},
                    },
                    "required": ["agent", "type", "content"],
                },
            },
            {
                "name": "memory_search",
                "description": "Search the agent's long-term memory store by natural language query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search query"},
                        "agent": {"type": "string", "description": "Filter by agent namespace"},
                        "memory_type": {"type": "string", "description": "Filter by memory type"},
                        "limit": {"type": "integer", "default": 10, "description": "Max results"},
                        "scoreThreshold": {"type": "number", "description": "Min relevance score (0-1)"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory_read",
                "description": "Read a specific memory by URI, or perform a content search",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uri": {"type": "string", "description": "Memory URI (required if no query)"},
                        "query": {"type": "string", "description": "Search query (required if no URI)"},
                        "agent": {"type": "string", "description": "Agent namespace"},
                        "memory_type": {"type": "string", "description": "Filter by memory type"},
                        "limit": {"type": "integer", "default": 10},
                        "include_expired": {"type": "boolean", "default": False},
                    },
                },
            },
            {
                "name": "memory_delete",
                "description": "Delete a specific memory by URI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uri": {"type": "string", "description": "Memory URI to delete"},
                    },
                    "required": ["uri"],
                },
            },
            {
                "name": "memory_snapshot",
                "description": "Generate an auto-summary of recent memories for agent startup context",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string", "description": "Agent identifier"},
                        "limit": {"type": "integer", "default": 200, "description": "Max source memories"},
                    },
                    "required": ["agent"],
                },
            },
        ]
    }


def _handle_tools_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "memory_write":
        r = _call_adapter("POST", "/memory/write", arguments)
        r.raise_for_status()
        data = r.json()
        return _tool_result([_text_content(json.dumps(data, indent=2))], is_error=data.get("status") == "error")

    elif name == "memory_search":
        r = _call_adapter("POST", "/memory/search", arguments)
        r.raise_for_status()
        data = r.json()
        memories = data.get("memories", [])
        lines = [f"Found {len(memories)} memory(s):"]
        for m in memories:
            lines.append(f"  [{m.get('category', '?')}] {m.get('abstract', m.get('content', '')[:80])}")
        return _tool_result([_text_content("\n".join(lines))])

    elif name == "memory_read":
        r = _call_adapter("POST", "/memory/read", arguments)
        r.raise_for_status()
        data = r.json()
        return _tool_result([_text_content(json.dumps(data, indent=2))])

    elif name == "memory_delete":
        r = _call_adapter("POST", "/memory/delete", arguments)
        r.raise_for_status()
        data = r.json()
        return _tool_result([_text_content(json.dumps(data, indent=2))], is_error=not data.get("success", False))

    elif name == "memory_snapshot":
        r = _call_adapter("POST", "/memory/snapshot", arguments)
        r.raise_for_status()
        data = r.json()
        md = data.get("markdown", "")
        return _tool_result([_text_content(md)])

    else:
        raise ValueError(f"Unknown tool: {name}")


def _handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}

    if method == "initialize":
        return _success_response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "ping":
        return _success_response(request_id, {})

    if method == "tools/list":
        return _success_response(request_id, _handle_tools_list())

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not isinstance(tool_name, str) or not tool_name.strip():
            return _error_response(request_id, -32602, "tool name is required")
        try:
            result = _handle_tools_call(tool_name, arguments)
        except httpx.HTTPStatusError as exc:
            try:
                err_data = exc.response.json()
                msg = json.dumps(err_data, indent=2)
            except Exception:
                msg = f"HTTP {exc.response.status_code}: {exc.response.text}"
            return _success_response(request_id, _tool_result([_text_content(msg)], is_error=True))
        except Exception as exc:
            return _success_response(
                request_id,
                _tool_result([_text_content(f"Error: {type(exc).__name__}: {exc}")], is_error=True),
            )
        return _success_response(request_id, result)

    if isinstance(method, str) and method.startswith("notifications/"):
        return None

    return _error_response(request_id, -32601, f"unsupported method '{method}'")


def main() -> int:
    while True:
        message = _read_message()
        if message is None:
            return 0
        response = _handle_request(message)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    raise SystemExit(main())
