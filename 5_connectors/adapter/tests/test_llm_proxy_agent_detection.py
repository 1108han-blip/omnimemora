import unittest
import gzip
from importlib import import_module
from types import SimpleNamespace
import httpx
from fastapi.responses import StreamingResponse


llm_proxy = import_module("5_connectors.adapter.llm_proxy")
compile_orchestrator = import_module("5_connectors.adapter.application.compile_orchestrator")
gateway_compile = import_module("5_connectors.adapter.application.gateway_compile")


class _MockState:
    pass


class _MockRequest:
    def __init__(self, headers=None, query_params=None, path="/v1/chat/completions"):
        self._headers = headers or {}
        self._query = query_params or {}
        self.state = _MockState()
        self.url = SimpleNamespace(path=path)

    @property
    def headers(self):
        return self._headers

    @property
    def query_params(self):
        return self._query


class TestLlmProxyAgentDetection(unittest.TestCase):
    def test_prefers_top_level_body_agent_id_for_openai_proxy(self):
        request = _MockRequest(headers={}, query_params={})

        detected = llm_proxy.detect_agent(
            request,
            {"agent_id": "codex-cli", "messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(detected, "codex_cli")

    def test_falls_back_to_body_agent_when_agent_id_missing(self):
        request = _MockRequest(headers={}, query_params={})

        detected = llm_proxy.detect_agent(
            request,
            {"agent": "openclaw-agent", "messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(detected, "openclaw")

    def test_supports_agent_family_header_when_agent_id_missing(self):
        request = _MockRequest(headers={"x-agent-family": "claude-code"}, query_params={})

        detected = llm_proxy.detect_agent(request, {"messages": [{"role": "user", "content": "hi"}]})

        self.assertEqual(detected, "claude_code")

    def test_openclaw_codex_responses_alias_defaults_to_openclaw(self):
        request = _MockRequest(
            headers={"user-agent": "pi (darwin 24.6.0; arm64)"},
            query_params={},
            path="/v1/codex/responses",
        )

        detected = llm_proxy.detect_agent(request, {"model": "gpt-5.4", "input": []})

        self.assertEqual(detected, "openclaw")

    def test_safe_passthrough_headers_drops_transport_lengths(self):
        headers = httpx.Headers(
            {
                "content-length": "12",
                "content-encoding": "gzip",
                "x-ratelimit-remaining": "99",
            }
        )

        forwarded = llm_proxy._safe_passthrough_headers(headers)

        self.assertNotIn("content-length", {key.lower() for key in forwarded})
        self.assertNotIn("content-encoding", {key.lower() for key in forwarded})
        self.assertEqual(forwarded["x-ratelimit-remaining"], "99")

    def test_streaming_response_header_copy_drops_transport_lengths(self):
        headers = httpx.Headers(
            {
                "content-length": "999",
                "content-encoding": "gzip",
                "x-request-id": "upstream-req-1",
                "x-ratelimit-remaining": "98",
            }
        )
        response = StreamingResponse(iter([b"hello"]), media_type="text/event-stream")

        llm_proxy._copy_upstream_headers_to_response(response, headers)

        forwarded = {key.lower(): value for key, value in response.headers.items()}
        self.assertNotIn("content-length", forwarded)
        self.assertNotIn("content-encoding", forwarded)
        self.assertEqual(response.headers["x-request-id"], "upstream-req-1")
        self.assertEqual(response.headers["x-ratelimit-remaining"], "98")

    def test_non_streaming_passthrough_drops_content_length(self):
        upstream_resp = httpx.Response(
            200,
            content=gzip.compress(b"{}"),
            headers={
                "content-type": "application/json",
                "content-length": "999",
                "content-encoding": "gzip",
                "x-request-id": "upstream-req-2",
            },
        )

        response = llm_proxy._build_passthrough_response(
            request_id="req-header-safe",
            route_label="/llm/v1/messages",
            upstream_resp=upstream_resp,
            fallback_media_type="application/json",
        )

        forwarded = {key.lower(): value for key, value in response.headers.items()}
        self.assertNotIn("content-length", forwarded)
        self.assertNotIn("content-encoding", forwarded)
        self.assertEqual(response.headers["x-request-id"], "upstream-req-2")

    def test_openclaw_query_extraction_skips_trailing_control_metadata(self):
        metadata = """Sender (untrusted metadata):
```json
{"label": "openclaw-control-ui", "id": "openclaw-control-ui"}
```"""
        task = metadata + "\n\n请阅读 docs/EP04_摄影与镜头语法.md 并补齐视频原稿。"
        messages = [
            {"role": "user", "content": [{"type": "text", "text": task}]},
            {"role": "assistant", "content": [{"type": "text", "text": "我会读取文档。"}]},
            {"role": "user", "content": [{"type": "text", "text": metadata}]},
        ]

        expected = "请阅读 docs/EP04_摄影与镜头语法.md 并补齐视频原稿。"
        self.assertEqual(llm_proxy._extract_user_query(messages), expected)
        self.assertEqual(gateway_compile._extract_query_from_messages(messages), expected)
        self.assertEqual(compile_orchestrator._extract_user_query({"messages": messages}), expected)

    def test_anthropic_thinking_blocks_force_passthrough(self):
        payload = {
            "_path": "/llm/v1/messages",
            "model": "reasoning-model",
            "messages": [
                {"role": "user", "content": "Use the tool."},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "I need to inspect tool output first."},
                        {"type": "text", "text": "I will check."},
                    ],
                },
                {"role": "user", "content": "Continue."},
            ],
        }

        normalized = gateway_compile.normalize_inbound_request(payload, "openclaw")

        self.assertFalse(normalized["can_compile"])
        self.assertEqual(normalized["skip_reason"], "reasoning_context_passthrough")

    def test_openai_reasoning_details_force_passthrough(self):
        payload = {
            "_path": "/llm/v1/chat/completions",
            "model": "openai-compatible-reasoner",
            "messages": [
                {"role": "user", "content": "Use the tool."},
                {
                    "role": "assistant",
                    "content": "",
                    "reasoning_details": [{"type": "text", "text": "I need the tool result."}],
                },
                {"role": "user", "content": "Continue."},
            ],
        }

        normalized = gateway_compile.normalize_inbound_request(payload, "openclaw")

        self.assertFalse(normalized["can_compile"])
        self.assertEqual(normalized["skip_reason"], "reasoning_context_passthrough")

    def test_inline_think_tags_force_passthrough(self):
        payload = {
            "_path": "/llm/v1/chat/completions",
            "model": "generic-reasoner",
            "messages": [
                {"role": "user", "content": "Use the tool."},
                {"role": "assistant", "content": "<think>I need to preserve this.</think>"},
                {"role": "user", "content": "Continue."},
            ],
        }

        normalized = gateway_compile.normalize_inbound_request(payload, "openclaw")

        self.assertFalse(normalized["can_compile"])
        self.assertEqual(normalized["skip_reason"], "reasoning_context_passthrough")


if __name__ == "__main__":
    unittest.main()


class TestOpenClawRouteFallback(unittest.IsolatedAsyncioTestCase):
    async def test_openclaw_anthropic_timeout_returns_protocol_error_without_assistant_takeover(self):
        body = {
            "model": "MiniMax-M2.7",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }

        class _Req:
            def __init__(self):
                self.headers = {"user-agent": "openclaw-control-ui"}
                self.query_params = {}
                self.state = SimpleNamespace()
                self._json = body
                self.url = SimpleNamespace(path="/llm/v1/messages")

            async def json(self):
                return self._json

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                seen["timeout"] = kwargs.get("timeout")

            def build_request(self, method, url, json=None, headers=None):
                return {"method": method, "url": url, "json": json, "headers": headers}

            async def send(self, request, stream=False):
                raise httpx.TimeoutException("upstream took too long")

            async def aclose(self):
                seen["client_closed"] = True

        seen = {}
        recorded_compile = []
        recorded_events = []
        original_client = llm_proxy.httpx.AsyncClient
        original_route_enabled = llm_proxy._routing_enabled_for_agent
        original_get_upstream = llm_proxy.get_upstream_for_anthropic
        original_record_compile = llm_proxy._record_compile_event
        original_record_event = llm_proxy._record_event
        original_true_stream_flag = llm_proxy._ANTHROPIC_TRUE_STREAMING_OPENCLAW

        try:
            llm_proxy.httpx.AsyncClient = _FakeClient
            llm_proxy._routing_enabled_for_agent = lambda agent_id: False
            llm_proxy.get_upstream_for_anthropic = lambda model: {
                "base_url": "https://example.test/anthropic",
                "api_key": "test-key",
                "timeout_seconds": 120,
            }
            llm_proxy._record_compile_event = lambda **kwargs: recorded_compile.append(kwargs)
            llm_proxy._record_event = lambda *args, **kwargs: recorded_events.append((args, kwargs))
            llm_proxy._ANTHROPIC_TRUE_STREAMING_OPENCLAW = True

            response = await llm_proxy.proxy_anthropic_messages_compatible(_Req())
        finally:
            llm_proxy.httpx.AsyncClient = original_client
            llm_proxy._routing_enabled_for_agent = original_route_enabled
            llm_proxy.get_upstream_for_anthropic = original_get_upstream
            llm_proxy._record_compile_event = original_record_compile
            llm_proxy._record_event = original_record_event
            llm_proxy._ANTHROPIC_TRUE_STREAMING_OPENCLAW = original_true_stream_flag

        body_text = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 504)
        self.assertIn("upstream_timeout", body_text)
        self.assertNotIn("message_start", body_text)
        self.assertNotIn("content_block_delta", body_text)
        self.assertTrue(seen["client_closed"])
        self.assertTrue(any(item.get("proxy_status_code") == 504 for item in recorded_compile))

    async def test_openclaw_anthropic_stream_uses_true_streaming_send(self):
        body = {
            "model": "MiniMax-M2.7",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }

        class _Req:
            def __init__(self):
                self.headers = {"user-agent": "openclaw-control-ui"}
                self.query_params = {}
                self.state = SimpleNamespace()
                self._json = body
                self.url = SimpleNamespace(path="/llm/v1/messages")

            async def json(self):
                return self._json

        class _FakeStreamResponse:
            status_code = 200
            headers = httpx.Headers({"content-type": "text/event-stream", "x-request-id": "stream-1"})

            async def aiter_bytes(self):
                yield b"event: message_start\n\n"
                yield b"data: {\"type\":\"message_delta\"}\n\n"

            async def aclose(self):
                seen["closed"] = True

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                seen["client_created"] = True

            def build_request(self, method, url, json=None, headers=None):
                seen["method"] = method
                seen["url"] = url
                seen["json"] = json
                return {"method": method, "url": url, "json": json, "headers": headers}

            async def send(self, request, stream=False):
                seen["send_stream"] = stream
                return _FakeStreamResponse()

            async def post(self, *args, **kwargs):
                raise AssertionError("streaming OpenClaw Anthropic path should not use post")

            async def aclose(self):
                seen["client_closed"] = True

        class _FakeContract:
            model_resolved = "MiniMax-M2.7"
            base_url_resolved = "https://example.test/anthropic"

        async def _fake_compile_and_resolve(**kwargs):
            return kwargs["payload"], {
                "compile_status": "compile_success",
                "selected_memory_count": 1,
                "original_token_estimate": 10,
                "compiled_token_estimate": 8,
                "compression_ratio": 0.2,
                "compile_path": "runtime_compile",
                "compile_error": None,
                "compile_reason": "runtime_compile",
            }, _FakeContract(), {"provider_resolved": "minimax_anthropic_compatible"}

        async def _fake_auto_write(**kwargs):
            seen["auto_write"] = True

        seen = {}
        recorded_compile = []
        recorded_events = []
        original_client = llm_proxy.httpx.AsyncClient
        original_route_enabled = llm_proxy._routing_enabled_for_agent
        original_get_upstream = llm_proxy.get_upstream_for_anthropic
        original_orchestrator = llm_proxy._get_compile_orchestrator
        original_auto_write = llm_proxy._auto_write_internal_work_memory
        original_record_compile = llm_proxy._record_compile_event
        original_record_event = llm_proxy._record_event
        original_schedule_meter = llm_proxy._schedule_gateway_meter_persistence
        original_true_stream_flag = llm_proxy._ANTHROPIC_TRUE_STREAMING_OPENCLAW

        try:
            llm_proxy.httpx.AsyncClient = _FakeClient
            llm_proxy._routing_enabled_for_agent = lambda agent_id: True
            llm_proxy.get_upstream_for_anthropic = lambda model: {
                "base_url": "https://example.test/anthropic",
                "api_key": "test-key",
                "timeout_seconds": 30,
            }
            llm_proxy._get_compile_orchestrator = lambda: SimpleNamespace(
                run_anthropic_compile_and_resolve=_fake_compile_and_resolve
            )
            llm_proxy._auto_write_internal_work_memory = _fake_auto_write
            llm_proxy._record_compile_event = lambda **kwargs: recorded_compile.append(kwargs)
            llm_proxy._record_event = lambda *args, **kwargs: recorded_events.append((args, kwargs))
            llm_proxy._schedule_gateway_meter_persistence = lambda **kwargs: seen.setdefault("meter", kwargs)
            llm_proxy._ANTHROPIC_TRUE_STREAMING_OPENCLAW = True

            response = await llm_proxy.proxy_anthropic_messages_compatible(_Req())
            chunks = [chunk async for chunk in response.body_iterator]
        finally:
            llm_proxy.httpx.AsyncClient = original_client
            llm_proxy._routing_enabled_for_agent = original_route_enabled
            llm_proxy.get_upstream_for_anthropic = original_get_upstream
            llm_proxy._get_compile_orchestrator = original_orchestrator
            llm_proxy._auto_write_internal_work_memory = original_auto_write
            llm_proxy._record_compile_event = original_record_compile
            llm_proxy._record_event = original_record_event
            llm_proxy._schedule_gateway_meter_persistence = original_schedule_meter
            llm_proxy._ANTHROPIC_TRUE_STREAMING_OPENCLAW = original_true_stream_flag

        self.assertEqual(response.status_code, 200)
        self.assertEqual(chunks, [b"event: message_start\n\n", b"data: {\"type\":\"message_delta\"}\n\n"])
        self.assertTrue(seen["send_stream"])
        self.assertTrue(seen["closed"])
        self.assertTrue(seen["client_closed"])
        self.assertTrue(seen["auto_write"])
        self.assertIn("meter", seen)
        self.assertTrue(any(item.get("proxy_status_code") == 200 for item in recorded_compile))

    async def test_llm_route_defaults_unknown_agent_to_openclaw(self):
        body = {"model": "gemma4:26b", "messages": [{"role": "user", "content": "hi"}], "stream": False}

        class _Req:
            def __init__(self):
                self.headers = {}
                self.query_params = {}
                self.state = SimpleNamespace()
                self._json = body
                self.url = SimpleNamespace(path="/llm/api/chat")

            async def json(self):
                return self._json

        request = _Req()

        async def _fake_compile(
            payload,
            agent_id,
            session_id=None,
            access_plan=None,
            request_id=None,
            trace_id=None,
        ):
            return payload, {
                "compile_status": "compile_skipped",
                "selected_memory_count": 0,
                "original_token_estimate": 1,
                "compiled_token_estimate": 0,
                "compression_ratio": 0.0,
                "compile_path": "test",
                "compile_error": None,
                "compile_reason": "test",
            }

        class _FakeResponse:
            status_code = 200
            headers = httpx.Headers({})
            content = b"{\"ok\":true}"

            def json(self):
                return {"ok": True}

            text = "{\"ok\":true}"

        seen = {}

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None, headers=None):
                seen["headers"] = headers or {}
                return _FakeResponse()

        original_compile = llm_proxy._gc.run_gateway_compile
        original_client = llm_proxy.httpx.AsyncClient
        original_record_event = llm_proxy._record_event
        original_route_enabled = llm_proxy._routing_enabled_for_agent
        recorded = []

        def _fake_record_event(
            agent_id,
            event_type,
            request_id,
            path,
            model,
            status,
            status_code=None,
            error=None,
            truth_meta=None,
            trace_id=None,
        ):
            recorded.append({
                "agent_id": agent_id,
                "event_type": event_type,
                "path": path,
                "model": model,
                "status": status,
            })

        try:
            llm_proxy._gc.run_gateway_compile = _fake_compile
            llm_proxy.httpx.AsyncClient = _FakeClient
            llm_proxy._record_event = _fake_record_event
            llm_proxy._routing_enabled_for_agent = lambda agent_id: True
            response = await llm_proxy.proxy_openai_chat(request)
        finally:
            llm_proxy._gc.run_gateway_compile = original_compile
            llm_proxy.httpx.AsyncClient = original_client
            llm_proxy._record_event = original_record_event
            llm_proxy._routing_enabled_for_agent = original_route_enabled

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                item["agent_id"] == "openclaw"
                and item["path"] in {"/llm/chat", "/llm/api/chat"}
                for item in recorded
            )
        )

    async def test_route_disabled_skips_compile_and_uses_passthrough(self):
        body = {"model": "gemma4:26b", "messages": [{"role": "user", "content": "hi"}], "stream": False}

        class _Req:
            def __init__(self):
                self.headers = {}
                self.query_params = {}
                self.state = SimpleNamespace()
                self._json = body
                self.url = SimpleNamespace(path="/llm/chat")

            async def json(self):
                return self._json

        request = _Req()

        class _FakeResponse:
            status_code = 200
            headers = httpx.Headers({})
            text = "{\"ok\":true}"
            content = b"{\"ok\":true}"

            def json(self):
                return {"ok": True}

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None, headers=None):
                return _FakeResponse()

        original_compile = llm_proxy._gc.run_gateway_compile
        original_client = llm_proxy.httpx.AsyncClient
        original_route_enabled = llm_proxy._routing_enabled_for_agent

        async def _unexpected_compile(*args, **kwargs):
            raise AssertionError("compile should not run when route is disabled")

        try:
            llm_proxy._gc.run_gateway_compile = _unexpected_compile
            llm_proxy.httpx.AsyncClient = _FakeClient
            llm_proxy._routing_enabled_for_agent = lambda agent_id: False
            response = await llm_proxy.proxy_openai_chat(request)
        finally:
            llm_proxy._gc.run_gateway_compile = original_compile
            llm_proxy.httpx.AsyncClient = original_client
            llm_proxy._routing_enabled_for_agent = original_route_enabled

        self.assertEqual(response.status_code, 200)
