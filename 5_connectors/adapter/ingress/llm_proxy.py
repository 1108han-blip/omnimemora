"""
llm_proxy.py — Protocol Ingress / Egress Layer
==============================================
職責定位（18011 內部三層結構）：

  [1] INGRESS LAYER（本文件）
      - Protocol entry points (OpenAI-compatible / Anthropic / Codex / OpenClaw)
      - Agent/session identity detection
      - Passthrough / upstream forwarding
      - Ingress trace/context attach
      - Compile dispatch (delegates to application/compile_orchestrator.py)

  [2] APPLICATION LAYER (application/compile_orchestrator.py, gateway_compile.py)
      - compile orchestration (application/compile_orchestrator.py)
      - truth resolution (via truth_bridge.py)
      - event recording (compile_store, meter_store)

  [3] INFRASTRUCTURE LAYER (runtime/store access)
      - meter/event storage
      - runtime/backend access

  truth_bridge.py is currently application-adjacent truth logic
  (not part of the Batch 3D infrastructure migration scope).

明確禁止進入本文件：
  - compile 執行細節（belong to application/compile_orchestrator.py）
  - truth resolution 業務邏輯（belong to truth_bridge.py）
  - metrics/read-model 聚合（belong to application/status_read_model.py）
  - control action execution（belong to agent_control_api.py）

OpenAI-compatible 主路徑狀態：
  - proxy_openai_chat: 已委託給 application/compile_orchestrator.run_compile_and_resolve()
  - proxy_v1_chat: 直接調用 proxy_openai_chat，自動受益
  - proxy_v1_responses: 待遷移（使用 _compile_or_passthrough_for_route 舊模式）

Anthropic 路徑狀態：
  - proxy_anthropic: 待遷移（使用 _compile_or_passthrough_for_route 舊模式）

端點：
  POST /v1/chat/completions  — OpenAI / Codex / Claude Code HTTP
  POST /llm/chat             — OpenClaw 專用（OpenAI 格式）
  POST /llm/anthropic         — Claude Code 專用（Anthropic 格式）
"""
import json
import importlib
import os
import time as _time
import httpx
from pathlib import Path
from typing import Optional, AsyncIterator, Iterable, Mapping
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

import loguru
from .. import config as _cfg
from ..config import config
from ..application import gateway_compile as _gc
from .. import agent_identity as _agent_identity
from .. import agent_routing_state as _route_state
from ..truth_bridge import (
    TruthResolution,
    auth_source_from_values,
    classify_model_resolution,
    infer_provider_name,
    product_auth_ref_for_provider,
    resolve_truth_contract,
)
from ..truth_registry import DEFAULT_TRUTH_REGISTRY
from ..config import config
from ..path_registry import classify_path
from ..trace_context import build_trace_event, get_request_context
from ..trace_events import append_trace_event

def _get_compile_orchestrator():
    return __import__("5_connectors.adapter.application.compile_orchestrator", fromlist=["dummy"])

router = APIRouter(tags=["llm_proxy"])
_meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
_v2_compute = importlib.import_module("4_core.logic.v2_compute")

_OMNI_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

_OMNI_COMPARE_HEADERS = {
    "content-type",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-request-id",
}


def _mark_quota_audit(
    request: Request,
    *,
    upstream_url: Optional[str],
    action: str,
) -> None:
    """
    Attach lightweight quota/audit routing metadata for outer middleware logging.
    """
    try:
        request.state.quota_audit = {
            "upstream_url": upstream_url or "",
            "action": action,
        }
    except Exception:
        pass


def _omni_filtered_passthrough_headers(headers: Mapping[str, str]) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _OMNI_HOP_BY_HOP_HEADERS:
            continue
        forwarded[key] = value
    return forwarded


def _omni_pick_compare_headers(headers: Mapping[str, str]) -> dict[str, str]:
    picked: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _OMNI_COMPARE_HEADERS:
            picked[key] = value
    return picked


def _omni_extract_usage(payload: Optional[dict]) -> Optional[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
        return payload["usage"]
    return None


def _omni_log_upstream_vs_final(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_payload: Optional[dict],
    final_mode: str,
) -> None:
    try:
        upstream_payload = upstream_resp.json()
    except Exception:
        upstream_payload = None

    upstream_usage = _omni_extract_usage(upstream_payload)
    final_usage = _omni_extract_usage(final_payload if final_payload is not None else upstream_payload)

    loguru.logger.info(
        f"[LLM_PROXY/USAGE_COMPARE] request_id={request_id} route={route} mode={final_mode} "
        f"upstream_usage_present={bool(upstream_usage)} final_usage_present={bool(final_usage)} "
        f"upstream_usage={upstream_usage} final_usage={final_usage} "
        f"upstream_headers={_omni_pick_compare_headers(upstream_resp.headers)} "
        f"final_headers={_omni_pick_compare_headers(_omni_filtered_passthrough_headers(upstream_resp.headers))}"
    )


def _omni_build_passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
) -> Response:
    _omni_log_upstream_vs_final(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_payload=None,
        final_mode="raw_passthrough",
    )
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=_omni_filtered_passthrough_headers(upstream_resp.headers),
    )

_HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

_DIAGNOSTIC_COMPARE_HEADERS = {
    "content-type",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-request-id",
}

_HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

BYPASS_PROXY_TRANSFORM = os.getenv("OMNIMEMORA_BYPASS_PROXY_TRANSFORM", "false").lower() == "true"
UPSTREAM_DEBUG = os.getenv("OMNIMEMORA_PROXY_USAGE_DEBUG", "true").lower() == "true"

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


def _should_bypass_codex_gateway(agent_id: str) -> bool:
    return (
        agent_id == "codex_cli"
        and os.getenv("OMNIMEMORA_BYPASS_CODEX", "").strip() == "1"
    )


def _build_codex_bypass_compile_meta() -> dict:
    return {
        "compile_status": "compile_skipped",
        "selected_memory_count": 0,
        "original_token_estimate": 0,
        "compiled_token_estimate": 0,
        "compression_ratio": 0.0,
        "compile_path": "codex_env_bypass",
        "compile_error": None,
        "compile_reason": "codex_env_bypass",
        "skill_suggestions": [],
    }


def _build_route_disabled_compile_meta() -> dict:
    return {
        "compile_status": "compile_skipped",
        "selected_memory_count": 0,
        "original_token_estimate": 0,
        "compiled_token_estimate": 0,
        "compression_ratio": 0.0,
        "compile_path": "agent_route_disabled",
        "compile_error": None,
        "compile_reason": "agent_route_disabled",
        "skill_suggestions": [],
    }


def _routing_enabled_for_agent(agent_id: str) -> bool:
    return _route_state.routing_enabled(agent_id)


async def _compile_or_passthrough_for_route(
    *,
    payload: dict,
    agent_id: str,
    request_id: str,
    trace_id: Optional[str],
) -> tuple[dict, dict]:
    if not _routing_enabled_for_agent(agent_id):
        loguru.logger.info(
            f"[LLM_PROXY/ROUTE] request_id={request_id} agent={agent_id} route=off passthrough=true"
        )
        return dict(payload), _build_route_disabled_compile_meta()

    return await _gc.run_gateway_compile(
        payload=payload,
        agent_id=agent_id,
        session_id=None,
        request_id=request_id,
        trace_id=trace_id,
    )


def _safe_passthrough_headers(headers: httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        lk = key.lower()
        if lk in _HOP_BY_HOP_HEADERS:
            continue
        out[key] = value
    return out


def _log_upstream_vs_final(
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_payload: Optional[dict] = None,
) -> None:
    if not UPSTREAM_DEBUG:
        return
    try:
        upstream_json = upstream_resp.json()
    except Exception:
        upstream_json = None

    upstream_usage = None
    if isinstance(upstream_json, dict) and isinstance(upstream_json.get("usage"), dict):
        upstream_usage = upstream_json.get("usage")

    final_usage = None
    final_keys: list[str] = []
    if isinstance(final_payload, dict):
        final_keys = sorted(list(final_payload.keys()))
        if isinstance(final_payload.get("usage"), dict):
            final_usage = final_payload.get("usage")

    loguru.logger.info(
        "[LLM_PROXY/USAGE_TRACE] "
        f"request_id={request_id} route={route} "
        f"upstream_status={upstream_resp.status_code} "
        f"upstream_has_usage={bool(upstream_usage)} "
        f"final_has_usage={bool(final_usage)} "
        f"upstream_usage={upstream_usage if upstream_usage is not None else 'null'} "
        f"final_usage={final_usage if final_usage is not None else 'null'} "
        f"final_keys={final_keys if final_keys else 'passthrough_raw'}"
    )
    loguru.logger.info(
        "[LLM_PROXY/HEADERS_TRACE] "
        f"request_id={request_id} route={route} "
        f"upstream_headers={dict(upstream_resp.headers)} "
        f"passthrough_headers={_safe_passthrough_headers(upstream_resp.headers)}"
    )


def _passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_payload: Optional[dict] = None,
) -> Response:
    _log_upstream_vs_final(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_payload=final_payload,
    )
    if BYPASS_PROXY_TRANSFORM or final_payload is None:
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            media_type=upstream_resp.headers.get("content-type", "application/json"),
            headers=_safe_passthrough_headers(upstream_resp.headers),
        )

    return Response(
        content=json.dumps(final_payload, ensure_ascii=False).encode("utf-8"),
        status_code=upstream_resp.status_code,
        media_type="application/json",
        headers=_safe_passthrough_headers(upstream_resp.headers),
    )

_PROXY_DEBUG_USAGE = os.getenv("OMNIMEMORA_PROXY_DEBUG_USAGE", "true").strip().lower() == "true"
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}


def _passthrough_headers(upstream_headers) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key, value in upstream_headers.items():
        lowered = key.lower().strip()
        if lowered in _HOP_BY_HOP_HEADERS:
            continue
        forwarded[key] = value
    return forwarded


def _debug_usage_compare(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_body: Optional[object] = None,
    extra: Optional[str] = None,
) -> None:
    if not _PROXY_DEBUG_USAGE:
        return
    try:
        upstream_json = upstream_resp.json()
    except Exception:
        upstream_json = None
    upstream_usage = upstream_json.get("usage") if isinstance(upstream_json, dict) else None
    final_usage = final_body.get("usage") if isinstance(final_body, dict) else None
    forwarded_headers = _passthrough_headers(upstream_resp.headers)
    header_keys = ",".join(sorted(k.lower() for k in forwarded_headers.keys()))
    detail = extra or ""
    loguru.logger.info(
        f"[LLM_PROXY/USAGE_COMPARE] request_id={request_id} route={route} "
        f"upstream_has_usage={bool(isinstance(upstream_usage, dict))} "
        f"final_has_usage={bool(isinstance(final_usage, dict))} "
        f"upstream_usage_keys={list((upstream_usage or {}).keys()) if isinstance(upstream_usage, dict) else []} "
        f"final_usage_keys={list((final_usage or {}).keys()) if isinstance(final_usage, dict) else []} "
        f"forwarded_header_keys={header_keys} extra={detail}"
    )


def _build_passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
) -> Response:
    headers = _passthrough_headers(upstream_resp.headers)
    content_type = upstream_resp.headers.get("content-type", "application/json")
    _debug_usage_compare(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_body=None,
        extra="mode=passthrough_body",
    )
    return Response(
        content=upstream_resp.content,
        media_type=content_type,
        status_code=upstream_resp.status_code,
        headers=headers,
    )

_BYPASS_PROXY_TRANSFORM = os.getenv("OMNIMEMORA_BYPASS_PROXY_TRANSFORM", "false").strip().lower() == "true"
_USAGE_TRACE_ENABLED = os.getenv("OMNIMEMORA_PROXY_USAGE_TRACE", "true").strip().lower() == "true"
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


def _passthrough_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _HOP_BY_HOP_HEADERS:
            continue
        out[key] = value
    return out


def _extract_usage_from_bytes(payload: bytes) -> Optional[dict]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    usage = parsed.get("usage") if isinstance(parsed, dict) else None
    return usage if isinstance(usage, dict) else None


def _log_response_compare(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_payload: Optional[object] = None,
    final_headers: Optional[Mapping[str, str]] = None,
    transformed: bool = False,
) -> None:
    if not _USAGE_TRACE_ENABLED:
        return
    upstream_usage = _extract_usage_from_bytes(upstream_resp.content)
    final_usage = None
    if isinstance(final_payload, dict):
        usage = final_payload.get("usage")
        if isinstance(usage, dict):
            final_usage = usage
    elif isinstance(final_payload, (bytes, bytearray)):
        final_usage = _extract_usage_from_bytes(bytes(final_payload))
    outgoing_headers = dict(final_headers or {})
    loguru.logger.info(
        "[LLM_PROXY/USAGE_COMPARE] "
        f"request_id={request_id} route={route} transformed={transformed} "
        f"upstream_usage_present={bool(upstream_usage)} final_usage_present={bool(final_usage)} "
        f"upstream_usage_keys={sorted((upstream_usage or {}).keys())} "
        f"final_usage_keys={sorted((final_usage or {}).keys())}"
    )
    loguru.logger.info(
        "[LLM_PROXY/HEADERS_COMPARE] "
        f"request_id={request_id} route={route} "
        f"upstream_header_count={len(upstream_resp.headers)} final_header_count={len(outgoing_headers)} "
        f"upstream_ratelimit_remaining={upstream_resp.headers.get('x-ratelimit-remaining')} "
        f"final_ratelimit_remaining={outgoing_headers.get('x-ratelimit-remaining')} "
        f"upstream_ratelimit_limit={upstream_resp.headers.get('x-ratelimit-limit')} "
        f"final_ratelimit_limit={outgoing_headers.get('x-ratelimit-limit')}"
    )
_TRACE_USAGE_PASSTHROUGH = os.getenv("OMNIMEMORA_TRACE_USAGE_PASSTHROUGH", "true").strip().lower() in {
    "1", "true", "yes", "on",
}

# ============================================================================
# Upstream Error Classification
# ============================================================================

UPSTREAM_ERROR_TYPES = {
    "upstream_overloaded_529": "upstream_overloaded_529",
    "upstream_http_error":     "upstream_http_error",
    "upstream_timeout":        "upstream_timeout",
    "proxy_internal_error":    "proxy_internal_error",
}

_HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


def _passthrough_headers(upstream_headers: httpx.Headers) -> dict:
    """
    Preserve upstream response headers except hop-by-hop transport headers.
    """
    headers: dict[str, str] = {}
    for key, value in upstream_headers.items():
        if key.lower() in _HOP_BY_HOP_RESPONSE_HEADERS:
            continue
        headers[key] = value
    return headers


def _extract_usage_dict(raw_body: bytes) -> Optional[dict]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    return usage if isinstance(usage, dict) else None


def _log_response_passthrough_compare(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_body: bytes,
    final_headers: dict,
) -> None:
    upstream_usage = _extract_usage_dict(upstream_resp.content)
    final_usage = _extract_usage_dict(final_body)
    upstream_has_ratelimit = any(k.lower().startswith("x-ratelimit-") for k in upstream_resp.headers.keys())
    final_has_ratelimit = any(k.lower().startswith("x-ratelimit-") for k in final_headers.keys())
    usage_state = "present" if upstream_usage else "missing"
    loguru.logger.info(
        f"[LLM_PROXY/PASSTHROUGH_COMPARE] "
        f"request_id={request_id} route={route} status={upstream_resp.status_code} "
        f"upstream_usage={usage_state} final_usage={'present' if final_usage else 'missing'} "
        f"upstream_headers={len(upstream_resp.headers)} final_headers={len(final_headers)} "
        f"upstream_ratelimit_headers={upstream_has_ratelimit} final_ratelimit_headers={final_has_ratelimit}"
    )


def _passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
) -> Response:
    headers = _passthrough_headers(upstream_resp.headers)
    body = upstream_resp.content
    _log_response_passthrough_compare(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_body=body,
        final_headers=headers,
    )
    return Response(
        content=body,
        media_type=upstream_resp.headers.get("content-type", "application/json"),
        status_code=upstream_resp.status_code,
        headers=headers,
    )

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _passthrough_headers(raw_headers: httpx.Headers) -> dict[str, str]:
    """
    Preserve upstream headers except hop-by-hop transport headers.
    This keeps provider metadata (rate-limit, request-id, etc.) visible to clients.
    """
    forwarded: dict[str, str] = {}
    for key, value in raw_headers.items():
        lower_key = key.lower()
        if lower_key in _HOP_BY_HOP_HEADERS:
            continue
        if lower_key == "content-length":
            # Let FastAPI/Starlette recompute content length for safety.
            continue
        forwarded[key] = value
    return forwarded


def _extract_usage_marker(response_body: bytes, content_type: str) -> str:
    if "json" not in (content_type or "").lower():
        return "non_json"
    try:
        decoded = json.loads(response_body.decode("utf-8"))
    except Exception:
        return "json_parse_failed"
    if not isinstance(decoded, dict):
        return "json_not_object"
    usage = decoded.get("usage")
    if isinstance(usage, dict):
        return "present"
    return "absent"


def _log_passthrough_compare(
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_headers: dict[str, str],
    final_body: bytes,
) -> None:
    upstream_headers = dict(upstream_resp.headers.items())
    upstream_rate_headers = sorted(
        key for key in upstream_headers.keys()
        if "ratelimit" in key.lower() or "rate-limit" in key.lower()
    )
    final_rate_headers = sorted(
        key for key in final_headers.keys()
        if "ratelimit" in key.lower() or "rate-limit" in key.lower()
    )
    content_type = upstream_resp.headers.get("content-type", "")
    usage_upstream = _extract_usage_marker(upstream_resp.content, content_type)
    usage_final = _extract_usage_marker(final_body, content_type)

    loguru.logger.info(
        f"[LLM_PROXY/PASSTHROUGH_COMPARE] request_id={request_id} route={route} "
        f"status={upstream_resp.status_code} usage_upstream={usage_upstream} usage_final={usage_final} "
        f"headers_upstream={len(upstream_headers)} headers_final={len(final_headers)} "
        f"ratelimit_upstream={upstream_rate_headers} ratelimit_final={final_rate_headers}"
    )


def _build_passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    fallback_media_type: str = "application/json",
) -> Response:
    final_headers = _passthrough_headers(upstream_resp.headers)
    final_body = upstream_resp.content
    content_type = upstream_resp.headers.get("content-type") or fallback_media_type

    if "content-type" not in {k.lower() for k in final_headers.keys()}:
        final_headers["Content-Type"] = content_type

    _log_passthrough_compare(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_headers=final_headers,
        final_body=final_body,
    )

    return Response(
        content=final_body,
        headers=final_headers,
        status_code=upstream_resp.status_code,
    )


def _classify_upstream_error(
    status_code: Optional[int],
    exception: Optional[BaseException],
) -> str:
    """
    Classify an upstream error into one of four specific types:
      upstream_overloaded_529 — upstream returned 529 (overloaded / throttled)
      upstream_http_error       — other non-2xx HTTP response
      upstream_timeout          — httpx.TimeoutException
      proxy_internal_error      — everything else (internal failure)
    """
    if isinstance(exception, httpx.TimeoutException):
        return UPSTREAM_ERROR_TYPES["upstream_timeout"]
    if status_code == 529:
        return UPSTREAM_ERROR_TYPES["upstream_overloaded_529"]
    return UPSTREAM_ERROR_TYPES["upstream_http_error"]


def _log_upstream_failure(
    request_id: str,
    upstream_url: str,
    error_type: str,
    status_code: Optional[int],
    error_message: str,
    agent_id: str,
    route: str,
    model: str,
):
    """
    Log detailed upstream failure info to the Gateway log.
    Fields: request_id, upstream_url, upstream_status, upstream_error_type, upstream_error_message
    """
    loguru.logger.warning(
        f"[LLM_PROXY/UPSTREAM_ERROR] "
        f"request_id={request_id} "
        f"upstream_url={upstream_url} "
        f"upstream_status={status_code} "
        f"upstream_error_type={error_type} "
        f"upstream_error_message={error_message[:200]}"
    )


def _annotate_upstream_error(
    raw_body: str,
    status_code: Optional[int],
    error_type: str,
) -> dict:
    """
    Annotate the raw upstream error body with Gateway context so the
    calling Agent understands where the failure originated.

    For 529 specifically: Claude Code would otherwise see an opaque
    Anthropic-style 529 and not know it came from MiniMax upstream.

    Returns a dict suitable for JSONResponse content=.
    """
    try:
        body_json = json.loads(raw_body) if raw_body else {}
    except (json.JSONDecodeError, ValueError):
        body_json = {}

    # Build descriptive gateway message
    if status_code == 529:
        gateway_msg = (
            f"MiniMax upstream overloaded (529). "
            f"Gateway compile succeeded — failure is in the upstream layer, not the compile pipeline. "
            f"Upstream may be rate-limiting or temporarily unavailable."
        )
    elif error_type == UPSTREAM_ERROR_TYPES["upstream_timeout"]:
        gateway_msg = (
            f"Gateway compile succeeded, upstream timed out. "
            f"The compile pipeline worked correctly; the failure is in the upstream call."
        )
    elif error_type == UPSTREAM_ERROR_TYPES["proxy_internal_error"]:
        gateway_msg = (
            f"Gateway internal error during proxy. "
            f"Compile pipeline status is in the compile_events log."
        )
    else:
        gateway_msg = (
            f"Gateway compile succeeded, upstream returned HTTP {status_code}. "
            f"The compile pipeline worked correctly; check upstream health."
        )

    # Preserve upstream error details in 'upstream_error' sub-object
    upstream_error = {
        "type": error_type,
        "status_code": status_code,
        "gateway_message": gateway_msg,
    }
    if isinstance(body_json, dict):
        upstream_error["upstream_body"] = body_json
    else:
        upstream_error["upstream_text"] = raw_body[:500]

    # Merge: preserve original type/message, add gateway context
    return {
        "type": body_json.get("type", "error"),
        "message": body_json.get("message", gateway_msg),
        "gateway_upstream_error": upstream_error,
    }


def _passthrough_headers_from_upstream(headers: httpx.Headers) -> dict:
    """
    Preserve upstream response metadata while filtering hop-by-hop headers.
    """
    out: dict[str, str] = {}
    for key, value in headers.multi_items():
        lower = key.lower()
        if lower in _HOP_BY_HOP_RESPONSE_HEADERS:
            continue
        out[key] = value
    return out


def _extract_usage_for_log(payload_bytes: bytes) -> Optional[dict]:
    try:
        parsed = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None
    usage = parsed.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def _log_upstream_vs_final_response(
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_content: bytes,
    final_headers: dict,
) -> None:
    upstream_usage = _extract_usage_for_log(upstream_resp.content)
    final_usage = _extract_usage_for_log(final_content)
    upstream_header_subset = {
        key: value
        for key, value in upstream_resp.headers.items()
        if key.lower() in _DIAGNOSTIC_COMPARE_HEADERS
    }
    final_header_subset = {
        key: value
        for key, value in final_headers.items()
        if key.lower() in _DIAGNOSTIC_COMPARE_HEADERS
    }
    loguru.logger.info(
        "[LLM_PROXY/RESPONSE_COMPARE] "
        f"request_id={request_id} route={route} "
        f"upstream_usage={json.dumps(upstream_usage, ensure_ascii=False) if upstream_usage is not None else 'null'} "
        f"final_usage={json.dumps(final_usage, ensure_ascii=False) if final_usage is not None else 'null'} "
        f"upstream_headers={json.dumps(upstream_header_subset, ensure_ascii=False)} "
        f"final_headers={json.dumps(final_header_subset, ensure_ascii=False)}"
    )


def _passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
) -> Response:
    response_headers = _passthrough_headers_from_upstream(upstream_resp.headers)
    _log_upstream_vs_final_response(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_content=upstream_resp.content,
        final_headers=response_headers,
    )
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=response_headers,
        media_type=upstream_resp.headers.get("content-type", "application/json"),
    )


def _passthrough_headers(upstream_resp: httpx.Response) -> dict:
    """Forward upstream response headers as-is for protocol compatibility."""
    return {k: v for k, v in upstream_resp.headers.items()}


def _usage_value_from_payload(raw_content: bytes, content_type: str) -> Optional[object]:
    if "json" not in (content_type or "").lower():
        return None
    try:
        payload = json.loads(raw_content.decode("utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload.get("usage")
    return None


def _log_upstream_vs_final(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    final_headers: dict,
) -> None:
    if not _TRACE_USAGE_PASSTHROUGH:
        return
    upstream_content_type = upstream_resp.headers.get("content-type", "")
    usage_value = _usage_value_from_payload(upstream_resp.content, upstream_content_type)
    loguru.logger.info(
        f"[LLM_PROXY/PASSTHROUGH_CHECK] request_id={request_id} route={route} "
        f"status={upstream_resp.status_code} usage_present={usage_value is not None} "
        f"upstream_header_count={len(upstream_resp.headers)} final_header_count={len(final_headers)}"
    )
    loguru.logger.info(
        f"[LLM_PROXY/UPSTREAM_RESPONSE] request_id={request_id} route={route} "
        f"headers={dict(upstream_resp.headers)} usage={usage_value}"
    )
    loguru.logger.info(
        f"[LLM_PROXY/FINAL_RESPONSE] request_id={request_id} route={route} "
        f"headers={final_headers} usage={usage_value}"
    )


def _passthrough_response(
    *,
    request_id: str,
    route: str,
    upstream_resp: httpx.Response,
    fallback_media_type: str = "application/json",
) -> Response:
    headers = _passthrough_headers(upstream_resp)
    _log_upstream_vs_final(
        request_id=request_id,
        route=route,
        upstream_resp=upstream_resp,
        final_headers=headers,
    )
    return Response(
        content=upstream_resp.content,
        media_type=upstream_resp.headers.get("content-type", fallback_media_type),
        status_code=upstream_resp.status_code,
        headers=headers,
    )


# ============================================================================
# Agent 識別
# ============================================================================

def detect_agent(request: Request, body: Optional[dict] = None) -> str:
    """
    按順序識別 Agent 身份：
    1. X-Omnimemora-Agent header
    2. Unified agent identity resolution (header/query/body)
    3. X-Agent-Family / User-Agent fallback
    4. nested body metadata
    4. fallback = unknown
    """
    # Make the raw request body visible to the shared identity resolver.
    if body is not None:
        try:
            request.state._body_cache = body
        except Exception:
            pass

    # 1. Product-specific explicit header
    agent = request.headers.get("x-omnimemora-agent") or ""
    if agent:
        return _agent_identity.resolve_canonical_agent_id(agent.strip().lower())

    # 2. Direct top-level body fields for OpenAI-style callers.
    if body:
        agent = body.get("agent_id", "") or body.get("agent", "")
        if agent:
            resolved = _agent_identity.resolve_canonical_agent_id(str(agent).strip().lower())
            if resolved != "unknown":
                return resolved

    # 3. Unified agent identity resolution
    try:
        identity = _agent_identity.resolve_agent_identity(request)
        if identity.canonical_agent_id != "unknown":
            return identity.canonical_agent_id
    except Exception:
        pass

    # 4. Family / User-Agent inference
    family = (request.headers.get("x-agent-family") or "").strip().lower()
    if family:
        resolved = _agent_identity.resolve_canonical_agent_id(family)
        if resolved != "unknown":
            return resolved

    ua = request.headers.get("user-agent", "").lower()
    if "claude" in ua:
        return "claude_code"
    if "codex" in ua:
        return "codex_cli"
    if "openclaw" in ua:
        return "openclaw"

    path = str(getattr(getattr(request, "url", None), "path", "") or "")
    if path == "/v1/codex/responses":
        return "openclaw"

    # 5. Nested body metadata fallback for legacy callers
    if body:
        meta = body.get("metadata", {})
        agent = meta.get("agent_id", "") or meta.get("agent", "")
        if agent:
            resolved = _agent_identity.resolve_canonical_agent_id(agent.strip().lower())
            if resolved != "unknown":
                return resolved

    return "unknown"


# ============================================================================
# 上游配置
# ============================================================================

def get_upstream_for_anthropic(requested_model: Optional[str] = None) -> dict:
    """
    返回 Anthropic wire-api 对应的上游配置。

    優先級：
    1. OpenClaw attach truth snapshot（如果存在且 wire_api=anthropic_messages）
    2. 模型特例 fallback（MiniMax-M2.7 等）
    3. product upstream config（默认配置）
    """
    # 檢查 OpenClaw attach truth
    attach_truth = _get_openclaw_attach_truth(wire_api="anthropic_messages")
    if attach_truth:
        fallback_api_key = (
            getattr(config, "anthropic_api_key", "")
            or os.getenv("OMNIMEMORA_ANTHROPIC_API_KEY", "").strip()
            or os.getenv("MINIMAX_API_KEY", "").strip()
            or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
        )
        return {
            "base_url": attach_truth.get("base_url", ""),
            "api_key": fallback_api_key,
            "provider": attach_truth.get("provider", "anthropic"),
            "timeout_seconds": 120,
            "model_map": {},
            "default_model": attach_truth.get("model", config.anthropic_default_model),
            "_truth_source": "openclaw_attach",
        }

    upstream = dict(config.upstreams.get("anthropic", {}))
    resolved = {
        "base_url": upstream.get("base_url", config.anthropic_base_url),
        "api_key": upstream.get("api_key", config.anthropic_api_key),
        "provider": upstream.get("provider", "anthropic"),
        "timeout_seconds": upstream.get("timeout_seconds", 120),
        "model_map": upstream.get("model_map", {}),
        "default_model": config.anthropic_default_model,
    }
    if not requested_model:
        return resolved

    # MiniMax-M2.7 等模型特例 — 現在作為低優先級 fallback
    model_lookup = DEFAULT_TRUTH_REGISTRY.canonicalize_refs(
        model_requested=requested_model,
        canonical_wire_api="anthropic_messages",
    )
    model_provider = getattr(getattr(model_lookup, "provider", None), "provider_ref", None)
    if model_provider != "minimax_anthropic_compatible":
        return resolved

    endpoint = model_lookup.endpoint or DEFAULT_TRUTH_REGISTRY.default_endpoint_for_provider(model_provider)
    if endpoint is not None:
        resolved["base_url"] = endpoint.base_url
    resolved["provider"] = model_provider
    resolved["_truth_source"] = "model_fallback"
    return resolved


def _get_openclaw_attach_truth(wire_api: Optional[str] = None) -> Optional[dict]:
    """
    獲取 OpenClaw attach metadata upstream truth snapshot。
    如果有 attach truth 且 wire_api 匹配（或不指定），返回該快照。
    """
    try:
        _openclaw_attach = __import__(
            "5_connectors.adapter.openclaw_attach_state",
            fromlist=["dummy"]
        )
        attach_truth = _openclaw_attach.get_openclaw_attach_truth()
        if not attach_truth:
            return None
        if wire_api and attach_truth.get("wire_api") != wire_api:
            return None
        return attach_truth
    except Exception:
        return None


def get_upstream_for_openai(provider_base: Optional[str] = None) -> dict:
    """
    返回 OpenAI-compatible 上游配置。

    優先級：
    1. OpenClaw attach truth snapshot（如果存在且 wire_api=chat_completions）
    2. runtime override（provider_base header）
    3. product upstream config（默认配置）
    """
    # 檢查 OpenClaw attach truth — 這是 attach 時捕獲的用戶端原始上游真相
    attach_truth = _get_openclaw_attach_truth(wire_api="chat_completions")
    if attach_truth:
        return {
            "base_url": attach_truth.get("base_url", ""),
            "api_key": "",  # auth 通過 runtime header 傳遞
            "provider": attach_truth.get("provider", "openai_compatible"),
            "timeout_seconds": 120,
            "model_map": {},
            "default_model": attach_truth.get("model", config.openai_default_model),
            "_truth_source": "openclaw_attach",
        }

    upstream = dict(config.upstreams.get("openai", {}))
    return {
        "base_url": provider_base or upstream.get("base_url", config.openai_base_url),
        "api_key": upstream.get("api_key", config.openai_api_key),
        "provider": upstream.get("provider", "openai_compatible"),
        "timeout_seconds": upstream.get("timeout_seconds", 120),
        "model_map": upstream.get("model_map", {}),
        "default_model": upstream.get("default_model", config.openai_default_model),
    }


def _coerce_bearer_header(raw_value: Optional[str]) -> Optional[str]:
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip()
    if not value:
        return None
    if value.lower().startswith("bearer "):
        return value
    return f"Bearer {value}"


def _normalize_responses_function_ids(
    raw_tool_id: object,
    raw_call_id: object = None,
) -> tuple[str, str]:
    """
    Preserve both Responses IDs across the chat-completions bridge.
    """
    raw_tool_text = str(raw_tool_id or "").strip()
    raw_call_text = str(raw_call_id or "").strip()

    combined_call_id = ""
    combined_item_id = ""
    if "|" in raw_tool_text:
        left, right = raw_tool_text.split("|", 1)
        combined_call_id = left.strip()
        combined_item_id = right.strip()

    item_id = combined_item_id or raw_tool_text or f"fc_{uuid4().hex[:12]}"
    if not item_id.startswith("fc_"):
        item_id = f"fc_{item_id}"

    call_id = raw_call_text or combined_call_id or raw_tool_text or f"call_{uuid4().hex[:12]}"
    if "|" in call_id:
        call_id = call_id.split("|", 1)[0].strip()
    if not call_id.startswith("call_"):
        call_id = f"call_{call_id}"

    return item_id, call_id


def _looks_like_responses_upstream(base_url: Optional[str]) -> bool:
    if not isinstance(base_url, str):
        return False
    normalized = base_url.strip().rstrip("/").lower()
    if not normalized:
        return False
    return normalized.endswith("/responses") or "/backend-api/codex" in normalized


def _normalize_responses_upstream_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    return f"{normalized}/responses"


def _local_codex_auth_store_path() -> Path:
    raw = os.getenv("OMNIMEMORA_CODEX_AUTH_STORE_PATH", "~/.codex/auth.json").strip()
    return Path(raw).expanduser()


def _load_local_codex_upstream_truth() -> Optional[dict]:
    """
    Reuse Codex's local auth truth instead of duplicating credentials into product config.
    Preference order:
    1. explicit OpenAI API key stored by Codex
    2. ChatGPT login access token stored in Codex auth.json
    """
    auth_path = _local_codex_auth_store_path()
    if not auth_path.exists():
        return None

    try:
        data = json.loads(auth_path.read_text())
    except Exception:
        return None

    openai_api_key = str(data.get("OPENAI_API_KEY") or "").strip()
    if openai_api_key:
        return {
            "wire_api": "responses",
            "base_url": os.getenv("OMNIMEMORA_CODEX_OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "authorization": f"Bearer {openai_api_key}",
            "source": "codex_auth_json_openai_api_key",
        }

    if str(data.get("auth_mode") or "").strip().lower() != "chatgpt":
        return None

    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
    access_token = str(tokens.get("access_token") or "").strip()
    if not access_token:
        return None

    return {
        "wire_api": "responses",
        "base_url": os.getenv(
            "OMNIMEMORA_CODEX_CHATGPT_BASE_URL",
            "https://chatgpt.com/backend-api/codex",
        ),
        "authorization": f"Bearer {access_token}",
        "source": "codex_auth_json_chatgpt_access_token",
    }


def _resolve_codex_responses_upstream(
    *,
    agent_id: str,
    provider_base: Optional[str],
    authorization_header: Optional[str],
) -> Optional[dict]:
    """
    Resolve the best Responses-compatible upstream for Codex.

    Priority:
    1. Explicit provider/auth passed from the client
    2. Local Codex auth store (weak-intrusion truth source)
    3. None -> fallback to chat/completions bridge
    """
    explicit_base = provider_base.strip() if isinstance(provider_base, str) else ""
    explicit_auth = _coerce_bearer_header(authorization_header)

    if explicit_base:
        return {
            "wire_api": "responses",
            "base_url": explicit_base,
            "authorization": explicit_auth,
            "source": "request_headers",
        }

    if agent_id != "codex_cli":
        return None

    return _load_local_codex_upstream_truth()


# ============================================================================
# 事件記錄
# ============================================================================


def _record_event(
    agent_id: str,
    event_type: str,
    request_id: str,
    path: str,
    model: str,
    status: str,
    status_code: Optional[int] = None,
    error: Optional[str] = None,
    truth_meta: Optional[dict] = None,
    trace_id: Optional[str] = None,
):
    """寫入 proxy_store 事件。"""
    try:
        import importlib
        _ps = importlib.import_module("5_connectors.adapter.infrastructure.proxy_store")
        row = {
            "type": event_type,
            "trace_id": trace_id or request_id,
            "request_id": request_id,
            "agent_id": agent_id,
            "path": path,
            "model": model,
            "timestamp": _time.time(),
            "status": status,
            "status_code": status_code,
            "error": error,
        }
        if truth_meta:
            row.update(truth_meta)
        row.update(classify_path(path))
        _ps.append_event(row)
        if config.trace_events_enabled:
            stage = "upstream"
            if event_type == "proxy_request":
                stage = "gateway/proxy"
            elif event_type == "proxy_error":
                stage = "error"
            append_trace_event(
                build_trace_event(
                    trace_id=trace_id or request_id,
                    request_id=request_id,
                    stage=stage,
                    path=path,
                    status=status,
                    agent_id=agent_id,
                    error_type=error.split("|", 1)[0] if error else None,
                    details={
                        "event_type": event_type,
                        "model": model,
                        "status_code": status_code,
                    },
                )
            )
    except Exception as e:
        loguru.logger.warning(f"[LLM_PROXY] failed to record event: {e}")


def _record_compile_event(
    request_id: str,
    agent_id: str,
    path: str,
    model: str,
    compile_meta: dict,
    proxy_status: str = "success",
    proxy_status_code: Optional[int] = None,
    truth_meta: Optional[dict] = None,
    trace_id: Optional[str] = None,
):
    """
    寫入 compile_store 事件（Phase 3）。

    proxy_status reflects the outcome of the upstream proxy call:
      "success"  — upstream returned 2xx
      "failed"   — upstream returned 4xx/5xx or timed out

    The same request_id can be re-recorded with updated proxy_status when
    the proxy call fails after the compile event was initially recorded.
    """
    try:
        import importlib
        _cs = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")
        row = {
            "trace_id": trace_id or request_id,
            "request_id": request_id,
            "agent_id": agent_id,
            "path": path,
            "model": model,
            "timestamp": _time.time(),
            "proxy_status": proxy_status,
            "proxy_status_code": proxy_status_code,
            "compile_status": compile_meta.get("compile_status", "unknown"),
            "selected_memory_count": compile_meta.get("selected_memory_count", 0),
            "original_token_estimate": compile_meta.get("original_token_estimate", 0),
            "compiled_token_estimate": compile_meta.get("compiled_token_estimate", 0),
            "compression_ratio": compile_meta.get("compression_ratio", 0.0),
            "compile_path": compile_meta.get("compile_path", "unknown"),
            "compile_error": compile_meta.get("compile_error"),
            "compile_reason": compile_meta.get("compile_reason", ""),
            "skill_suggestions": compile_meta.get("skill_suggestions", []) or [],
        }
        if truth_meta:
            row.update(truth_meta)
            row["compile_used"] = True
        row.update(classify_path(path))
        _cs.append_compile_event(row)
        if config.trace_events_enabled:
            append_trace_event(
                build_trace_event(
                    trace_id=trace_id or request_id,
                    request_id=request_id,
                    stage="adapter",
                    path=path,
                    status=compile_meta.get("compile_status", "unknown"),
                    agent_id=agent_id,
                    error_type=compile_meta.get("compile_error"),
                    details={
                        "proxy_status": proxy_status,
                        "proxy_status_code": proxy_status_code,
                        "selected_memory_count": compile_meta.get("selected_memory_count", 0),
                        "compile_path": compile_meta.get("compile_path", "unknown"),
                    },
                )
            )
    except Exception as e:
        loguru.logger.warning(f"[LLM_PROXY] compile_store record failed: {e}")


def _sanitize_payload_for_trace(payload: dict) -> dict:
    """Keep traces compact while preserving payload shape for compatibility debugging."""
    def _redact_text(value: str, limit: int = 300) -> str:
        if not isinstance(value, str):
            return value
        if not config.trace_redact:
            return value
        trimmed = value[:limit]
        if len(value) > limit:
            trimmed += "…"
        return trimmed

    traced = {}
    for key, value in payload.items():
        if key == "messages" and isinstance(value, list):
            messages = []
            for msg in value[-6:]:
                item = {"role": msg.get("role")}
                content = msg.get("content")
                if isinstance(content, str):
                    item["content"] = _redact_text(content, 500)
                elif isinstance(content, list):
                    blocks = []
                    for block in content[:12]:
                        if isinstance(block, dict):
                            block_copy = {k: v for k, v in block.items() if k not in {"input"}}
                            if "text" in block_copy:
                                block_copy["text"] = _redact_text(str(block_copy["text"]), 300)
                            if "content" in block_copy and isinstance(block_copy["content"], str):
                                block_copy["content"] = _redact_text(block_copy["content"], 300)
                            if config.trace_redact and block_copy.get("type") == "tool_result":
                                if "content" in block_copy:
                                    block_copy["content"] = "[redacted-tool-result]"
                                if "text" in block_copy:
                                    block_copy["text"] = "[redacted-tool-result]"
                            blocks.append(block_copy)
                        else:
                            blocks.append(str(block)[:120])
                    item["content"] = blocks
                else:
                    item["content"] = content
                messages.append(item)
            traced[key] = messages
            continue
        if key == "system":
            if isinstance(value, str):
                traced[key] = _redact_text(value, 1000)
            elif isinstance(value, list):
                if config.trace_redact:
                    redacted_blocks = []
                    for block in value[:8]:
                        if isinstance(block, dict):
                            block = dict(block)
                            if "text" in block:
                                block["text"] = _redact_text(str(block["text"]), 400)
                        redacted_blocks.append(block)
                    traced[key] = redacted_blocks
                else:
                    traced[key] = value[:8]
            else:
                traced[key] = value
            continue
        if key == "tools" and isinstance(value, list):
            traced[key] = value[:8]
            continue
        if key in {"metadata"} and config.trace_redact:
            traced[key] = "[redacted]"
            continue
        traced[key] = value
    return traced


def _trace_anthropic_payload(request_id: str, stage: str, payload: dict, extra: Optional[dict] = None):
    """Append a compact Anthropic payload trace for success/failure diffing."""
    try:
        if not config.trace_anthropic_payload:
            return
        path = config.anthropic_payload_trace_path
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        row = {
            "request_id": request_id,
            "stage": stage,
            "timestamp": _time.time(),
            "payload": _sanitize_payload_for_trace(payload),
        }
        if extra:
            row["extra"] = extra
        loguru.logger.info(
            f"[LLM_PROXY/ANTHROPIC_TRACE] {json.dumps(row, ensure_ascii=False)}"
        )
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        loguru.logger.warning(f"[LLM_PROXY] payload trace failed: {e}")


def _trace_anthropic_status(
    request_id: str,
    stage: str,
    status_code: int,
    body: Optional[str] = None,
):
    """Trace upstream response status for request_id-linked diagnostics."""
    try:
        if not config.trace_anthropic_payload:
            return
        path = config.anthropic_payload_trace_path
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        row = {
            "request_id": request_id,
            "stage": stage,
            "timestamp": _time.time(),
            "status_code": status_code,
        }
        if body is not None:
            row["body"] = "[redacted]" if config.trace_redact else body[:1000]
        loguru.logger.info(
            f"[LLM_PROXY/ANTHROPIC_TRACE] {json.dumps(row, ensure_ascii=False)}"
        )
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        loguru.logger.warning(f"[LLM_PROXY] payload trace failed: {e}")


def resolve_anthropic_upstream_model(requested_model: str, upstream: dict) -> str:
    """
    Normalize inbound Claude Code model ids to the configured Anthropic-compatible upstream model.

    Current production target:
      Claude Code -> OmniMemora Gateway -> MiniMax-M2.7
    """
    model_map = upstream.get("model_map", {}) or {}
    default_model = upstream.get("default_model") or requested_model or "unknown"

    if requested_model in model_map:
        return model_map[requested_model]

    if requested_model.startswith("claude-"):
        return default_model

    return requested_model or default_model


def resolve_openai_upstream_model(requested_model: str, upstream: dict) -> str:
    """Resolve OpenAI upstream model without silent family-level remapping."""
    model_map = upstream.get("model_map", {}) or {}
    default_model = upstream.get("default_model") or requested_model or config.openai_default_model

    if requested_model in model_map:
        return model_map[requested_model]

    return requested_model or default_model


def _build_anthropic_truth_resolution(
    *,
    agent_id: str,
    route_label: str,
    requested_model: str,
    upstream: dict,
    resolved_model: str,
) -> TruthResolution:
    default_model = upstream.get("default_model") or requested_model or "unknown"
    return TruthResolution(
        agent_id=agent_id,
        route=route_label,
        wire_api_resolved="anthropic_messages",
        provider_resolved=infer_provider_name(
            upstream.get("base_url", ""),
            upstream.get("provider", "anthropic"),
        ),
        base_url_resolved=upstream.get("base_url", ""),
        base_url_source="product_upstream_config",
        model_requested=requested_model,
        model_resolved=resolved_model,
        model_resolution_source=classify_model_resolution(
            requested_model=requested_model,
            resolved_model=resolved_model,
            default_model=default_model,
            mapped_models=(upstream.get("model_map", {}) or {}).keys(),
            family_prefix="claude-",
            family_default_reason="anthropic_family_default",
        ),
        auth_source=auth_source_from_values(
            product_api_key_present=bool(upstream.get("api_key")),
        ),
        auth_present=bool(upstream.get("api_key")),
        fallback_used=False,
        override_fields=["model"] if requested_model and requested_model != resolved_model else [],
    )


def _build_openai_truth_resolution(
    *,
    agent_id: str,
    route_label: str,
    requested_model: str,
    resolved_model: str,
    upstream: dict,
    explicit_provider_base: Optional[str],
    explicit_authorization: Optional[str],
    wire_api: str = "chat_completions",
    fallback_used: bool = False,
    fallback_reason: str = "",
    agent_truth_source: Optional[str] = None,
) -> TruthResolution:
    override_fields: list[str] = []
    if explicit_provider_base:
        override_fields.append("base_url")
    if explicit_authorization:
        override_fields.append("authorization")
    if requested_model and requested_model != resolved_model:
        override_fields.append("model")

    return TruthResolution(
        agent_id=agent_id,
        route=route_label,
        wire_api_resolved=wire_api,
        provider_resolved=infer_provider_name(
            upstream.get("base_url", ""),
            upstream.get("provider", "openai_compatible"),
        ),
        base_url_resolved=upstream.get("base_url", ""),
        base_url_source="runtime_override" if explicit_provider_base else (
            "agent_truth_bridge" if agent_truth_source else "product_upstream_config"
        ),
        model_requested=requested_model,
        model_resolved=resolved_model,
        model_resolution_source=classify_model_resolution(
            requested_model=requested_model,
            resolved_model=resolved_model,
            default_model=upstream.get("default_model") or config.openai_default_model,
            mapped_models=(upstream.get("model_map", {}) or {}).keys(),
        ),
        auth_source=auth_source_from_values(
            explicit_authorization=bool(explicit_authorization),
            agent_truth_source=agent_truth_source,
            product_api_key_present=bool(upstream.get("api_key")),
        ),
        auth_present=bool(explicit_authorization or upstream.get("api_key") or agent_truth_source),
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        override_fields=override_fields,
    )


def _anthropic_product_auth_ref(upstream: dict) -> str:
    provider = infer_provider_name(
        upstream.get("base_url", ""),
        upstream.get("provider", "anthropic"),
    )
    if provider == "minimax_anthropic_compatible":
        return "product_minimax_api_key"
    return "product_anthropic_api_key"


def _codex_responses_auth_ref(
    source: Optional[str],
    explicit_authorization: Optional[str],
) -> Optional[str]:
    if explicit_authorization:
        return "runtime_authorization_header"
    if source == "codex_auth_json_chatgpt_access_token":
        return "codex_chatgpt_access_token"
    if source == "codex_auth_json_openai_api_key":
        return "product_openai_api_key"
    return None


def _safe_json_dumps(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _normalize_openai_message(message):
    if not isinstance(message, dict):
        return message

    normalized = dict(message)
    content = normalized.get("content")
    if content is None:
        normalized["content"] = ""
    elif not isinstance(content, (str, list)):
        normalized["content"] = _safe_json_dumps(content)

    tool_calls = normalized.get("tool_calls")
    if isinstance(tool_calls, list):
        normalized_calls = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                normalized_calls.append(tool_call)
                continue
            normalized_tool_call = dict(tool_call)
            function_def = normalized_tool_call.get("function")
            if isinstance(function_def, dict):
                normalized_function = dict(function_def)
                arguments = normalized_function.get("arguments", "")
                if not isinstance(arguments, str):
                    normalized_function["arguments"] = _safe_json_dumps(arguments)
                normalized_tool_call["function"] = normalized_function
            normalized_calls.append(normalized_tool_call)
        normalized["tool_calls"] = normalized_calls

    if normalized.get("role") == "tool":
        tool_content = normalized.get("content", "")
        if not isinstance(tool_content, str):
            normalized["content"] = _safe_json_dumps(tool_content)

    return normalized


def _normalize_openai_upstream_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload

    normalized = dict(payload)
    messages = normalized.get("messages")
    if isinstance(messages, list):
        normalized["messages"] = [_normalize_openai_message(message) for message in messages]
    return normalized


def _collect_text_parts(parts) -> str:
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return ""

    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
            continue
        if not isinstance(part, dict):
            continue
        part_type = str(part.get("type", "")).lower()
        if part_type in {"input_text", "output_text", "text"}:
            text = part.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
    return "".join(chunks)


def _extract_user_query(messages) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if str(message.get("role", "")).lower() != "user":
            continue
        content = _collect_text_parts(message.get("content"))
        if content:
            return content
    return ""


def _persist_gateway_meter(
    *,
    request_id: str,
    agent_id: str,
    query: str,
    compile_meta: dict,
) -> None:
    baseline_tokens = int(compile_meta.get("original_token_estimate") or 0)
    actual_tokens = int(compile_meta.get("compiled_token_estimate") or 0)
    compile_status = str(compile_meta.get("compile_status") or "compile_skipped")

    if actual_tokens <= 0 or compile_status != "compile_success":
        actual_tokens = baseline_tokens

    baseline_chars = max(len(query or ""), baseline_tokens * 4)
    actual_chars = max(0, actual_tokens * 4)
    saved_tokens = max(0, baseline_tokens - actual_tokens)
    saved_chars = max(0, baseline_chars - actual_chars)
    packed_count = int(compile_meta.get("selected_memory_count") or 0)
    tenant = agent_id if agent_id and agent_id != "unknown" else "gateway"

    try:
        meter = _v2_compute.TokenSavingsMeter(
            request_id=request_id,
            tenant=tenant,
            user=tenant,
            agent=agent_id or "unknown",
            client=f"{agent_id or 'unknown'}-gateway",
            timestamp=datetime.utcnow().isoformat() + "Z",
            query_shape=_v2_compute.classify_query_shape(query or ""),
            query_chars=len(query or ""),
            query=query or "",
            baseline_chars=baseline_chars,
            actual_chars=actual_chars,
            saved_chars=saved_chars,
            baseline_tokens_estimate=baseline_tokens,
            actual_tokens_estimate=actual_tokens,
            saved_tokens_estimate=saved_tokens,
            savings_ratio=round((saved_tokens / baseline_tokens), 3) if baseline_tokens > 0 else 0.0,
            packed_memory_count=packed_count,
            local_cards_used=packed_count,
            remote_candidates_considered=max(packed_count, 0),
            remote_candidates_skipped=0,
            remote_used_count=0,
            skipped_remote_reason=None,
            coverage_satisfied=packed_count > 0,
            packing_enabled=compile_status == "compile_success",
            abstract_preferred=False,
            dedup_applied=True,
            task_type=None,
            context_bypass=compile_status != "compile_success",
            bypassed_context_tokens=baseline_tokens if compile_status != "compile_success" else 0,
            matched_keywords=[],
            candidate_memories=[],
            dropped_memories=[],
        )
        _meter_store.store_meter(meter)
    except Exception as exc:
        loguru.logger.warning(f"[LLM_PROXY/METER] request_id={request_id} persist skipped: {exc}")


def _responses_tools_to_chat_tools(tools) -> list[dict]:
    if not isinstance(tools, list):
        return []

    chat_tools: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "function":
            continue

        function_def = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = function_def.get("name")
        if not name:
            continue

        normalized = {
            "type": "function",
            "function": {
                "name": name,
            },
        }
        if "description" in function_def:
            normalized["function"]["description"] = function_def.get("description")
        if "parameters" in function_def:
            normalized["function"]["parameters"] = function_def.get("parameters")
        if "strict" in function_def:
            normalized["function"]["strict"] = function_def.get("strict")
        chat_tools.append(normalized)

    return chat_tools


def _responses_input_to_chat_messages(body: dict) -> list[dict]:
    messages: list[dict] = []
    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions})

    raw_input = body.get("input")
    if isinstance(raw_input, str):
        raw_input = [{"type": "message", "role": "user", "content": raw_input}]
    elif isinstance(raw_input, dict):
        raw_input = [raw_input]
    elif not isinstance(raw_input, list):
        raw_input = []

    for item in raw_input:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue
        if not isinstance(item, dict):
            continue

        item_type = str(item.get("type", "message")).lower()
        if item_type == "message":
            role = str(item.get("role", "user")).lower()
            content = _collect_text_parts(item.get("content"))
            if content or role == "system":
                messages.append({"role": role, "content": content})
            continue

        if item_type == "function_call":
            arguments = item.get("arguments", "")
            if not isinstance(arguments, str):
                arguments = _safe_json_dumps(arguments)
            item_id, call_id = _normalize_responses_function_ids(
                item.get("id"),
                item.get("call_id"),
            )
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": f"{call_id}|{item_id}",
                    "type": "function",
                    "function": {
                        "name": item.get("name", "tool_call"),
                        "arguments": arguments,
                    },
                }],
            })
            continue

        if item_type == "function_call_output":
            output = item.get("output", "")
            if not isinstance(output, str):
                output = _safe_json_dumps(output)
            messages.append({
                "role": "tool",
                "tool_call_id": item.get("call_id") or item.get("id") or f"call_{uuid4().hex[:12]}",
                "content": output,
            })
            continue

        if item_type in {"input_text", "text"}:
            text = item.get("text")
            if isinstance(text, str) and text:
                messages.append({"role": "user", "content": text})

    return messages


def _chat_message_to_text(message: dict) -> str:
    return _extract_chat_output_text(message)


def _chat_messages_to_responses_payload(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
    instructions: Optional[str] = None
    items: list[dict] = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role", "user")).lower()
        text = _chat_message_to_text(message)

        if role == "system":
            if instructions is None:
                instructions = text
            else:
                items.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": text}],
                })
            continue

        if role == "tool":
            output = message.get("content", "")
            if not isinstance(output, str):
                output = _safe_json_dumps(output)
            items.append({
                "type": "function_call_output",
                "call_id": message.get("tool_call_id") or message.get("id") or f"call_{uuid4().hex[:12]}",
                "output": output,
            })
            continue

        if role == "assistant" and isinstance(message.get("tool_calls"), list):
            if text:
                items.append({
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                    "status": "completed",
                    "id": message.get("id") or f"msg_{uuid4().hex[:12]}",
                })
            for tool_call in message.get("tool_calls") or []:
                if not isinstance(tool_call, dict):
                    continue
                function_def = tool_call.get("function") or {}
                arguments = function_def.get("arguments", "")
                if not isinstance(arguments, str):
                    arguments = _safe_json_dumps(arguments)
                item_id, call_id = _normalize_responses_function_ids(tool_call.get("id"))
                items.append({
                    "type": "function_call",
                    "id": item_id,
                    "call_id": call_id,
                    "name": function_def.get("name", "tool_call"),
                    "arguments": arguments,
                })
            continue

        if role == "assistant":
            items.append({
                "type": "message",
                "role": role,
                "content": [{"type": "output_text", "text": text}],
                "status": "completed",
                "id": message.get("id") or f"msg_{uuid4().hex[:12]}",
            })
            continue

        items.append({
            "role": role,
            "content": [{"type": "input_text", "text": text}],
        })

    return instructions, items


def _compiled_chat_to_responses_request(original_body: dict, compiled_body: dict) -> dict:
    rebuilt = dict(original_body)
    instructions, input_items = _chat_messages_to_responses_payload(
        compiled_body.get("messages", []) if isinstance(compiled_body.get("messages"), list) else []
    )
    if instructions:
        rebuilt["instructions"] = instructions
    else:
        rebuilt.pop("instructions", None)
    rebuilt["input"] = input_items
    rebuilt["model"] = original_body.get("model", config.openai_default_model)
    return rebuilt


def _responses_request_to_chat_body(body: dict) -> dict:
    chat_body = {
        "model": body.get("model", config.openai_default_model),
        "messages": _responses_input_to_chat_messages(body),
        "stream": False,
    }

    tools = _responses_tools_to_chat_tools(body.get("tools"))
    if tools:
        chat_body["tools"] = tools

    tool_choice = body.get("tool_choice")
    if tool_choice is not None:
        chat_body["tool_choice"] = tool_choice

    if "parallel_tool_calls" in body:
        chat_body["parallel_tool_calls"] = body.get("parallel_tool_calls")

    text_cfg = body.get("text")
    if isinstance(text_cfg, dict):
        if text_cfg.get("verbosity") == "low":
            chat_body["temperature"] = 0.2

    return chat_body


def _extract_chat_output_text(choice_message: dict) -> str:
    content = choice_message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif isinstance(part, str):
                chunks.append(part)
        return "".join(chunks)
    return ""


def _chat_choice_to_responses_output(choice_message: dict) -> list[dict]:
    output: list[dict] = []

    text = _extract_chat_output_text(choice_message)
    if text:
        output.append({
            "type": "message",
            "id": choice_message.get("id") or f"msg_{uuid4().hex[:12]}",
            "status": "completed",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": text,
                "annotations": [],
            }],
        })

    tool_calls = choice_message.get("tool_calls")
    if isinstance(tool_calls, list):
        for idx, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, dict):
                continue
            function_def = tool_call.get("function") or {}
            arguments = function_def.get("arguments", "")
            if not isinstance(arguments, str):
                arguments = _safe_json_dumps(arguments)
            output.append({
                "type": "function_call",
                "id": tool_call.get("id") or f"fc_{uuid4().hex[:12]}_{idx}",
                "call_id": tool_call.get("id") or f"call_{uuid4().hex[:12]}_{idx}",
                "name": function_def.get("name", "tool_call"),
                "arguments": arguments,
                "status": "completed",
            })

    if not output:
        output.append({
            "type": "message",
            "id": f"msg_{uuid4().hex[:12]}",
            "status": "completed",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": "",
                "annotations": [],
            }],
        })

    return output


def _chat_response_to_responses_object(chat_json: dict, requested_model: str) -> dict:
    choices = chat_json.get("choices") or []
    first_choice = choices[0] if choices else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    if not isinstance(message, dict):
        message = {}

    output = _chat_choice_to_responses_output(message)
    output_text = ""
    for item in output:
        if item.get("type") == "message":
            content = item.get("content") or []
            if content and isinstance(content[0], dict):
                output_text = content[0].get("text", "")
                break

    usage = chat_json.get("usage") if isinstance(chat_json.get("usage"), dict) else None
    response = {
        "id": chat_json.get("id") or f"resp_{uuid4().hex[:12]}",
        "object": "response",
        "status": "completed",
        "model": requested_model,
        "output": output,
        "output_text": output_text,
        "parallel_tool_calls": len([item for item in output if item.get("type") == "function_call"]) > 1,
    }
    if usage:
        response["usage"] = usage
    return response


def _sse_event(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _iter_responses_stream_events(response_obj: dict) -> Iterable[bytes]:
    response_id = response_obj["id"]

    yield _sse_event("response.created", {
        "type": "response.created",
        "response": {
            "id": response_id,
            "object": "response",
            "status": "in_progress",
            "model": response_obj.get("model"),
            "output": [],
        },
    })

    for output_index, item in enumerate(response_obj.get("output", [])):
        item_type = item.get("type")
        if item_type == "message":
            item_id = item.get("id") or f"msg_{uuid4().hex[:12]}"
            text = ""
            content = item.get("content") or []
            if content and isinstance(content[0], dict):
                text = content[0].get("text", "")

            yield _sse_event("response.output_item.added", {
                "type": "response.output_item.added",
                "response_id": response_id,
                "output_index": output_index,
                "item": {
                    "id": item_id,
                    "type": "message",
                    "status": "in_progress",
                    "role": "assistant",
                    "content": [],
                },
            })
            yield _sse_event("response.content_part.added", {
                "type": "response.content_part.added",
                "response_id": response_id,
                "item_id": item_id,
                "output_index": output_index,
                "content_index": 0,
                "part": {
                    "type": "output_text",
                    "text": "",
                    "annotations": [],
                },
            })
            if text:
                yield _sse_event("response.output_text.delta", {
                    "type": "response.output_text.delta",
                    "response_id": response_id,
                    "item_id": item_id,
                    "output_index": output_index,
                    "content_index": 0,
                    "delta": text,
                })
            yield _sse_event("response.output_text.done", {
                "type": "response.output_text.done",
                "response_id": response_id,
                "item_id": item_id,
                "output_index": output_index,
                "content_index": 0,
                "text": text,
            })
            yield _sse_event("response.content_part.done", {
                "type": "response.content_part.done",
                "response_id": response_id,
                "item_id": item_id,
                "output_index": output_index,
                "content_index": 0,
                "part": {
                    "type": "output_text",
                    "text": text,
                    "annotations": [],
                },
            })
            yield _sse_event("response.output_item.done", {
                "type": "response.output_item.done",
                "response_id": response_id,
                "output_index": output_index,
                "item": item,
            })
            continue

        if item_type == "function_call":
            item_id = item.get("id") or f"fc_{uuid4().hex[:12]}"
            arguments = item.get("arguments", "")
            yield _sse_event("response.output_item.added", {
                "type": "response.output_item.added",
                "response_id": response_id,
                "output_index": output_index,
                "item": {
                    "id": item_id,
                    "type": "function_call",
                    "status": "in_progress",
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": "",
                },
            })
            if arguments:
                yield _sse_event("response.function_call_arguments.delta", {
                    "type": "response.function_call_arguments.delta",
                    "response_id": response_id,
                    "item_id": item_id,
                    "output_index": output_index,
                    "delta": arguments,
                })
            yield _sse_event("response.function_call_arguments.done", {
                "type": "response.function_call_arguments.done",
                "response_id": response_id,
                "item_id": item_id,
                "output_index": output_index,
                "arguments": arguments,
            })
            yield _sse_event("response.output_item.done", {
                "type": "response.output_item.done",
                "response_id": response_id,
                "output_index": output_index,
                "item": item,
            })

    yield _sse_event("response.completed", {
        "type": "response.completed",
        "response": response_obj,
    })


def _openai_model_catalog_response() -> dict:
    upstream = get_upstream_for_openai()
    model_ids: list[str] = []

    def _add(model_id: Optional[str]):
        if isinstance(model_id, str) and model_id and model_id not in model_ids:
            model_ids.append(model_id)

    _add(upstream.get("default_model"))
    for model_id in (upstream.get("model_map") or {}).keys():
        _add(model_id)
    for model_id in (upstream.get("model_map") or {}).values():
        _add(model_id)

    default_tier = os.getenv("OMNIMEMORA_DEFAULT_SERVICE_TIER", "standard").strip() or "standard"
    tier_switch_enabled = os.getenv("OMNIMEMORA_SERVICE_TIER_SWITCH_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }

    data = [{
        "id": model_id,
        "object": "model",
        "created": 0,
        "owned_by": "omnimemora",
        # Minimal capability metadata for GUI feature gating.
        "capabilities": {
            "responses": True,
            "chat_completions": True,
            "streaming": True,
            "model_selection": True,
            "service_tier_switch": tier_switch_enabled,
        },
        "default_service_tier": default_tier,
    } for model_id in model_ids]

    return {
        "object": "list",
        "data": data,
    }


def _capability_limits_payload() -> dict:
    default_tier = os.getenv("OMNIMEMORA_DEFAULT_SERVICE_TIER", "standard").strip() or "standard"
    tier_switch_enabled = os.getenv("OMNIMEMORA_SERVICE_TIER_SWITCH_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    monthly_token_limit = int(os.getenv("OMNIMEMORA_GUI_MONTHLY_TOKEN_LIMIT", "5000000"))
    monthly_token_used = int(os.getenv("OMNIMEMORA_GUI_MONTHLY_TOKEN_USED", "0"))
    remaining = monthly_token_limit - monthly_token_used
    return {
        "object": "limits",
        "model_selection_enabled": True,
        "service_tier_switch_enabled": tier_switch_enabled,
        "usage_visibility_enabled": True,
        "default_service_tier": default_tier,
        "service_tiers": ["standard", "priority"] if tier_switch_enabled else [default_tier],
        "rate_limits": {
            "requests_per_minute": int(config.rate_limit_per_minute),
        },
        "token_limits": {
            "period": "monthly",
            "limit": monthly_token_limit,
            "used": monthly_token_used,
            "remaining": remaining if remaining >= 0 else 0,
        },
    }


def _capability_account_payload() -> dict:
    return {
        "object": "account",
        "id": os.getenv("OMNIMEMORA_GUI_ACCOUNT_ID", "omnimemora-local"),
        "status": "active",
        "plan": os.getenv("OMNIMEMORA_GUI_PLAN", "local_gateway"),
        "features": {
            "model_selection": True,
            "usage_display": True,
            "service_tier_switch": os.getenv("OMNIMEMORA_SERVICE_TIER_SWITCH_ENABLED", "true").strip().lower() in {
                "1", "true", "yes", "on",
            },
        },
    }


def _capability_entitlements_payload() -> dict:
    tier_switch_enabled = os.getenv("OMNIMEMORA_SERVICE_TIER_SWITCH_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    return {
        "object": "list",
        "data": [
            {"id": "model_selection", "object": "entitlement", "enabled": True},
            {"id": "usage_display", "object": "entitlement", "enabled": True},
            {"id": "service_tier_switch", "object": "entitlement", "enabled": tier_switch_enabled},
        ],
    }


def _capability_session_payload() -> dict:
    default_tier = os.getenv("OMNIMEMORA_DEFAULT_SERVICE_TIER", "standard").strip() or "standard"
    account_id = os.getenv("OMNIMEMORA_GUI_ACCOUNT_ID", "omnimemora-local")
    user_id = os.getenv("OMNIMEMORA_GUI_USER_ID", account_id)
    return {
        "object": "session",
        "id": f"session-{account_id}",
        "user": {
            "id": user_id,
            "account_id": account_id,
        },
        "account": {
            "id": account_id,
            "plan": os.getenv("OMNIMEMORA_GUI_PLAN", "local_gateway"),
        },
        "plan": os.getenv("OMNIMEMORA_GUI_PLAN", "local_gateway"),
        "capabilities": {
            "model_selection": True,
            "usage_display": True,
            "service_tier_switch": True,
        },
        "default_service_tier": default_tier,
        "models": {
            "visibility": "all",
        },
    }


# ============================================================================
# Streaming 代理
# ============================================================================

async def _stream_response(
    upstream_resp: httpx.Response,
    media_type: str = "text/event-stream",
) -> AsyncIterator[bytes]:
    """Preserve upstream streaming bytes exactly, including SSE delimiters."""
    async for chunk in upstream_resp.aiter_bytes():
        if chunk:
            yield chunk


async def _close_streaming_upstream(
    upstream_resp: httpx.Response,
    client: httpx.AsyncClient,
) -> None:
    try:
        await upstream_resp.aclose()
    finally:
        await client.aclose()


def _streaming_proxy_response(
    upstream_resp: httpx.Response,
    client: httpx.AsyncClient,
    fallback_media_type: str = "text/event-stream",
) -> StreamingResponse:
    content_type = upstream_resp.headers.get("content-type") or fallback_media_type
    response = StreamingResponse(
        _stream_response(upstream_resp, media_type=content_type),
        media_type=content_type,
        status_code=upstream_resp.status_code,
        background=BackgroundTask(_close_streaming_upstream, upstream_resp, client),
    )
    _copy_upstream_headers_to_response(response, upstream_resp.headers)
    _log_upstream_final_comparison(
        request_id=None,
        route_label="streaming_passthrough",
        upstream_resp=upstream_resp,
        final_response=response,
    )
    return response


def _copy_upstream_headers_to_response(response: Response, upstream_headers: httpx.Headers) -> None:
    """Copy upstream headers while dropping hop-by-hop transport headers."""
    for key, value in upstream_headers.multi_items():
        lower = key.lower()
        if lower in _HOP_BY_HOP_RESPONSE_HEADERS:
            continue
        response.headers.append(key, value)


def _extract_usage_snapshot_from_bytes(raw: bytes) -> Optional[str]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    usage = parsed.get("usage")
    if isinstance(usage, dict):
        try:
            return json.dumps(usage, ensure_ascii=False, sort_keys=True)
        except Exception:
            return "<dict>"
    return None


def _log_upstream_final_comparison(
    *,
    request_id: Optional[str],
    route_label: str,
    upstream_resp: httpx.Response,
    final_response: Response,
) -> None:
    upstream_usage: Optional[str] = None
    if not isinstance(final_response, StreamingResponse):
        upstream_usage = _extract_usage_snapshot_from_bytes(upstream_resp.content)
    final_usage: Optional[str] = None
    if isinstance(final_response, JSONResponse):
        final_body = getattr(final_response, "body", b"")
        if isinstance(final_body, (bytes, bytearray)):
            final_usage = _extract_usage_snapshot_from_bytes(bytes(final_body))
    elif isinstance(final_response, Response):
        final_body = getattr(final_response, "body", b"")
        if isinstance(final_body, (bytes, bytearray)):
            final_usage = _extract_usage_snapshot_from_bytes(bytes(final_body))

    upstream_rate_limit = {
        "x-ratelimit-limit": upstream_resp.headers.get("x-ratelimit-limit"),
        "x-ratelimit-remaining": upstream_resp.headers.get("x-ratelimit-remaining"),
    }
    final_rate_limit = {
        "x-ratelimit-limit": final_response.headers.get("x-ratelimit-limit"),
        "x-ratelimit-remaining": final_response.headers.get("x-ratelimit-remaining"),
    }
    req = request_id or "-"
    loguru.logger.info(
        f"[LLM_PROXY/PASSTHROUGH_COMPARE] request_id={req} route={route_label} "
        f"upstream_status={upstream_resp.status_code} final_status={final_response.status_code} "
        f"upstream_usage={upstream_usage or 'none'} final_usage={final_usage or 'none'} "
        f"upstream_rate_limit={upstream_rate_limit} final_rate_limit={final_rate_limit}"
    )


def _build_passthrough_response(
    *,
    request_id: str,
    route_label: str,
    upstream_resp: httpx.Response,
    fallback_media_type: str,
) -> Response:
    content_type = upstream_resp.headers.get("content-type") or fallback_media_type
    response = Response(
        content=upstream_resp.content,
        media_type=content_type,
        status_code=upstream_resp.status_code,
    )
    _copy_upstream_headers_to_response(response, upstream_resp.headers)
    _log_upstream_final_comparison(
        request_id=request_id,
        route_label=route_label,
        upstream_resp=upstream_resp,
        final_response=response,
    )
    return response


# ============================================================================
# Anthropic-compatible message endpoints
# ============================================================================

async def _proxy_anthropic_messages(request: Request, route_label: str):
    """Handle Anthropic Messages requests across legacy and official paths."""
    request_ctx = get_request_context(request)
    request_id = request_ctx["request_id"]
    trace_id = request_ctx["trace_id"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    explicit_agent = (
        body.get("agent_id")
        or body.get("agent")
        or request.headers.get("x-omnimemora-agent")
        or request.headers.get("x-agent-id")
        or request.headers.get("x-agent-family")
    )
    if explicit_agent:
        resolved_explicit = _agent_identity.resolve_canonical_agent_id(str(explicit_agent).strip().lower())
        explicit_agent = None if resolved_explicit == "unknown" else resolved_explicit
    if explicit_agent:
        agent_id = explicit_agent
    else:
        detected_agent = detect_agent(request, body)
        path_lower = str(request.url.path).lower()
        model_hint = str(body.get("model", "") or "").lower()
        user_agent = (request.headers.get("user-agent") or "").lower()
        payload_hint = str(body).lower()
        # OpenClaw anthropic gateway fallback:
        # keep unknown requests from being gated out when OpenClaw metadata is
        # present but not canonicalized.
        if detected_agent == "unknown":
            looks_like_openclaw = (
                path_lower == "/llm/v1/messages"
                or "openclaw" in user_agent
                or "openclaw-control-ui" in payload_hint
                or ("minimax" in model_hint and path_lower in ("/llm/v1/messages", "/v1/messages", "/llm/anthropic"))
            )
            agent_id = "openclaw" if looks_like_openclaw else detected_agent
        else:
            agent_id = detected_agent
    model = body.get("model", "unknown")
    is_streaming = body.get("stream", False)
    _record_event(agent_id, "proxy_request", request_id, route_label, model, "received", trace_id=trace_id)
    _trace_anthropic_payload(
        request_id,
        "inbound",
        body,
        {"agent_id": agent_id, "route": route_label},
    )

    loguru.logger.info(
        f"[LLM_PROXY/ANTHROPIC] request_id={request_id} agent={agent_id} "
        f"model={model} streaming={is_streaming}"
    )

    upstream = get_upstream_for_anthropic(model)
    truth_meta: Optional[dict] = None
    if not _routing_enabled_for_agent(agent_id):
        loguru.logger.info(
            f"[LLM_PROXY/ANTHROPIC] request_id={request_id} agent={agent_id} routing=off passthrough=true"
        )
        compiled_body = dict(body)
        compile_meta = _build_route_disabled_compile_meta()
        upstream_model = resolve_anthropic_upstream_model(model, upstream)
        upstream_base = upstream["base_url"]
    else:
        compile_input = {**body, "_path": route_label}
        compiled_body, compile_meta, contract, truth_meta = await _get_compile_orchestrator().run_anthropic_compile_and_resolve(
            payload=compile_input,
            agent_id=agent_id,
            upstream=upstream,
            route=route_label,
            requested_model=model,
            request_id=request_id,
            trace_id=trace_id,
        )
        upstream_model = contract.model_resolved or resolve_anthropic_upstream_model(model, upstream)
        upstream_base = contract.base_url_resolved or upstream["base_url"]

    _trace_anthropic_payload(
        request_id,
        "post_compile",
        compiled_body,
        {"agent_id": agent_id, "route": route_label, "compile_meta": compile_meta},
    )

    compiled_body["model"] = upstream_model
    headers = {
        "Content-Type": "application/json",
        "x-api-key": upstream["api_key"],
        "anthropic-version": "2023-06-01",
    }

    loguru.logger.info(
        f"[LLM_PROXY/ANTHROPIC] request_id={request_id} requested_model={model} "
        f"upstream_model={compiled_body['model']} upstream_base={upstream_base}"
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(upstream["timeout_seconds"], connect=15.0)
        ) as client:
            upstream_resp = await client.post(
                f"{upstream_base}/v1/messages",
                json=compiled_body,
                headers=headers,
            )

            if upstream_resp.status_code >= 400:
                upstream_url = f"{upstream_base}/v1/messages"
                status_code = upstream_resp.status_code
                error_type = _classify_upstream_error(status_code, None)
                error_msg = upstream_resp.text[:300]
                _log_upstream_failure(
                    request_id=request_id,
                    upstream_url=upstream_url,
                    error_type=error_type,
                    status_code=status_code,
                    error_message=error_msg,
                    agent_id=agent_id,
                    route=route_label,
                    model=model,
                )
                _trace_anthropic_status(
                    request_id,
                    "upstream_response",
                    status_code,
                    upstream_resp.text[:500],
                )
                # Re-record compile event with actual proxy outcome (P1-2 fix)
                _record_compile_event(
                    request_id, agent_id, route_label, model,
                    compile_meta, proxy_status="failed", proxy_status_code=status_code,
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                _record_event(
                    agent_id, "proxy_error", request_id, route_label, model,
                    "failed", status_code,
                    error=f"{error_type}|{error_msg[:150]}",
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                # P1-1: annotate error body so Claude Code knows it's a Gateway-upstream issue
                error_body = _annotate_upstream_error(
                    raw_body=upstream_resp.text,
                    status_code=status_code,
                    error_type=error_type,
                )
                return JSONResponse(
                    content=error_body,
                    status_code=status_code,
                )

            _record_event(
                agent_id, "proxy_response", request_id, route_label, model,
                "success", upstream_resp.status_code,
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            _trace_anthropic_status(
                request_id,
                "upstream_response",
                upstream_resp.status_code,
            )

            if is_streaming:
                response = StreamingResponse(
                    _stream_response(upstream_resp),
                    media_type="text/event-stream",
                    status_code=upstream_resp.status_code,
                )
                _copy_upstream_headers_to_response(response, upstream_resp.headers)
                _log_upstream_final_comparison(
                    request_id=request_id,
                    route_label=route_label,
                    upstream_resp=upstream_resp,
                    final_response=response,
                )
                return response
            else:
                return _build_passthrough_response(
                    request_id=request_id,
                    route_label=route_label,
                    upstream_resp=upstream_resp,
                    fallback_media_type="application/json",
                )

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response else None
        upstream_url = f"{upstream_base}/v1/messages"
        error_type = _classify_upstream_error(status_code, e)
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=status_code,
            error_message=error_msg,
            agent_id=agent_id,
            route=route_label,
            model=model,
        )
        _record_compile_event(
            request_id, agent_id, route_label, model,
            compile_meta, proxy_status="failed", proxy_status_code=status_code,
            truth_meta=truth_meta,
            trace_id=trace_id,
        )
        _record_event(
            agent_id, "proxy_error", request_id, route_label, model,
            "error", status_code,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
            trace_id=trace_id,
        )
        if e.response:
            error_body = _annotate_upstream_error(
                raw_body=e.response.text,
                status_code=status_code,
                error_type=error_type,
            )
            return JSONResponse(content=error_body, status_code=status_code)
        return JSONResponse(status_code=502, content={"error": f"{error_type}|{error_msg}"})

    except httpx.TimeoutException as e:
        upstream_url = f"{upstream_base}/v1/messages"
        error_type = UPSTREAM_ERROR_TYPES["upstream_timeout"]
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=None,
            error_message=error_msg,
            agent_id=agent_id,
            route=route_label,
            model=model,
        )
        _record_compile_event(
            request_id, agent_id, route_label, model,
            compile_meta, proxy_status="failed", proxy_status_code=None,
            truth_meta=truth_meta,
        )
        _record_event(
            agent_id, "proxy_error", request_id, route_label, model,
            "error", None,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
        )
        loguru.logger.error(f"[LLM_PROXY/ANTHROPIC] upstream timeout: {e}")
        error_body = _annotate_upstream_error(
            raw_body=str(e),
            status_code=None,
            error_type=error_type,
        )
        return JSONResponse(status_code=504, content=error_body)

    except Exception as e:
        upstream_url = f"{upstream_base}/v1/messages"
        error_type = UPSTREAM_ERROR_TYPES["proxy_internal_error"]
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=None,
            error_message=error_msg,
            agent_id=agent_id,
            route=route_label,
            model=model,
        )
        _record_compile_event(
            request_id, agent_id, route_label, model,
            compile_meta, proxy_status="failed", proxy_status_code=None,
            truth_meta=truth_meta,
        )
        _record_event(
            agent_id, "proxy_error", request_id, route_label, model,
            "error", None,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
        )
        loguru.logger.error(f"[LLM_PROXY/ANTHROPIC] unexpected error: {e}")
        error_body = _annotate_upstream_error(
            raw_body=str(e),
            status_code=None,
            error_type=error_type,
        )
        return JSONResponse(status_code=500, content=error_body)


@router.post("/llm/anthropic")
async def proxy_anthropic(request: Request):
    """
    Claude Code legacy入口（Anthropic /v1/messages 格式）。
    支持 streaming 和非 streaming。
    """
    return await _proxy_anthropic_messages(request, "/llm/anthropic")


@router.post("/llm/v1/messages")
@router.post("/v1/messages")
async def proxy_anthropic_messages_compatible(request: Request):
    """
    Claude Code 官方 Anthropic Messages 兼容入口。
    Allows `ANTHROPIC_BASE_URL=<gateway>/llm` and `<gateway>`.
    """
    return await _proxy_anthropic_messages(request, str(request.url.path))


# ============================================================================
# OpenAI /llm/chat
# ============================================================================


@router.get("/llm/models")
@router.get("/llm/v1/models")
@router.get("/v1/models")
async def list_openai_models():
    return JSONResponse(content=_openai_model_catalog_response())


@router.get("/limits")
@router.get("/v1/limits")
async def get_limits_capability():
    return JSONResponse(content=_capability_limits_payload())


@router.get("/account")
@router.get("/v1/account")
async def get_account_capability():
    return JSONResponse(content=_capability_account_payload())


@router.get("/entitlements")
@router.get("/v1/entitlements")
async def get_entitlements_capability():
    return JSONResponse(content=_capability_entitlements_payload())


@router.get("/session")
@router.get("/v1/session")
async def get_session_capability():
    return JSONResponse(content=_capability_session_payload())


@router.post("/llm/chat")
@router.post("/llm/chat/completions")
@router.post("/llm/v1/chat/completions")
@router.post("/llm/api/chat")
async def proxy_openai_chat(request: Request):
    """
    OpenClaw / Codex HTTP 入口（OpenAI /v1/chat/completions 格式）。
    支持 streaming 和非 streaming。
    """
    request_ctx = get_request_context(request)
    request_id = request_ctx["request_id"]
    trace_id = request_ctx["trace_id"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    explicit_agent = (
        body.get("agent_id")
        or body.get("agent")
        or request.headers.get("x-omnimemora-agent")
        or request.headers.get("x-agent-id")
        or request.headers.get("x-agent-family")
    )
    if explicit_agent:
        resolved_explicit = _agent_identity.resolve_canonical_agent_id(str(explicit_agent).strip().lower())
        explicit_agent = None if resolved_explicit == "unknown" else resolved_explicit
    if explicit_agent:
        agent_id = explicit_agent
    else:
        detected_agent = detect_agent(request, body)
        path_lower = str(request.url.path).lower()
        # OpenClaw CLI/gateway 请求识别增强：
        # - 当 detect_agent 返回 unknown 时，只要路径是 /llm/* 或 OpenAI chat 兼容路径
        #   且无其他明确 agent 标识，优先判定为 openclaw
        if detected_agent == "unknown":
            if path_lower.startswith("/llm/"):
                agent_id = "openclaw"
            elif path_lower in ("/v1/chat/completions", "/chat/completions"):
                # OpenClaw 和 Codex 常用路径，无明确 agent 时优先 openclaw
                agent_id = "openclaw"
            else:
                agent_id = detected_agent
        else:
            agent_id = detected_agent
    model = body.get("model", config.openai_default_model)
    is_streaming = body.get("stream", False)
    provider_base = request.headers.get("x-provider-base-url")
    api_key_override = request.headers.get("authorization", "").replace("Bearer ", "")

    _record_event(agent_id, "proxy_request", request_id, "/llm/chat", model, "received", trace_id=trace_id)
    _mark_quota_audit(request, upstream_url=None, action="intercepted")

    loguru.logger.info(
        f"[LLM_PROXY/OPENAI] request_id={request_id} agent={agent_id} "
        f"model={model} streaming={is_streaming}"
    )

    # Phase 3: Compile + Truth Resolution + Event Recording
    # Routing decision stays at ingress layer: check here before delegating to application layer
    if not _routing_enabled_for_agent(agent_id):
        loguru.logger.info(
            f"[LLM_PROXY/OPENAI] request_id={request_id} agent={agent_id} routing=off passthrough=true"
        )
        upstream = get_upstream_for_openai(provider_base)
        # Use _compile_or_passthrough_for_route which handles routing-off correctly
        compiled_body, compile_meta = await _compile_or_passthrough_for_route(
            payload=body,
            agent_id=agent_id,
            request_id=request_id,
            trace_id=trace_id,
        )
        # Passthrough: original payload, no compile, no application-layer involvement
        upstream_model = resolve_openai_upstream_model(model, upstream)
        compiled_body["model"] = upstream_model
        compiled_body = _normalize_openai_upstream_payload(compiled_body)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key_override or upstream['api_key']}",
        }
        upstream_url = f"{upstream['base_url']}/chat/completions"
        _mark_quota_audit(request, upstream_url=upstream_url, action="proxied")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(upstream["timeout_seconds"], connect=15.0)
        ) as client:
            upstream_resp = await client.post(upstream_url, json=compiled_body, headers=headers)
            return _passthrough_response(
                request_id=request_id,
                route="/llm/chat",
                upstream_resp=upstream_resp,
            )

    # Routing is on: delegate to application layer for compile + truth resolution
    upstream = get_upstream_for_openai(provider_base)
    compiled_body, compile_meta, contract, truth_meta = await _get_compile_orchestrator().run_compile_and_resolve(
        payload=body,
        agent_id=agent_id,
        upstream=upstream,
        api_key_override=api_key_override,
        route="/llm/chat",
        requested_model=model,
        wire_api_requested="chat_completions",
        provider_base=provider_base,
        provider_source="runtime_override" if provider_base else "product_policy_binding",
        base_url_source="runtime_override" if provider_base else "product_upstream_config",
        model_source="agent_payload_explicit",
        auth_source="",  # computed internally by run_compile_and_resolve
        policy_profile="openai_chat_default",
        request_id=request_id,
        trace_id=trace_id,
    )
    compiled_body["model"] = contract.model_resolved or model
    compiled_body = _normalize_openai_upstream_payload(compiled_body)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key_override or upstream['api_key']}",
    }
    upstream_url = f"{(contract.base_url_resolved or upstream['base_url'])}/chat/completions"
    _mark_quota_audit(request, upstream_url=upstream_url, action="proxied")
    streaming_client: Optional[httpx.AsyncClient] = None
    streaming_resp: Optional[httpx.Response] = None

    try:
        if is_streaming:
            streaming_client = httpx.AsyncClient(
                timeout=httpx.Timeout(upstream["timeout_seconds"], connect=15.0)
            )
            upstream_req = streaming_client.build_request(
                "POST",
                upstream_url,
                json=compiled_body,
                headers=headers,
            )
            streaming_resp = await streaming_client.send(upstream_req, stream=True)
            upstream_resp = streaming_resp
        else:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(upstream["timeout_seconds"], connect=15.0)
            ) as client:
                upstream_resp = await client.post(
                    upstream_url,
                    json=compiled_body,
                    headers=headers,
                )

                if upstream_resp.status_code >= 400:
                    status_code = upstream_resp.status_code
                    error_type = _classify_upstream_error(status_code, None)
                    error_msg = upstream_resp.text[:300]
                    _log_upstream_failure(
                        request_id=request_id,
                        upstream_url=upstream_url,
                        error_type=error_type,
                        status_code=status_code,
                        error_message=error_msg,
                        agent_id=agent_id,
                        route="/llm/chat",
                        model=model,
                    )
                    # Re-record compile event with actual proxy outcome (P1-2 fix)
                    _record_compile_event(
                        request_id, agent_id, "/llm/chat", model,
                        compile_meta, proxy_status="failed", proxy_status_code=status_code,
                        truth_meta=truth_meta,
                        trace_id=trace_id,
                    )
                    _record_event(
                        agent_id, "proxy_error", request_id, "/llm/chat", model,
                        "failed", status_code,
                        error=f"{error_type}|{error_msg[:150]}",
                        truth_meta=truth_meta,
                        trace_id=trace_id,
                    )
                    # P1-1: annotate error body for OpenAI-compatible clients
                    error_body = _annotate_upstream_error(
                        raw_body=upstream_resp.text,
                        status_code=status_code,
                        error_type=error_type,
                    )
                    return JSONResponse(content=error_body, status_code=status_code)

                _record_event(
                    agent_id, "proxy_response", request_id, "/llm/chat", model,
                    "success", upstream_resp.status_code,
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                return _build_passthrough_response(
                    request_id=request_id,
                    route_label="/llm/chat",
                    upstream_resp=upstream_resp,
                    fallback_media_type="application/json",
                )

        if upstream_resp.status_code >= 400:
            status_code = upstream_resp.status_code
            error_text = (await upstream_resp.aread()).decode("utf-8", errors="replace")
            error_type = _classify_upstream_error(status_code, None)
            error_msg = error_text[:300]
            _log_upstream_failure(
                request_id=request_id,
                upstream_url=upstream_url,
                error_type=error_type,
                status_code=status_code,
                error_message=error_msg,
                agent_id=agent_id,
                route="/llm/chat",
                model=model,
            )
            _record_compile_event(
                request_id, agent_id, "/llm/chat", model,
                compile_meta, proxy_status="failed", proxy_status_code=status_code,
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            _record_event(
                agent_id, "proxy_error", request_id, "/llm/chat", model,
                "failed", status_code,
                error=f"{error_type}|{error_msg[:150]}",
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            error_body = _annotate_upstream_error(
                raw_body=error_text,
                status_code=status_code,
                error_type=error_type,
            )
            await _close_streaming_upstream(upstream_resp, streaming_client)
            streaming_resp = None
            streaming_client = None
            return JSONResponse(content=error_body, status_code=status_code)

        _record_event(
            agent_id, "proxy_response", request_id, "/llm/chat", model,
            "success", upstream_resp.status_code,
            truth_meta=truth_meta,
            trace_id=trace_id,
        )
        # Read full body from streaming upstream then return non-streaming Response
        body = await upstream_resp.aread()
        content_type = upstream_resp.headers.get("content-type", "text/event-stream")
        response = Response(
            content=body,
            media_type=content_type,
            status_code=upstream_resp.status_code,
        )
        _copy_upstream_headers_to_response(response, upstream_resp.headers)
        _log_upstream_final_comparison(
            request_id=request_id,
            route_label="/llm/chat",
            upstream_resp=upstream_resp,
            final_response=response,
        )
        await _close_streaming_upstream(upstream_resp, streaming_client)
        streaming_resp = None
        streaming_client = None
        return response

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response else None
        error_type = _classify_upstream_error(status_code, e)
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=status_code,
            error_message=error_msg,
            agent_id=agent_id,
            route="/llm/chat",
            model=model,
        )
        _record_compile_event(
            request_id, agent_id, "/llm/chat", model,
            compile_meta, proxy_status="failed", proxy_status_code=status_code,
            truth_meta=truth_meta,
        )
        _record_event(
            agent_id, "proxy_error", request_id, "/llm/chat", model,
            "error", status_code,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
        )
        if e.response:
            error_body = _annotate_upstream_error(
                raw_body=e.response.text,
                status_code=status_code,
                error_type=error_type,
            )
            return JSONResponse(content=error_body, status_code=status_code)
        return JSONResponse(status_code=502, content={"error": f"{error_type}|{error_msg}"})

    except httpx.TimeoutException as e:
        upstream_url = f"{upstream['base_url']}/chat/completions"
        error_type = UPSTREAM_ERROR_TYPES["upstream_timeout"]
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=None,
            error_message=error_msg,
            agent_id=agent_id,
            route="/llm/chat",
            model=model,
        )
        _record_compile_event(
            request_id, agent_id, "/llm/chat", model,
            compile_meta, proxy_status="failed", proxy_status_code=None,
            truth_meta=truth_meta,
        )
        _record_event(
            agent_id, "proxy_error", request_id, "/llm/chat", model,
            "error", None,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
        )
        loguru.logger.error(f"[LLM_PROXY/OPENAI] upstream timeout: {e}")
        error_body = _annotate_upstream_error(
            raw_body=str(e),
            status_code=None,
            error_type=error_type,
        )
        return JSONResponse(status_code=504, content=error_body)

    except Exception as e:
        upstream_url = f"{upstream['base_url']}/chat/completions"
        error_type = UPSTREAM_ERROR_TYPES["proxy_internal_error"]
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=None,
            error_message=error_msg,
            agent_id=agent_id,
            route="/llm/chat",
            model=model,
        )
        _record_compile_event(
            request_id, agent_id, "/llm/chat", model,
            compile_meta, proxy_status="failed", proxy_status_code=None,
            truth_meta=truth_meta,
        )
        _record_event(
            agent_id, "proxy_error", request_id, "/llm/chat", model,
            "error", None,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
        )
        loguru.logger.error(f"[LLM_PROXY/OPENAI] unexpected error: {e}")
        error_body = _annotate_upstream_error(
            raw_body=str(e),
            status_code=None,
            error_type=error_type,
        )
        return JSONResponse(status_code=500, content=error_body)
    finally:
        if streaming_resp is not None and streaming_client is not None:
            await _close_streaming_upstream(streaming_resp, streaming_client)


# ============================================================================
# OpenAI Responses-compatible path for Codex
# ============================================================================

@router.post("/v1/responses")
@router.post("/v1/codex/responses")
async def proxy_v1_responses(request: Request):
    """
    Responses-compatible endpoint for Codex.
    Internally compiles and forwards as a non-streaming chat completion, then
    synthesizes a minimal Responses API object or SSE event sequence.
    """
    request_ctx = get_request_context(request)
    request_id = request_ctx["request_id"]
    trace_id = request_ctx["trace_id"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    agent_id = detect_agent(request, body)
    ingress_path = request.url.path or "/v1/responses"
    requested_model = body.get("model", config.openai_default_model)
    wants_stream = bool(body.get("stream", True))
    provider_base = request.headers.get("x-provider-base-url")
    authorization_header = request.headers.get("authorization", "")
    api_key_override = authorization_header.replace("Bearer ", "")

    _record_event(agent_id, "proxy_request", request_id, ingress_path, requested_model, "received", trace_id=trace_id)
    _mark_quota_audit(request, upstream_url=None, action="intercepted")

    chat_body = _responses_request_to_chat_body(body)

    loguru.logger.info(
        f"[LLM_PROXY/RESPONSES] request_id={request_id} agent={agent_id} "
        f"model={requested_model} stream={wants_stream}"
    )

    if _should_bypass_codex_gateway(agent_id):
        compiled_body = dict(chat_body)
        compile_meta = _build_codex_bypass_compile_meta()
        loguru.logger.warning(
            f"[LLM_PROXY/RESPONSES] request_id={request_id} agent={agent_id} "
            "compile/runtime/context bypassed by OMNIMEMORA_BYPASS_CODEX=1"
        )
    else:
        compiled_body, compile_meta = await _compile_or_passthrough_for_route(
            payload={**chat_body, "_path": ingress_path},
            agent_id=agent_id,
            request_id=request_id,
            trace_id=trace_id,
        )

    responses_upstream = _resolve_codex_responses_upstream(
        agent_id=agent_id,
        provider_base=provider_base,
        authorization_header=authorization_header,
    )
    if responses_upstream:
        responses_provider = infer_provider_name(responses_upstream["base_url"], "openai_compatible")
        responses_auth_source = None if responses_upstream.get("source") == "request_headers" else responses_upstream.get("source")
        contract, truth_meta = resolve_truth_contract(
            request_id=request_id,
            agent_id=agent_id,
            route=ingress_path,
            requested_model=requested_model,
            wire_api_requested="responses",
            provider_requested=responses_provider,
            base_url_requested=responses_upstream["base_url"],
            auth_requested=("runtime_authorization_header" if authorization_header else None),
            provider_source="runtime_override" if provider_base else ("agent_truth_bridge" if responses_auth_source else "product_policy_binding"),
            base_url_source="runtime_override" if provider_base else ("agent_truth_bridge" if responses_auth_source else "product_upstream_config"),
            model_source="agent_payload_explicit",
            auth_source=auth_source_from_values(
                explicit_authorization=bool(authorization_header),
                agent_truth_source=responses_auth_source,
                product_api_key_present=False,
            ),
            policy_profile="codex_responses_native",
            candidates_by_source={
                "agent_truth_bridge": {
                    "provider": responses_provider if responses_auth_source else None,
                    "base_url": responses_upstream["base_url"] if responses_auth_source else None,
                    "wire_api": "responses" if responses_auth_source else None,
                },
                "runtime_override": {
                    "base_url": provider_base,
                    "auth": "runtime_authorization_header" if authorization_header else None,
                },
                "provider_default": {
                    "provider": responses_provider,
                    "base_url": responses_upstream["base_url"],
                    "model": requested_model,
                    "wire_api": "responses",
                    "fallback": False,
                },
            },
            compile_enabled=bool(compile_meta),
        )
        _record_compile_event(
            request_id, agent_id, ingress_path, requested_model, compile_meta, truth_meta=truth_meta, trace_id=trace_id
        )
        rebuilt_body = _compiled_chat_to_responses_request(body, compiled_body)
        upstream_url = _normalize_responses_upstream_url(contract.base_url_resolved or responses_upstream["base_url"])
        _mark_quota_audit(request, upstream_url=upstream_url, action="proxied")
        headers = {
            "Content-Type": "application/json",
        }
        if responses_upstream.get("authorization"):
            headers["Authorization"] = responses_upstream["authorization"]

        loguru.logger.info(
            f"[LLM_PROXY/RESPONSES] request_id={request_id} requested_model={requested_model} "
            f"responses_upstream={upstream_url} source={responses_upstream.get('source')}"
        )

        streaming_client: Optional[httpx.AsyncClient] = None
        streaming_resp: Optional[httpx.Response] = None
        try:
            if wants_stream:
                streaming_client = httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=15.0))
                upstream_req = streaming_client.build_request(
                    "POST",
                    upstream_url,
                    json=rebuilt_body,
                    headers=headers,
                )
                streaming_resp = await streaming_client.send(upstream_req, stream=True)
                if streaming_resp.status_code >= 400:
                    error_text = (await streaming_resp.aread()).decode("utf-8", errors="ignore")
                    status_code = streaming_resp.status_code
                    error_type = _classify_upstream_error(status_code, None)
                    _log_upstream_failure(
                        request_id=request_id,
                        upstream_url=upstream_url,
                        error_type=error_type,
                        status_code=status_code,
                        error_message=error_text[:300],
                        agent_id=agent_id,
                        route=ingress_path,
                        model=requested_model,
                    )
                    _record_compile_event(
                        request_id, agent_id, ingress_path, requested_model,
                        compile_meta, proxy_status="failed", proxy_status_code=status_code,
                        truth_meta=truth_meta,
                        trace_id=trace_id,
                    )
                    _record_event(
                        agent_id, "proxy_error", request_id, ingress_path, requested_model,
                        "failed", status_code,
                        error=f"{error_type}|{error_text[:150]}",
                        truth_meta=truth_meta,
                        trace_id=trace_id,
                    )
                    error_body = _annotate_upstream_error(
                        raw_body=error_text,
                        status_code=status_code,
                        error_type=error_type,
                    )
                    return JSONResponse(content=error_body, status_code=status_code)

                _record_event(
                    agent_id, "proxy_response", request_id, ingress_path, requested_model,
                    "success", streaming_resp.status_code,
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                # Read full body from streaming upstream then return non-streaming Response
                body = await streaming_resp.aread()
                content_type = streaming_resp.headers.get("content-type", "text/event-stream")
                response = Response(
                    content=body,
                    media_type=content_type,
                    status_code=streaming_resp.status_code,
                )
                _copy_upstream_headers_to_response(response, streaming_resp.headers)
                _log_upstream_final_comparison(
                    request_id=request_id,
                    route_label=ingress_path,
                    upstream_resp=streaming_resp,
                    final_response=response,
                )
                await _close_streaming_upstream(streaming_resp, streaming_client)
                streaming_resp = None
                streaming_client = None
                return response

            async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=15.0)) as client:
                upstream_resp = await client.post(
                    upstream_url,
                    json=rebuilt_body,
                    headers=headers,
                )
            if upstream_resp.status_code >= 400:
                status_code = upstream_resp.status_code
                error_type = _classify_upstream_error(status_code, None)
                error_msg = upstream_resp.text[:300]
                _log_upstream_failure(
                    request_id=request_id,
                    upstream_url=upstream_url,
                    error_type=error_type,
                    status_code=status_code,
                    error_message=error_msg,
                    agent_id=agent_id,
                    route=ingress_path,
                    model=requested_model,
                )
                _record_compile_event(
                    request_id, agent_id, ingress_path, requested_model,
                    compile_meta, proxy_status="failed", proxy_status_code=status_code,
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                _record_event(
                    agent_id, "proxy_error", request_id, ingress_path, requested_model,
                    "failed", status_code,
                    error=f"{error_type}|{error_msg[:150]}",
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                error_body = _annotate_upstream_error(
                    raw_body=upstream_resp.text,
                    status_code=status_code,
                    error_type=error_type,
                )
                return JSONResponse(content=error_body, status_code=status_code)

            _record_event(
                agent_id, "proxy_response", request_id, ingress_path, requested_model,
                "success", upstream_resp.status_code,
                truth_meta=truth_meta,
            )
            return _build_passthrough_response(
                request_id=request_id,
                route_label=ingress_path,
                upstream_resp=upstream_resp,
                fallback_media_type="application/json",
            )
        except httpx.TimeoutException as e:
            error_type = UPSTREAM_ERROR_TYPES["upstream_timeout"]
            error_msg = str(e)[:300]
            _log_upstream_failure(
                request_id=request_id,
                upstream_url=upstream_url,
                error_type=error_type,
                status_code=None,
                error_message=error_msg,
                agent_id=agent_id,
                route=ingress_path,
                model=requested_model,
            )
            _record_compile_event(
                request_id, agent_id, ingress_path, requested_model,
                compile_meta, proxy_status="failed", proxy_status_code=None,
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            _record_event(
                agent_id, "proxy_error", request_id, ingress_path, requested_model,
                "error", None,
                error=f"{error_type}|{error_msg[:150]}",
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            error_body = _annotate_upstream_error(
                raw_body=str(e),
                status_code=None,
                error_type=error_type,
            )
            return JSONResponse(status_code=504, content=error_body)
        except Exception as e:
            error_type = UPSTREAM_ERROR_TYPES["proxy_internal_error"]
            error_msg = str(e)[:300]
            _log_upstream_failure(
                request_id=request_id,
                upstream_url=upstream_url,
                error_type=error_type,
                status_code=None,
                error_message=error_msg,
                agent_id=agent_id,
                route=ingress_path,
                model=requested_model,
            )
            _record_compile_event(
                request_id, agent_id, ingress_path, requested_model,
                compile_meta, proxy_status="failed", proxy_status_code=None,
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            _record_event(
                agent_id, "proxy_error", request_id, ingress_path, requested_model,
                "error", None,
                error=f"{error_type}|{error_msg[:150]}",
                truth_meta=truth_meta,
                trace_id=trace_id,
            )
            error_body = _annotate_upstream_error(
                raw_body=str(e),
                status_code=None,
                error_type=error_type,
            )
            return JSONResponse(status_code=500, content=error_body)
        finally:
            if streaming_resp is not None and streaming_client is not None:
                await _close_streaming_upstream(streaming_resp, streaming_client)

    upstream = get_upstream_for_openai(provider_base)
    upstream_model = resolve_openai_upstream_model(requested_model, upstream)
    contract, truth_meta = resolve_truth_contract(
        request_id=request_id,
        agent_id=agent_id,
        route=ingress_path,
        requested_model=requested_model,
        wire_api_requested="chat_completions",
        provider_requested=infer_provider_name(upstream.get("base_url", ""), upstream.get("provider", "openai_compatible")),
        base_url_requested=provider_base or upstream.get("base_url"),
        auth_requested=("runtime_authorization_header" if api_key_override else product_auth_ref_for_provider(upstream.get("provider", "openai_compatible"))),
        provider_source="runtime_override" if provider_base else "product_policy_binding",
        base_url_source="runtime_override" if provider_base else "product_upstream_config",
        model_source="agent_payload_explicit",
        auth_source=auth_source_from_values(
            explicit_authorization=bool(api_key_override),
            product_api_key_present=bool(upstream.get("api_key")),
        ),
        policy_profile="codex_responses_fallback",
        candidates_by_source={
            "product_policy_binding": {
                "provider": infer_provider_name(upstream.get("base_url", ""), upstream.get("provider", "openai_compatible")),
                "base_url": upstream.get("base_url"),
                "auth": product_auth_ref_for_provider(upstream.get("provider", "openai_compatible")),
                "wire_api": "chat_completions",
            },
            "runtime_override": {
                "base_url": provider_base,
                "auth": "runtime_authorization_header" if api_key_override else None,
            },
            "provider_default": {
                "provider": infer_provider_name(upstream.get("base_url", ""), upstream.get("provider", "openai_compatible")),
                "base_url": upstream.get("base_url"),
                "model": upstream_model,
                "auth": product_auth_ref_for_provider(upstream.get("provider", "openai_compatible")),
                "wire_api": "chat_completions",
                "fallback": True,
            },
        },
        compile_enabled=bool(compile_meta),
    )
    truth_meta["fallback_reason"] = "responses_upstream_unavailable"
    _record_compile_event(
        request_id, agent_id, ingress_path, requested_model, compile_meta, truth_meta=truth_meta, trace_id=trace_id
    )
    if config.trace_events_enabled:
        append_trace_event(
            build_trace_event(
                trace_id=trace_id,
                request_id=request_id,
                stage="bypass",
                path=ingress_path,
                status="fallback",
                agent_id=agent_id,
                details={"fallback_reason": "responses_upstream_unavailable"},
            )
        )
    compiled_body["model"] = contract.model_resolved or upstream_model
    compiled_body = _normalize_openai_upstream_payload(compiled_body)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key_override or upstream['api_key']}",
    }

    upstream_url = f"{(contract.base_url_resolved or upstream['base_url'])}/chat/completions"
    _mark_quota_audit(request, upstream_url=upstream_url, action="proxied_fallback")
    loguru.logger.info(
        f"[LLM_PROXY/RESPONSES] request_id={request_id} requested_model={requested_model} "
        f"upstream_model={upstream_model} upstream_base={upstream['base_url']}"
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(upstream["timeout_seconds"], connect=15.0)
        ) as client:
            upstream_resp = await client.post(
                upstream_url,
                json=compiled_body,
                headers=headers,
            )

            if upstream_resp.status_code >= 400:
                status_code = upstream_resp.status_code
                error_type = _classify_upstream_error(status_code, None)
                error_msg = upstream_resp.text[:300]
                _log_upstream_failure(
                    request_id=request_id,
                    upstream_url=upstream_url,
                    error_type=error_type,
                    status_code=status_code,
                    error_message=error_msg,
                    agent_id=agent_id,
                    route=ingress_path,
                    model=requested_model,
                )
                _record_compile_event(
                    request_id, agent_id, ingress_path, requested_model,
                    compile_meta, proxy_status="failed", proxy_status_code=status_code,
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                _record_event(
                    agent_id, "proxy_error", request_id, ingress_path, requested_model,
                    "failed", status_code,
                    error=f"{error_type}|{error_msg[:150]}",
                    truth_meta=truth_meta,
                    trace_id=trace_id,
                )
                error_body = _annotate_upstream_error(
                    raw_body=upstream_resp.text,
                    status_code=status_code,
                    error_type=error_type,
                )
                return JSONResponse(content=error_body, status_code=status_code)

            chat_json = upstream_resp.json()
            response_obj = _chat_response_to_responses_object(chat_json, requested_model)

            _record_event(
                agent_id, "proxy_response", request_id, ingress_path, requested_model,
                "success", upstream_resp.status_code,
                truth_meta=truth_meta,
                trace_id=trace_id,
            )

            if wants_stream:
                response = StreamingResponse(
                    iter(_iter_responses_stream_events(response_obj)),
                    media_type="text/event-stream",
                    status_code=upstream_resp.status_code,
                )
                _copy_upstream_headers_to_response(response, upstream_resp.headers)
                _log_upstream_final_comparison(
                    request_id=request_id,
                    route_label=ingress_path,
                    upstream_resp=upstream_resp,
                    final_response=response,
                )
                return response

            response = JSONResponse(content=response_obj, status_code=upstream_resp.status_code)
            _copy_upstream_headers_to_response(response, upstream_resp.headers)
            _log_upstream_final_comparison(
                request_id=request_id,
                route_label=ingress_path,
                upstream_resp=upstream_resp,
                final_response=response,
            )
            return response

    except httpx.TimeoutException as e:
        error_type = UPSTREAM_ERROR_TYPES["upstream_timeout"]
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=None,
            error_message=error_msg,
            agent_id=agent_id,
            route=ingress_path,
            model=requested_model,
        )
        _record_compile_event(
            request_id, agent_id, ingress_path, requested_model,
            compile_meta, proxy_status="failed", proxy_status_code=None,
            truth_meta=truth_meta,
            trace_id=trace_id,
        )
        _record_event(
            agent_id, "proxy_error", request_id, ingress_path, requested_model,
            "error", None,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
            trace_id=trace_id,
        )
        error_body = _annotate_upstream_error(
            raw_body=str(e),
            status_code=None,
            error_type=error_type,
        )
        return JSONResponse(status_code=504, content=error_body)

    except Exception as e:
        error_type = UPSTREAM_ERROR_TYPES["proxy_internal_error"]
        error_msg = str(e)[:300]
        _log_upstream_failure(
            request_id=request_id,
            upstream_url=upstream_url,
            error_type=error_type,
            status_code=None,
            error_message=error_msg,
            agent_id=agent_id,
            route=ingress_path,
            model=requested_model,
        )
        _record_compile_event(
            request_id, agent_id, ingress_path, requested_model,
            compile_meta, proxy_status="failed", proxy_status_code=None,
            truth_meta=truth_meta,
        )
        _record_event(
            agent_id, "proxy_error", request_id, ingress_path, requested_model,
            "error", None,
            error=f"{error_type}|{error_msg[:150]}",
            truth_meta=truth_meta,
        )
        error_body = _annotate_upstream_error(
            raw_body=str(e),
            status_code=None,
            error_type=error_type,
        )
        return JSONResponse(status_code=500, content=error_body)


# ============================================================================
# OpenAI 顯式路徑 /v1/chat/completions
# ============================================================================

@router.post("/v1/chat/completions")
async def proxy_v1_chat(request: Request):
    """
    標準 OpenAI /v1/chat/completions 端點。
    Claude Code / Codex / 其他 OpenAI 客戶端通用。
    """
    return await proxy_openai_chat(request)
