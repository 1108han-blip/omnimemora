import asyncio
import json as _json
from typing import Any, Callable, Dict, List, Optional, Set, Type
from uuid import uuid4

import httpx
import loguru
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()

_adapter_http_base = ""
_config = None
_agent_identity_module = None
_memory_request_model: Optional[Type[Any]] = None
_write_memory_fn: Optional[Callable[..., Any]] = None

_mcp_sessions: Dict[str, asyncio.Queue] = {}
_mcp_sessions_lock: Optional[asyncio.Lock] = None
_mcp_bootstrap_done: Set[str] = set()
_mcp_bootstrap_lock: Optional[asyncio.Lock] = None


def configure_mcp_surface(
    *,
    adapter_http_base: str,
    config_obj: Any,
    agent_identity_module: Any,
    memory_request_model: Type[Any],
    write_memory_fn: Callable[..., Any],
) -> None:
    global _adapter_http_base, _config, _agent_identity_module, _memory_request_model, _write_memory_fn
    _adapter_http_base = adapter_http_base
    _config = config_obj
    _agent_identity_module = agent_identity_module
    _memory_request_model = memory_request_model
    _write_memory_fn = write_memory_fn


def _get_sessions_lock() -> asyncio.Lock:
    global _mcp_sessions_lock
    if _mcp_sessions_lock is None:
        _mcp_sessions_lock = asyncio.Lock()
    return _mcp_sessions_lock


def _get_bootstrap_lock() -> asyncio.Lock:
    global _mcp_bootstrap_lock
    if _mcp_bootstrap_lock is None:
        _mcp_bootstrap_lock = asyncio.Lock()
    return _mcp_bootstrap_lock


@router.get("/sse")
async def mcp_sse(request: Request):
    session_id = f"mcp_{uuid4().hex[:8]}"

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        async with _get_sessions_lock():
            _mcp_sessions[session_id] = queue

        try:
            yield f"event: endpoint\ndata: /messages?sessionId={session_id}\n\n"
            yield "event: keepalive\ndata: \n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: message\ndata: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield "event: keepalive\ndata: \n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with _get_sessions_lock():
                _mcp_sessions.pop(session_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _mcp_result(msg_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _mcp_error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _mcp_tools_payload() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "memory.search",
                "description": "Compatibility memory search tool. Product request compilation and memory use happen inside the 18011 ingress path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["keyword"],
                },
            },
            {
                "name": "memory.write",
                "description": "Write memory content.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "scope": {"type": "string"},
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "omnimemora_write_memory",
                "description": "[alias for memory.write] Write a memory item.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "scope": {"type": "string"},
                    },
                    "required": ["content"],
                },
            },
        ],
    }


def _mcp_initialize_payload() -> Dict[str, Any]:
    return {
        "protocolVersion": "2025-03-26",
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": "omnimemora-adapter",
            "version": "2.2.0",
        },
    }


def _infer_agent_id_for_bootstrap(body: Dict[str, Any], request: Optional[Request]) -> str:
    params = body.get("params", {}) if isinstance(body, dict) else {}
    if isinstance(params, dict):
        client_info = params.get("clientInfo", {})
        if isinstance(client_info, dict):
            name = str(client_info.get("name", "")).strip()
            if name:
                return name
    if request:
        raw = (request.headers.get("x-agent-id") or "").strip()
        if raw:
            return raw
        ua = (request.headers.get("user-agent") or "").lower()
        if "codex" in ua:
            return "codex"
        if "claude" in ua:
            return "claude_code"
        if "openclaw" in ua:
            return "openclaw-agent"
    return "mcp-client"


def _bootstrap_key(request: Optional[Request], tenant: str, agent: str) -> str:
    if request:
        sid = (
            request.query_params.get("sessionId")
            or request.headers.get("x-session-id")
            or request.headers.get("x-conversation-id")
            or request.headers.get("x-thread-id")
        )
        if sid:
            return f"sid:{sid}"
        client_ip = request.client.host if request.client else "unknown"
        return f"client:{client_ip}:{tenant}:{agent}"
    return f"fallback:{tenant}:{agent}"


async def _bootstrap_mcp_initialize(request: Optional[Request], body: Dict[str, Any]) -> None:
    if not _config.mcp_auto_bootstrap_enabled:
        return

    tenant = "openclaw"
    user = "openclaw-user"
    if request:
        tenant = (
            request.headers.get("x-omnimemora-tenant")
            or tenant
        ).strip() or tenant
        user = (
            request.headers.get("x-omnimemora-user")
            or request.headers.get("x-user-id")
            or user
        ).strip() or user
    agent = _infer_agent_id_for_bootstrap(body, request)
    canonical_agent = _agent_identity_module.resolve_canonical_agent_id(agent)
    key = _bootstrap_key(request, tenant, canonical_agent)

    async with _get_bootstrap_lock():
        if key in _mcp_bootstrap_done:
            return
        _mcp_bootstrap_done.add(key)

    payload: Dict[str, Any] = {
        "query": _config.mcp_auto_bootstrap_query[:200],
        "keyword": _config.mcp_auto_bootstrap_query[:200],
        "limit": 4,
        "tenant": tenant,
        "user": user,
        "agent": canonical_agent,
        "agent_id": canonical_agent,
        "integration_type": "pre_llm_connector",
    }
    if request:
        session_id = (
            request.query_params.get("sessionId")
            or request.headers.get("x-session-id")
            or request.headers.get("x-conversation-id")
            or request.headers.get("x-thread-id")
        )
        workspace_id = request.headers.get("x-workspace-id")
        if session_id:
            payload["session_id"] = session_id
        if workspace_id:
            payload["workspace_id"] = workspace_id

    try:
        async with httpx.AsyncClient(timeout=12.0, trust_env=False) as client:
            resp = await client.post(f"{_adapter_http_base}/mcp/query", json=payload)
            if resp.status_code >= 400:
                loguru.logger.warning(
                    f"[MCP_BOOTSTRAP] initialize bootstrap failed status={resp.status_code} key={key}"
                )
                return
            data = resp.json()
            loguru.logger.info(
                f"[MCP_BOOTSTRAP] initialized key={key} tenant={tenant} agent={canonical_agent} request_id={data.get('request_id')}"
            )
    except Exception as exc:
        loguru.logger.warning(f"[MCP_BOOTSTRAP] initialize bootstrap error key={key}: {exc}")


async def _dispatch_mcp_jsonrpc(body: Dict[str, Any], request: Optional[Request] = None) -> Optional[Dict[str, Any]]:
    method = body.get("method", "")
    msg_id = body.get("id")
    if not isinstance(body, dict):
        return _mcp_error(None, -32600, "invalid request")

    if method == "initialize":
        asyncio.create_task(_bootstrap_mcp_initialize(request, body))
        return _mcp_result(msg_id, _mcp_initialize_payload())
    if method in ("notifications/initialized",):
        return None
    if method in ("ping",):
        return _mcp_result(msg_id, {})
    if method == "tools/list":
        return _mcp_result(msg_id, _mcp_tools_payload())
    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            content_blocks = await _mcp_call_tool(tool_name, tool_args)
            return _mcp_result(msg_id, {"content": content_blocks})
        except Exception as exc:
            return _mcp_error(msg_id, -32603, f"tool error: {exc}")
    return _mcp_error(msg_id, -32601, f"method not found: {method}")


@router.post("/messages")
async def mcp_messages(request: Request, sessionId: Optional[str] = None):
    del sessionId
    body = await request.json()
    response = await _dispatch_mcp_jsonrpc(body, request)
    if response is None:
        return JSONResponse(status_code=204, content={})
    return JSONResponse(response)


@router.get("/mcp")
async def mcp_http_health():
    return {
        "status": "ok",
        "transport": "http-jsonrpc",
        "message_endpoint": "/mcp",
        "legacy_sse_endpoint": "/sse",
    }


@router.post("/mcp")
async def mcp_http_jsonrpc(request: Request):
    body = await request.json()
    response = await _dispatch_mcp_jsonrpc(body, request)
    if response is None:
        return JSONResponse(status_code=204, content={})
    return JSONResponse(response)


async def _mcp_call_tool(name: str, args: Dict[str, Any]) -> List[Dict[str, Any]]:
    if name in ("memory.context", "memory.recall", "omnimemora_search_memory"):
        meta = {
            "status": "deprecated",
            "tool": name,
            "product_ingress": "http://127.0.0.1:18011",
        }
        return [
            {
                "type": "text",
                "text": (
                    "deprecated: this MCP context tool is no longer an agent-facing "
                    "compile path. Send model requests through OmniMemora product "
                    "ingress at http://127.0.0.1:18011; no compiled prompt context "
                    "is returned from this tool."
                ),
            },
            {"type": "text", "text": _json.dumps(meta, ensure_ascii=False)},
        ]

    if name in ("memory.search",):
        keyword = args.get("keyword", "")
        limit = int(args.get("limit", 8)) or 8
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            sr = await client.post(
                f"{_adapter_http_base}/memory/search",
                json={"query": keyword, "keyword": keyword, "limit": limit, "agent": "openclaw-agent"},
                headers={"X-OmniMemora-Tenant": "openclaw", "X-OmniMemora-User": "openclaw-user"},
            )
            if sr.status_code >= 400:
                return [{"type": "text", "text": f"error: search failed ({sr.status_code})"}]
            search_result = sr.json()

        memories = search_result.get("memories", [])
        total = search_result.get("total", 0)
        lines = [f"Found {total} memories:"]
        for memory in memories[:limit]:
            lines.append(
                f"- [{memory.get('category','memory')} | score={memory.get('score',0):.2f}] "
                f"{memory.get('abstract', memory.get('content',''))[:80]}"
            )
        return [{"type": "text", "text": "\n".join(lines)}]

    if name in ("memory.write", "memory.store", "omnimemora_write_memory"):
        content = args.get("content", "")
        if not content:
            return [{"type": "text", "text": "error: content required"}]
        write_req = _memory_request_model(content=content, agent="openclaw-agent")
        write_result = await _write_memory_fn(write_req, Request(scope={"type": "http"}))
        uri = write_result.uri or write_result.memory_id or "unknown"
        return [{"type": "text", "text": f"memory stored: {uri}"}]

    return [{"type": "text", "text": f"error: unknown tool: {name}"}]
