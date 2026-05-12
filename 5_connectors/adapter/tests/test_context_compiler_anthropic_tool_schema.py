import importlib


tool_schema = importlib.import_module(
    "5_connectors.adapter.application.context_compiler.anthropic_tool_schema"
)


def test_tool_schema_accepts_matching_declared_tools():
    payload = {
        "tools": [{"name": "grep", "description": "search files"}],
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}],
            },
        ],
    }

    analysis = tool_schema.analyze_anthropic_tool_schema(payload)

    assert analysis.valid is True
    assert analysis.issues == []


def test_tool_schema_rejects_undeclared_tool_use_when_tools_are_provided():
    payload = {
        "tools": [{"name": "read"}],
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}],
            },
        ],
    }

    analysis = tool_schema.analyze_anthropic_tool_schema(payload)

    assert analysis.valid is False
    assert [issue.code for issue in analysis.issues] == ["undeclared_tool_use_name"]
    assert analysis.issues[0].tool_name == "grep"


def test_tool_schema_accepts_absent_tools_for_session_context_payloads():
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "grep", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}],
            },
        ],
    }

    analysis = tool_schema.analyze_anthropic_tool_schema(payload)

    assert analysis.valid is True
