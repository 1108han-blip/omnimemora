import asyncio
import importlib
from unittest import mock


backend_mod = importlib.import_module("5_connectors.adapter.backends.omnimemora_runtime_backend")
base_mod = importlib.import_module("5_connectors.adapter.backends.base")


async def _run_search_case():
    with mock.patch(
        "5_connectors.adapter.backends.omnimemora_runtime_backend._it.resolve_internal_base_url_sync",
        return_value=("http://127.0.0.1:8765", {}),
    ):
        backend = backend_mod.OmniMemoraRuntimeBackend(base_url="http://127.0.0.1:8765")

    captured = {}

    async def _fake_runtime_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return {
            "results": [
                {
                    "memory_id": "m-1",
                    "content": "hello",
                    "score": 0.9,
                    "created_at": "2026-04-24T00:00:00Z",
                }
            ],
            "total": 1,
            "enforcement_trace": {
                "actual_enforced_domains": [
                    {"domain_id": "d-private", "operation": "search", "decision": "applied", "result_count": 1}
                ]
            },
        }

    backend._runtime_request = _fake_runtime_request  # type: ignore[attr-defined]
    try:
        result = await backend.search(
            base_mod.MemorySearchRequest(
                query="hello",
                scope="agent",
                scope_ref="openclaw",
                access_plan={
                    "identity": {"tenant_id": "tenant-a", "instance_id": "openclaw-i1"},
                    "read_domains": [],
                    "primary_write_domain": {},
                    "secondary_write_domains": [],
                    "allow_secondary_writes": False,
                },
            )
        )
    finally:
        await backend.close()

    assert captured["method"] == "POST"
    assert captured["path"] == "/memory/search"
    assert captured["json"]["keyword"] == "hello"
    assert captured["json"]["query"] == "hello"
    assert captured["json"]["access_plan"]["identity"]["tenant_id"] == "tenant-a"
    assert result.total == 1
    assert result.enforcement_trace["actual_enforced_domains"][0]["decision"] == "applied"


async def _run_write_case():
    with mock.patch(
        "5_connectors.adapter.backends.omnimemora_runtime_backend._it.resolve_internal_base_url_sync",
        return_value=("http://127.0.0.1:8765", {}),
    ):
        backend = backend_mod.OmniMemoraRuntimeBackend(base_url="http://127.0.0.1:8765")

    captured = {}

    async def _fake_runtime_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return {
            "memory_id": "m-write-1",
            "created_at": "2026-04-24T00:00:00Z",
            "enforcement_trace": {
                "actual_enforced_domains": [
                    {"domain_id": "d-private", "operation": "write", "decision": "applied", "memory_id": "m-write-1"}
                ]
            },
        }

    backend._runtime_request = _fake_runtime_request  # type: ignore[attr-defined]
    try:
        result = await backend.write(
            base_mod.MemoryWriteRequest(
                content="hello",
                scope="agent",
                scope_ref="openclaw",
                metadata={},
                access_plan={
                    "identity": {"tenant_id": "tenant-a", "instance_id": "openclaw-i1"},
                    "read_domains": [],
                    "primary_write_domain": {},
                    "secondary_write_domains": [],
                    "allow_secondary_writes": False,
                },
            )
        )
    finally:
        await backend.close()

    assert captured["method"] == "POST"
    assert captured["path"] == "/memory/write"
    assert captured["json"]["access_plan"]["identity"]["instance_id"] == "openclaw-i1"
    assert result.memory_id == "m-write-1"
    assert result.enforcement_trace["actual_enforced_domains"][0]["operation"] == "write"


def test_runtime_backend_search_forwards_access_plan_and_reads_enforcement_trace():
    asyncio.run(_run_search_case())


def test_runtime_backend_write_forwards_access_plan_and_reads_enforcement_trace():
    asyncio.run(_run_write_case())


async def _run_search_alias_case():
    with mock.patch(
        "5_connectors.adapter.backends.omnimemora_runtime_backend._it.resolve_internal_base_url_sync",
        return_value=("http://127.0.0.1:8765", {}),
    ):
        backend = backend_mod.OmniMemoraRuntimeBackend(base_url="http://127.0.0.1:8765")

    async def _fake_runtime_request(method: str, path: str, **kwargs):
        return {
            "results": [],
            "total": 0,
            "actual_enforcement": {
                "actual_enforced_domains": [
                    {"domain_id": "d-private", "operation": "search", "decision": "applied", "result_count": 0}
                ]
            },
        }

    backend._runtime_request = _fake_runtime_request  # type: ignore[attr-defined]
    try:
        result = await backend.search(
            base_mod.MemorySearchRequest(
                query="hello",
                scope="agent",
                scope_ref="openclaw",
                access_plan={"identity": {"tenant_id": "tenant-a"}},
            )
        )
    finally:
        await backend.close()

    assert result.enforcement_trace["actual_enforced_domains"][0]["operation"] == "search"


def test_runtime_backend_search_accepts_actual_enforcement_alias():
    asyncio.run(_run_search_alias_case())
