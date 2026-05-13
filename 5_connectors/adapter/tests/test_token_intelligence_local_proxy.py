import importlib
import json
import sqlite3
import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "application"
sys.path.insert(0, str(APP_DIR))
token_intelligence = importlib.import_module("token_intelligence")


class _FakeUpstreamHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib handler API
        content_length = int(self.headers.get("content-length") or "0")
        body = self.rfile.read(content_length)
        self.server.state["last_path"] = self.path
        self.server.state["last_body"] = body
        self.server.state["last_authorization"] = self.headers.get("authorization")
        self.server.state["last_x_api_key"] = self.headers.get("x-api-key")
        self.server.state["last_anthropic_version"] = self.headers.get("anthropic-version")
        self.server.state["last_content_type"] = self.headers.get("content-type")

        response_body = self.server.state.get("response_body", b"{}")
        self.send_response(int(self.server.state.get("response_status", 200)))
        self.send_header("content-type", self.server.state.get("response_content_type", "application/json"))
        self.send_header("content-length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, _format, *_args):
        return


def test_local_proxy_health_and_version_routes():
    proxy = _start_proxy("http://127.0.0.1:1/v1")
    try:
        health = _get_json(f"{_base_url(proxy)}/health")
        version = _get_json(f"{_base_url(proxy)}/version")
    finally:
        _stop_server(proxy)

    assert health["status"] == "ok"
    assert health["service"] == "omni-token-audit-local-proxy"
    assert health["mode"] == "candidate_local_proxy"
    assert version["version"] == "0.1.0-beta.2"


def test_report_page_is_local_static_html():
    proxy = _start_proxy("http://127.0.0.1:1/v1")
    try:
        report_status, report_body, report_headers = _get_raw(f"{_base_url(proxy)}/report")
        root_status, root_body, _root_headers = _get_raw(f"{_base_url(proxy)}/")
    finally:
        _stop_server(proxy)

    assert report_status == 200
    assert root_status == 200
    assert report_headers["content-type"].startswith("text/html")
    assert b"DoloToken Report" in report_body
    assert b"/audit/summary?limit=1000" in report_body
    assert b"/audit/reports/top-requests?limit=50" in report_body
    assert b"/audit/reports/potential-savings?limit=1000" in report_body
    assert b"https://" not in report_body
    assert b"DoloToken Report" in root_body


def test_chat_completions_forwards_body_to_configured_upstream():
    upstream_body = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    }
    upstream = _start_fake_upstream(response_body=_json_bytes(upstream_body))
    proxy = _start_proxy(f"{_base_url(upstream)}/v1", upstream_api_key="upstream-secret")
    request_body = {
        "model": "relay-model",
        "messages": [{"role": "user", "content": "keep this payload unchanged"}],
        "temperature": 0.2,
    }
    try:
        status, body = _post_json(f"{_base_url(proxy)}/v1/chat/completions", request_body)
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert json.loads(body) == upstream_body
    assert upstream.state["last_path"] == "/v1/chat/completions"
    assert json.loads(upstream.state["last_body"]) == request_body
    assert upstream.state["last_authorization"] == "Bearer upstream-secret"
    assert upstream.state["last_content_type"] == "application/json"


def test_chat_completions_records_audit_without_raw_prompt(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    secret_prompt = "SECRET_PROMPT_SHOULD_NOT_BE_IN_LEDGER"
    secret_response = "SECRET_RESPONSE_SHOULD_NOT_BE_IN_LEDGER"
    upstream_body = {
        "id": "chatcmpl-audited",
        "model": "relay-model-reported",
        "choices": [{"message": {"content": secret_response}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "cost": 0.0015,
            "pricing_version": "relay-test-price-v1",
        },
    }
    upstream = _start_fake_upstream(response_body=_json_bytes(upstream_body))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    request_body = {
        "model": "relay-model-requested",
        "messages": [{"role": "user", "content": secret_prompt}],
    }
    try:
        status, body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            request_body,
            headers={
                "x-omni-agent-id": "openclaw",
                "x-omni-project-id": "token-audit-test",
                "x-omni-workflow-tag": "coding",
            },
        )
        audit_id = headers["x-omni-token-audit-id"]
        receipt_status, receipt = _get_json_with_status(f"{_base_url(proxy)}/audit/events/{audit_id}/receipt")
        event_status, event = _get_json_with_status(f"{_base_url(proxy)}/audit/events/{audit_id}")
        summary_status, summary = _get_json_with_status(f"{_base_url(proxy)}/audit/summary?limit=10")
        top_status, top_requests = _get_json_with_status(f"{_base_url(proxy)}/audit/reports/top-requests?limit=5000")
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert json.loads(body) == upstream_body
    assert audit_id.startswith("omni_audit_")
    assert receipt_status == 200
    assert receipt["usage"]["source"] == "relay_reported"
    assert receipt["usage"]["confidence"] == "official_usage"
    assert receipt["cost"]["total_cost_usd"] == 0.0015
    assert receipt["cost"]["source"] == "relay_reported"
    assert receipt["cost"]["pricing_version"] == "relay-test-price-v1"
    assert receipt["reconciliation"]["reported_total_tokens"] == 15
    assert receipt["reconciliation"]["status"] in {"normal", "warning", "unexplained_delta"}
    assert {block["block_type"] for block in receipt["blocks"]} >= {"current_user_intent", "provider_output"}
    assert event_status == 200
    assert event["metadata"]["route"] == "/v1/chat/completions"
    assert event["metadata"]["agent_id"] == "openclaw"
    assert event["metadata"]["project_id"] == "token-audit-test"
    assert event["metadata"]["workflow_tag"] == "coding"
    assert event["blocks"] == receipt["blocks"]
    assert summary_status == 200
    assert summary["event_count"] == 1
    assert summary["usage"]["total_tokens"] == 15
    assert summary["usage_sources"] == {"relay_reported": 1}
    assert summary["top_models"] == [
        {"model": "relay-model-requested", "request_count": 1, "total_tokens": 15}
    ]
    assert summary["top_agents"][0]["agent_id"] == "openclaw"
    assert summary["top_workflows"][0]["workflow_tag"] == "coding"
    assert summary["top_projects"][0]["project_id"] == "token-audit-test"
    assert top_status == 200
    assert top_requests["window"] == {"bounded": True, "limit": 1000}
    assert top_requests["top_by_tokens"][0]["audit_id"] == audit_id
    assert top_requests["top_by_tokens"][0]["total_tokens"] == 15
    assert top_requests["top_by_tokens"][0]["agent_id"] == "openclaw"
    assert top_requests["top_by_tokens"][0]["workflow_tag"] == "coding"
    assert top_requests["top_by_cost"][0]["total_cost_usd"] == 0.0015
    assert {block["block_type"] for block in summary["top_blocks"]} >= {"current_user_intent", "provider_output"}
    assert sum(summary["reconciliation"]["status_counts"].values()) == 1
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_events LIMIT 1").fetchone()
    assert row["request_id"] == "chatcmpl-audited"
    assert row["model_requested"] == "relay-model-requested"
    assert row["model_reported"] == "relay-model-reported"
    usage = json.loads(row["usage_json"])
    assert usage["total_tokens"] == 15
    assert usage["source"] == "relay_reported"
    cost = json.loads(row["cost_json"])
    assert cost["total_cost_usd"] == 0.0015
    assert cost["source"] == "relay_reported"
    serialized_row = json.dumps(dict(row), sort_keys=True)
    assert secret_prompt not in serialized_row
    assert secret_response not in serialized_row
    serialized_api_payloads = json.dumps([receipt, event, summary, top_requests], sort_keys=True)
    assert secret_prompt not in serialized_api_payloads
    assert secret_response not in serialized_api_payloads


def test_anthropic_messages_forwards_and_records_audit_without_raw_content(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    secret_prompt = "SECRET_ANTHROPIC_PROMPT_NOT_IN_LEDGER"
    secret_response = "SECRET_ANTHROPIC_RESPONSE_NOT_IN_LEDGER"
    upstream_body = {
        "id": "msg_test_123",
        "type": "message",
        "role": "assistant",
        "model": "MiniMax-M2.7",
        "content": [{"type": "text", "text": secret_response}],
        "usage": {
            "input_tokens": 11,
            "output_tokens": 7,
            "cache_creation_input_tokens": 3,
            "cache_read_input_tokens": 2,
        },
    }
    upstream = _start_fake_upstream(response_body=_json_bytes(upstream_body))
    proxy = _start_proxy(
        _base_url(upstream),
        upstream_api_key="anthropic-secret",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    request_body = {
        "model": "MiniMax-M2.7",
        "max_tokens": 16,
        "messages": [{"role": "user", "content": secret_prompt}],
    }
    try:
        status, body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/messages",
            request_body,
            headers={
                "anthropic-version": "2023-06-01",
                "x-omni-agent-id": "openclaw",
            },
        )
        audit_id = headers["x-omni-token-audit-id"]
        receipt_status, receipt = _get_json_with_status(f"{_base_url(proxy)}/audit/events/{audit_id}/receipt")
        event_status, event = _get_json_with_status(f"{_base_url(proxy)}/audit/events/{audit_id}")
        summary_status, summary = _get_json_with_status(f"{_base_url(proxy)}/audit/summary?limit=10")
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert json.loads(body) == upstream_body
    assert upstream.state["last_path"] == "/v1/messages"
    assert json.loads(upstream.state["last_body"]) == request_body
    assert upstream.state["last_authorization"] is None
    assert upstream.state["last_x_api_key"] == "anthropic-secret"
    assert upstream.state["last_anthropic_version"] == "2023-06-01"
    assert receipt_status == 200
    assert event_status == 200
    assert summary_status == 200
    assert receipt["usage"]["source"] == "relay_reported"
    assert receipt["usage"]["confidence"] == "official_usage"
    assert receipt["usage"]["input_tokens"] == 11
    assert receipt["usage"]["output_tokens"] == 7
    assert receipt["usage"]["cache_write_tokens"] == 3
    assert receipt["usage"]["cached_input_tokens"] == 2
    assert receipt["usage"]["total_tokens"] == 23
    assert event["metadata"]["route"] == "/v1/messages"
    assert event["metadata"]["wire_protocol"] == "anthropic_messages"
    assert event["metadata"]["agent_id"] == "openclaw"
    assert summary["event_count"] == 1
    assert summary["usage"]["total_tokens"] == 23
    assert summary["top_agents"][0]["agent_id"] == "openclaw"
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_events LIMIT 1").fetchone()
    assert row["request_id"] == "msg_test_123"
    assert row["model_requested"] == "MiniMax-M2.7"
    assert row["model_reported"] == "MiniMax-M2.7"
    serialized = json.dumps([dict(row), receipt, event, summary], sort_keys=True)
    assert secret_prompt not in serialized
    assert secret_response not in serialized


def test_protocol_specific_upstreams_are_routed_separately():
    openai_upstream = _start_fake_upstream(
        response_body=_json_bytes(
            {
                "id": "chatcmpl-split",
                "model": "openai-relay-model",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
        )
    )
    anthropic_upstream = _start_fake_upstream(
        response_body=_json_bytes(
            {
                "id": "msg_split",
                "type": "message",
                "model": "MiniMax-M2.7",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 4, "output_tokens": 3},
            }
        )
    )
    proxy = _start_proxy_with_options(
        "https://legacy.example.invalid/v1",
        upstream_api_key="legacy-secret",
        openai_upstream_base_url=f"{_base_url(openai_upstream)}/v1",
        openai_upstream_api_key="openai-secret",
        anthropic_upstream_base_url=_base_url(anthropic_upstream),
        anthropic_upstream_api_key="anthropic-secret",
    )
    try:
        openai_status, _openai_body = _post_json(
            f"{_base_url(proxy)}/v1/chat/completions",
            {"model": "openai-relay-model", "messages": [{"role": "user", "content": "hello"}]},
        )
        anthropic_status, _anthropic_body = _post_json(
            f"{_base_url(proxy)}/v1/messages",
            {"model": "MiniMax-M2.7", "max_tokens": 8, "messages": [{"role": "user", "content": "hello"}]},
        )
    finally:
        _stop_server(proxy)
        _stop_server(openai_upstream)
        _stop_server(anthropic_upstream)

    assert openai_status == 200
    assert anthropic_status == 200
    assert openai_upstream.state["last_path"] == "/v1/chat/completions"
    assert openai_upstream.state["last_authorization"] == "Bearer openai-secret"
    assert openai_upstream.state["last_x_api_key"] is None
    assert anthropic_upstream.state["last_path"] == "/v1/messages"
    assert anthropic_upstream.state["last_authorization"] is None
    assert anthropic_upstream.state["last_x_api_key"] == "anthropic-secret"


def test_audit_write_failure_is_fail_open(tmp_path):
    sqlite_dir_path = tmp_path / "not-a-db-dir"
    sqlite_dir_path.mkdir()
    upstream_body = {
        "id": "chatcmpl-fail-open",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    upstream = _start_fake_upstream(response_body=_json_bytes(upstream_body))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_dir_path),
        audit_enabled=True,
        audit_fail_open=True,
    )
    try:
        status, body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            {"model": "relay-model"},
        )
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert json.loads(body) == upstream_body
    assert headers["x-omni-token-audit-error"] == "persistence_failed"


def test_missing_upstream_usage_records_compatible_local_estimate(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    upstream_body = {
        "id": "chatcmpl-no-usage",
        "model": "relay-model",
        "choices": [{"message": {"role": "assistant", "content": "estimated answer"}}],
    }
    upstream = _start_fake_upstream(response_body=_json_bytes(upstream_body))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    try:
        status, _body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            {"model": "relay-model", "messages": [{"role": "user", "content": "estimate this"}]},
        )
        receipt_status, receipt = _get_json_with_status(
            f"{_base_url(proxy)}/audit/events/{headers['x-omni-token-audit-id']}/receipt"
        )
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert receipt_status == 200
    assert receipt["usage"]["source"] == "local_estimated"
    assert receipt["usage"]["confidence"] == "compatible_estimate"
    assert receipt["usage"]["raw_usage_present"] is False
    assert receipt["usage"]["total_tokens"] > 0


def test_proxy_receipt_and_summary_include_safe_optimization_opportunities(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    repeated = "repeat this long context block for proxy duplicate detection"
    secret_tool_result = "SECRET_PROXY_TOOL_RESULT_NOT_IN_RECEIPT " * 160
    upstream = _start_fake_upstream(response_body=_json_bytes({"id": "chatcmpl-opportunities"}))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    request_body = {
        "model": "relay-model",
        "messages": [
            {"role": "user", "content": repeated},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": repeated},
            {"role": "tool", "content": secret_tool_result},
            {"role": "user", "content": "current request"},
        ],
    }
    try:
        status, _body, headers = _post_json_with_headers(f"{_base_url(proxy)}/v1/chat/completions", request_body)
        receipt_status, receipt = _get_json_with_status(
            f"{_base_url(proxy)}/audit/events/{headers['x-omni-token-audit-id']}/receipt"
        )
        summary_status, summary = _get_json_with_status(f"{_base_url(proxy)}/audit/summary")
        report_status, report = _get_json_with_status(f"{_base_url(proxy)}/audit/reports/potential-savings")
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert receipt_status == 200
    assert summary_status == 200
    categories = {item["category"] for item in receipt["opportunities"]}
    assert "duplicate_context" in categories
    assert "long_tool_result" in categories
    assert summary["top_opportunities"][0]["potential_saving_tokens"] > 0
    assert report_status == 200
    assert report["potential_saving_tokens"] > 0
    assert report["top_opportunities"]
    serialized = json.dumps([receipt, summary, report], sort_keys=True)
    assert secret_tool_result not in serialized
    assert repeated not in serialized


def test_audit_delete_and_disabled_audit_controls(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    upstream = _start_fake_upstream(response_body=_json_bytes({"id": "chatcmpl-delete"}))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    try:
        status, _body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            {"model": "relay-model", "messages": [{"role": "user", "content": "delete me"}]},
        )
        audit_id = headers["x-omni-token-audit-id"]
        delete_status, delete_payload = _delete_json(f"{_base_url(proxy)}/audit/events/{audit_id}")
        receipt_status, missing_payload = _get_json_with_status(f"{_base_url(proxy)}/audit/events/{audit_id}/receipt")
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert delete_status == 200
    assert delete_payload == {"audit_id": audit_id, "status": "deleted"}
    assert receipt_status == 404
    assert missing_payload["error"] == "audit_event_not_found"

    upstream = _start_fake_upstream(response_body=_json_bytes({"id": "chatcmpl-disabled"}))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=False,
    )
    try:
        status, _body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            {"model": "relay-model", "messages": [{"role": "user", "content": "do not audit"}]},
        )
        summary_status, summary = _get_json_with_status(f"{_base_url(proxy)}/audit/summary")
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert "x-omni-token-audit-id" not in headers
    assert summary_status == 200
    assert summary["event_count"] == 0


def test_retention_purge_endpoint_removes_old_rows(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    upstream = _start_fake_upstream(response_body=_json_bytes({"id": "chatcmpl-retention"}))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    try:
        status, _body, headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            {"model": "relay-model", "messages": [{"role": "user", "content": "old event"}]},
        )
        audit_id = headers["x-omni-token-audit-id"]
        with sqlite3.connect(str(sqlite_path)) as conn:
            conn.execute(
                "UPDATE audit_events SET created_at = ? WHERE audit_id = ?",
                ("2000-01-01T00:00:00+00:00", audit_id),
            )
        purge_status, purge_payload, _purge_headers = _post_json_with_headers(
            f"{_base_url(proxy)}/audit/retention/purge",
            {"older_than_days": 7},
        )
        summary_status, summary = _get_json_with_status(f"{_base_url(proxy)}/audit/summary")
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert purge_status == 200
    assert purge_payload and json.loads(purge_payload)["deleted_count"] == 1
    assert summary_status == 200
    assert summary["event_count"] == 0


def test_actual_savings_proof_endpoint_is_stateless(tmp_path):
    proxy = _start_proxy(
        "https://example.invalid/v1",
        audit_db_path=str(tmp_path / "audit.sqlite3"),
        audit_enabled=False,
    )
    try:
        status, body, _headers = _post_json_with_headers(
            f"{_base_url(proxy)}/audit/reports/actual-savings/proof",
            {
                "recommendation_id": "rec-proxy",
                "category": "duplicate_context",
                "recommended_saving_tokens": 20,
                "baseline_tokens": 100,
                "actual_tokens": 90,
            },
        )
    finally:
        _stop_server(proxy)

    payload = json.loads(body)
    assert status == 200
    assert payload["status"] == "partial"
    assert payload["realized_saving_tokens"] == 10
    assert payload["source"] == "local_estimated"


def test_mcp_companion_exposes_read_only_summary_tools(tmp_path):
    sqlite_path = tmp_path / "audit.sqlite3"
    upstream = _start_fake_upstream(response_body=_json_bytes({"id": "chatcmpl-mcp"}))
    proxy = _start_proxy(
        f"{_base_url(upstream)}/v1",
        audit_db_path=str(sqlite_path),
        audit_enabled=True,
    )
    repeated = "repeat this long context block for mcp summary"
    try:
        status, _body, _headers = _post_json_with_headers(
            f"{_base_url(proxy)}/v1/chat/completions",
            {
                "model": "relay-model",
                "messages": [
                    {"role": "user", "content": repeated},
                    {"role": "user", "content": repeated},
                    {"role": "user", "content": "current request"},
                ],
            },
        )
        health_status, health = _get_json_with_status(f"{_base_url(proxy)}/mcp")
        tools_status, tools_body, _tools_headers = _post_json_with_headers(
            f"{_base_url(proxy)}/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        report_status, report_body, _report_headers = _post_json_with_headers(
            f"{_base_url(proxy)}/mcp",
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "token_intelligence.potential_savings", "arguments": {"limit": 5}},
            },
        )
        top_status, top_body, _top_headers = _post_json_with_headers(
            f"{_base_url(proxy)}/mcp",
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "token_intelligence.top_requests", "arguments": {"limit": 5000}},
            },
        )
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 200
    assert health_status == 200
    assert health["mode"] == "candidate_local_companion"
    tools_payload = json.loads(tools_body)
    tool_names = {tool["name"] for tool in tools_payload["result"]["tools"]}
    assert tool_names == {
        "token_intelligence.summary",
        "token_intelligence.potential_savings",
        "token_intelligence.top_requests",
    }
    report_payload = json.loads(report_body)
    report = json.loads(report_payload["result"]["content"][0]["text"])
    top_payload = json.loads(top_body)
    top_report = json.loads(top_payload["result"]["content"][0]["text"])
    assert report_status == 200
    assert top_status == 200
    assert report["potential_saving_tokens"] > 0
    assert top_report["window"] == {"bounded": True, "limit": 1000}
    assert top_report["top_by_tokens"][0]["request_id"] == "chatcmpl-mcp"
    assert repeated not in json.dumps(report_payload, sort_keys=True)
    assert repeated not in json.dumps(top_payload, sort_keys=True)


def test_update_check_reads_release_metadata_without_download(tmp_path):
    metadata_path = tmp_path / "latest.json"
    metadata_path.write_text(
        json.dumps(
            {
                "product": "omnimemora-token-intelligence",
                "channel": "beta",
                "version": "0.1.0-beta.2",
                "published_at": "2026-05-13T00:00:00Z",
                "minimum_supported_version": "0.1.0-beta.2",
                "force_update": False,
                "platforms": {
                    "darwin-arm64": {
                        "download_url": "https://doloclaw.com/download/file/token-intelligence/darwin-arm64",
                        "sha256": "abc123",
                        "unsigned_beta": True,
                        "gatekeeper_note": "Manual Privacy & Security approval may be required during beta.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    proxy = _start_proxy(
        "https://example.invalid/v1",
        update_metadata_url=metadata_path.as_uri(),
    )
    try:
        status, payload = _get_json_with_status(f"{_base_url(proxy)}/updates/check")
    finally:
        _stop_server(proxy)

    assert status == 200
    assert payload["status"] == "ok"
    assert payload["current_version"] == "0.1.0-beta.2"
    assert payload["latest_version"] == "0.1.0-beta.2"
    assert payload["update_available"] is False
    assert payload["unsigned_beta"] is True
    assert "Privacy & Security" in payload["gatekeeper_note"]
    assert "download_url" not in payload


def test_chat_completions_preserves_upstream_error_status_and_body():
    upstream_body = {"error": {"message": "rate limited", "type": "rate_limit"}}
    upstream = _start_fake_upstream(response_status=429, response_body=_json_bytes(upstream_body))
    proxy = _start_proxy(f"{_base_url(upstream)}/v1")
    try:
        status, body = _post_json(f"{_base_url(proxy)}/v1/chat/completions", {"model": "relay-model"})
    finally:
        _stop_server(proxy)
        _stop_server(upstream)

    assert status == 429
    assert json.loads(body) == upstream_body


def _start_proxy_with_options(
    upstream_base_url: str,
    *,
    upstream_api_key: str = "",
    openai_upstream_base_url: str = "",
    openai_upstream_api_key: str = "",
    anthropic_upstream_base_url: str = "",
    anthropic_upstream_api_key: str = "",
    audit_enabled: bool = False,
    audit_db_path: str = "",
    audit_fail_open: bool = True,
    update_metadata_url: str = "",
):
    config = token_intelligence.LocalProxyConfig(
        host="127.0.0.1",
        port=_free_port(),
        upstream_base_url=upstream_base_url,
        upstream_api_key=upstream_api_key,
        openai_upstream_base_url=openai_upstream_base_url,
        openai_upstream_api_key=openai_upstream_api_key,
        anthropic_upstream_base_url=anthropic_upstream_base_url,
        anthropic_upstream_api_key=anthropic_upstream_api_key,
        upstream_timeout_seconds=5,
        audit_enabled=audit_enabled,
        audit_db_path=audit_db_path or None,
        audit_fail_open=audit_fail_open,
        update_metadata_url=update_metadata_url
        or "https://doloclaw.com/releases/token-intelligence/latest.json",
    )
    server = token_intelligence.create_server(config)
    _serve_in_thread(server)
    return server


def _start_proxy(
    upstream_base_url: str,
    *,
    upstream_api_key: str = "",
    audit_enabled: bool = False,
    audit_db_path: str = "",
    audit_fail_open: bool = True,
    update_metadata_url: str = "",
):
    return _start_proxy_with_options(
        upstream_base_url,
        upstream_api_key=upstream_api_key,
        audit_enabled=audit_enabled,
        audit_db_path=audit_db_path,
        audit_fail_open=audit_fail_open,
        update_metadata_url=update_metadata_url,
    )


def _start_fake_upstream(*, response_status: int = 200, response_body: bytes = b"{}"):
    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), _FakeUpstreamHandler)
    server.daemon_threads = True
    server.state = {
        "response_status": response_status,
        "response_body": response_body,
    }
    _serve_in_thread(server)
    return server


def _serve_in_thread(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.thread = thread


def _stop_server(server):
    server.shutdown()
    server.server_close()
    server.thread.join(timeout=2)


def _base_url(server) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"


def _get_json(url: str):
    _status, payload = _get_json_with_status(url)
    return payload


def _get_json_with_status(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return int(response.status), json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read())


def _get_raw(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            return int(response.status), response.read(), headers
    except urllib.error.HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()}
        return int(exc.code), exc.read(), headers


def _post_json(url: str, payload: dict):
    status, body, _headers = _post_json_with_headers(url, payload)
    return status, body


def _post_json_with_headers(url: str, payload: dict, headers=None):
    data = _json_bytes(payload)
    request_headers = {"content-type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            return int(response.status), response.read(), headers
    except urllib.error.HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()}
        return int(exc.code), exc.read(), headers


def _delete_json(url: str):
    request = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return int(response.status), json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read())


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
