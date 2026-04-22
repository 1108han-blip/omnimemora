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

from typing import Any, Dict, Optional, Tuple


def _get_gateway_compile():
    return __import__("5_connectors.adapter.gateway_compile", fromlist=["dummy"])

def _get_truth_bridge():
    return __import__("5_connectors.adapter.truth_bridge", fromlist=["dummy"])

def _get_compile_store():
    return __import__("5_connectors.adapter.compile_store", fromlist=["dummy"])

def _get_meter_store():
    return __import__("5_connectors.adapter.meter_store", fromlist=["dummy"])

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
    upstream_model = _tb.classify_model_resolution(
        requested=requested_model,
        upstream_model=upstream.get("model"),
        provider=upstream.get("provider", "openai_compatible"),
    )

    auth_source_label = _tb.auth_source_from_values(
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
            "fallback": True,
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
    """Persist gateway meter record."""
    _ms = _get_meter_store()
    try:
        _ms.store_meter(
            request_id=request_id or "unknown",
            agent=agent_id,
            route=route,
            model=compile_meta.get("model", payload.get("model", "unknown")),
            compile_status=compile_meta.get("compile_status", "unknown"),
            selected_memory_count=compile_meta.get("selected_memory_count", 0),
            original_tokens=compile_meta.get("original_token_estimate", 0),
            compiled_tokens=compile_meta.get("compiled_token_estimate", 0),
            baseline_tokens_estimate=0,
            actual_tokens_estimate=0,
            saved_tokens_estimate=0,
            savings_ratio=0.0,
            truth_provider=truth_contract.get("provider_resolved"),
            truth_base_url=truth_contract.get("base_url_resolved"),
            truth_model=truth_contract.get("model_resolved"),
        )
    except Exception:
        pass
