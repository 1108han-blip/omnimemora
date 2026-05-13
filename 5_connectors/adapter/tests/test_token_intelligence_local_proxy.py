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
    assert version["version"] == "0.1.0-dev"


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
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
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
    assert audit_id.startswith("omni_audit_")
    assert receipt_status == 200
    assert receipt["usage"]["source"] == "relay_reported"
    assert receipt["usage"]["confidence"] == "official_usage"
    assert {block["block_type"] for block in receipt["blocks"]} >= {"current_user_intent", "provider_output"}
    assert event_status == 200
    assert event["metadata"]["route"] == "/v1/chat/completions"
    assert event["blocks"] == receipt["blocks"]
    assert summary_status == 200
    assert summary["event_count"] == 1
    assert summary["usage"]["total_tokens"] == 15
    assert summary["usage_sources"] == {"relay_reported": 1}
    assert summary["top_models"] == [
        {"model": "relay-model-requested", "request_count": 1, "total_tokens": 15}
    ]
    assert {block["block_type"] for block in summary["top_blocks"]} >= {"current_user_intent", "provider_output"}
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_events LIMIT 1").fetchone()
    assert row["request_id"] == "chatcmpl-audited"
    assert row["model_requested"] == "relay-model-requested"
    assert row["model_reported"] == "relay-model-reported"
    usage = json.loads(row["usage_json"])
    assert usage["total_tokens"] == 15
    assert usage["source"] == "relay_reported"
    serialized_row = json.dumps(dict(row), sort_keys=True)
    assert secret_prompt not in serialized_row
    assert secret_response not in serialized_row
    serialized_api_payloads = json.dumps([receipt, event, summary], sort_keys=True)
    assert secret_prompt not in serialized_api_payloads
    assert secret_response not in serialized_api_payloads


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
    serialized = json.dumps([receipt, summary], sort_keys=True)
    assert secret_tool_result not in serialized
    assert repeated not in serialized


def test_update_check_reads_release_metadata_without_download(tmp_path):
    metadata_path = tmp_path / "latest.json"
    metadata_path.write_text(
        json.dumps(
            {
                "product": "omnimemora-token-intelligence",
                "channel": "beta",
                "version": "0.1.0-beta.1",
                "published_at": "2026-05-13T00:00:00Z",
                "minimum_supported_version": "0.1.0-beta.1",
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
    assert payload["current_version"] == "0.1.0-dev"
    assert payload["latest_version"] == "0.1.0-beta.1"
    assert payload["update_available"] is True
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


def _post_json(url: str, payload: dict):
    status, body, _headers = _post_json_with_headers(url, payload)
    return status, body


def _post_json_with_headers(url: str, payload: dict):
    data = _json_bytes(payload)
    request = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            return int(response.status), response.read(), headers
    except urllib.error.HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()}
        return int(exc.code), exc.read(), headers


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
