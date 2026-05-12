import importlib


compiler = importlib.import_module("5_connectors.adapter.application.context_compiler.compiler")


def test_long_old_tool_result_compresses_and_preserves_graph():
    old_output = "\n".join(
        [f"/tmp/project/file_{i}.py:{i}: regular search hit with repeated details" for i in range(120)]
    )
    payload = {
        "model": "claude-test",
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_old", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_old", "content": old_output}],
            },
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_recent", "name": "read", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_recent", "content": "latest result"}],
            },
        ],
    }

    result = compiler.compile_anthropic_tool_context(payload, max_tool_result_chars=900)

    assert result.status == "structured_compile_success"
    assert result.changed_blocks == 1
    assert result.compiled_token_estimate < result.original_token_estimate
    assert result.token_estimator_name
    assert result.token_estimator_confidence in {"medium", "high"}
    old_result = result.payload["messages"][1]["content"][0]
    recent_result = result.payload["messages"][3]["content"][0]
    assert old_result["tool_use_id"] == "toolu_old"
    assert recent_result["tool_use_id"] == "toolu_recent"
    assert "original_chars=" in old_result["content"]
    assert recent_result["content"] == "latest result"


def test_latest_tool_result_is_protected_even_when_long():
    long_latest = "\n".join([f"latest line {i}" for i in range(200)])
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": long_latest}],
            },
        ],
    }

    result = compiler.compile_anthropic_tool_context(payload, max_tool_result_chars=500)

    assert result.status == "structured_compile_passthrough"
    assert result.reason == "no_eligible_tool_result"
    assert result.payload is payload


def test_invalid_graph_falls_back_to_passthrough():
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_missing", "content": "wrong"}],
            },
        ],
    }

    result = compiler.compile_anthropic_tool_context(payload)

    assert result.status == "structured_compile_passthrough"
    assert result.reason == "invalid_tool_graph"
    assert "unknown_tool_result_id" in result.issues
    assert result.payload is payload


def test_text_only_payload_falls_back_without_change():
    payload = {"messages": [{"role": "user", "content": "hello"}]}

    result = compiler.compile_anthropic_tool_context(payload)

    assert result.status == "structured_compile_passthrough"
    assert result.reason == "no_tool_graph"
    assert result.payload is payload


def test_tool_result_content_list_compresses_to_text_block():
    old_output = "\n".join([f"error line {i} module.py:{i}" for i in range(100)])
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_old", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_old",
                        "content": [{"type": "text", "text": old_output}],
                    }
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_recent", "name": "read", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_recent", "content": "latest"}],
            },
        ]
    }

    result = compiler.compile_anthropic_tool_context(payload, max_tool_result_chars=800)

    assert result.status == "structured_compile_success"
    compressed_content = result.payload["messages"][1]["content"][0]["content"]
    assert compressed_content[0]["type"] == "text"
    assert "original_chars=" in compressed_content[0]["text"]


def test_declared_tool_schema_is_preserved_during_compile():
    old_output = "\n".join([f"match line {i} src/file.py:{i}" for i in range(100)])
    tools = [{"name": "grep", "description": "search files"}]
    payload = {
        "tools": tools,
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_old", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_old", "content": old_output}],
            },
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_recent", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_recent", "content": "latest"}],
            },
        ],
    }

    result = compiler.compile_anthropic_tool_context(payload, max_tool_result_chars=800)

    assert result.status == "structured_compile_success"
    assert result.payload["tools"] == tools


def test_invalid_declared_tool_schema_falls_back_before_rewrite():
    old_output = "\n".join([f"match line {i} src/file.py:{i}" for i in range(100)])
    payload = {
        "tools": [{"name": "read"}],
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_old", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_old", "content": old_output}],
            },
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_recent", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_recent", "content": "latest"}],
            },
        ],
    }

    result = compiler.compile_anthropic_tool_context(payload, max_tool_result_chars=800)

    assert result.status == "structured_compile_passthrough"
    assert result.reason == "invalid_tool_schema"
    assert result.issues == ["undeclared_tool_use_name", "undeclared_tool_use_name"]
    assert result.payload is payload
