"""
V2 计算层 - 纯逻辑，不碰文件系统
只负责：token 估算、meter 生成、quota 判断
"""
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class CallChainStage:
    """Single stage in a call chain trace."""
    name: str
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallChain:
    """Full call chain for a single request."""
    trace_id: str
    stages: List[CallChainStage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "stages": [
                {"name": s.name, "duration_ms": round(s.duration_ms, 3), "metadata": s.metadata}
                for s in self.stages
            ],
        }


@dataclass
class TokenSavingsMeter:
    """Token Savings Meter artifact - full specification."""
    request_id: str
    tenant: str
    user: str
    agent: str
    client: Optional[str]
    timestamp: str
    query_shape: str  # "field_only" or "mixed"
    query_chars: int
    query: str  # The original query text

    baseline_chars: int
    actual_chars: int
    saved_chars: int

    baseline_tokens_estimate: int
    actual_tokens_estimate: int
    saved_tokens_estimate: int

    savings_ratio: float

    packed_memory_count: int
    local_cards_used: int
    remote_candidates_considered: int
    remote_candidates_skipped: int
    remote_used_count: int

    skipped_remote_reason: Optional[str]
    coverage_satisfied: bool
    packing_enabled: bool
    abstract_preferred: bool
    dedup_applied: bool

    # Policy v1: Task classification & context bypass
    task_type: Optional[str] = None  # "implementation" | "decision" | "continuation"
    context_bypass: bool = False       # True if context injection was skipped
    bypassed_context_tokens: int = 0   # Estimated tokens bypassed (for implementation tasks)
    matched_keywords: List[str] = field(default_factory=list)   # Keywords that triggered the classification

    # Context diff: full candidate list and dropped memories (for Before/After UI)
    candidate_memories: List[Dict[str, Any]] = field(default_factory=list)
    dropped_memories: List[Dict[str, Any]] = field(default_factory=list)

    # Identity spine (product-core traceability fields)
    tenant_id: Optional[str] = None
    family_id: Optional[str] = None
    instance_id: Optional[str] = None
    window_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_agent_id: Optional[str] = None

    # Domain-level traceability aliases (flat fields for legacy aggregators)
    workspace_id: Optional[str] = None
    domain_id: Optional[str] = None
    scope_type: Optional[str] = None
    sharing_mode: Optional[str] = None

    # Access-plan first-class projection
    identity_spine: Dict[str, Any] = field(default_factory=dict)
    read_domains: List[Dict[str, Any]] = field(default_factory=list)
    primary_write_domain: Optional[Dict[str, Any]] = None
    secondary_write_domains: List[Dict[str, Any]] = field(default_factory=list)
    sharing_policy_source: Optional[str] = None
    access_plan: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuotaEnforcementResult:
    """Result of a quota enforcement check."""
    quota_exceeded: bool
    current_usage: int
    monthly_quota: Optional[int]
    quota_status: str  # "over_quota" | "within_quota" | "untracked"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quota_exceeded": self.quota_exceeded,
            "current_usage": self.current_usage,
            "monthly_quota": self.monthly_quota,
            "quota_status": self.quota_status,
        }


def estimate_tokens(chars: int) -> int:
    """Estimate token count from character count (simplified: chars / 4)."""
    return max(1, chars // 4)


def classify_query_shape(query: str) -> str:
    """Classify query shape: field_only vs mixed.

    field_only: short, structured lookup queries (timezone, user preferences, settings).
    mixed: complex queries with multiple terms or sentence-like structure.
    """
    # Patterns that indicate structured field lookups
    field_patterns = [
        "timezone", "preference", "user.", "project.", "setting.",
    ]
    # Short question patterns — only match if query is short (<= 6 words)
    short_question_patterns = [
        "what is", "what's", "who is", "who's", "where is", "when is"
    ]
    query_lower = query.lower()
    query_words = query_lower.split()

    # Field patterns can appear anywhere in the query
    has_field_indicator = any(pattern in query_lower for pattern in field_patterns)

    # Short question patterns: only count if query is short (structured lookup, not a sentence)
    has_short_question = (
        len(query_words) <= 6
        and any(pattern in query_lower for pattern in short_question_patterns)
    )

    # Complex indicators: many words or sentence punctuation
    has_complex_terms = len(query_words) > 8 or any(c in query for c in ".,!?;")

    if (has_field_indicator or has_short_question) and not has_complex_terms:
        return "field_only"
    return "mixed"


def build_packed_context(memories: List[Dict[str, Any]]) -> str:
    """Build packed context string from memories."""
    if not memories:
        return "<relevant-memories>\n</relevant-memories>"

    lines = ["<relevant-memories>"]
    for mem in memories:
        mem_type = mem.get("type", "memory")
        score = mem.get("score", 0) or mem.get("_final_score", 0)
        content = mem.get("content", "")
        lines.append(f"- [{mem_type} | score={score}] {content}")
    lines.append("</relevant-memories>")
    return "\n".join(lines)


def calculate_baseline_chars(memories: List[Dict[str, Any]], remote_candidates: int = 16) -> int:
    """Calculate baseline character count (all candidates without optimization)."""
    if not memories:
        return 0

    avg_mem_chars = sum(len(m.get("content", "")) for m in memories) / len(memories)
    baseline = avg_mem_chars * remote_candidates

    return int(baseline)


def generate_meter_artifact(
    request_id: str,
    tenant: str,
    user: str,
    agent: str,
    client: Optional[str],
    query: str,
    selected_memories: List[Dict[str, Any]],
    candidate_memories: List[Dict[str, Any]] = None,
    dropped_memories: List[Dict[str, Any]] = None,
    remote_candidates_considered: int = 16,
    local_cards_used: int = 4,
    packing_enabled: bool = True,
    task_type: Optional[str] = None,
    context_bypass: bool = False,
    bypassed_context_tokens: int = 0,
    matched_keywords: Optional[List[str]] = None,
) -> TokenSavingsMeter:
    """Generate a complete Token Savings Meter artifact."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    query_shape = classify_query_shape(query)
    query_chars = len(query)

    # Calculate actual chars from selected memories
    actual_chars = sum(len(m.get("content", "")) for m in selected_memories)
    packed_context = build_packed_context(selected_memories) if packing_enabled else ""
    if packing_enabled:
        actual_chars = len(packed_context)

    # Calculate baseline (what it would have been without optimization)
    baseline_chars = calculate_baseline_chars(selected_memories, remote_candidates_considered)

    # Derived savings metrics
    saved_chars = max(0, baseline_chars - actual_chars)
    baseline_tokens = estimate_tokens(baseline_chars)
    actual_tokens = estimate_tokens(actual_chars)
    saved_tokens = max(0, baseline_tokens - actual_tokens)
    savings_ratio = saved_tokens / baseline_tokens if baseline_tokens > 0 else 0.0

    # Local-first strategy defaults
    remote_candidates_skipped = remote_candidates_considered - 0  # 0 used
    skipped_remote_reason = "local-first coverage satisfied" if local_cards_used >= len(selected_memories) else None
    coverage_satisfied = True

    return TokenSavingsMeter(
        request_id=request_id,
        tenant=tenant,
        user=user,
        agent=agent,
        client=client,
        timestamp=timestamp,
        query_shape=query_shape,
        query_chars=query_chars,
        query=query,
        baseline_chars=baseline_chars,
        actual_chars=actual_chars,
        saved_chars=saved_chars,
        baseline_tokens_estimate=baseline_tokens,
        actual_tokens_estimate=actual_tokens,
        saved_tokens_estimate=saved_tokens,
        savings_ratio=round(savings_ratio, 3),
        packed_memory_count=len(selected_memories),
        local_cards_used=min(local_cards_used, len(selected_memories)),
        remote_candidates_considered=remote_candidates_considered,
        remote_candidates_skipped=remote_candidates_skipped,
        remote_used_count=0,
        skipped_remote_reason=skipped_remote_reason,
        coverage_satisfied=coverage_satisfied,
        packing_enabled=packing_enabled,
        abstract_preferred=False,
        dedup_applied=True,
        # Policy v1 fields
        task_type=task_type,
        context_bypass=context_bypass,
        bypassed_context_tokens=bypassed_context_tokens,
        matched_keywords=matched_keywords or [],
        # Context diff
        candidate_memories=candidate_memories or [],
        dropped_memories=dropped_memories or [],
    )


def check_quota_enforcement(
    current_usage: int,
    monthly_quota: Optional[int],
) -> QuotaEnforcementResult:
    """
    判断当前用量是否超出配额。

    纯函数：只做计算，不碰任何存储或网络。
    caller 负责提供 current_usage（从 meter_store 汇聚得到）
    和 monthly_quota（从 registry 配置读取）。
    """
    if monthly_quota is None:
        quota_status = "untracked"
        quota_exceeded = False
    else:
        quota_exceeded = current_usage > monthly_quota
        quota_status = "over_quota" if quota_exceeded else "within_quota"

    return QuotaEnforcementResult(
        quota_exceeded=quota_exceeded,
        current_usage=current_usage,
        monthly_quota=monthly_quota,
        quota_status=quota_status,
    )
