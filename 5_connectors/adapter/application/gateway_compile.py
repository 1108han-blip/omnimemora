"""
gateway_compile.py — Gateway Compile Orchestrator
===================================================
Phase 3 Task A: Single orchestration adapter between Gateway ingress
and existing runtime core compile logic.

Responsibilities:
  - normalize inbound LLM request into compile input
  - resolve agent identity
  - call memory search + runtime compile
  - produce compiled request payload
  - return compile metadata
  - expose fallback modes when compile cannot run

Three modes (no silent pass-through):
  compile_success  — compile ran OK, upstream receives compiled payload
  compile_skipped  — known unsupported shape, upstream receives original payload
  compile_failed   — compile attempted but failed, upstream receives original payload
"""
from __future__ import annotations

import time as _time
from typing import Any, Dict, List, Optional, Tuple

import loguru
from ..config import config
from ..request_classifier import extract_user_visible_query
from ..trace_context import build_trace_event
from ..trace_events import append_trace_event


# ============================================================================
# Task A-1: Request Normalization
# ============================================================================

def normalize_inbound_request(payload: dict, agent_id: str) -> dict:
    """
    Convert raw OpenAI/Anthropic-compatible request body into internal compile format.

    Args:
        payload: Raw request body from llm_proxy.py
        agent_id: Detected agent identifier

    Returns:
        {
            "messages": [...],        # original messages array
            "query": str,             # extracted primary query
            "model": str,
            "is_streaming": bool,
            "protocol": "openai" | "anthropic",
            "can_compile": bool,
            "skip_reason": Optional[str],
        }
    """
    messages = payload.get("messages", [])
    model = payload.get("model", "unknown")
    is_streaming = payload.get("stream", False)
    request_path = str(payload.get("_path", ""))
    protocol = "openai"
    if any(segment in request_path for segment in ("/llm/anthropic", "/llm/v1/messages", "/v1/messages")):
        protocol = "anthropic"

    # Extract primary query from messages
    query = _extract_query_from_messages(messages)

    # Determine compile eligibility
    can_compile, skip_reason = _assess_compile_eligibility(payload, messages, query)
    task_type = _classify_task_type(query)

    return {
        "messages": messages,
        "query": query,
        "model": model,
        "is_streaming": is_streaming,
        "protocol": protocol,
        "can_compile": can_compile,
        "skip_reason": skip_reason,
        "original_token_estimate": _estimate_original_tokens(payload, messages),
        "task_type": task_type,
    }


def _content_to_text(content: Any) -> str:
    """Flatten Anthropic/OpenAI message content into a searchable text string."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = str(part.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _contains_tool_context(messages: List[Dict[str, Any]]) -> bool:
    """Tool-use turns must preserve the original provider message graph."""
    for msg in messages:
        role = str(msg.get("role", "") or "").lower()
        if role == "tool":
            return True
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") in {"tool_use", "tool_result"}:
                    return True
    return False


def _extract_query_from_messages(messages: List[Dict[str, Any]]) -> str:
    """Extract primary user-visible query, skipping trailing control metadata."""
    fallback = ""
    for msg in reversed(messages):
        role = msg.get("role", "")
        content = _content_to_text(msg.get("content", ""))
        if role == "user" and content:
            fallback = fallback or content
            visible = extract_user_visible_query(content)
            if visible:
                return visible
    if fallback:
        return fallback
    # Fallback: first non-empty content
    for msg in messages:
        content = _content_to_text(msg.get("content", ""))
        if content:
            return extract_user_visible_query(content) or content
    return ""


def _estimate_original_tokens(payload: dict, messages: List[Dict[str, Any]]) -> int:
    """
    Estimate token count from messages array.
    Rough estimate: ~4 chars per token.
    """
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            # Multi-modal content (e.g., image + text)
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total_chars += len(part.get("text", ""))
    return max(1, int(total_chars / 3))  # ~3 chars/token for English


def _assess_compile_eligibility(
    payload: dict,
    messages: List[Dict[str, Any]],
    query: str,
) -> Tuple[bool, Optional[str]]:
    """
    Determine if a request is compile-eligible.

    Returns:
        (can_compile, skip_reason)
        can_compile=True, skip_reason=None  → should compile
        can_compile=False, skip_reason!=None → skip (known unsupported shape)
    """
    # No messages = nothing to compile
    if not messages:
        return False, "no_messages"

    # Empty query = nothing to search for
    if not query:
        return False, "empty_query"

    # System prompt only = nothing to augment
    has_user_message = any(
        msg.get("role") == "user" and msg.get("content")
        for msg in messages
    )
    if not has_user_message:
        return False, "no_user_message"

    # Assistant-only continuation = no new context needed
    if all(msg.get("role") in ("assistant", "system") for msg in messages):
        return False, "assistant_only_continuation"

    # Agent tool loops rely on exact tool_use/tool_result ordering and IDs.
    # Compiling these turns would drop the tool results and make the LLM repeat
    # searches instead of answering from the retrieved local context.
    if _contains_tool_context(messages):
        return False, "tool_context_passthrough"

    # Streaming with compile: supported (compile first chunk)
    # Non-streaming: fully supported
    return True, None


# ============================================================================
# Task A-2: Compile Context Builder
# ============================================================================

def build_compile_context(
    normalized: dict,
    agent_id: str,
    session_id: Optional[str] = None,
) -> dict:
    """
    Create the internal request object required by runtime_bridge.

    Args:
        normalized: Output of normalize_inbound_request()
        agent_id: Canonical agent identifier
        session_id: Optional session ID

    Returns:
        Internal compile context dict.
    """
    return {
        "query": normalized["query"],
        "task_type": normalized.get("task_type", "continuation"),
        "agent_id": agent_id,
        "session_id": session_id,
        "model": normalized["model"],
        "protocol": normalized["protocol"],
        "original_token_estimate": normalized["original_token_estimate"],
        "messages": normalized["messages"],
    }


# ============================================================================
# Task A-3: Main Gateway Compile Entry Point
# ============================================================================

async def run_gateway_compile(
    payload: dict,
    agent_id: str,
    session_id: Optional[str] = None,
    access_plan: Optional[dict] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Tuple[dict, dict]:
    """
    Main orchestration function: normalize → search → compile → rebuild.

    Args:
        payload: Raw LLM request body
        agent_id: Canonical agent identifier
        session_id: Optional session ID

    Returns:
        (compiled_payload, compile_meta)

        compiled_payload:
            LLM request body ready for upstream forwarding.
            If compile_success: contains compiled context injected.
            If compile_skipped/compile_failed: contains original payload (unmodified).

        compile_meta:
            {
                "compile_status": "compile_success" | "compile_skipped" | "compile_failed",
                "selected_memory_count": int,
                "original_token_estimate": int,
                "compiled_token_estimate": int,
                "compression_ratio": float,
                "compile_path": str,
                "compile_error": Optional[str],
                "compile_reason": str,
            }
    """
    # Step 1: Normalize
    normalized = normalize_inbound_request(payload, agent_id)
    request_path = str(payload.get("_path", "unknown"))
    if config.trace_events_enabled:
        append_trace_event(
            build_trace_event(
                trace_id=trace_id or request_id or "unknown",
                request_id=request_id or "unknown",
                stage="gateway",
                path=request_path,
                status="compile_enter",
                agent_id=agent_id,
                details={
                    "protocol": normalized["protocol"],
                    "can_compile": normalized["can_compile"],
                    "skip_reason": normalized["skip_reason"],
                },
            )
        )

    if not normalized["can_compile"]:
        loguru.logger.info(
            f"[GATEWAY_COMPILE] agent={agent_id} compile_skipped "
            f"reason={normalized['skip_reason']}"
        )
        return _build_original_payload(payload, normalized), _build_meta(
            status="compile_skipped",
            selected_count=0,
            candidate_count=0,
            original_tokens=normalized["original_token_estimate"],
            compiled_tokens=0,
            path="gateway_normalize",
            error=None,
            reason=f"skip_{normalized['skip_reason']}",
            internal_memory_status="no_product_memory_found",
        )

    # Step 2: Fetch memory candidates
    compile_context = build_compile_context(normalized, agent_id, session_id)

    from ..infrastructure import runtime_bridge as _rb

    enforcement_capture: Dict[str, Any] = {}
    try:
        candidates = await _rb.fetch_memory_candidates(
            query=compile_context["query"],
            agent_id=agent_id,
            limit=16,
            scope="agent",
            access_plan=access_plan,
            enforcement_capture=enforcement_capture,
            request_id=request_id,
            trace_id=trace_id,
        )
    except Exception as e:
        loguru.logger.warning(f"[GATEWAY_COMPILE] search failed agent={agent_id}: {e}")
        candidates = []

    # Step 3: Run runtime compile
    try:
        compile_result = await _rb.execute_runtime_compile(
            query=compile_context["query"],
            candidate_memories=candidates,
            agent_id=agent_id,
            task_type=compile_context.get("task_type", "continuation"),
            session_id=session_id,
            model=compile_context.get("model"),
            original_token_estimate=normalized["original_token_estimate"],
            request_id=request_id,
            trace_id=trace_id,
        )
    except Exception as e:
        loguru.logger.warning(f"[GATEWAY_COMPILE] compile failed agent={agent_id}: {e}")
        compile_result = {
            "compiled_messages": None,
            "selected_memories": [],
            "packed_context": "",
            "original_token_estimate": compile_context["original_token_estimate"],
            "compiled_token_estimate": 0,
            "saved_token_estimate": 0,
            "compression_ratio": 0.0,
            "compile_reason": "runtime_compile",
            "compile_error": str(e)[:200],
            "candidate_count": 0,
            "selected_count": 0,
            "skill_suggestions": [],
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "fallback",
            "task_type": compile_context.get("task_type", "continuation"),
        }

    # Step 4: Determine status and build response
    selected_memories = compile_result.get("selected_memories", [])
    packed_context = str(compile_result.get("packed_context", "") or "")
    has_compiled_context = bool(selected_memories) and bool(packed_context.strip())

    if compile_result.get("compile_error"):
        status = "compile_failed"
        compiled_payload = _build_original_payload(payload, normalized)
        loguru.logger.warning(
            f"[GATEWAY_COMPILE] agent={agent_id} compile_failed "
            f"error={compile_result['compile_error'][:80]}"
        )
    elif not has_compiled_context:
        status = "compile_skipped"
        compiled_payload = _build_original_payload(payload, normalized)
        compile_result["compiled_token_estimate"] = 0
        compile_result["saved_token_estimate"] = 0
        compile_result["compression_ratio"] = 0.0
        compile_result["compile_reason"] = (
            "no_product_memory_found"
            if not candidates
            else "no_selected_product_memory"
        )
        loguru.logger.info(
            f"[GATEWAY_COMPILE] agent={agent_id} compile_skipped "
            f"reason={compile_result['compile_reason']} passthrough=true"
        )
    else:
        status = "compile_success"
        compiled_payload = _inject_compiled_context(
            payload=payload,
            normalized=normalized,
            packed_context=packed_context,
            selected_memories=selected_memories,
        )
        loguru.logger.info(
            f"[GATEWAY_COMPILE] agent={agent_id} compile_success "
            f"selected={len(selected_memories)} "
            f"original={compile_result['original_token_estimate']} "
            f"compiled={compile_result['compiled_token_estimate']} "
            f"ratio={compile_result['compression_ratio']:.3f}"
        )

    # Step 5: Build compile metadata
    compile_meta = _build_meta(
        status=status,
        selected_count=len(selected_memories),
        candidate_count=len(candidates),
        original_tokens=compile_result.get("original_token_estimate", 0),
        compiled_tokens=compile_result.get("compiled_token_estimate", 0),
        path="runtime_compile",
        error=compile_result.get("compile_error"),
        reason=compile_result.get("compile_reason", "runtime_compile"),
        compression_ratio=compile_result.get("compression_ratio", 0.0),
        skill_suggestions=compile_result.get("skill_suggestions", []),
        skill_policy_name=compile_result.get("skill_policy_name", "local_fallback"),
        skill_policy_version=compile_result.get("skill_policy_version", "static_catalog_v1"),
        skill_policy_source=compile_result.get("skill_policy_source", "local_builtin"),
        skill_policy_status=compile_result.get("skill_policy_status", "fallback"),
        task_type=compile_result.get("task_type", compile_context.get("task_type", "continuation")),
        enforcement_trace=enforcement_capture.get("enforcement_trace"),
        internal_memory_status=(
            "used"
            if len(selected_memories) > 0
            else (
                "found_not_selected"
                if len(candidates) > 0
                else "no_product_memory_found"
            )
        ),
    )
    if config.trace_events_enabled:
        append_trace_event(
            build_trace_event(
                trace_id=trace_id or request_id or "unknown",
                request_id=request_id or "unknown",
                stage="gateway",
                path=request_path,
                status=status,
                agent_id=agent_id,
                error_type="compile_failed" if compile_result.get("compile_error") else None,
                details={
                    "compile_status": status,
                    "selected_memory_count": compile_meta["selected_memory_count"],
                    "compiled_token_estimate": compile_meta["compiled_token_estimate"],
                    "compression_ratio": compile_meta["compression_ratio"],
                    "compile_reason": compile_meta["compile_reason"],
                },
            )
        )

    return compiled_payload, compile_meta


# ============================================================================
# Helper: Build compiled payload
# ============================================================================

def _inject_compiled_context(
    payload: dict,
    normalized: dict,
    packed_context: str,
    selected_memories: List[dict],
) -> dict:
    """
    Inject compiled context into LLM request payload.

    Strategy: build a compact upstream payload from product-compiled context and
    the current user-visible query. Do not forward the original message history
    again; that would stack the raw submission on top of the compiled context.
    """
    del selected_memories
    protocol = normalized["protocol"]
    context_block = f"Relevant context:\n{packed_context}" if packed_context else ""
    user_query = str(normalized.get("query") or "").strip()
    base_payload = _build_forwardable_payload(payload)

    if protocol == "anthropic":
        compiled = {**base_payload, "messages": [{"role": "user", "content": user_query}]}
        if context_block:
            compiled["system"] = context_block
        return compiled

    messages = []
    if context_block:
        messages.append({"role": "system", "content": context_block})
    messages.append({"role": "user", "content": user_query})
    return {**base_payload, "messages": messages}


def _build_forwardable_payload(payload: dict) -> dict:
    """Copy provider-facing fields while dropping internal compile markers."""
    return {
        key: value
        for key, value in payload.items()
        if key not in {"messages", "system"} and not str(key).startswith("_")
    }


def _build_original_payload(payload: dict, normalized: dict) -> dict:
    """Return the original payload unchanged (for skipped/failed cases)."""
    return dict(payload)


def _build_meta(
    status: str,
    selected_count: int,
    candidate_count: int,
    original_tokens: int,
    compiled_tokens: int,
    path: str,
    error: Optional[str],
    reason: str,
    compression_ratio: float = 0.0,
    skill_suggestions: Optional[List[dict]] = None,
    skill_policy_name: str = "local_fallback",
    skill_policy_version: str = "static_catalog_v1",
    skill_policy_source: str = "local_builtin",
    skill_policy_status: str = "fallback",
    task_type: str = "continuation",
    enforcement_trace: Optional[dict] = None,
    internal_memory_status: Optional[str] = None,
) -> dict:
    """
    Build standardized compile metadata.
    compression_ratio: stored separately from compile_meta to avoid confusion
    """
    ratio = compression_ratio
    if ratio == 0.0 and original_tokens > 0 and compiled_tokens > 0:
        ratio = 1.0 - (compiled_tokens / original_tokens)
    ratio = max(0.0, min(1.0, ratio))

    return {
        "compile_status": status,
        "selected_memory_count": selected_count,
        "candidate_count": int(candidate_count or 0),
        "original_token_estimate": original_tokens,
        "compiled_token_estimate": compiled_tokens,
        "compression_ratio": ratio,
        "compile_path": path,
        "compile_error": error,
        "compile_reason": reason,
        "skill_suggestions": skill_suggestions or [],
        "skill_policy_name": skill_policy_name,
        "skill_policy_version": skill_policy_version,
        "skill_policy_source": skill_policy_source,
        "skill_policy_status": skill_policy_status,
        "task_type": task_type,
        "internal_memory_status": internal_memory_status,
        "enforcement_trace": enforcement_trace if isinstance(enforcement_trace, dict) else None,
    }


def _classify_task_type(query: str) -> str:
    try:
        from ..task_classifier import classify_task

        classification = classify_task(query or "")
        task_type = (classification.task_type or "").strip().lower()
        if task_type in {"implementation", "decision", "continuation"}:
            return task_type
    except Exception:
        pass
    return "continuation"
