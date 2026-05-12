import importlib


compressors = importlib.import_module("5_connectors.adapter.application.context_compiler.compressors")


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
