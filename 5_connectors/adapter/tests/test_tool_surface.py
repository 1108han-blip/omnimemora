import asyncio
import importlib

import pytest
from fastapi import HTTPException


tool_surface = importlib.import_module("5_connectors.adapter.tool_surface")


def test_mmx_search_success_compacts_json(monkeypatch):
    async def fake_run_command(args, timeout_seconds):
        assert args[0] == "mmx"
        assert args[1:4] == ["search", "query", "--q"]
        assert "--output" in args
        assert "json" in args
        return tool_surface.CommandResult(
            returncode=0,
            stdout='{"results":[{"title":"A","snippet":"hello"}]}',
            stderr="",
        )

    monkeypatch.setattr(tool_surface, "_run_command", fake_run_command)
    monkeypatch.setattr(tool_surface, "_resolve_mmx_executable", lambda: "mmx")
    response = asyncio.run(
        tool_surface.search_tool(
            tool_surface.ToolSearchRequest(
                query="MiniMax search",
                max_chars=2000,
                agent_id="openclaw",
                trace_id="tool-test",
            )
        )
    )

    assert response["status"] == "ok"
    assert response["provider"] == "mmx"
    assert response["backend"] == "mmx_cli"
    assert response["output_format"] == "json"
    assert response["truncated"] is False
    assert response["agent_id"] == "openclaw"
    assert response["trace_id"] == "tool-test"
    assert "hello" in response["content"]
    assert response["retention"] == "response_only_no_product_log"


def test_mmx_search_caps_large_output(monkeypatch):
    async def fake_run_command(args, timeout_seconds):
        return tool_surface.CommandResult(returncode=0, stdout="x" * 2000, stderr="")

    monkeypatch.setattr(tool_surface, "_run_command", fake_run_command)
    monkeypatch.setattr(tool_surface, "_resolve_mmx_executable", lambda: "mmx")
    response = asyncio.run(
        tool_surface.search_tool(
            tool_surface.ToolSearchRequest(query="large output", max_chars=300)
        )
    )

    assert response["output_format"] == "text"
    assert response["truncated"] is True
    assert response["content_chars"] <= 300
    assert "omnimemora_truncated" in response["content"]


def test_search_rejects_unsupported_provider():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            tool_surface.search_tool(
                tool_surface.ToolSearchRequest(query="hello", provider="perplexity")
            )
        )

    assert exc.value.status_code == 400
    assert "unsupported_tool_search_provider" in exc.value.detail


def test_search_backend_failure_is_bounded(monkeypatch):
    async def fake_run_command(args, timeout_seconds):
        return tool_surface.CommandResult(returncode=9, stdout="", stderr="bad" * 1000)

    monkeypatch.setattr(tool_surface, "_run_command", fake_run_command)
    monkeypatch.setattr(tool_surface, "_resolve_mmx_executable", lambda: "mmx")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(tool_surface.search_tool(tool_surface.ToolSearchRequest(query="fail")))

    assert exc.value.status_code == 502
    assert exc.value.detail["error"] == "tool_search_backend_failed"
    assert len(exc.value.detail["stderr"]) <= 1000


def test_mmx_executable_resolution_prefers_env(monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_TOOL_SEARCH_MMX_PATH", "/tmp/mmx")

    assert tool_surface._resolve_mmx_executable() == "/tmp/mmx"
