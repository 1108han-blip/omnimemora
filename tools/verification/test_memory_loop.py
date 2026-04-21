#!/usr/bin/env python3
"""
Memory Value Loop v1 — Controlled Validation Script
===================================================
Hardened acceptance test for the Memory Value Loop v1.

Two validation layers:
  Layer 1 — Compile layer: execute_runtime_compile() + generate_meter_artifact()
  Layer 2 — Adapter HTTP layer: POST /memory/query + GET /debug/request_evidence

Run from repo root:
  python3 tools/verification/test_memory_loop.py

Exit codes:
  0  — all validations passed
  1  — seed/candidate failure
  2  — compile layer failure
  3  — meter layer failure
  4  — HTTP layer failure
  5  — evidence validation failure
"""
import asyncio
import json
import os
import sys
import importlib
from typing import Any, Dict, List, Optional

# Add repo root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Fixed validation seeds — deliberately fixed so the script is repeatable
# ---------------------------------------------------------------------------
_TENANT = "validation-tenant"
_USER = "validation-user"
_AGENT = "validation-agent"
_QUERY_SEED = "python async FastAPI dependency injection"
_QUERY_VALIDATE = "How do I use Python async patterns in FastAPI?"
_ADAPTER_BASE = os.getenv("ADAPTER_BASE", "http://localhost:18011")

_SEEDED_MEMORIES = [
    "Python async/await: use asyncio.gather for concurrent I/O operations",
    "FastAPI: use Depends() for dependency injection and shared logic",
    "Pydantic v2: use model_validator for complex cross-field validation",
    "SQLAlchemy: use AsyncSession with asyncpg for non-blocking database access",
]

# Expected outcomes (fixed per validation contract)
_EXPECTED_MIN_SELECTED = 1
_EXPECTED_MIN_PACKED = 1
_EXPECTED_REQUEST_CLASS = "value_qualified"
_EXPECTED_VALUE_PATH = ["packed_memory", "local_cards"]
_EXPECTED_UPSTREAM_STATUS = "not_used"


def _import(name: str):
    """Import using importlib to bypass digit-prefix module name restriction."""
    return importlib.import_module(name)


# ---------------------------------------------------------------------------
# Layer 1 — Compile-layer validation
# ---------------------------------------------------------------------------

async def _validate_compile_layer() -> Dict[str, Any]:
    """
    Validate the compile path: execute_runtime_compile() + generate_meter_artifact().

    Returns dict with keys: seeded_count, candidate_count, selected_count,
    packed_memory_count, local_cards_used, savings_ratio, compile_error, passed
    """
    backends_factory = _import("5_connectors.adapter.backends.factory")
    config_mod = _import("5_connectors.adapter.config")
    backends_base = _import("5_connectors.adapter.backends.base")
    runtime_bridge = _import("5_connectors.adapter.runtime_bridge")
    v2_compute = _import("4_core.logic.v2_compute")

    create_backend = backends_factory.create_backend
    config = config_mod.config
    MemorySearchRequest = backends_base.MemorySearchRequest
    MemoryWriteRequest = backends_base.MemoryWriteRequest
    execute_runtime_compile = runtime_bridge.execute_runtime_compile
    generate_meter_artifact = v2_compute.generate_meter_artifact

    backend = create_backend(config.memory_backend)

    # Step 1: Seed memories
    written = []
    for content in _SEEDED_MEMORIES:
        record = await backend.write(MemoryWriteRequest(
            content=content,
            scope="agent",
            scope_ref=_AGENT,
        ))
        written.append(record.memory_id)

    # Step 2: Search for candidates
    search_result = await backend.search(MemorySearchRequest(
        query=_QUERY_SEED,
        limit=10,
        scope="agent",
        scope_ref=_AGENT,
        score_threshold=0.0,
    ))
    candidates = [
        {
            "uri": m.memory_id,
            "content": m.content,
            "abstract": m.content[:200],
            "category": "memory",
            "score": m.score or 0.5,
        }
        for m in search_result.memories
    ]

    # Step 3: execute_runtime_compile
    compile_result = await execute_runtime_compile(
        query=_QUERY_VALIDATE,
        candidate_memories=candidates,
        agent_id=_AGENT,
        request_id="val-compile-001",
    )

    selected_count = compile_result.get("selected_count", 0)
    selected_memories = compile_result.get("selected_memories", [])
    compression_ratio = compile_result.get("compression_ratio", 0.0)
    compile_error = compile_result.get("compile_error")

    # Step 4: generate_meter_artifact
    meter = generate_meter_artifact(
        request_id="val-meter-001",
        tenant=_TENANT,
        user=_USER,
        agent=_AGENT,
        client="validation-script",
        query=_QUERY_VALIDATE,
        selected_memories=selected_memories,
        candidate_memories=candidates,
        local_cards_used=min(4, len(selected_memories)),
        packing_enabled=True,
    )

    return {
        "seeded_count": len(written),
        "candidate_count": len(candidates),
        "selected_count": selected_count,
        "packed_memory_count": meter.packed_memory_count,
        "local_cards_used": meter.local_cards_used,
        "savings_ratio": meter.savings_ratio,
        "compile_error": compile_error,
        "passed": (
            selected_count >= _EXPECTED_MIN_SELECTED
            and meter.packed_memory_count >= _EXPECTED_MIN_PACKED
            and compile_error is None
        ),
    }


# ---------------------------------------------------------------------------
# Layer 2 — HTTP-layer validation via adapter endpoints
# ---------------------------------------------------------------------------

async def _validate_http_layer() -> Dict[str, Any]:
    """
    Validate the HTTP path: POST /memory/query + GET /debug/request_evidence.

    Returns dict with keys: query_request_id, request_class, value_path,
    value_qualified, request_status, upstream_status, upstream_note, passed
    """
    try:
        import httpx
    except ImportError:
        return {"error": "httpx not installed — cannot run HTTP validation", "passed": False}

    query_payload = {
        "tenant": _TENANT,
        "user": _USER,
        "query": _QUERY_VALIDATE,
        "agent": _AGENT,
    }

    # Step 1: POST /memory/query
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{_ADAPTER_BASE}/memory/query", json=query_payload)
        resp.raise_for_status()
        query_data = resp.json()

    request_id = query_data.get("request_id")
    if not request_id:
        return {"error": "no request_id in query response", "passed": False}

    # Step 2: GET /debug/request_evidence
    async with httpx.AsyncClient(timeout=30.0) as client:
        evidence_resp = await client.get(
            f"{_ADAPTER_BASE}/debug/request_evidence",
            params={"request_id": request_id},
        )
        evidence_resp.raise_for_status()
        evidence = evidence_resp.json()

    # Extract relevant fields
    request_class_obj = evidence.get("request_class", {})
    request_class = request_class_obj.get("request_class", "unknown")
    value_path = request_class_obj.get("value_path", [])
    value_qualified = evidence.get("status", {}).get("value_qualified", False)
    request_status = evidence.get("status", {}).get("request_status", "unknown")

    # Check upstream_forward node in chain
    upstream_node = next(
        (n for n in evidence.get("chain", {}).get("nodes", []) if n.get("id") == "upstream_forward"),
        None,
    )
    upstream_status = upstream_node.get("status", "unknown") if upstream_node else "missing"
    upstream_note = upstream_node.get("note", "") if upstream_node else ""

    return {
        "query_request_id": request_id,
        "request_class": request_class,
        "value_path": value_path,
        "value_qualified": value_qualified,
        "request_status": request_status,
        "upstream_status": upstream_status,
        "upstream_note": upstream_note,
        "passed": (
            request_class == _EXPECTED_REQUEST_CLASS
            and value_qualified is True
            and request_status == "success"
            and upstream_status == _EXPECTED_UPSTREAM_STATUS
            and set(value_path) == set(_EXPECTED_VALUE_PATH)
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    print("=" * 60)
    print("Memory Value Loop v1 — Controlled Validation")
    print("=" * 60)
    print()

    # Layer 1: Compile layer
    print("=== Layer 1: Compile-layer validation ===")
    compile_result = await _validate_compile_layer()

    print(f"  seeded_count:       {compile_result['seeded_count']}")
    print(f"  candidate_count:    {compile_result['candidate_count']}")
    print(f"  selected_count:     {compile_result['selected_count']}")
    print(f"  packed_memory_count:{compile_result['packed_memory_count']}")
    print(f"  local_cards_used:   {compile_result['local_cards_used']}")
    print(f"  savings_ratio:       {compile_result['savings_ratio']:.3f}")
    print(f"  compile_error:      {compile_result['compile_error']}")
    print()

    if not compile_result["passed"]:
        print("FAIL: compile layer — selected_count or packed_memory_count is zero")
        return 2

    if compile_result["compile_error"]:
        print(f"FAIL: compile layer — compile_error: {compile_result['compile_error']}")
        return 2

    print("PASS: compile layer")
    print()

    # Layer 2: HTTP layer
    print("=== Layer 2: Adapter HTTP-layer validation ===")

    if compile_result["candidate_count"] == 0:
        print("SKIP: HTTP layer — no candidates to drive a request")
        return 1

    http_result = await _validate_http_layer()

    if "error" in http_result:
        print(f"FAIL: HTTP layer — {http_result['error']}")
        return 4

    print(f"  query_request_id:   {http_result['query_request_id']}")
    print(f"  request_class:      {http_result['request_class']}")
    print(f"  value_path:         {http_result['value_path']}")
    print(f"  value_qualified:    {http_result['value_qualified']}")
    print(f"  request_status:     {http_result['request_status']}")
    print(f"  upstream_status:    {http_result['upstream_status']}")
    print(f"  upstream_note:     '{http_result['upstream_note']}'")
    print()

    if not http_result["passed"]:
        print("FAIL: HTTP layer — evidence validation failed")
        print(f"  expected request_class={_EXPECTED_REQUEST_CLASS}, got {http_result['request_class']}")
        print(f"  expected value_qualified=True, got {http_result['value_qualified']}")
        print(f"  expected request_status=success, got {http_result['request_status']}")
        print(f"  expected value_path={_EXPECTED_VALUE_PATH}, got {http_result['value_path']}")
        print(f"  expected upstream_status={_EXPECTED_UPSTREAM_STATUS}, got {http_result['upstream_status']}")
        return 5

    print("PASS: HTTP layer")
    print()

    # Full summary
    print("=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    summary = {
        "seeded_count": compile_result["seeded_count"],
        "candidate_count": compile_result["candidate_count"],
        "selected_count": compile_result["selected_count"],
        "packed_memory_count": compile_result["packed_memory_count"],
        "local_cards_used": compile_result["local_cards_used"],
        "savings_ratio": round(compile_result["savings_ratio"], 3),
        "request_class": http_result["request_class"],
        "request_status": http_result["request_status"],
        "value_path": http_result["value_path"],
    }
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
