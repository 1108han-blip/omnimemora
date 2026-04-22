"""
runtime_bridge.py — Gateway -> Existing Runtime Compile Logic
=============================================================
Phase 3 Task B: Wraps existing runtime/core compile logic for Gateway use.

Principle: Do not rewrite core compilation behavior. Wrap it.

Reuses:
  - 4_core.logic.engine.optimize_context()
  - OmniMemoraRuntimeBackend.search()
  - MemoryBackend / MemorySearchRequest
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..backends.base import MemoryBackend, MemorySearchRequest
from ..backends.factory import create_backend
from ..config import config
from ..trace_context import build_trace_event
from ..trace_events import append_trace_event

# Lazy backend singleton (same pattern as main.py)
_initialized_backend: Optional[MemoryBackend] = None


def _get_backend() -> MemoryBackend:
    global _initialized_backend
    if _initialized_backend is None:
        _initialized_backend = create_backend(config.memory_backend)
    return _initialized_backend


async def execute_runtime_compile(
    query: str,
    candidate_memories: List[Dict[str, Any]],
    agent_id: str,
    session_id: Optional[str] = None,
    model: Optional[str] = None,
    token_limit: Optional[int] = None,
    original_token_estimate: int = 0,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Wraps existing 4_core.logic.engine.optimize_context() for Gateway use.
    """
    import importlib

    import loguru

    _engine_mod = importlib.import_module("4_core.logic.engine")

    optimize_context = _engine_mod.optimize_context
    OptimizationInput = _engine_mod.OptimizationInput
    FilterRules = _engine_mod.FilterRules
    RoutingRules = _engine_mod.RoutingRules

    try:
        policy_snapshot = None
        try:
            from .recommendation_policy_loader import load_recommendation_policy

            policy_snapshot = load_recommendation_policy()
        except Exception:
            policy_snapshot = None

        if config.trace_events_enabled:
            append_trace_event(
                build_trace_event(
                    trace_id=trace_id or request_id or "unknown",
                    request_id=request_id or "unknown",
                    stage="adapter",
                    path="runtime:/memory/search",
                    status="compile_start",
                    agent_id=agent_id,
                    details={
                        "candidate_input_count": len(candidate_memories),
                        "model": model or "unknown",
                    },
                )
            )

        input_data = OptimizationInput(
            query=query,
            candidate_memories=candidate_memories,
            filter_rules=FilterRules(),
            routing_rules=RoutingRules(),
            agent=agent_id,
            client="gateway",
            current_usage=0,
            monthly_quota=None,
            packing_enabled=True,
            max_local_cards=4,
            candidate_limit=16,
            task_type=None,
            context_bypass=False,
            bypassed_context_tokens=0,
            recommendation_policy_snapshot=policy_snapshot,
        )

        result = optimize_context(input_data)

        packed_chars = len(result.packed_context) if result.packed_context else 0
        query_chars = len(query) if query else 0
        if packed_chars == 0 and query_chars > 0:
            orig = max(1, int(query_chars / 3))
            compiled_tokens = orig
        else:
            orig = original_token_estimate if original_token_estimate > 0 else max(1, int(packed_chars / 3))
            compiled_tokens = max(1, int(packed_chars / 3))

        ratio = 0.0
        if orig > 0 and compiled_tokens > 0:
            ratio = max(0.0, min(1.0, 1.0 - compiled_tokens / orig))
        saved = max(0, orig - compiled_tokens)

        loguru.logger.debug(
            f"[RUNTIME_BRIDGE] agent={agent_id} query_len={len(query)} "
            f"candidates={result.candidate_count} selected={result.selected_count} "
            f"original={orig} compiled={compiled_tokens} ratio={ratio:.3f}"
        )

        if config.trace_events_enabled:
            append_trace_event(
                build_trace_event(
                    trace_id=trace_id or request_id or "unknown",
                    request_id=request_id or "unknown",
                    stage="adapter",
                    path="runtime:/memory/search",
                    status="ok",
                    agent_id=agent_id,
                    details={
                        "candidate_count": result.candidate_count,
                        "selected_count": result.selected_count,
                        "compiled_token_estimate": compiled_tokens,
                        "compression_ratio": ratio,
                    },
                )
            )

        return {
            "compiled_messages": None,
            "selected_memories": [
                {
                    "uri": mem.get("uri", ""),
                    "content": mem.get("content", ""),
                    "abstract": mem.get("abstract", mem.get("content", "")[:200]),
                    "category": mem.get("category", "memory"),
                    "score": mem.get("score", 0.5),
                }
                for mem in result.selected_memories
            ],
            "packed_context": result.packed_context,
            "original_token_estimate": orig,
            "compiled_token_estimate": compiled_tokens,
            "saved_token_estimate": saved,
            "compression_ratio": ratio,
            "compile_reason": "runtime_compile",
            "compile_error": None,
            "candidate_count": result.candidate_count,
            "selected_count": result.selected_count,
            "skill_suggestions": [s.to_dict() for s in (result.skill_suggestions or [])],
            "skill_policy_name": getattr(result, "skill_policy_name", "local_fallback"),
            "skill_policy_version": getattr(result, "skill_policy_version", "static_catalog_v1"),
            "skill_policy_source": getattr(result, "skill_policy_source", "local_builtin"),
            "skill_policy_status": getattr(result, "skill_policy_status", "fallback"),
        }

    except Exception as e:
        loguru.logger.warning(f"[RUNTIME_BRIDGE] compile failed for agent={agent_id}: {e}")
        if config.trace_events_enabled:
            append_trace_event(
                build_trace_event(
                    trace_id=trace_id or request_id or "unknown",
                    request_id=request_id or "unknown",
                    stage="error",
                    path="runtime:/memory/search",
                    status="error",
                    agent_id=agent_id,
                    error_type="runtime_compile_error",
                    details={"error": str(e)[:200]},
                )
            )
        return {
            "compiled_messages": None,
            "selected_memories": [],
            "packed_context": "",
            "original_token_estimate": 0,
            "compiled_token_estimate": 0,
            "saved_token_estimate": 0,
            "compression_ratio": 0.0,
            "compile_reason": "runtime_compile",
            "compile_error": str(e)[:200],
            "candidate_count": 0,
            "selected_count": 0,
            "skill_suggestions": [],
            "skill_policy_name": "local_fallback",
            "skill_policy_version": "static_catalog_v1",
            "skill_policy_source": "local_builtin",
            "skill_policy_status": "fallback",
        }


async def fetch_memory_candidates(
    query: str,
    agent_id: str,
    limit: int = 16,
    scope: str = "agent",
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch relevant memory candidates from OmniMemora Runtime backend.
    """
    import loguru

    backend = _get_backend()
    try:
        search_result = await backend.search(
            MemorySearchRequest(
                query=query,
                limit=limit,
                scope=scope,
                scope_ref=agent_id,
                score_threshold=0.0,
            ),
            request_id=request_id,
            trace_id=trace_id,
            agent_id=agent_id,
        )
        memories = []
        for record in search_result.memories:
            memories.append(
                {
                    "memory_id": record.memory_id,
                    "content": record.content,
                    "abstract": record.content[:200] if record.content else "",
                    "category": "memory",
                    "score": record.score,
                    "scope": record.scope,
                    "scope_ref": record.scope_ref,
                    "metadata": record.metadata or {},
                    "created_at": record.created_at.isoformat()
                    if hasattr(record.created_at, "isoformat")
                    else str(record.created_at or ""),
                }
            )
        loguru.logger.debug(
            f"[RUNTIME_BRIDGE] search agent={agent_id} query={query[:50]} results={len(memories)}"
        )
        return memories
    except Exception as e:
        loguru.logger.warning(f"[RUNTIME_BRIDGE] search failed: {e}")
        if config.trace_events_enabled:
            append_trace_event(
                build_trace_event(
                    trace_id=trace_id or request_id or "unknown",
                    request_id=request_id or "unknown",
                    stage="error",
                    path="runtime:/memory/search",
                    status="error",
                    agent_id=agent_id,
                    error_type="runtime_search_error",
                    details={"error": str(e)[:200]},
                )
            )
        return []
