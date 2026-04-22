"""
统一能力入口 - 串联纯逻辑模块
所有外部依赖（规则、数据）从外部注入，engine 只负责编排决策流程
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .rules import FilterRules, RoutingRules
from .filter import filter_with_score, detect_failure_content
from .router import calculate_memory_score, calculate_memory_score_detailed, route_memory_type_and_level
from .v2_compute import (
    TokenSavingsMeter,
    QuotaEnforcementResult,
    generate_meter_artifact,
    build_packed_context,
    check_quota_enforcement,
    estimate_tokens,
    CallChain,
    CallChainStage,
)
from .skill_suggestion import (
    RecommendationPolicyInput,
    SkillSuggestion,
    evaluate_recommendation_policy,
)
import time


@dataclass
class OptimizationInput:
    """Query 路径的统一输入"""
    query: str
    candidate_memories: List[Dict[str, Any]]
    filter_rules: FilterRules
    routing_rules: RoutingRules

    agent: str = "supervisor"
    client: str = "openclaw"

    current_usage: int = 0
    monthly_quota: Optional[int] = None

    packing_enabled: bool = True
    max_local_cards: int = 4
    candidate_limit: int = 16

    # Policy v1: Task classification (set by adapter before calling optimize_context)
    task_type: Optional[str] = None  # "implementation" | "decision" | "continuation"
    context_bypass: bool = False      # True if context injection was skipped (pre-bypassed at adapter)
    bypassed_context_tokens: int = 0   # Estimated tokens bypassed (set if context_bypass=True)

    # Multi-source candidates (Phase 4: final compile gate)
    native_compiled_context: Optional[str] = None  # OpenClaw native compiler output (treated as one candidate)
    current_session_context: Optional[str] = None  # Current session context (treated as one candidate)
    raw_candidates: Optional[List[Dict[str, Any]]] = None  # Explicit candidate list from caller

    # Recommendation policy snapshot injected by adapter binding.
    recommendation_policy_snapshot: Optional[dict] = None

@dataclass
class OptimizationResult:
    """Query 路径的统一输出"""
    selected_memories: List[Dict[str, Any]]
    packed_context: str
    token_savings: TokenSavingsMeter
    quota_result: QuotaEnforcementResult
    meter_artifact: Dict[str, Any]

    candidate_count: int
    selected_count: int

    # Call chain timing trace
    call_chain: CallChain = None
    skill_suggestions: List[SkillSuggestion] = field(default_factory=list)
    skill_policy_name: str = "local_fallback"
    skill_policy_version: str = "static_catalog_v1"
    skill_policy_source: str = "local_builtin"
    skill_policy_status: str = "fallback"


def _extract_content_metadata(mem: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """Extract content and metadata from a memory dict."""
    content = mem.get("content", "") or mem.get("abstract", "") or ""
    metadata = {"type": mem.get("category", "general")}
    return content, metadata


def optimize_context(input: OptimizationInput) -> OptimizationResult:
    """
    统一优化入口：串联 filter → route/score → reduce redundancy → select → pack → meter
    不碰文件系统，不读配置，不负责持久化
    """
    _t0 = time.perf_counter()
    stages = []

    # Input validation
    if input.candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    if input.max_local_cards <= 0:
        raise ValueError("max_local_cards must be positive")
    if input.max_local_cards > input.candidate_limit:
        raise ValueError("max_local_cards cannot exceed candidate_limit")

    # Snapshot candidates BEFORE any filtering (for context_diff)
    # Multi-source merge: native_compiled_context + current_session_context + raw_candidates
    merged_candidates = list(input.candidate_memories[:input.candidate_limit])
    if input.native_compiled_context:
        merged_candidates.append({
            "content": input.native_compiled_context,
            "abstract": "[native-compiled-context]",
            "category": "native_compiled",
            "score": 0.8,
            "_source": "native_compiled",
        })
    if input.current_session_context:
        merged_candidates.append({
            "content": input.current_session_context,
            "abstract": "[current-session-context]",
            "category": "session",
            "score": 0.8,
            "_source": "session",
        })
    if input.raw_candidates:
        for rc in input.raw_candidates[:input.candidate_limit]:
            rc["_source"] = "raw_candidate"
            merged_candidates.append(rc)
    all_candidates = merged_candidates[:input.candidate_limit]
    candidate_count = len(all_candidates)

    # 1. Filter 阶段
    t1 = time.perf_counter()
    filtered = []
    for mem in all_candidates:
        content, metadata = _extract_content_metadata(mem)
        ok, reason, score = filter_with_score(content, metadata, input.filter_rules)
        if ok:
            mem["_score"] = score
            mem["_filter_reason"] = reason
            filtered.append(mem)
    t2 = time.perf_counter()
    stages.append(CallChainStage(name="filter", duration_ms=(t2 - t1) * 1000))

    # 2. Route / Score 阶段
    t3 = time.perf_counter()
    scored = []
    for mem in filtered:
        content, metadata = _extract_content_metadata(mem)
        relevance_score, type_score, length_penalty, final_score, _ = calculate_memory_score_detailed(content, metadata, input.routing_rules)

        # 记录 3 个维度 + final_score
        mem["_relevance_score"] = relevance_score
        mem["_type_score"] = type_score
        mem["_length_penalty"] = length_penalty
        mem["_final_score"] = final_score
        mem["_score"] = final_score  # 向后兼容

        is_failure, _ = detect_failure_content(content)
        if is_failure and final_score < 3:
            final_score = 3
            mem["_score"] = final_score  # 向后兼容
            mem["_final_score"] = final_score  # 同步更新
        scored.append((final_score, mem))
    t4 = time.perf_counter()
    stages.append(CallChainStage(name="route_score", duration_ms=(t4 - t3) * 1000))

    # 3. Reduce redundancy（query 侧去冗余）
    t5 = time.perf_counter()
    scored_without_dup = []
    seen_contents = set()
    for score, mem in scored:
        content = mem.get("content", "").strip()
        if content not in seen_contents:
            seen_contents.add(content)
            scored_without_dup.append((score, mem))
    t6 = time.perf_counter()
    stages.append(CallChainStage(name="dedup", duration_ms=(t6 - t5) * 1000))

    # 4. Select top-k
    t7 = time.perf_counter()
    scored_without_dup.sort(key=lambda x: x[0], reverse=True)
    selected = [mem for _, mem in scored_without_dup[:input.max_local_cards]]
    selected_count = len(selected)
    t8 = time.perf_counter()
    stages.append(CallChainStage(name="select", duration_ms=(t8 - t7) * 1000))

    # 5. Build packed context
    t9 = time.perf_counter()
    packed_context = build_packed_context(selected) if input.packing_enabled else ""
    t10 = time.perf_counter()
    stages.append(CallChainStage(name="pack", duration_ms=(t10 - t9) * 1000))

    # 6. Token savings compute
    # baseline = avg candidate chars × candidate_limit (what full unoptimized set would cost)
    actual_chars = len(packed_context) if input.packing_enabled else sum(len(m.get("content", "") or "") for m in selected)
    avg_chars = sum(len(m.get("content", "") or "") for m in all_candidates) / len(all_candidates) if all_candidates else 0
    baseline_chars = int(avg_chars * input.candidate_limit)
    saved_chars = max(0, baseline_chars - actual_chars)
    baseline_tokens = estimate_tokens(baseline_chars)
    actual_tokens = estimate_tokens(actual_chars)
    saved_tokens = max(0, baseline_tokens - actual_tokens)
    savings_ratio = saved_tokens / baseline_tokens if baseline_tokens > 0 else 0.0

    # Compute dropped memories (candidates that were filtered/scored but not selected)
    selected_content_set = {m.get("content", "").strip() for m in selected}
    dropped_memories = [m for m in all_candidates if m.get("content", "").strip() not in selected_content_set]

    # 7. Meter artifact
    t11 = time.perf_counter()
    dedup_applied = len(scored) != len(scored_without_dup)
    meter = TokenSavingsMeter(
        request_id="engine-local",
        tenant="engine",
        user="engine",
        agent=input.agent,
        client=input.client,
        timestamp=datetime.utcnow().isoformat() + "Z",
        query_shape="mixed",
        query_chars=len(input.query),
        query=input.query[:100],
        baseline_chars=baseline_chars,
        actual_chars=actual_chars,
        saved_chars=saved_chars,
        baseline_tokens_estimate=baseline_tokens,
        actual_tokens_estimate=actual_tokens,
        saved_tokens_estimate=saved_tokens,
        savings_ratio=round(savings_ratio, 3),
        packed_memory_count=len(selected),
        local_cards_used=len(selected),
        remote_candidates_considered=input.candidate_limit,
        remote_candidates_skipped=input.candidate_limit - len(selected),
        remote_used_count=0,
        skipped_remote_reason="local-first coverage satisfied",
        coverage_satisfied=True,
        packing_enabled=input.packing_enabled,
        abstract_preferred=False,
        dedup_applied=dedup_applied,
        # Policy v1 fields (passed through from adapter)
        task_type=input.task_type,
        context_bypass=input.context_bypass,
        bypassed_context_tokens=input.bypassed_context_tokens,
        # Context diff (Before/After)
        candidate_memories=all_candidates,
        dropped_memories=dropped_memories,
    )
    t12 = time.perf_counter()
    stages.append(CallChainStage(name="meter", duration_ms=(t12 - t11) * 1000))

    # 8. Quota check
    quota_result = check_quota_enforcement(input.current_usage, input.monthly_quota)

    # Total engine time
    total_ms = (time.perf_counter() - _t0) * 1000
    stages.insert(0, CallChainStage(name="engine_total", duration_ms=total_ms))

    # Build call chain (trace_id placeholder — adapter will replace with real request_id)
    call_chain = CallChain(trace_id="engine-local", stages=stages)

    # Skill suggestions (advisory-only sidecar metadata; never affects packed_context)
    normalized_task = (input.task_type or "").strip().lower()
    if normalized_task not in {"decision", "continuation", "implementation"}:
        normalized_task = "continuation"

    policy_result = evaluate_recommendation_policy(
        RecommendationPolicyInput(
            query=input.query,
            task_type=normalized_task,
            agent=input.agent,
            client=input.client,
            limit=3,
        ),
        snapshot_dict=input.recommendation_policy_snapshot,
    )

    task_type = (input.task_type or "").strip().lower()
    if task_type == "implementation":
        skill_suggestions: List[SkillSuggestion] = []
        policy_status = (
            "invalid_snapshot"
            if policy_result.policy_status == "invalid_snapshot"
            else "disabled"
        )
    else:
        skill_suggestions = policy_result.skill_suggestions
        policy_status = policy_result.policy_status

    return OptimizationResult(
        selected_memories=selected,
        packed_context=packed_context,
        token_savings=meter,
        quota_result=quota_result,
        meter_artifact=meter.to_dict(),
        candidate_count=candidate_count,
        selected_count=selected_count,
        call_chain=call_chain,
        skill_suggestions=skill_suggestions,
        skill_policy_name=policy_result.policy_name,
        skill_policy_version=policy_result.policy_version,
        skill_policy_source=policy_result.policy_source,
        skill_policy_status=policy_status,
    )
