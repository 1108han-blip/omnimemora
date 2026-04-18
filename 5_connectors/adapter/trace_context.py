"""
trace_context.py - lightweight request/trace context helpers
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4
import time as _time


TRACE_HEADER = "X-OmniMemora-Trace-Id"
REQUEST_HEADER = "X-OmniMemora-Request-Id"


def ensure_request_trace(request: Any) -> Dict[str, str]:
    state = getattr(request, "state", None)

    request_id = getattr(state, "request_id", "") if state is not None else ""
    if not request_id:
        request_id = uuid4().hex[:12]
        if state is not None:
            state.request_id = request_id

    trace_id = getattr(state, "trace_id", "") if state is not None else ""
    if not trace_id:
        incoming_trace = ""
        try:
            incoming_trace = request.headers.get(TRACE_HEADER, "") or request.headers.get(REQUEST_HEADER, "")
        except Exception:
            incoming_trace = ""
        trace_id = incoming_trace.strip() or request_id
        if state is not None:
            state.trace_id = trace_id

    return {
        "request_id": request_id,
        "trace_id": trace_id,
    }


def bind_runtime_trace(
    *,
    request_id: Optional[str],
    trace_id: Optional[str],
    path: Optional[str],
    agent_id: Optional[str],
) -> Dict[str, Optional[str]]:
    return {
        "request_id": (request_id or "").strip() or uuid4().hex[:12],
        "trace_id": (trace_id or request_id or "").strip() or uuid4().hex[:12],
        "path": (path or "").strip(),
        "agent_id": (agent_id or "").strip(),
    }


def ensure_request_context(request: Any) -> Dict[str, str]:
    """Compatibility wrapper: returns a dict with request_id, trace_id and path."""
    ids = ensure_request_trace(request)
    path = ""
    try:
        path = str(getattr(getattr(request, "url", None), "path", "") or "")
    except Exception:
        path = ""
    return {
        "request_id": ids.get("request_id", ""),
        "trace_id": ids.get("trace_id", ""),
        "path": path,
    }


def get_request_context(request: Any) -> Dict[str, str]:
    """Alias for ensure_request_context used across the codebase."""
    return ensure_request_context(request)


def build_trace_event(
    *,
    trace_id: Optional[str],
    request_id: Optional[str],
    stage: str,
    path: Optional[str] = None,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    error_type: Optional[str] = None,
    details: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Construct a simple trace event dict for append_trace_event consumers."""
    return {
        "timestamp": int(_time.time()),
        "trace_id": (trace_id or request_id or "").strip() or uuid4().hex[:12],
        "request_id": (request_id or "").strip() or uuid4().hex[:12],
        "stage": stage,
        "path": (path or "").strip() if path is not None else "",
        "status": status or "",
        "agent_id": agent_id or "",
        "error_type": error_type,
        "details": details or {},
    }
