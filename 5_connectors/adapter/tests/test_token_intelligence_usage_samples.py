import importlib
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "application"
sys.path.insert(0, str(APP_DIR))
token_intelligence = importlib.import_module("token_intelligence")


def test_openai_usage_sample_records_metadata_only_event(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    secret = "SECRET_OPENAI_PROMPT_NOT_STORED"

    event = token_intelligence.record_openai_usage_sample(
        request_id="req-openai-sample",
        route="/llm/chat",
        request_payload={
            "model": "mini-model",
            "messages": [{"role": "user", "content": secret}],
            "workflow_tag": "manual-check",
        },
        response_payload={
            "id": "chatcmpl-sample",
            "model": "mini-model",
            "choices": [{"message": {"content": "short answer"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 3,
                "total_tokens": 15,
                "prompt_tokens_details": {"cached_tokens": 2},
                "completion_tokens_details": {"reasoning_tokens": 1},
            },
        },
        upstream_base_url="https://relay.example/v1",
        provider="openai_compatible",
        model_requested="mini-model",
        latency_ms=42,
        status_code=200,
        agent_id="openclaw",
    )

    loaded = token_intelligence.get_audit_event(event.audit_id)
    receipt = token_intelligence.build_receipt(loaded)
    serialized = json.dumps([receipt, loaded.to_dict()], ensure_ascii=False, sort_keys=True)

    assert loaded is not None
    assert receipt["usage"]["source"] == "provider_reported"
    assert receipt["usage"]["confidence"] == "official_usage"
    assert receipt["usage"]["total_tokens"] == 15
    assert loaded.metadata["schema_version"] == "llm-usage-sample-v1"
    assert loaded.metadata["protocol"] == "openai_chat_completions"
    assert loaded.metadata["agent_id"] == "openclaw"
    assert loaded.metadata["verification_status"] in {"normal", "warning", "unexplained_delta"}
    assert secret not in serialized


def test_anthropic_usage_sample_records_cache_fields_without_raw_content(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    secret = "SECRET_ANTHROPIC_PROMPT_NOT_STORED"

    event = token_intelligence.record_anthropic_usage_sample(
        request_id="req-anthropic-sample",
        route="/llm/v1/messages",
        request_payload={
            "model": "minimax-m2.7",
            "messages": [{"role": "user", "content": secret}],
        },
        response_payload={
            "id": "msg_sample",
            "model": "minimax-m2.7",
            "content": [{"type": "text", "text": "anthropic compatible answer"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 11,
                "output_tokens": 7,
                "cache_creation_input_tokens": 3,
                "cache_read_input_tokens": 2,
            },
        },
        upstream_base_url="https://anthropic-relay.example",
        provider="minimax_anthropic_compatible",
        model_requested="minimax-m2.7",
        latency_ms=55,
        status_code=200,
        agent_id="claude_code",
    )

    loaded = token_intelligence.get_audit_event(event.audit_id)
    receipt = token_intelligence.build_receipt(loaded)
    serialized = json.dumps([receipt, loaded.to_dict()], ensure_ascii=False, sort_keys=True)

    assert loaded is not None
    assert receipt["usage"]["source"] == "provider_reported"
    assert receipt["usage"]["input_tokens"] == 11
    assert receipt["usage"]["output_tokens"] == 7
    assert receipt["usage"]["cached_input_tokens"] == 2
    assert receipt["usage"]["cache_write_tokens"] == 3
    assert loaded.metadata["protocol"] == "anthropic_messages"
    assert loaded.metadata["finish_reason"] == "end_turn"
    assert secret not in serialized


def test_usage_sample_without_provider_usage_is_explicit_estimate(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))

    event = token_intelligence.record_openai_usage_sample(
        request_id="req-estimated-sample",
        route="/llm/chat",
        request_payload={
            "model": "mini-model",
            "messages": [{"role": "user", "content": "estimate this"}],
        },
        response_payload={
            "id": "chatcmpl-no-usage",
            "model": "mini-model",
            "choices": [{"message": {"content": "estimated answer"}, "finish_reason": "stop"}],
        },
        upstream_base_url="https://relay.example/v1",
        provider="openai_compatible",
        model_requested="mini-model",
        status_code=200,
        agent_id="openclaw",
    )

    loaded = token_intelligence.get_audit_event(event.audit_id)
    receipt = token_intelligence.build_receipt(loaded)

    assert receipt["usage"]["source"] == "local_estimated"
    assert receipt["usage"]["confidence"] == "tokenizer_estimate"
    assert receipt["usage"]["raw_usage_present"] is False
    assert loaded.metadata["verification_status"] == "estimated_only"
    assert receipt["usage"]["total_tokens"] > 0
