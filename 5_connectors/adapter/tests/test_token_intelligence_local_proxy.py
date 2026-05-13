import importlib
import json
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


def _start_proxy(upstream_base_url: str, *, upstream_api_key: str = ""):
    config = token_intelligence.LocalProxyConfig(
        host="127.0.0.1",
        port=_free_port(),
        upstream_base_url=upstream_base_url,
        upstream_api_key=upstream_api_key,
        upstream_timeout_seconds=5,
    )
    server = token_intelligence.create_server(config)
    _serve_in_thread(server)
    return server


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
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read())


def _post_json(url: str, payload: dict):
    data = _json_bytes(payload)
    request = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
