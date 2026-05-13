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


def test_openai_compatible_cost_normalization_keeps_source_and_pricing_version():
    cost = token_intelligence.normalize_openai_compatible_cost(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cost": "0.00123",
                "pricing_version": "relay-price-2026-05-13",
            }
        },
        cost_source="relay_reported",
    )
    missing = token_intelligence.normalize_openai_compatible_cost({"usage": {"total_tokens": 15}})

    assert cost.total_cost_usd == 0.00123
    assert cost.source == "relay_reported"
    assert cost.confidence == "official_usage"
    assert cost.pricing_version == "relay-price-2026-05-13"
    assert missing.total_cost_usd is None


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


def test_potential_savings_report_summarizes_opportunities():
    report = token_intelligence.build_potential_savings_report(
        {
            "event_count": 2,
            "top_opportunities": [
                {"category": "duplicate_context", "potential_saving_tokens": 12},
                {"category": "long_tool_result", "potential_saving_tokens": 30},
            ],
            "top_blocks": [{"block_type": "tool_results", "token_estimate": 80}],
            "top_models": [{"model": "relay-model", "total_tokens": 100}],
        }
    )

    assert report["potential_saving_tokens"] == 42
    assert report["confidence"] == "compatible_estimate"
    assert {item["category"] for item in report["advice"]} == {"duplicate_context", "tool_results"}


def test_actual_savings_proof_classifies_realized_and_negative_savings():
    realized = token_intelligence.build_actual_savings_proof(
        {
            "recommendation_id": "rec-1",
            "category": "duplicate_context",
            "recommended_saving_tokens": 40,
            "baseline_tokens": 100,
            "actual_tokens": 55,
        }
    )
    negative = token_intelligence.build_actual_savings_proof(
        {
            "recommendation_id": "rec-2",
            "category": "tool_results",
            "recommended_saving_tokens": 40,
            "baseline_tokens": 100,
            "actual_tokens": 120,
        }
    )

    assert realized["status"] == "realized"
    assert realized["realized_saving_tokens"] == 45
    assert realized["realization_ratio"] == 1.125
    assert negative["status"] == "negative_saving"
    assert negative["negative_saving_tokens"] == 20


def test_usage_reconciliation_classifies_normal_and_unexplained_delta():
    request_payload = {"model": "relay-model", "messages": [{"role": "user", "content": "short request"}]}
    response_payload = {"choices": [{"message": {"content": "short answer"}}]}
    local_input = token_intelligence.estimate_openai_compatible_input_tokens(request_payload) or 1
    local_output = token_intelligence.estimate_openai_compatible_output_tokens(response_payload) or 1
    local_total = local_input + local_output
    normal_usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": local_total, "completion_tokens": 0, "total_tokens": local_total}},
        usage_source="relay_reported",
    )
    high_usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": local_total * 3, "completion_tokens": 0, "total_tokens": local_total * 3}},
        usage_source="relay_reported",
    )

    normal = token_intelligence.reconcile_openai_compatible_usage(request_payload, response_payload, normal_usage)
    high = token_intelligence.reconcile_openai_compatible_usage(request_payload, response_payload, high_usage)

    assert normal["status"] == "normal"
    assert normal["delta_tokens"] == 0
    assert high["status"] == "unexplained_delta"
    assert high["delta_ratio"] > 1.0


def test_mcp_companion_tools_are_read_only_and_bounded(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        usage_source="relay_reported",
    )
    event = token_intelligence.build_audit_event(
        request_id="mcp-summary",
        request_payload={"model": "relay"},
        response_payload={"id": "mcp-summary"},
        upstream_base_url="https://relay.example/v1",
        provider="local_proxy",
        model_requested="relay-model",
        usage=usage,
        opportunities=[
            {
                "detector_id": "duplicate_context_v1",
                "category": "duplicate_context",
                "reason_code": "repeated_message_content",
                "token_estimate": 10,
                "potential_saving_tokens": 10,
                "item_count": 1,
                "severity": "medium",
                "source": "local_estimated",
                "confidence": "compatible_estimate",
            }
        ],
        reconciliation={
            "schema_version": "token-intelligence-usage-reconciliation-v1",
            "reported_total_tokens": 25,
            "local_total_estimate": 20,
            "delta_tokens": 5,
            "delta_ratio": 0.25,
            "status": "normal",
            "source": "local_estimated",
            "confidence": "compatible_estimate",
            "raw_content": "SECRET_RECONCILIATION_CONTENT_NOT_STORED",
        },
    )
    token_intelligence.record_audit_event(event)

    tools = token_intelligence.dispatch_mcp_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    summary = token_intelligence.dispatch_mcp_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "token_intelligence.summary", "arguments": {"limit": 5000}},
        }
    )
    report = token_intelligence.dispatch_mcp_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "token_intelligence.potential_savings", "arguments": {"limit": 1}},
        }
    )

    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    assert tool_names == {"token_intelligence.summary", "token_intelligence.potential_savings"}
    summary_payload = json.loads(summary["result"]["content"][0]["text"])
    report_payload = json.loads(report["result"]["content"][0]["text"])
    assert summary_payload["window"] == {"bounded": True, "limit": 1000}
    assert summary_payload["event_count"] == 1
    assert report_payload["potential_saving_tokens"] == 10


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
        reconciliation={
            "schema_version": "token-intelligence-usage-reconciliation-v1",
            "reported_total_tokens": 25,
            "local_total_estimate": 20,
            "delta_tokens": 5,
            "delta_ratio": 0.25,
            "status": "normal",
            "source": "local_estimated",
            "confidence": "compatible_estimate",
            "raw_content": request_secret,
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
    assert loaded.reconciliation["status"] == "normal"
    assert receipt["request_hash"].startswith("sha256:")
    assert receipt["response_hash"].startswith("sha256:")
    assert receipt["usage"]["source"] == "provider_reported"
    assert receipt["blocks"][0]["block_type"] == "current_user_intent"
    assert receipt["opportunities"][0]["category"] == "duplicate_context"
    assert receipt["reconciliation"]["status"] == "normal"
    assert "raw_content" not in receipt["reconciliation"]

    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_events WHERE audit_id = ?", (event.audit_id,)).fetchone()
        meta = dict(conn.execute("SELECT key, value FROM audit_meta").fetchall())

    serialized_row = json.dumps(dict(row), sort_keys=True)
    assert request_secret not in serialized_row
    assert response_secret not in serialized_row
    assert meta["schema_version"] == "token-intelligence-ledger-v1"
    assert meta["content_mode"] == "metadata_only"


def test_top_requests_report_is_bounded_and_metadata_only(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    secret_prompt = "SECRET_TOP_REQUEST_PROMPT_NOT_STORED"
    small_usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5}},
        usage_source="relay_reported",
    )
    large_usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": 90, "completion_tokens": 10, "total_tokens": 100}},
        usage_source="relay_reported",
    )
    small_event = token_intelligence.build_audit_event(
        request_id="req-small",
        request_payload={"messages": [{"role": "user", "content": secret_prompt}]},
        response_payload={"id": "req-small"},
        upstream_base_url="https://relay.example/v1",
        provider="relay",
        model_requested="small-model",
        usage=small_usage,
    )
    large_event = token_intelligence.build_audit_event(
        request_id="req-large",
        request_payload={"messages": [{"role": "user", "content": secret_prompt}]},
        response_payload={"id": "req-large"},
        upstream_base_url="https://relay.example/v1",
        provider="relay",
        model_requested="large-model",
        usage=large_usage,
        cost=token_intelligence.NormalizedCost(
            total_cost_usd=0.0123,
            source="relay_reported",
            confidence="official_usage",
            pricing_version="test-price-v1",
        ),
        opportunities=[
            {
                "detector_id": "duplicate_context_v1",
                "category": "duplicate_context",
                "reason_code": "repeated_message_content",
                "token_estimate": 50,
                "potential_saving_tokens": 20,
                "item_count": 2,
                "severity": "medium",
                "source": "local_estimated",
                "confidence": "compatible_estimate",
            }
        ],
        reconciliation={"status": "normal"},
        latency_ms=42,
        status_code=200,
        metadata={"agent_id": "openclaw", "workflow_tag": "coding", "project_id": "token-audit-test"},
    )
    token_intelligence.record_audit_event(small_event)
    token_intelligence.record_audit_event(large_event)

    report = token_intelligence.list_top_requests(limit=5000)
    summary = token_intelligence.summarize_recent_events(limit=5000)

    assert report["window"] == {"bounded": True, "limit": 1000}
    assert report["event_count"] == 2
    assert report["top_by_tokens"][0]["request_id"] == "req-large"
    assert report["top_by_tokens"][0]["total_tokens"] == 100
    assert report["top_by_tokens"][0]["agent_id"] == "openclaw"
    assert report["top_by_tokens"][0]["workflow_tag"] == "coding"
    assert report["top_by_tokens"][0]["potential_saving_tokens"] == 20
    assert report["top_by_cost"][0]["total_cost_usd"] == 0.0123
    assert summary["top_agents"][0]["agent_id"] == "openclaw"
    assert summary["top_workflows"][0]["workflow_tag"] == "coding"
    assert summary["top_projects"][0]["project_id"] == "token-audit-test"
    assert secret_prompt not in json.dumps(report, sort_keys=True)
    assert secret_prompt not in json.dumps(summary, sort_keys=True)


def test_audit_ledger_delete_and_retention_purge(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "token_intelligence.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    )
    old_event = token_intelligence.build_audit_event(
        request_id="old",
        request_payload={"model": "relay"},
        response_payload={"id": "old"},
        upstream_base_url="https://relay.example/v1",
        provider="relay",
        model_requested="relay",
        usage=usage,
    )
    delete_event = token_intelligence.build_audit_event(
        request_id="delete",
        request_payload={"model": "relay"},
        response_payload={"id": "delete"},
        upstream_base_url="https://relay.example/v1",
        provider="relay",
        model_requested="relay",
        usage=usage,
    )
    token_intelligence.record_audit_event(old_event)
    token_intelligence.record_audit_event(delete_event)
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.execute(
            "UPDATE audit_events SET created_at = ? WHERE audit_id = ?",
            ("2000-01-01T00:00:00+00:00", old_event.audit_id),
        )

    assert token_intelligence.count_events() == 2
    assert token_intelligence.delete_audit_event(delete_event.audit_id) is True
    assert token_intelligence.delete_audit_event(delete_event.audit_id) is False
    assert token_intelligence.count_events() == 1
    assert token_intelligence.purge_audit_events_older_than(7) == 1
    assert token_intelligence.count_events() == 0
