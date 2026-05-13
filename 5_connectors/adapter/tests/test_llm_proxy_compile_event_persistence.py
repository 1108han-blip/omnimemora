import importlib
from unittest import mock


llm_proxy = importlib.import_module("5_connectors.adapter.ingress.llm_proxy")


def test_record_compile_event_persists_task_type_and_skill_policy_defaults():
    captured = {"rows": []}

    class _FakeCompileStore:
        @staticmethod
        def append_compile_event(row):
            captured["rows"].append(row)

    real_import = importlib.import_module

    def _fake_import(name, *args, **kwargs):
        if name == "5_connectors.adapter.infrastructure.compile_store":
            return _FakeCompileStore
        return real_import(name, *args, **kwargs)

    compile_meta = {
        "compile_status": "compile_success",
        "task_type": "decision",
        "selected_memory_count": 1,
        "original_token_estimate": 100,
        "compiled_token_estimate": 70,
        "compression_ratio": 0.3,
        "compile_path": "runtime_compile",
        "compile_error": None,
        "compile_reason": "runtime_compile",
        "token_estimator_name": "mixed_script_heuristic_v1",
        "token_estimator_confidence": "medium",
        "structured_compile_latency_ms": 17,
        "deadline_profile": "openclaw_45s_long_tool_context",
        "deadline_profile_applied": True,
        "client_deadline_seconds": 45.0,
        "compile_budget_ms": 2500,
        "deadline_budget_exceeded": False,
        "protect_latest_tool_result": False,
        "max_tool_result_chars": 700,
        "skill_suggestions": None,
        "skill_policy_name": None,
        "skill_policy_version": None,
        "skill_policy_source": None,
        "skill_policy_status": None,
    }

    with mock.patch("importlib.import_module", side_effect=_fake_import):
        llm_proxy._record_compile_event(
            request_id="req-persist-1",
            agent_id="codex_cli",
            path="/v1/chat/completions",
            model="gpt-5.4",
            compile_meta=compile_meta,
        )

    assert captured["rows"], "append_compile_event should be called"
    row = captured["rows"][0]
    assert row["task_type"] == "decision"
    assert row["skill_suggestions"] == []
    assert row["skill_policy_name"] == "local_fallback"
    assert row["skill_policy_version"] == "static_catalog_v1"
    assert row["skill_policy_source"] == "local_builtin"
    assert row["skill_policy_status"] == "fallback"
    assert row["token_estimator_name"] == "mixed_script_heuristic_v1"
    assert row["token_estimator_confidence"] == "medium"
    assert row["structured_compile_latency_ms"] == 17
    assert row["deadline_profile"] == "openclaw_45s_long_tool_context"
    assert row["deadline_profile_applied"] is True
    assert row["client_deadline_seconds"] == 45.0
    assert row["compile_budget_ms"] == 2500
    assert row["deadline_budget_exceeded"] is False
    assert row["protect_latest_tool_result"] is False
    assert row["max_tool_result_chars"] == 700


def test_streaming_usage_sample_records_metadata_only_placeholder():
    captured = {}

    def _fake_schedule(**kwargs):
        captured.update(kwargs)

    with mock.patch.object(llm_proxy, "_schedule_product_usage_sample_fail_open", side_effect=_fake_schedule):
        llm_proxy._schedule_streaming_product_usage_sample_fail_open(
            protocol="anthropic_messages",
            request_id="req-stream-claude",
            route_label="/llm/v1/messages",
            request_payload={
                "model": "MiniMax-M2.7",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
            upstream_base_url="https://api.minimaxi.com/anthropic",
            provider="minimax_anthropic_compatible",
            model_requested="MiniMax-M2.7",
            latency_ms=123,
            status_code=200,
            agent_id="claude_code",
        )

    assert captured["protocol"] == "anthropic_messages"
    assert captured["request_id"] == "req-stream-claude"
    assert captured["agent_id"] == "claude_code"
    assert captured["response_payload"] == {
        "id": "req-stream-claude",
        "model": "MiniMax-M2.7",
        "content": [],
        "stop_reason": "stream_complete",
    }
