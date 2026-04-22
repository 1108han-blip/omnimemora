"""
compile_orchestrator.py — Compile Application Entry Point
=========================================================
職責：作為 18011 內部 compile application 層的單一 entry point。

明確邊界：
- 接收 ingress 層的請求
- 協調 candidate fetch、compile plan assembly
- 調用 gateway_compile.run_gateway_compile
- 執行 truth resolution
- 記錄 compile event / meter
- 返回編譯結果和 truth contract

禁止：
- 不做 protocol 處理（屬於 ingress）
- 不做 upstream forwarding（屬於 ingress/egress）
- 不做 runtime/backend 直接訪問（屬於 infrastructure）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple


def _get_gateway_compile():
    return __import__("5_connectors.adapter.application.gateway_compile", fromlist=["dummy"])

def _get_truth_bridge():
    return __import__("5_connectors.adapter.truth_bridge", fromlist=["dummy"])

def _get_compile_store():
    return __import__("5_connectors.adapter.infrastructure.compile_store", fromlist=["dummy"])

def _get_meter_store():
    return __import__("5_connectors.adapter.infrastructure.meter_store", fromlist=["dummy"])

def _get_v2_compute():
    return __import__("4_core.logic.v2_compute", fromlist=["dummy"])

def _get_config():
    return __import__("5_connectors.adapter.config", fromlist=["dummy"]).config


async def run_compile_and_resolve(
    payload: dict,
    agent_id: str,
    upstream: dict,
    api_key_override: Optional[str],
    route: str,
    requested_model: str,
    wire_api_requested: str,
    provider_base: Optional[str],
    provider_source: str,
    base_url_source: str,
    model_source: str,
    auth_source: str,
    policy_profile: str,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Tuple[dict, dict, dict, dict]:
    return await _run_compile_and_resolve(
        payload=payload,
        agent_id=agent_id,
        upstream=upstream,
        api_key_override=api_key_override,
        route=route,
        requested_model=requested_model,
        wire_api_requested=wire_api_requested,
        provider_base=provider_base,
        provider_source=provider_source,
        base_url_source=base_url_source,
        model_source=model_source,
        auth_source=auth_source,
        policy_profile=policy_profile,
        session_id=session_id,
        request_id=request_id,
        trace_id=trace_id,
        family_prefix=None,
        family_default_reason="product_family_default",
        provider_default_fallback=True,
    )


async def run_anthropic_compile_and_resolve(
    payload: dict,
    agent_id: str,
    upstream: dict,
    route: str,
    requested_model: str,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Tuple[dict, dict, dict, dict]:
    """
    Protocol-aware compile application entry for Anthropic-compatible ingress.
    """
    return await _run_compile_and_resolve(
        payload=payload,
        agent_id=agent_id,
        upstream=upstream,
        api_key_override=None,
        route=route,
        requested_model=requested_model,
        wire_api_requested="anthropic_messages",
        provider_base=None,
        provider_source="product_policy_binding",
        base_url_source="product_upstream_config",
        model_source="agent_payload_explicit",
        auth_source="",
        policy_profile="anthropic_default",
        session_id=session_id,
        request_id=request_id,
        trace_id=trace_id,
        family_prefix="claude-",
        family_default_reason="anthropic_family_default",
        provider_default_fallback=False,
    )


def _resolve_upstream_model(
    *,
    requested_model: str,
    upstream: dict,
    family_prefix: Optional[str] = None,
) -> str:
    model_map = upstream.get("model_map", {}) or {}
    default_model = upstream.get("default_model") or requested_model or "unknown"
    if requested_model in model_map:
        return model_map[requested_model]
    if family_prefix and requested_model and requested_model.startswith(family_prefix):
        return default_model
    return requested_model or default_model


async def _run_compile_and_resolve(
    payload: dict,
    agent_id: str,
    upstream: dict,
    api_key_override: Optional[str],
    route: str,
    requested_model: str,
    wire_api_requested: str,
    provider_base: Optional[str],
    provider_source: str,
    base_url_source: str,
    model_source: str,
    auth_source: str,
    policy_profile: str,
    session_id: Optional[str],
    request_id: Optional[str],
    trace_id: Optional[str],
    family_prefix: Optional[str],
    family_default_reason: str,
    provider_default_fallback: bool,
) -> Tuple[dict, dict, dict, dict]:
    """
    Compile application 的單一 entry point。

    整合：
    1. compile execution (via gateway_compile.run_gateway_compile)
    2. truth resolution (via truth_bridge.resolve_truth_contract)
    3. event recording

    upstream 由 ingress 層傳入（protocol-specific upstream config），
    但 upstream 解析和 truth contract 由本函數內部完成。

    Returns:
        (compiled_payload, compile_meta, truth_contract, truth_meta)
    """
    _gc = _get_gateway_compile()
    _tb = _get_truth_bridge()

    # Step 1: Compile
    compiled_payload, compile_meta = await _gc.run_gateway_compile(
        payload=payload,
        agent_id=agent_id,
        session_id=session_id,
        request_id=request_id,
        trace_id=trace_id,
    )

    # Step 2: Resolve upstream model (within application layer)
    upstream_model = _resolve_upstream_model(
        requested_model=requested_model,
        upstream=upstream,
        family_prefix=family_prefix,
    )

    auth_source_label = auth_source or _tb.auth_source_from_values(
        explicit_authorization=bool(api_key_override),
        product_api_key_present=bool(upstream.get("api_key")),
    )

    candidates_by_source = {
        "product_policy_binding": {
            "provider": upstream.get("provider", "openai_compatible"),
            "base_url": upstream.get("base_url"),
            "auth": _tb.product_auth_ref_for_provider(upstream.get("provider", "openai_compatible")),
            "wire_api": wire_api_requested,
        },
        "runtime_override": {
            "base_url": provider_base,
            "auth": "runtime_authorization_header" if api_key_override else None,
        },
        "provider_default": {
            "provider": upstream.get("provider", "openai_compatible"),
            "base_url": upstream.get("base_url"),
            "model": upstream_model,
            "auth": _tb.product_auth_ref_for_provider(upstream.get("provider", "openai_compatible")),
            "wire_api": wire_api_requested,
            "fallback": provider_default_fallback,
        },
    }

    # Step 3: Truth resolution
    truth_contract, truth_meta = _tb.resolve_truth_contract(
        request_id=request_id or "unknown",
        agent_id=agent_id,
        route=route,
        requested_model=requested_model,
        wire_api_requested=wire_api_requested,
        provider_requested=upstream.get("provider", "openai_compatible"),
        base_url_requested=provider_base or upstream.get("base_url"),
        auth_requested=("runtime_authorization_header" if api_key_override else _tb.product_auth_ref_for_provider(upstream.get("provider", "openai_compatible"))),
        provider_source=provider_source,
        base_url_source=base_url_source,
        model_source=model_source,
        auth_source=auth_source_label,
        policy_profile=policy_profile,
        candidates_by_source=candidates_by_source,
        compile_enabled=bool(compile_meta),
    )

    # Step 4: Record compile event
    _record_compile_event(
        request_id=request_id,
        agent_id=agent_id,
        route=route,
        model=requested_model,
        compile_meta=compile_meta,
    )

    # Step 5: Persist gateway meter
    _persist_gateway_meter(
        request_id=request_id,
        agent_id=agent_id,
        route=route,
        compile_meta=compile_meta,
        truth_contract=truth_contract,
        payload=payload,
    )

    return compiled_payload, compile_meta, truth_contract, truth_meta


def _record_compile_event(
    request_id: Optional[str],
    agent_id: str,
    route: str,
    model: str,
    compile_meta: dict,
) -> None:
    """Record compile event to compile_store."""
    _cs = _get_compile_store()
    try:
        _cs.record_compile(
            request_id=request_id or "unknown",
            agent_id=agent_id,
            route=route,
            model=model,
            compile_status=compile_meta.get("compile_status", "unknown"),
            selected_memory_count=compile_meta.get("selected_memory_count", 0),
            original_token_estimate=compile_meta.get("original_token_estimate", 0),
            compiled_token_estimate=compile_meta.get("compiled_token_estimate", 0),
            compression_ratio=compile_meta.get("compression_ratio", 0.0),
            compile_path=compile_meta.get("compile_path", "unknown"),
            compile_error=compile_meta.get("compile_error"),
        )
    except Exception:
        pass


def _persist_gateway_meter(
    request_id: Optional[str],
    agent_id: str,
    route: str,
    compile_meta: dict,
    truth_contract: dict,
    payload: dict,
) -> None:
    """Persist gateway meter artifact in TokenSavingsMeter-compatible shape."""
    _ms = _get_meter_store()
    _v2 = _get_v2_compute()
    query = _extract_user_query(payload)
    baseline_tokens = int(compile_meta.get("original_token_estimate") or 0)
    actual_tokens = int(compile_meta.get("compiled_token_estimate") or 0)
    compile_status = str(compile_meta.get("compile_status") or "compile_skipped")
    selected_count = int(compile_meta.get("selected_memory_count") or 0)

    if actual_tokens <= 0 or compile_status != "compile_success":
        actual_tokens = baseline_tokens

    baseline_chars = max(len(query), baseline_tokens * 4)
    actual_chars = max(0, actual_tokens * 4)
    saved_tokens = max(0, baseline_tokens - actual_tokens)
    saved_chars = max(0, baseline_chars - actual_chars)
    tenant = agent_id if agent_id and agent_id != "unknown" else "gateway"
    try:
        meter = _v2.TokenSavingsMeter(
            request_id=request_id or "unknown",
            tenant=tenant,
            user=tenant,
            agent=agent_id,
            client=f"{agent_id or 'unknown'}-gateway",
            timestamp=datetime.utcnow().isoformat() + "Z",
            query_shape=_v2.classify_query_shape(query),
            query_chars=len(query),
            query=query,
            baseline_chars=baseline_chars,
            actual_chars=actual_chars,
            saved_chars=saved_chars,
            baseline_tokens_estimate=baseline_tokens,
            actual_tokens_estimate=actual_tokens,
            saved_tokens_estimate=saved_tokens,
            savings_ratio=round((saved_tokens / baseline_tokens), 3) if baseline_tokens > 0 else 0.0,
            packed_memory_count=selected_count,
            local_cards_used=selected_count,
            remote_candidates_considered=max(selected_count, 0),
            remote_candidates_skipped=0,
            remote_used_count=0,
            skipped_remote_reason=None,
            coverage_satisfied=selected_count > 0,
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
        _ms.store_meter(meter)
    except Exception:
        pass


def _collect_text_parts(parts: object) -> str:
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
        if str(part.get("type", "")).lower() in {"input_text", "output_text", "text"}:
            text = part.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
    return "".join(chunks)


def _extract_user_query(payload: dict) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role", "")).lower() != "user":
                continue
            text = _collect_text_parts(message.get("content"))
            if text:
                return text
    raw_input = payload.get("input")
    if isinstance(raw_input, str):
        return raw_input
    return ""
