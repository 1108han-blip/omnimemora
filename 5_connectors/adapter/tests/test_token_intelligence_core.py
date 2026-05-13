import importlib
import json
import sqlite3
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "application"
sys.path.insert(0, str(APP_DIR))
token_intelligence = importlib.import_module("token_intelligence")


def test_openai_compatible_usage_normalization_keeps_source_and_details():
    usage = token_intelligence.normalize_openai_compatible_usage(
        {
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "total_tokens": 1500,
                "prompt_tokens_details": {
                    "cached_tokens": 256,
                    "cache_write_tokens": 64,
                    "image_tokens": 12,
                },
                "completion_tokens_details": {
                    "reasoning_tokens": 42,
                },
            }
        }
    )

    assert usage.input_tokens == 1200
    assert usage.output_tokens == 300
    assert usage.total_tokens == 1500
    assert usage.cached_input_tokens == 256
    assert usage.cache_write_tokens == 64
    assert usage.reasoning_tokens == 42
    assert usage.image_tokens == 12
    assert usage.source == "provider_reported"
    assert usage.confidence == "official_usage"
    assert usage.raw_usage_present is True


def test_missing_usage_is_labeled_as_local_estimate():
    usage = token_intelligence.normalize_openai_compatible_usage(
        {"id": "chatcmpl-missing-usage"},
        local_input_estimate=90,
        local_output_estimate=10,
    )

    assert usage.input_tokens == 90
    assert usage.output_tokens == 10
    assert usage.total_tokens == 100
    assert usage.source == "local_estimated"
    assert usage.confidence == "tokenizer_estimate"
    assert usage.raw_usage_present is False


def test_openai_compatible_estimator_returns_bounded_counts():
    request_tokens = token_intelligence.estimate_openai_compatible_input_tokens(
        {"model": "relay-model", "messages": [{"role": "user", "content": "中文 mixed request"}]}
    )
    output_tokens = token_intelligence.estimate_openai_compatible_output_tokens(
        {"choices": [{"message": {"role": "assistant", "content": "estimated answer"}}]}
    )
    usage = token_intelligence.normalize_openai_compatible_usage(
        {"id": "chatcmpl-no-usage"},
        local_input_estimate=request_tokens,
        local_output_estimate=output_tokens,
        local_estimate_confidence="compatible_estimate",
    )

    assert request_tokens is not None and request_tokens > 0
    assert output_tokens is not None and output_tokens > 0
    assert usage.source == "local_estimated"
    assert usage.confidence == "compatible_estimate"
    assert usage.total_tokens == request_tokens + output_tokens


def test_block_breakdown_classifies_without_raw_content():
    secret_tool_result = "SECRET_TOOL_RESULT_NOT_IN_BLOCKS"
    blocks = token_intelligence.classify_openai_compatible_blocks(
        {
            "model": "relay-model",
            "messages": [
                {"role": "system", "content": "system rules"},
                {"role": "user", "content": "older request"},
                {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "search"}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": secret_tool_result},
                {"role": "user", "content": "current request"},
            ],
            "tools": [{"type": "function", "function": {"name": "search"}}],
            "omni_memory_context": {"hit_count": 2},
        },
        {"choices": [{"message": {"content": "answer"}}]},
    )
    block_types = {block["block_type"] for block in blocks}

    assert {
        "system_developer_instructions",
        "current_user_intent",
        "conversation_history",
        "tool_schemas",
        "tool_calls",
        "tool_results",
        "memory_context_injection",
        "provider_output",
    }.issubset(block_types)
    assert all(block["token_estimate"] > 0 for block in blocks)
    assert secret_tool_result not in json.dumps(blocks, sort_keys=True)


def test_waste_detectors_emit_safe_optimization_opportunities():
    repeated = "repeat this long context block for duplicate detection"
    secret_tool_result = "SECRET_LONG_TOOL_RESULT_NOT_IN_OPPORTUNITY " * 160
    blocks = token_intelligence.classify_openai_compatible_blocks(
        {
            "messages": [
                {"role": "user", "content": repeated},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": repeated},
                {"role": "tool", "content": secret_tool_result},
                {"role": "user", "content": "current request"},
            ]
        }
    )
    opportunities = token_intelligence.detect_openai_compatible_waste(
        {
            "messages": [
                {"role": "user", "content": repeated},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": repeated},
                {"role": "tool", "content": secret_tool_result},
                {"role": "user", "content": "current request"},
            ]
        },
        blocks,
    )
    categories = {item["category"] for item in opportunities}

    assert "duplicate_context" in categories
    assert "long_tool_result" in categories
    assert all(item["potential_saving_tokens"] > 0 for item in opportunities)
    assert all(item["source"] == "local_estimated" for item in opportunities)
    assert secret_tool_result not in json.dumps(opportunities, sort_keys=True)


def test_audit_ledger_roundtrip_and_receipt_are_metadata_only(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    request_secret = "SECRET_PROMPT_SHOULD_NOT_BE_STORED"
    response_secret = "SECRET_RESPONSE_SHOULD_NOT_BE_STORED"
    usage = token_intelligence.normalize_openai_compatible_usage(
        {
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 5,
                "total_tokens": 25,
            }
        }
    )

    event = token_intelligence.build_audit_event(
        request_id="req-token-intelligence",
        request_payload={"messages": [{"role": "user", "content": request_secret}]},
        response_payload={"choices": [{"message": {"content": response_secret}}]},
        upstream_base_url="https://relay.example/v1",
        provider="relay",
        model_requested="gpt-compatible",
        model_reported="gpt-compatible",
        usage=usage,
        latency_ms=123,
        status_code=200,
        metadata={
            "agent_id": "test-agent",
            "raw_prompt": request_secret,
            "tool_output": response_secret,
            "nested": {"content": request_secret},
        },
        blocks=[
            {
                "block_type": "current_user_intent",
                "token_estimate": 8,
                "item_count": 1,
                "source": "local_estimated",
                "confidence": "compatible_estimate",
                "raw_content": request_secret,
            }
        ],
        opportunities=[
            {
                "detector_id": "duplicate_context_v1",
                "category": "duplicate_context",
                "reason_code": "repeated_message_content",
                "token_estimate": 8,
                "potential_saving_tokens": 8,
                "item_count": 1,
                "severity": "medium",
                "source": "local_estimated",
                "confidence": "compatible_estimate",
                "raw_content": request_secret,
            }
        ],
    )

    token_intelligence.record_audit_event(event)
    loaded = token_intelligence.get_audit_event(event.audit_id)
    receipt = token_intelligence.build_receipt(loaded)

    assert token_intelligence.count_events() == 1
    assert loaded is not None
    assert loaded.audit_id == event.audit_id
    assert loaded.request_id == "req-token-intelligence"
    assert loaded.usage.total_tokens == 25
    assert loaded.metadata == {"agent_id": "test-agent"}
    assert loaded.blocks == [
        {
            "block_type": "current_user_intent",
            "token_estimate": 8,
            "item_count": 1,
            "source": "local_estimated",
            "confidence": "compatible_estimate",
        }
    ]
    assert loaded.opportunities == [
        {
            "detector_id": "duplicate_context_v1",
            "category": "duplicate_context",
            "reason_code": "repeated_message_content",
            "token_estimate": 8,
            "potential_saving_tokens": 8,
            "item_count": 1,
            "severity": "medium",
            "source": "local_estimated",
            "confidence": "compatible_estimate",
        }
    ]
    assert receipt["request_hash"].startswith("sha256:")
    assert receipt["response_hash"].startswith("sha256:")
    assert receipt["usage"]["source"] == "provider_reported"
    assert receipt["blocks"][0]["block_type"] == "current_user_intent"
    assert receipt["opportunities"][0]["category"] == "duplicate_context"

    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_events WHERE audit_id = ?", (event.audit_id,)).fetchone()
        meta = dict(conn.execute("SELECT key, value FROM audit_meta").fetchall())

    serialized_row = json.dumps(dict(row), sort_keys=True)
    assert request_secret not in serialized_row
    assert response_secret not in serialized_row
    assert meta["schema_version"] == "token-intelligence-ledger-v1"
    assert meta["content_mode"] == "metadata_only"
