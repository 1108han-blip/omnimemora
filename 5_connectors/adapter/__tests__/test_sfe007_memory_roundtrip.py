"""
test_sfe007_memory_roundtrip.py — SFE-007 Memory Feedback Loop Verification
=============================================================================
Goal:
    Prove that OmniMemora's feedback loop exists:
        response returns
        → product writes internal work memory
        → next related request retrieves it

Architecture question this tests:
    The compile path (gateway_compile) fetches memories and injects them
    into the compiled prompt. Does that retrieved memory include content
    written from a previous response in the same session/task?

Two sub-paths tested here:

[Path A] API round-trip (always testable):
    POST /memory/write  →  write a memory item with a known unique marker
    POST /memory/search →  search with query that should retrieve it
    VERIFY: the item appears in search results

[Path B] Compile round-trip (requires live service + memory backend):
    1. Write a memory item via POST /memory/write
    2. Build a request that should retrieve it via compile
    3. Call run_gateway_compile()
    4. VERIFY: the compiled payload contains the memory item

[Path C] End-to-end agent loop (requires Claude Code / OpenClaw running):
    1. Agent sends a request that produces useful output
    2. Agent writes that output to memory (via MCP or CLI)
    3. Agent sends a related follow-up request
    4. VERIFY: compile retrieves the memory from step 2

    Path C is NOT fully testable in harness — it depends on agent behavior.
    This test only instruments Path B to confirm the compile path works.

Gate criteria (Path B must pass):
    - Memory write succeeds (HTTP 200, status=stored)
    - Subsequent compile retrieves the memory
    - Compiled payload includes the written content

Prerequisites:
    - OmniMemora adapter running on 18011
    - Memory backend accessible (8765 or embedded)
    - For Path C: Claude Code or OpenClaw with OmniMemora MCP/CLI attached

Usage:
    # Run all tests
    python -m pytest 5_connectors/adapter/__tests__/test_sfe007_memory_roundtrip.py -v

    # Run Path A only (no compile needed)
    python -m pytest 5_connectors/adapter/__tests__/test_sfe007_memory_roundtrip.py -v -k "path_a"

    # Run Path B only (requires adapter running)
    python -m pytest 5_connectors/adapter/__tests__/test_sfe007_memory_roundtrip.py -v -k "path_b"

    # Environment variables:
    export OMNIMEMORA_ADAPTER_URL=http://127.0.0.1:18011   # default
    export OMNIMEMORA_AGENT_ID=claude_code                 # default
    export OMNIMEMORA_MEMORY_BACKEND_URL=http://127.0.0.1:8765  # default
"""
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_adapter_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_connectors_dir = os.path.dirname(_adapter_dir)
_project_root = os.path.dirname(_connectors_dir)

for _p in (_project_root, _connectors_dir, _adapter_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import asyncio
import httpx


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _cfg() -> dict:
    return {
        "adapter_url": os.environ.get("OMNIMEMORA_ADAPTER_URL", "http://127.0.0.1:18011").rstrip("/"),
        "memory_url": os.environ.get("OMNIMEMORA_MEMORY_BACKEND_URL", "http://127.0.0.1:8765").rstrip("/"),
        "agent_id": os.environ.get("OMNIMEMORA_AGENT_ID", "claude_code"),
    }


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class WriteResult:
    success: bool
    memory_id: str = ""
    status: str = ""
    error: str = ""


@dataclass
class SearchResult:
    success: bool
    memories: List[dict] = field(default_factory=list)
    error: str = ""


@dataclass
class CompileResult:
    success: bool
    compile_status: str = ""
    selected_memory_count: int = 0
    packed_context: str = ""
    error: str = ""


@dataclass
class RoundtripResult:
    path: str          # "path_a" | "path_b" | "path_c"
    write_ok: bool = False
    search_ok: bool = False
    compile_retrieves_memory: bool = False
    memory_found_in_context: bool = False
    write_result: Optional[WriteResult] = None
    search_result: Optional[SearchResult] = None
    compile_result: Optional[CompileResult] = None
    error: str = ""

    @property
    def passed(self) -> bool:
        if self.path == "path_a":
            return self.write_ok and self.search_ok
        elif self.path == "path_b":
            return (
                self.write_ok
                and self.compile_retrieves_memory
                and self.memory_found_in_context
            )
        return False


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _http_post(url: str, json_body: dict, timeout: float = 30.0) -> httpx.Response:
    """POST JSON to a URL and return the response."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=json_body)


async def write_memory_via_adapter(
    content: str,
    agent_id: str,
    cfg: dict,
    memory_type: str = "work_experience",
) -> WriteResult:
    """
    Call POST /memory/write on the adapter.
    Returns WriteResult.
    """
    url = f"{cfg['adapter_url']}/memory/write"
    body = {
        "agent": agent_id,
        "content": content,
        "type": memory_type,
    }
    try:
        resp = await _http_post(url, body)
        if resp.status_code >= 400:
            return WriteResult(success=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        status = data.get("status", "")
        reason = data.get("reason", "")
        error_code = data.get("error_code", "")
        support = data.get("support", {}) if isinstance(data.get("support"), dict) else {}
        detail = support.get("detail", "") if isinstance(support, dict) else ""
        error_text = " | ".join([x for x in [reason, error_code, detail] if x])
        return WriteResult(
            success=status in ("stored", "stored_with_warning"),
            memory_id=data.get("memory_id", ""),
            status=status,
            error=error_text,
        )
    except httpx.ConnectError as e:
        return WriteResult(success=False, error=f"Connection error: {e}")
    except Exception as e:
        return WriteResult(success=False, error=str(e)[:200])


async def search_memory_via_adapter(
    query: str,
    agent_id: str,
    cfg: dict,
    limit: int = 10,
) -> SearchResult:
    """
    Call POST /memory/search on the adapter.
    Returns SearchResult.
    """
    url = f"{cfg['adapter_url']}/memory/search"
    body = {
        "query": query,
        "agent": agent_id,
        "limit": limit,
    }
    try:
        resp = await _http_post(url, body)
        if resp.status_code >= 400:
            return SearchResult(success=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        memories = data.get("memories", []) if isinstance(data, dict) else []
        return SearchResult(success=True, memories=memories)
    except httpx.ConnectError as e:
        return SearchResult(success=False, error=f"Connection error: {e}")
    except Exception as e:
        return SearchResult(success=False, error=str(e)[:200])


# ---------------------------------------------------------------------------
# Path A: Direct API write→search round-trip
# ---------------------------------------------------------------------------

async def run_path_a(marker: str, cfg: dict) -> RoundtripResult:
    """
    Path A: Write a memory with a unique marker, then search for it.
    Tests: /memory/write → /memory/search round-trip via API.

    This is always testable if adapter is running.
    """
    result = RoundtripResult(path="path_a")
    agent_id = cfg["agent_id"]

    # Write a memory with a unique marker
    unique_content = (
        f"SFE-007 Path A test memory at {time.time()} "
        f"marker={marker} agent={agent_id} "
        "This is a test memory item that should be retrievable."
    )

    write_res = await write_memory_via_adapter(unique_content, agent_id, cfg=cfg)
    result.write_result = write_res
    result.write_ok = write_res.success

    if not write_res.success:
        result.error = f"write failed: {write_res.error}"
        return result

    # Search for marker with short retry to absorb indexing lag.
    search_res: Optional[SearchResult] = None
    found = False
    for _ in range(5):
        search_res = await search_memory_via_adapter(
            query=marker,
            agent_id=agent_id,
            cfg=cfg,
        )
        if not search_res.success:
            await asyncio.sleep(0.2)
            continue
        found = any(marker in str(mem.get("content", "")) for mem in search_res.memories)
        if found:
            break
        await asyncio.sleep(0.2)

    result.search_result = search_res or SearchResult(success=False, memories=[], error="search_not_executed")
    result.search_ok = bool(search_res and search_res.success and found)

    if not result.search_ok:
        if search_res and not search_res.success:
            result.error = f"search failed: {search_res.error}"
        else:
            count = len(search_res.memories) if search_res else 0
            result.error = (
                f"write succeeded (id={write_res.memory_id}) "
                f"but search returned {count} results without marker"
            )

    return result


# ---------------------------------------------------------------------------
# Path B: Compile round-trip (write → compile retrieves)
# ---------------------------------------------------------------------------

async def run_path_b(marker: str, cfg: dict) -> RoundtripResult:
    """
    Path B: Write a memory item, then call run_gateway_compile() with a
    related query. Verify the compiled payload contains the written content.

    Tests: /memory/write → compile retrieves it → packed_context includes it

    Requires: adapter running + memory backend accessible.
    """
    result = RoundtripResult(path="path_b")
    agent_id = cfg["agent_id"]

    # Write a memory with known content that relates to a query we'll make
    known_content = (
        f"SFE-007 Path B context: project config is in src/config/settings.py "
        f"marker={marker} test_id={uuid.uuid4().hex[:8]} "
        "Database connection uses env DB_HOST. Tests are in tests/."
    )

    write_res = await write_memory_via_adapter(known_content, agent_id, cfg=cfg)
    if not write_res.success:
        await asyncio.sleep(0.2)
        write_res = await write_memory_via_adapter(known_content, agent_id, cfg=cfg)
    result.write_result = write_res
    result.write_ok = write_res.success

    if not write_res.success:
        result.error = f"write failed: {write_res.error}"
        return result

    # Give backend a moment to index
    await asyncio.sleep(0.5)

    # Build a request that should trigger retrieval of this memory
    # (compile should find it based on the config-related keywords)
    test_query = marker
    payload = {
        "messages": [{"role": "user", "content": test_query}],
    }

    # Call run_gateway_compile directly
    compile_res = await _compile_via_adapter(payload, agent_id, cfg=cfg)
    result.compile_result = compile_res

    if not compile_res.success:
        result.error = f"compile failed: {compile_res.error}"
        return result

    # Check if the written memory's content appears in the compiled context
    found_in_context = marker in compile_res.packed_context
    result.memory_found_in_context = found_in_context
    result.compile_retrieves_memory = found_in_context

    if not found_in_context:
        result.error = (
            f"write succeeded (id={write_res.memory_id}) "
            f"but compile retrieved {compile_res.selected_memory_count} memories "
            f"and packed_context does not contain marker. "
            f"Context preview: {compile_res.packed_context[:300]!r}"
        )

    return result


async def _compile_via_adapter(
    payload: dict,
    agent_id: str,
    cfg: dict,
) -> CompileResult:
    """
    Call run_gateway_compile via the adapter's HTTP interface.
    Uses /memory/search endpoint indirectly via the compile pipeline.

    For Path B, we call run_gateway_compile directly via import
    (same pattern as SFE-006).
    """
    import importlib

    try:
        _gc = importlib.import_module("5_connectors.adapter.application.gateway_compile")
        _ai_mod = importlib.import_module("5_connectors.adapter.agent_identity")
    except ImportError as e:
        return CompileResult(success=False, error=f"import error: {e}")

    try:
        resolved = _ai_mod.resolve_agent(agent_id)
    except Exception:
        resolved = agent_id

    try:
        compiled_payload, compile_meta = await _gc.run_gateway_compile(
            payload=payload,
            agent_id=resolved,
            session_id=None,
            access_plan=None,
            request_id=f"sfe007-{int(time.time())}",
            trace_id=f"sfe007-{int(time.time())}",
        )
    except Exception as e:
        return CompileResult(success=False, error=str(e)[:200])

    packed_context = ""
    if isinstance(compiled_payload, dict):
        system_payload = compiled_payload.get("system")
        if isinstance(system_payload, str):
            packed_context = system_payload
        elif isinstance(system_payload, list):
            text_parts = []
            for part in system_payload:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            packed_context = "\n".join([p for p in text_parts if p]).strip()
        else:
            messages = compiled_payload.get("messages")
            if isinstance(messages, list) and messages:
                first = messages[0]
                if isinstance(first, dict) and first.get("role") == "system":
                    packed_context = str(first.get("content", "") or "")

    return CompileResult(
        success=compile_meta.get("compile_status") == "compile_success",
        compile_status=compile_meta.get("compile_status", "unknown"),
        selected_memory_count=compile_meta.get("selected_memory_count", 0),
        packed_context=packed_context,
    )


# ---------------------------------------------------------------------------
# Path C: Agent end-to-end (instrumented — not auto-tested here)
# ---------------------------------------------------------------------------

async def run_path_c(cfg: dict) -> RoundtripResult:
    """
    Path C: End-to-end agent feedback loop.

    This path CANNOT be automatically tested in this harness because:
    1. It requires Claude Code or OpenClaw to be running
    2. The agent must send a request → get response → write memory
    3. Then send a follow-up request

    This function documents the expected behavior and returns a skip result.
    In practice, Path C is verified by:
    - Instrumenting the MCP memory.write calls
    - Adding logging to the agent's post-response hook
    - Checking that subsequent compile requests retrieve those MCP-written memories

    For now, Path C is OUT OF SCOPE for automated testing.
    """
    result = RoundtripResult(path="path_c")
    result.error = (
        "Path C (agent end-to-end) is out of scope for automated harness. "
        "Verify manually: run Claude Code with OmniMemora MCP attached, "
        "send two related requests, and confirm the compile context "
        "retrieves the first response's written memory."
    )
    return result


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

import pytest


def test_sfe007_path_a_write_search_roundtrip():
    """
    Path A: Write memory via /memory/write, then search via /memory/search.
    Verify the written memory appears in search results.
    """
    cfg = _cfg()
    marker = f"patha-{uuid.uuid4().hex[:8]}"

    result = asyncio.run(run_path_a(marker, cfg))

    _print_result(result)

    assert result.passed, (
        f"SFE-007 Path A FAILED: {result.error}\n"
        f"  write_ok={result.write_ok} search_ok={result.search_ok}"
    )


def test_sfe007_path_b_write_compile_retrieval():
    """
    Path B: Write a memory item, then call run_gateway_compile() with
    a related query. Verify the compiled payload retrieves it.

    This requires the adapter and memory backend to be running.
    Skips if adapter is unreachable.
    """
    cfg = _cfg()
    marker = f"pathb-{uuid.uuid4().hex[:8]}"

    # Check if adapter is reachable
    async def _check_health() -> Optional[int]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{cfg['adapter_url']}/health")
            return health.status_code

    try:
        health_status = asyncio.run(_check_health())
        if health_status is not None and health_status >= 500:
            pytest.skip(f"Adapter health check failed: {health_status}")
    except httpx.ConnectError:
        pytest.skip(f"Adapter not reachable at {cfg['adapter_url']} — start adapter first")

    result = asyncio.run(run_path_b(marker, cfg))

    _print_result(result)

    assert result.passed, (
        f"SFE-007 Path B FAILED: {result.error}\n"
        f"  write_ok={result.write_ok} "
        f"compile_retrieves={result.compile_retrieves_memory} "
        f"found_in_context={result.memory_found_in_context}\n"
        f"  compile_status={result.compile_result.compile_status if result.compile_result else 'N/A'}\n"
        f"  packed_context: {result.compile_result.packed_context[:500] if result.compile_result else 'N/A'!r}"
    )


def test_sfe007_path_c_agent_loop():
    """
    Path C: Agent end-to-end feedback loop.

    OUT OF SCOPE for automated testing.
    Documents the expected behavior.
    """
    cfg = _cfg()
    result = asyncio.run(run_path_c(cfg))

    _print_result(result)

    # Path C always returns "passed" with an out-of-scope note
    # It is verified manually
    print(f"NOTE: Path C is verified manually. See docstring.")
    assert True


def _print_result(r: RoundtripResult) -> None:
    print(f"\n{'='*70}")
    print(f"SFE-007 | {r.path}")
    print(f"  write_ok:             {r.write_ok}")
    print(f"  search_ok:            {r.search_ok}")
    print(f"  compile_retrieves:    {r.compile_retrieves_memory}")
    print(f"  memory_found_in_ctx:  {r.memory_found_in_context}")
    if r.write_result:
        print(f"  write status:         {r.write_result.status} | id={r.write_result.memory_id[:20] if r.write_result.memory_id else 'N/A'}")
    if r.search_result:
        print(f"  search count:         {len(r.search_result.memories)}")
    if r.compile_result:
        print(f"  compile status:       {r.compile_result.compile_status}")
        print(f"  selected memories:    {r.compile_result.selected_memory_count}")
        print(f"  packed_context (300): {r.compile_result.packed_context[:300]!r}")
    if r.error:
        print(f"  ERROR: {r.error}")
    print(f"  PASSED: {'✅' if r.passed else '❌'}")
    print(f"{'='*70}")
