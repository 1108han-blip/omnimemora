import asyncio
import importlib


gateway_compile = importlib.import_module("5_connectors.adapter.application.gateway_compile")
runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")


def test_gateway_compile_passes_classified_task_type_to_runtime_bridge():
    captured = {"task_type": None}

    async def _fake_fetch_memory_candidates(**kwargs):
        return [{"content": "memory candidate", "score": 0.9}]

    async def _fake_execute_runtime_compile(**kwargs):
        captured["task_type"] = kwargs.get("task_type")
        return {
            "compiled_messages": None,
            "selected_memories": [],
            "packed_context": "",
            "original_token_estimate": 80,
            "compiled_token_estimate": 80,
            "saved_token_estimate": 0,
            "compression_ratio": 0.0,
            "compile_reason": "runtime_compile",
            "compile_error": None,
            "candidate_count": 1,
            "selected_count": 0,
            "skill_suggestions": [],
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "disabled",
            "task_type": kwargs.get("task_type"),
        }

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    runtime_bridge.fetch_memory_candidates = _fake_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _fake_execute_runtime_compile
    try:
        payload = {
            "messages": [{"role": "user", "content": "implement login token refresh middleware"}],
            "model": "gpt-5.4",
            "stream": False,
        }
        asyncio.run(gateway_compile.run_gateway_compile(payload=payload, agent_id="codex_cli"))
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute

    assert captured["task_type"] == "implementation"
