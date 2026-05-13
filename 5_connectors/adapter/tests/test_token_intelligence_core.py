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
    assert receipt["request_hash"].startswith("sha256:")
    assert receipt["response_hash"].startswith("sha256:")
    assert receipt["usage"]["source"] == "provider_reported"

    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_events WHERE audit_id = ?", (event.audit_id,)).fetchone()
        meta = dict(conn.execute("SELECT key, value FROM audit_meta").fetchall())

    serialized_row = json.dumps(dict(row), sort_keys=True)
    assert request_secret not in serialized_row
    assert response_secret not in serialized_row
    assert meta["schema_version"] == "token-intelligence-ledger-v1"
    assert meta["content_mode"] == "metadata_only"
