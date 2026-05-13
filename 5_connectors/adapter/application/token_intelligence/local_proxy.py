"""Local OpenAI-compatible proxy skeleton for Token Intelligence Lite."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import urljoin

VERSION = "0.1.0-dev"
SERVICE_NAME = "omni-token-audit-local-proxy"


@dataclass(frozen=True)
class LocalProxyConfig:
    upstream_base_url: str
    upstream_api_key: str = ""
    upstream_timeout_seconds: float = 120.0
    host: str = "127.0.0.1"
    port: int = 18081


def create_server(config: LocalProxyConfig) -> ThreadingHTTPServer:
    """Create a local proxy server without starting it."""
    _validate_config(config)
    server = ThreadingHTTPServer((config.host, config.port), _make_handler(config))
    server.daemon_threads = True
    return server


def serve_forever(config: LocalProxyConfig) -> None:
    """Run the local proxy until interrupted."""
    server = create_server(config)
    with server:
        server.serve_forever()


def _make_handler(config: LocalProxyConfig) -> type[BaseHTTPRequestHandler]:
    class TokenAuditProxyHandler(BaseHTTPRequestHandler):
        server_version = f"{SERVICE_NAME}/{VERSION}"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path == "/health":
                _send_json(
                    self,
                    200,
                    {
                        "status": "ok",
                        "service": SERVICE_NAME,
                        "version": VERSION,
                        "mode": "candidate_local_proxy",
                    },
                )
                return
            if self.path == "/version":
                _send_json(
                    self,
                    200,
                    {
                        "service": SERVICE_NAME,
                        "version": VERSION,
                    },
                )
                return
            _send_json(self, 404, {"error": "not_found", "path": self.path})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path != "/v1/chat/completions":
                _send_json(self, 404, {"error": "not_found", "path": self.path})
                return
            content_length = int(self.headers.get("content-length") or "0")
            body = self.rfile.read(content_length)
            started = time.monotonic()
            status_code, response_headers, response_body = _forward_chat_completion(
                config,
                body,
                content_type=self.headers.get("content-type", "application/json"),
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self.send_response(status_code)
            content_type = response_headers.get("content-type", "application/json")
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(response_body)))
            self.send_header("x-omni-token-audit-mode", "passthrough")
            self.send_header("x-omni-token-audit-latency-ms", str(elapsed_ms))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return TokenAuditProxyHandler


def _forward_chat_completion(
    config: LocalProxyConfig,
    body: bytes,
    *,
    content_type: str,
) -> tuple[int, dict[str, str], bytes]:
    target = _join_upstream_path(config.upstream_base_url, "chat/completions")
    headers = {"content-type": content_type}
    if config.upstream_api_key:
        headers["authorization"] = f"Bearer {config.upstream_api_key}"

    request = urllib.request.Request(
        target,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.upstream_timeout_seconds) as response:
            response_body = response.read()
            return int(response.status), _lower_headers(response.headers.items()), response_body
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        return int(exc.code), _lower_headers(exc.headers.items()), response_body
    except Exception as exc:
        return (
            502,
            {"content-type": "application/json"},
            _json_bytes(
                {
                    "error": "upstream_request_failed",
                    "message": str(exc),
                }
            ),
        )


def _join_upstream_path(base_url: str, path: str) -> str:
    normalized_base = base_url.rstrip("/") + "/"
    return urljoin(normalized_base, path)


def _send_json(handler: BaseHTTPRequestHandler, status_code: int, payload: dict[str, Any]) -> None:
    body = _json_bytes(payload)
    handler.send_response(status_code)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _lower_headers(headers: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers}


def _validate_config(config: LocalProxyConfig) -> None:
    if config.host != "127.0.0.1":
        raise ValueError("TI-001 local proxy must bind to 127.0.0.1 by default")
    if not config.upstream_base_url.strip():
        raise ValueError("upstream_base_url is required")
    if config.port <= 0 or config.port > 65535:
        raise ValueError("port must be between 1 and 65535")
    if config.upstream_timeout_seconds <= 0:
        raise ValueError("upstream_timeout_seconds must be positive")
