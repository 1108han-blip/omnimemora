import unittest
from importlib import import_module
from types import SimpleNamespace
import httpx


llm_proxy = import_module("5_connectors.adapter.llm_proxy")


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


if __name__ == "__main__":
    unittest.main()


class TestOpenClawRouteFallback(unittest.IsolatedAsyncioTestCase):
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

        async def _fake_compile(payload, agent_id, session_id=None, request_id=None, trace_id=None):
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
