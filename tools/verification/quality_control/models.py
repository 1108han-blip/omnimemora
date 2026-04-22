"""
Golden Case Models — V1 QC Loop
================================
Offline deterministic comparison of active vs candidate policies.
"""
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class GateClass(str, Enum):
    MUST_PASS = "must_pass"
    SCORED = "scored"


class MemoryEntry(BaseModel):
    """A memory entry in the golden case fixture."""
    memory_id: str
    uri: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    term: Optional[str] = None  # alias for content snippet
    score: Optional[float] = None


class GoldenCase(BaseModel):
    """
    A single golden test case for context layer validation.

    V1: Self-contained fixture with candidate_memories that the runner
    uses for offline deterministic comparison.
    """
    case_id: str
    gate_class: GateClass
    query: str
    candidate_memories: List[MemoryEntry] = []
    agent: str = "test-agent"
    client: str = "test-client"
    max_local_cards: int = 999
    candidate_limit: int = 999
    expected_task_type: Optional[str] = None
    expected_context_bypass: Optional[bool] = None
    required_memory_refs_or_terms: List[str] = []  # memory_id, uri, category, or content term
    forbidden_memory_refs_or_terms: List[str] = []
    min_selected: int = 0
    max_selected: int = 999


class CaseResult(BaseModel):
    """Result of running a single golden case against a policy."""

    case_id: str
    passed: bool
    gate_class: GateClass
    task_type_match: bool = True
    context_bypass_match: bool = True
    required_hit: bool = True
    forbidden_hit: bool = True
    selection_count_ok: bool = True
    score: float = 0.0
    details: str = ""


class PolicyEvaluationResult(BaseModel):
    """Result of running all golden cases against a single policy."""

    policy_version: str
    total_cases: int
    must_pass_cases: int
    scored_cases: int
    must_pass_passed: int
    scored_passed: int
    total_score: float
    all_must_pass_passed: bool
    baseline_invalid: bool = False  # True if active has must-pass failures
    case_results: List[CaseResult]


class ComparisonReport(BaseModel):
    """
    Comparison report between active and candidate policies.
    V1: Offline deterministic comparison.
    """

    report_id: str
    timestamp: str
    evaluated_active_version: str
    evaluated_candidate_version: Optional[str]
    active_report: PolicyEvaluationResult
    candidate_report: Optional[PolicyEvaluationResult]
    promotion_allowed: bool
    blocked_reason: Optional[str] = None
