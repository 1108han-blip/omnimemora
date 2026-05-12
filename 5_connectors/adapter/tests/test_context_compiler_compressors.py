import importlib


compressors = importlib.import_module("5_connectors.adapter.application.context_compiler.compressors")
compiler = importlib.import_module("5_connectors.adapter.application.context_compiler.compiler")


GOLDEN_TOOL_OUTPUT_FIXTURES = [
    {
        "label": "search_result",
        "tool_name": "grep",
        "expected_output_type": "search_result",
        "max_chars": 900,
        "text": "\n".join(
            [f"src/generated_{i}.py:{i}: ordinary search hit" for i in range(80)]
            + ["src/target.py:404: REQUIRED_SEARCH_MARKER compiled_payload_token_delta"]
            + [f"docs/noise_{i}.md:{i}: repeated search hit" for i in range(80)]
        ),
        "required_markers": ["src/target.py:404", "REQUIRED_SEARCH_MARKER"],
    },
    {
        "label": "file_read",
        "tool_name": "read",
        "expected_output_type": "file_read",
        "max_chars": 900,
        "text": "\n".join(
            ["import os", "from pathlib import Path"]
            + [f"implementation detail {i}" for i in range(140)]
            + ["def required_function_marker():", "    return 'REQUIRED_FILE_MARKER'"]
        ),
        "required_markers": ["required_function_marker", "REQUIRED_FILE_MARKER"],
    },
    {
        "label": "log",
        "tool_name": "logs",
        "expected_output_type": "log",
        "max_chars": 900,
        "text": "\n".join(
            [f"2026-05-13T00:00:{i:02d} INFO regular request_id=req-{i}" for i in range(60)]
            + ["2026-05-13T00:01:00 ERROR REQUIRED_LOG_MARKER timeout request_id=req-critical"]
            + [f"2026-05-13T00:02:{i:02d} DEBUG noisy detail" for i in range(80)]
        ),
        "required_markers": ["REQUIRED_LOG_MARKER", "req-critical"],
    },
    {
        "label": "diff",
        "tool_name": "read",
        "expected_output_type": "diff",
        "max_chars": 900,
        "text": "\n".join(
            [
                "diff --git a/src/compiler.py b/src/compiler.py",
                "index 111..222",
                "--- a/src/compiler.py",
                "+++ b/src/compiler.py",
                "@@ -80,6 +80,7 @@",
            ]
            + [f"+added implementation line {i}" for i in range(60)]
            + ["+REQUIRED_DIFF_MARKER preserve_tool_result_id"]
            + [f"-removed noisy line {i}" for i in range(60)]
        ),
        "required_markers": ["REQUIRED_DIFF_MARKER", "@@ -80,6 +80,7 @@"],
    },
    {
        "label": "test_output",
        "tool_name": "pytest",
        "expected_output_type": "test_output",
        "max_chars": 900,
        "text": "\n".join(
            ["============================= test session starts ============================="]
            + [f"tests/test_noise.py::{i} PASSED" for i in range(100)]
            + ["FAILED tests/test_required.py::test_marker - AssertionError: REQUIRED_TEST_MARKER"]
            + ["=========================== 1 failed, 100 passed ============================"]
        ),
        "required_markers": ["REQUIRED_TEST_MARKER", "1 failed"],
    },
]


def test_diff_output_uses_diff_classifier_and_marker():
    text = "\n".join(
        ["diff --git a/a.py b/a.py", "index 111..222", "--- a/a.py", "+++ b/a.py", "@@ -1,3 +1,3 @@"]
        + [f"+added line {i}" for i in range(120)]
    )

    result = compressors.compress_tool_result_text(text, max_chars=700)

    assert result.changed is True
    assert result.output_type == "diff"
    assert "deterministic diff compression" in result.text
    assert result.compressed_chars < result.original_chars


def test_test_output_preserves_failure_lines():
    text = "\n".join(
        ["============================= test session starts ============================="]
        + [f"test_module.py::{i} PASSED" for i in range(80)]
        + ["FAILED test_module.py::test_breaks - AssertionError: expected true"]
        + ["=========================== 1 failed, 80 passed ============================"]
    )

    result = compressors.compress_tool_result_text(text, max_chars=800)

    assert result.changed is True
    assert result.output_type == "test_output"
    assert "AssertionError" in result.text
    assert "1 failed" in result.text


def test_search_result_classifier_keeps_path_hits():
    text = "\n".join([f"src/file_{i}.py:{i}: match line with context" for i in range(100)])

    result = compressors.compress_tool_result_text(text, max_chars=700)

    assert result.changed is True
    assert result.output_type == "search_result"
    assert "src/file_0.py:0" in result.text


def test_file_read_classifier_keeps_definitions():
    text = "\n".join(
        ["import os", "from pathlib import Path"]
        + [f"regular implementation line {i}" for i in range(90)]
        + ["def important_function():", "    return True"]
    )

    result = compressors.compress_tool_result_text(text, max_chars=700)

    assert result.changed is True
    assert result.output_type == "file_read"
    assert "def important_function" in result.text


def test_golden_tool_output_fixtures_reduce_tokens_and_keep_required_markers():
    for fixture in GOLDEN_TOOL_OUTPUT_FIXTURES:
        result = compressors.compress_tool_result_text(
            fixture["text"],
            max_chars=fixture["max_chars"],
        )

        assert result.changed is True, fixture["label"]
        assert result.output_type == fixture["expected_output_type"]
        assert result.compressed_chars < result.original_chars
        for marker in fixture["required_markers"]:
            assert marker in result.text, fixture["label"]


def test_golden_tool_output_fixtures_preserve_graph_and_latest_result():
    latest_result = "LATEST_RESULT_UNCHANGED"

    for fixture in GOLDEN_TOOL_OUTPUT_FIXTURES:
        tool_name = fixture["tool_name"]
        payload = {
            "tools": [{"name": tool_name, "description": f"{tool_name} fixture"}],
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_old", "name": tool_name, "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_old", "content": fixture["text"]}],
                },
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "toolu_latest", "name": tool_name, "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_latest", "content": latest_result}],
                },
            ],
        }

        result = compiler.compile_anthropic_tool_context(
            payload,
            max_tool_result_chars=fixture["max_chars"],
        )

        assert result.status == "structured_compile_success", fixture["label"]
        assert result.changed_blocks == 1
        old_content = result.payload["messages"][1]["content"][0]["content"]
        latest_content = result.payload["messages"][3]["content"][0]["content"]
        assert result.compiled_token_estimate < result.original_token_estimate
        assert result.payload["messages"][1]["content"][0]["tool_use_id"] == "toolu_old"
        assert result.payload["messages"][3]["content"][0]["tool_use_id"] == "toolu_latest"
        assert latest_content == latest_result
        for marker in fixture["required_markers"]:
            assert marker in old_content, fixture["label"]
