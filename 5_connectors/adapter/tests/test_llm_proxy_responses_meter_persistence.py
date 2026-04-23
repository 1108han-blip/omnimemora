import unittest
from importlib import import_module
from types import SimpleNamespace
import httpx


llm_proxy = import_module("5_connectors.adapter.llm_proxy")


class TestResponsesMeterPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_native_responses_path_persists_gateway_meter(self):
        body = {
            "model": "gpt-5.4",
            "stream": False,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "hello from codex"}]}],
        }

        class _Req:
            def __init__(self):
                self.headers = {
                    "authorization": "Bearer test-key",
                    "x-omnimemora-agent": "codex_cli",
                }
                self.query_params = {}
                self.state = SimpleNamespace()
                self._json = body
                self.url = SimpleNamespace(path="/v1/responses")

            async def json(self):
                return self._json

        request = _Req()

        class _FakeResponse:
            status_code = 200
            headers = httpx.Headers({"content-type": "application/json"})
            text = "{\"id\":\"resp_123\",\"object\":\"response\",\"output\":[],\"model\":\"gpt-5.4\"}"
            content = text.encode()

            def json(self):
                return {"id": "resp_123", "object": "response", "output": [], "model": "gpt-5.4"}

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None, headers=None):
                return _FakeResponse()

        original_resolve = llm_proxy._resolve_codex_responses_upstream
        original_compile = llm_proxy._compile_or_passthrough_for_route
        original_client = llm_proxy.httpx.AsyncClient
        original_record_compile = llm_proxy._record_compile_event
        original_persist_meter = llm_proxy._persist_gateway_meter
        original_record_event = llm_proxy._record_event

        captured = {"meters": [], "compile_rows": []}

        async def _fake_compile(*args, **kwargs):
            return {
                "messages": [{"role": "user", "content": "hello from codex"}],
                "model": "gpt-5.4",
                "stream": False,
            }, {
                "compile_status": "compile_success",
                "selected_memory_count": 1,
                "original_token_estimate": 100,
                "compiled_token_estimate": 60,
                "compression_ratio": 0.4,
                "compile_path": "runtime_compile",
                "compile_error": None,
                "compile_reason": "runtime_compile",
            }

        def _fake_resolve(*args, **kwargs):
            return {
                "base_url": "https://example.invalid/backend-api/codex",
                "authorization": "Bearer test-key",
                "source": "request_headers",
            }

        def _fake_record_compile(*args, **kwargs):
            captured["compile_rows"].append({"args": args, "kwargs": kwargs})

        def _fake_persist_meter(*, request_id, agent_id, query, compile_meta):
            captured["meters"].append(
                {
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "query": query,
                    "compile_meta": dict(compile_meta),
                }
            )

        def _noop_record_event(*args, **kwargs):
            return None

        try:
            llm_proxy._resolve_codex_responses_upstream = _fake_resolve
            llm_proxy._compile_or_passthrough_for_route = _fake_compile
            llm_proxy.httpx.AsyncClient = _FakeClient
            llm_proxy._record_compile_event = _fake_record_compile
            llm_proxy._persist_gateway_meter = _fake_persist_meter
            llm_proxy._record_event = _noop_record_event

            response = await llm_proxy.proxy_v1_responses(request)
        finally:
            llm_proxy._resolve_codex_responses_upstream = original_resolve
            llm_proxy._compile_or_passthrough_for_route = original_compile
            llm_proxy.httpx.AsyncClient = original_client
            llm_proxy._record_compile_event = original_record_compile
            llm_proxy._persist_gateway_meter = original_persist_meter
            llm_proxy._record_event = original_record_event

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured["compile_rows"]), 1)
        self.assertEqual(len(captured["meters"]), 1)
        self.assertEqual(captured["meters"][0]["agent_id"], "codex_cli")
        self.assertEqual(captured["meters"][0]["query"], "hello from codex")
        self.assertEqual(captured["meters"][0]["compile_meta"]["compile_status"], "compile_success")
