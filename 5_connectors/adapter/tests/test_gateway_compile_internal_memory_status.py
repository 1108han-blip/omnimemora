import asyncio
import importlib


gateway_compile = importlib.import_module("5_connectors.adapter.application.gateway_compile")
runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")


def _run_with_stubbed_bridge(*, candidates, selected_memories):
    async def _fake_fetch_memory_candidates(**kwargs):
        return candidates

    async def _fake_execute_runtime_compile(**kwargs):
        return {
            "compiled_messages": None,
            "selected_memories": selected_memories,
            "packed_context": "CTX" if selected_memories else "",
            "original_token_estimate": 100,
            "compiled_token_estimate": 60 if selected_memories else 100,
            "saved_token_estimate": 40 if selected_memories else 0,
            "compression_ratio": 0.4 if selected_memories else 0.0,
            "compile_reason": "runtime_compile",
            "compile_error": None,
            "candidate_count": len(candidates),
            "selected_count": len(selected_memories),
            "skill_suggestions": [],
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "disabled",
            "task_type": "continuation",
        }

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    runtime_bridge.fetch_memory_candidates = _fake_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _fake_execute_runtime_compile
    try:
        payload = {"messages": [{"role": "user", "content": "check memory status"}], "stream": False}
        _, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="claude_code")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute
    return compile_meta


def test_internal_memory_status_no_product_memory_found():
    meta = _run_with_stubbed_bridge(candidates=[], selected_memories=[])
    assert meta["candidate_count"] == 0
    assert meta["selected_memory_count"] == 0
    assert meta["internal_memory_status"] == "no_product_memory_found"


def test_internal_memory_status_found_not_selected():
    meta = _run_with_stubbed_bridge(
        candidates=[{"content": "candidate A", "score": 0.8}],
        selected_memories=[],
    )
    assert meta["candidate_count"] == 1
    assert meta["selected_memory_count"] == 0
    assert meta["internal_memory_status"] == "found_not_selected"


def test_internal_memory_status_used():
    meta = _run_with_stubbed_bridge(
        candidates=[{"content": "candidate A", "score": 0.8}],
        selected_memories=[{"content": "candidate A", "score": 0.8}],
    )
    assert meta["candidate_count"] == 1
    assert meta["selected_memory_count"] == 1
    assert meta["internal_memory_status"] == "used"
