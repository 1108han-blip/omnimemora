import asyncio
import importlib


gateway_compile = importlib.import_module("5_connectors.adapter.application.gateway_compile")
runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")
adapter_config = importlib.import_module("5_connectors.adapter.config").config


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

    assert compile_meta["compile_status"] == "compile_skipped"
    assert compile_meta["compile_reason"] == "no_product_memory_found"
    assert compile_meta["selected_memory_count"] == 0
    assert compile_meta["compiled_token_estimate"] == 0
    assert compiled_payload == payload


def test_gateway_compile_passthrough_for_anthropic_tool_context():
    async def _unexpected_fetch_memory_candidates(**kwargs):
        raise AssertionError("tool context should not search product memory")

    async def _unexpected_execute_runtime_compile(**kwargs):
        raise AssertionError("tool context should not run runtime compile")

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    runtime_bridge.fetch_memory_candidates = _unexpected_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _unexpected_execute_runtime_compile
    try:
        payload = {
            "_path": "/llm/v1/messages",
            "messages": [
                {"role": "user", "content": "Search this repo and answer"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "Grep",
                            "input": {"pattern": "gateway_compile"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": "gateway_compile.py contains the compile path",
                        }
                    ],
                },
            ],
            "model": "MiniMax-M2.7",
            "stream": True,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="claude_code")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute

    assert compile_meta["compile_status"] == "structured_compile_passthrough"
    assert compile_meta["compile_reason"] == "no_eligible_tool_result"
    assert compile_meta["selected_memory_count"] == 0
    assert compiled_payload == payload


def test_gateway_compile_structured_tool_context_compresses_old_result():
    async def _unexpected_fetch_memory_candidates(**kwargs):
        raise AssertionError("structured tool context should not search product memory")

    async def _unexpected_execute_runtime_compile(**kwargs):
        raise AssertionError("structured tool context should not run runtime compile")

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    old_max_chars = adapter_config.structured_compile_max_tool_result_chars
    runtime_bridge.fetch_memory_candidates = _unexpected_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _unexpected_execute_runtime_compile
    adapter_config.structured_compile_max_tool_result_chars = 700
    try:
        old_output = "\n".join([f"src/module_{i}.py:{i}: repeated search result" for i in range(120)])
        payload = {
            "_path": "/llm/v1/messages",
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_old", "name": "Grep", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_old", "content": old_output}],
                },
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_recent", "name": "Read", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_recent", "content": "latest result"}],
                },
            ],
            "model": "MiniMax-M2.7",
            "stream": True,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="claude_code")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute
        adapter_config.structured_compile_max_tool_result_chars = old_max_chars

    assert compile_meta["compile_status"] == "structured_compile_success"
    assert compile_meta["compile_path"] == "structured_context_compile"
    assert compile_meta["selected_memory_count"] == 0
    assert compile_meta["structured_compile_changed_blocks"] == 1
    assert compile_meta["compiled_token_estimate"] < compile_meta["original_token_estimate"]
    assert "original_chars=" in compiled_payload["messages"][1]["content"][0]["content"]
    assert compiled_payload["messages"][3]["content"][0]["content"] == "latest result"


def test_gateway_compile_tool_context_uses_passthrough_when_structured_compile_disabled():
    old_enabled = adapter_config.structured_compile_enabled
    adapter_config.structured_compile_enabled = False
    try:
        payload = {
            "_path": "/llm/v1/messages",
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_1", "name": "Grep", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "result"}],
                },
            ],
            "model": "MiniMax-M2.7",
            "stream": True,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="claude_code")
        )
    finally:
        adapter_config.structured_compile_enabled = old_enabled

    assert compile_meta["compile_status"] == "compile_skipped"
    assert compile_meta["compile_reason"] == "skip_tool_context_passthrough"
    assert compiled_payload == payload


def test_gateway_compile_openclaw_deadline_profile_protects_latest_result():
    async def _unexpected_fetch_memory_candidates(**kwargs):
        raise AssertionError("OpenClaw deadline profile should not search product memory")

    async def _unexpected_execute_runtime_compile(**kwargs):
        raise AssertionError("OpenClaw deadline profile should not run runtime compile")

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    old_enabled = adapter_config.structured_compile_openclaw_deadline_profile_enabled
    old_threshold = adapter_config.structured_compile_openclaw_long_context_tokens
    old_max_chars = adapter_config.structured_compile_openclaw_max_tool_result_chars
    runtime_bridge.fetch_memory_candidates = _unexpected_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _unexpected_execute_runtime_compile
    adapter_config.structured_compile_openclaw_deadline_profile_enabled = True
    adapter_config.structured_compile_openclaw_long_context_tokens = 100
    adapter_config.structured_compile_openclaw_max_tool_result_chars = 500
    try:
        long_latest = "\n".join(
            [f"src/large_{i}.py:{i}: latest OpenClaw result with repeated payload" for i in range(220)]
        )
        payload = {
            "_path": "/llm/v1/messages",
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_latest", "name": "Grep", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_latest", "content": long_latest}],
                },
            ],
            "model": "MiniMax-M2.7",
            "stream": True,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="openclaw")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute
        adapter_config.structured_compile_openclaw_deadline_profile_enabled = old_enabled
        adapter_config.structured_compile_openclaw_long_context_tokens = old_threshold
        adapter_config.structured_compile_openclaw_max_tool_result_chars = old_max_chars

    assert compile_meta["compile_status"] == "structured_compile_passthrough"
    assert compile_meta["compile_reason"] == "no_eligible_tool_result"
    assert compile_meta["deadline_profile"] == "openclaw_45s_long_tool_context"
    assert compile_meta["deadline_profile_applied"] is True
    assert compile_meta["protect_latest_tool_result"] is True
    assert compile_meta["max_tool_result_chars"] == 500
    latest_result = compiled_payload["messages"][1]["content"][0]
    assert latest_result["tool_use_id"] == "toolu_latest"
    assert latest_result["content"] == long_latest


def test_gateway_compile_openclaw_deadline_profile_protects_markdown_document_result():
    async def _unexpected_fetch_memory_candidates(**kwargs):
        raise AssertionError("OpenClaw document protection should not search product memory")

    async def _unexpected_execute_runtime_compile(**kwargs):
        raise AssertionError("OpenClaw document protection should not run runtime compile")

    old_fetch = runtime_bridge.fetch_memory_candidates
    old_execute = runtime_bridge.execute_runtime_compile
    old_enabled = adapter_config.structured_compile_openclaw_deadline_profile_enabled
    old_threshold = adapter_config.structured_compile_openclaw_long_context_tokens
    old_max_chars = adapter_config.structured_compile_openclaw_max_tool_result_chars
    runtime_bridge.fetch_memory_candidates = _unexpected_fetch_memory_candidates
    runtime_bridge.execute_runtime_compile = _unexpected_execute_runtime_compile
    adapter_config.structured_compile_openclaw_deadline_profile_enabled = True
    adapter_config.structured_compile_openclaw_long_context_tokens = 100
    adapter_config.structured_compile_openclaw_max_tool_result_chars = 500
    try:
        document = "\n".join(
            [
                "# AI Runtime Telemetry System",
                "",
                "这份文档是用户要求改写的专业技术文案主体。",
                "",
                "- 采样系统",
                "- 流式观测系统",
                "- 时间序列分析系统",
                "- 指纹分类系统",
                "",
                "## 关键架构",
                "Runtime Recorder 负责记录请求、chunk、完成事件和延迟。",
                "",
                "```text",
                "Client -> OmniMemora Gateway -> Runtime Recorder -> LLM",
                "```",
            ]
            + [f"正文段落 {i}：这段内容必须完整保留给模型改写。" for i in range(100)]
        )
        payload = {
            "_path": "/llm/v1/messages",
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_doc", "name": "Read", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_doc", "content": document}],
                },
            ],
            "model": "MiniMax-M2.7",
            "stream": True,
        }
        compiled_payload, compile_meta = asyncio.run(
            gateway_compile.run_gateway_compile(payload=payload, agent_id="openclaw")
        )
    finally:
        runtime_bridge.fetch_memory_candidates = old_fetch
        runtime_bridge.execute_runtime_compile = old_execute
        adapter_config.structured_compile_openclaw_deadline_profile_enabled = old_enabled
        adapter_config.structured_compile_openclaw_long_context_tokens = old_threshold
        adapter_config.structured_compile_openclaw_max_tool_result_chars = old_max_chars

    assert compile_meta["compile_status"] == "structured_compile_passthrough"
    assert compile_meta["deadline_profile"] == "openclaw_45s_long_tool_context"
    assert compile_meta["protect_latest_tool_result"] is True
    assert compiled_payload["messages"][1]["content"][0]["content"] == document
