import importlib


tool_graph = importlib.import_module(
    "5_connectors.adapter.application.context_compiler.anthropic_tool_graph"
)


def test_valid_tool_use_result_pair_parses_to_ir():
    payload = {
        "system": "Preserve tool protocol.",
        "messages": [
            {"role": "user", "content": "Search the project."},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I will search."},
                    {"type": "tool_use", "id": "toolu_1", "name": "grep", "input": {"q": "compile"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "gateway_compile.py: compile_success",
                    }
                ],
            },
        ],
    }

    analysis = tool_graph.analyze_anthropic_tool_graph(payload)

    assert analysis.valid is True
    assert analysis.has_tool_graph is True
    assert [block.block_type for block in analysis.ir.blocks] == [
        "system_policy",
        "conversation_history",
        "assistant_state",
        "tool_call",
        "tool_result_recent",
    ]
    tool_call = next(block for block in analysis.ir.blocks if block.block_type == "tool_call")
    tool_result = next(block for block in analysis.ir.blocks if block.block_type == "tool_result_recent")
    assert tool_call.protected is True
    assert tool_result.protected is True
    assert tool_call.tool_use_id == "toolu_1"
    assert tool_result.tool_use_id == "toolu_1"


def test_missing_tool_result_id_is_invalid():
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "read", "input": {}}],
            },
            {"role": "user", "content": [{"type": "tool_result", "content": "result without id"}]},
        ]
    }

    analysis = tool_graph.analyze_anthropic_tool_graph(payload)

    assert analysis.valid is False
    assert {issue.code for issue in analysis.issues} == {"missing_tool_result_id", "missing_tool_result"}


def test_mismatched_tool_result_id_is_invalid():
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "read", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_2", "content": "wrong result"}],
            },
        ]
    }

    analysis = tool_graph.analyze_anthropic_tool_graph(payload)

    assert analysis.valid is False
    assert {issue.code for issue in analysis.issues} == {
        "unknown_tool_result_id",
        "missing_tool_result",
    }


def test_multiple_tool_calls_validate_when_each_has_result():
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "toolu_a", "name": "read", "input": {}},
                    {"type": "tool_use", "id": "toolu_b", "name": "grep", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_a", "content": "a"},
                    {"type": "tool_result", "tool_use_id": "toolu_b", "content": "b"},
                ],
            },
        ]
    }

    analysis = tool_graph.analyze_anthropic_tool_graph(payload)

    assert analysis.valid is True
    assert len([block for block in analysis.ir.blocks if block.block_type == "tool_call"]) == 2
    assert len([block for block in analysis.ir.blocks if block.block_type == "tool_result_recent"]) == 2


def test_text_only_payload_parses_without_tool_graph():
    payload = {
        "system": "You are concise.",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Summarize this."},
        ],
    }

    analysis = tool_graph.analyze_anthropic_tool_graph(payload)

    assert analysis.valid is True
    assert analysis.has_tool_graph is False
    assert [block.block_type for block in analysis.ir.blocks] == [
        "system_policy",
        "conversation_history",
        "assistant_state",
        "current_user_intent",
    ]
