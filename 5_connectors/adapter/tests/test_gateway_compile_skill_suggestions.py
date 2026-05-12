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
            "skill_policy_name": "recommendation_local_active",
            "skill_policy_version": "local-default-v1",
            "skill_policy_source": "local_manifest",
            "skill_policy_status": "active",
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
    assert compile_meta["skill_policy_name"] == "recommendation_local_active"
    assert compile_meta["skill_policy_version"] == "local-default-v1"
    assert compile_meta["skill_policy_source"] == "local_manifest"
    assert compile_meta["skill_policy_status"] == "active"

    # suggestions should remain metadata only; packed context is provider-facing
    # system context, not a visible skill recommendation.
    sys_msg = compiled_payload["messages"][0]
    assert sys_msg["role"] == "system"
    assert "PACKED-CONTEXT-ONLY" in sys_msg["content"]
    assert "checks" not in sys_msg["content"].lower()


def test_gateway_compile_replaces_raw_submission_with_compact_payload():
    async def _fake_fetch_memory_candidates(**kwargs):
        return [{"content": "memory candidate", "score": 0.9}]

    async def _fake_execute_runtime_compile(**kwargs):
        return {
            "compiled_messages": None,
            "selected_memories": [{"content": "memory candidate", "score": 0.9}],
            "packed_context": "PACKED-CONTEXT-ONLY",
            "original_token_estimate": 500,
            "compiled_token_estimate": 50,
            "saved_token_estimate": 450,
            "compression_ratio": 0.9,
            "compile_reason": "runtime_compile",
            "compile_error": None,
            "candidate_count": 1,
            "selected_count": 1,
            "skill_suggestions": [],
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "disabled",
        }

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    runtime_bridge.fetch_memory_candidates = _fake_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _fake_execute_runtime_compile
    try:
        payload = {
            "_path": "/llm/chat",
            "messages": [
                {"role": "system", "content": "ORIGINAL-SYSTEM-SHOULD-NOT-FORWARD"},
                {"role": "assistant", "content": "ORIGINAL-HISTORY-SHOULD-NOT-FORWARD"},
                {"role": "user", "content": "Please answer the compact request"},
            ],
            "model": "gpt-5.4",
            "stream": False,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="codex_cli")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute

    assert compile_meta["compile_status"] == "compile_success"
    assert "_path" not in compiled_payload
    assert compiled_payload["messages"] == [
        {"role": "system", "content": "Relevant context:\nPACKED-CONTEXT-ONLY"},
        {"role": "user", "content": "Please answer the compact request"},
    ]
    forwarded_text = "\n".join(m["content"] for m in compiled_payload["messages"])
    assert "ORIGINAL-SYSTEM-SHOULD-NOT-FORWARD" not in forwarded_text
    assert "ORIGINAL-HISTORY-SHOULD-NOT-FORWARD" not in forwarded_text


def test_gateway_compile_uses_compact_payload_without_packed_context():
    async def _fake_fetch_memory_candidates(**kwargs):
        return []

    async def _fake_execute_runtime_compile(**kwargs):
        return {
            "compiled_messages": None,
            "selected_memories": [],
            "packed_context": "",
            "original_token_estimate": 500,
            "compiled_token_estimate": 20,
            "saved_token_estimate": 480,
            "compression_ratio": 0.96,
            "compile_reason": "runtime_compile",
            "compile_error": None,
            "candidate_count": 0,
            "selected_count": 0,
            "skill_suggestions": [],
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "disabled",
        }

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    runtime_bridge.fetch_memory_candidates = _fake_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _fake_execute_runtime_compile
    try:
        payload = {
            "messages": [
                {"role": "system", "content": "ORIGINAL-SYSTEM-SHOULD-NOT-FORWARD"},
                {"role": "assistant", "content": "ORIGINAL-HISTORY-SHOULD-NOT-FORWARD"},
                {"role": "user", "content": "Please answer without context"},
            ],
            "model": "gpt-5.4",
            "stream": False,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="codex_cli")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute

    assert compile_meta["compile_status"] == "compile_success"
    assert compiled_payload["messages"] == [
        {"role": "user", "content": "Please answer without context"},
    ]
