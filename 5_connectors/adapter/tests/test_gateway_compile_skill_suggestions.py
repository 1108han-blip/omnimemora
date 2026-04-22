import asyncio
import importlib


gateway_compile = importlib.import_module("5_connectors.adapter.application.gateway_compile")
runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")


def test_gateway_compile_meta_includes_skill_suggestions_without_polluting_context():
    async def _fake_fetch_memory_candidates(**kwargs):
        return [{"content": "memory candidate", "score": 0.9}]

    async def _fake_execute_runtime_compile(**kwargs):
        return {
            "compiled_messages": None,
            "selected_memories": [{"content": "memory candidate", "score": 0.9}],
            "packed_context": "PACKED-CONTEXT-ONLY",
            "original_token_estimate": 100,
            "compiled_token_estimate": 60,
            "saved_token_estimate": 40,
            "compression_ratio": 0.4,
            "compile_reason": "runtime_compile",
            "compile_error": None,
            "candidate_count": 1,
            "selected_count": 1,
            "skill_suggestions": [
                {
                    "skill_id": "checks",
                    "title": "Checks And Validation",
                    "reason": "Matched keywords",
                    "confidence": 0.72,
                    "source": "static_catalog_v1",
                }
            ],
        }

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    runtime_bridge.fetch_memory_candidates = _fake_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _fake_execute_runtime_compile
    try:
        payload = {
            "messages": [{"role": "user", "content": "Need decision with validation"}],
            "model": "gpt-5.4",
            "stream": False,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="codex_cli")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute

    assert compile_meta["skill_suggestions"]
    assert compile_meta["skill_suggestions"][0]["skill_id"] == "checks"

    # suggestions should remain metadata only; packed context injection remains unchanged
    sys_msg = compiled_payload["messages"][0]
    assert sys_msg["role"] == "system"
    assert "PACKED-CONTEXT-ONLY" in sys_msg["content"]
    assert "checks" not in sys_msg["content"].lower()
