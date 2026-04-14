"""Thin MCP stdio server backed by the commercialization tool registry."""

from __future__ import annotations

import json
import sys
from typing import Any

from ov_enterprise_tool_registry import invoke_tool, list_tool_specs

SERVER_INFO = {"name": "ov-enterprise-mcp", "version": "2026.03.28"}
PROTOCOL_VERSION = "2024-11-05"


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


def _error_response(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data is not None:
        payload["error"]["data"] = data
    return payload


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
        return _success_response(request_id, {"tools": list_tool_specs(public_only=True)})
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not isinstance(tool_name, str) or not tool_name.strip():
            return _error_response(request_id, -32602, "tool name is required")
        try:
            result = invoke_tool(tool_name, arguments)
        except Exception as exc:  # noqa: BLE001
            return _success_response(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2)}],
                    "structuredContent": {"status": "fail", "error": str(exc), "tool": tool_name},
                    "isError": True,
                },
            )
        return _success_response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                "structuredContent": result,
                "isError": result.get("status") not in {"pass", "warn"},
            },
        )
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
