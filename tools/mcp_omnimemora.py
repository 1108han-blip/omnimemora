#!/usr/bin/env python3
"""
mcp_omnimemora.py — OmniMemora MCP Shim

A stdio-based MCP client that proxies JSON-RPC requests to the
OmniMemora Python Adapter's HTTP MCP endpoint (18011).

Usage ( Codex / Claude Code MCP config):
{
  "mcpServers": {
    "omnimemora": {
      "command": "python",
      "args": ["path/to/mcp_omnimemora.py"]
    }
  }
}

Or directly:
  python tools/mcp_omnimemora.py

Environment:
  OMNIMEMORA_ADAPTER_URL  — adapter base URL (default: http://127.0.0.1:18011)
  OMNIMEMORA_ADAPTER_MCP  — MCP endpoint path (default: /mcp)
"""
import sys
import os
import json
import urllib.request
import urllib.error

ADAPTER_BASE = os.environ.get("OMNIMEMORA_ADAPTER_URL", "http://127.0.0.1:18011").rstrip("/")
MCP_PATH = os.environ.get("OMNIMEMORA_ADAPTER_MCP", "/mcp")
MCP_URL = ADAPTER_BASE + MCP_PATH


def send_jsonrpc_request(body: dict) -> dict | None:
    """Send a JSON-RPC 2.0 request to the HTTP MCP endpoint. Returns parsed response or None."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8") if e.fp else ""
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32603, "message": f"HTTP {e.code}: {body_text[:200]}"}
        }), file=sys.stderr)
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32603, "message": f"HTTP {e.code}"}}
    except Exception as e:
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32603, "message": str(e)}
        }), file=sys.stderr)
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32603, "message": str(e)}}


def main():
    """Read JSON-RPC requests from stdin, proxy to HTTP MCP endpoint, write responses to stdout."""
    if "--version" in sys.argv or "-v" in sys.argv:
        print("OmniMemora MCP Shim v1.0")
        print(f"  Proxy endpoint: {MCP_URL}")
        return

    # Probe endpoint on startup (handles --help / version check from Codex)
    try:
        probe_req = urllib.request.Request(
            ADAPTER_BASE + "/health?mode=local",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(probe_req, timeout=5) as r:
            pass
    except Exception as e:
        print(f"[omnimemora-mcp-shim] WARNING: adapter unreachable at {ADAPTER_BASE}: {e}", file=sys.stderr)

    # Read lines from stdin — each line is a JSON-RPC request
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            # Not a valid JSON line — skip
            continue

        # Batch request: array of requests
        if isinstance(request, list):
            responses = []
            for r in request:
                resp = send_jsonrpc_request(r)
                if resp is not None:
                    responses.append(resp)
            if responses:
                print(json.dumps(responses), flush=True)
        else:
            # Single request
            resp = send_jsonrpc_request(request)
            if resp is not None:
                print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
