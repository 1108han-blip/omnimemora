import asyncio
import importlib
import json

llm_proxy = importlib.import_module("5_connectors.adapter.llm_proxy")
MemoryRecord = importlib.import_module("5_connectors.adapter.backends.base").MemoryRecord


class _FakeResponse:
    status_code = 200
    text = '{"choices":[{"message":{"role":"assistant","content":"done"}}]}'

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "done",
                    }
                }
            ]
        }


class _FakeBackend:
    def __init__(self):
        self.writes = []

    async def write(self, request, **kwargs):
        self.writes.append(request)
        return MemoryRecord(
            memory_id="mem-test-1",
            content=request.content,
            scope=request.scope,
            scope_ref=request.scope_ref,
            metadata=request.metadata,
        )


def test_auto_memory_write_stores_internal_work_memory():
    backend = _FakeBackend()
    old_get_backend = llm_proxy._get_memory_backend
    llm_proxy._internal_memory_write_dedup.clear()
    llm_proxy._get_memory_backend = lambda: backend
    compile_meta = {"task_type": "implementation"}
    try:
        asyncio.run(
            llm_proxy._auto_write_internal_work_memory(
                request_id="req-auto-1",
                route_label="/llm/v1/messages",
                agent_id="claude_code",
                status_code=200,
                request_messages=[{"role": "user", "content": "Implement retry logic for adapter upstream timeout"}],
                upstream_resp=_FakeResponse(),
                compile_meta=compile_meta,
            )
        )
    finally:
        llm_proxy._get_memory_backend = old_get_backend
        llm_proxy._internal_memory_write_dedup.clear()

    assert compile_meta["internal_memory_write_status"] == "stored"
    assert len(backend.writes) == 1
    req = backend.writes[0]
    assert req.scope == "agent"
    assert req.scope_ref == "claude_code"
    assert req.metadata["tenant_id"] == "default"
    assert req.metadata["sharing_mode"] == "isolated"
    assert req.metadata["source_request_id"] == "req-auto-1"
    assert len(req.content) <= 1000
    content_obj = json.loads(req.content)
    assert content_obj["task_type"] == "implementation"
    assert content_obj["source_request_id"] == "req-auto-1"
    assert "retry logic" in content_obj["user_visible_query"].lower()


def test_auto_memory_write_deduplicates_same_query_within_10_minutes():
    backend = _FakeBackend()
    old_get_backend = llm_proxy._get_memory_backend
    llm_proxy._internal_memory_write_dedup.clear()
    llm_proxy._get_memory_backend = lambda: backend
    try:
        first_meta = {"task_type": "continuation"}
        second_meta = {"task_type": "continuation"}
        kwargs = {
            "request_id": "req-auto-dedup",
            "route_label": "/llm/v1/messages",
            "agent_id": "claude_code",
            "status_code": 200,
            "request_messages": [{"role": "user", "content": "Summarize this compile event evidence"}],
            "upstream_resp": _FakeResponse(),
        }
        asyncio.run(llm_proxy._auto_write_internal_work_memory(compile_meta=first_meta, **kwargs))
        asyncio.run(llm_proxy._auto_write_internal_work_memory(compile_meta=second_meta, **kwargs))
    finally:
        llm_proxy._get_memory_backend = old_get_backend
        llm_proxy._internal_memory_write_dedup.clear()

    assert first_meta["internal_memory_write_status"] == "stored"
    assert second_meta["internal_memory_write_status"] == "skipped_dedup_10m"
    assert len(backend.writes) == 1
