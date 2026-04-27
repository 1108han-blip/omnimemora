import importlib
from datetime import datetime, timezone

import pytest

runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")
base_mod = importlib.import_module("5_connectors.adapter.backends.base")


class _DummyBackend:
    def __init__(self, table):
        self.table = table
        self.calls = []

    async def search(self, request, **kwargs):
        self.calls.append(request.query)
        items = self.table.get(request.query, [])
        memories = [
            base_mod.MemoryRecord(
                memory_id=item["memory_id"],
                content=item["content"],
                scope=request.scope,
                scope_ref=request.scope_ref,
                metadata={},
                created_at=datetime.now(timezone.utc),
                score=0.9,
            )
            for item in items
        ]
        return base_mod.MemorySearchResult(memories=memories, total=len(memories), query=request.query)


@pytest.mark.anyio
async def test_fetch_memory_candidates_retries_with_identifier_keyword_on_empty_primary():
    old_backend = runtime_bridge._initialized_backend
    backend = _DummyBackend(
        {
            "sfe007-abc123": [
                {"memory_id": "mem-1", "content": "contains sfe007-abc123 note"},
            ]
        }
    )
    runtime_bridge._initialized_backend = backend
    try:
        result = await runtime_bridge.fetch_memory_candidates(
            query="请基于之前标识 sfe007-abc123 给我继续",
            agent_id="claude_code",
            limit=8,
            scope="agent",
        )
    finally:
        runtime_bridge._initialized_backend = old_backend

    assert len(result) == 1
    assert "sfe007-abc123" in result[0]["content"]
    assert backend.calls[0] == "请基于之前标识 sfe007-abc123 给我继续"
    assert "sfe007-abc123" in backend.calls[1:]


@pytest.mark.anyio
async def test_fetch_memory_candidates_keeps_primary_query_when_primary_hits():
    old_backend = runtime_bridge._initialized_backend
    backend = _DummyBackend(
        {
            "exact primary query": [
                {"memory_id": "mem-2", "content": "primary hit"},
            ]
        }
    )
    runtime_bridge._initialized_backend = backend
    try:
        result = await runtime_bridge.fetch_memory_candidates(
            query="exact primary query",
            agent_id="claude_code",
            limit=8,
            scope="agent",
        )
    finally:
        runtime_bridge._initialized_backend = old_backend

    assert len(result) == 1
    assert backend.calls == ["exact primary query"]
