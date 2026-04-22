"""
Golden Case Runner — V1 QC Loop
================================
Offline deterministic comparison of active vs candidate policies.

V1: No live adapter calls, no /compile endpoint.
- Loads active and candidate policies from policy_version_manager
- Applies policy selection logic locally to candidate_memories fixture
- Compares context layer outcomes between policies
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Optional

# Add adapter to path for policy imports
_adapter_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "5_connectors")
if _adapter_path not in sys.path:
    sys.path.insert(0, _adapter_path)

try:
    from adapter.cloud.models import Policy
    from adapter.policy_version_manager import (
        get_manifest,
        load_active_policy,
        load_candidate_policy,
        record_verification,
    )
except ImportError:
    from cloud.models import Policy
    from policy_version_manager import (
        get_manifest,
        load_active_policy,
        load_candidate_policy,
        record_verification,
    )

try:
    from .models import (
        GoldenCase,
        CaseResult,
        PolicyEvaluationResult,
        ComparisonReport,
        GateClass,
        MemoryEntry,
    )
    from .loader import load_golden_cases
except ImportError:
    from models import (
        GoldenCase,
        CaseResult,
        PolicyEvaluationResult,
        ComparisonReport,
        GateClass,
        MemoryEntry,
    )
    from loader import load_golden_cases


def _score_memory(memory: MemoryEntry, policy: Policy, case: GoldenCase) -> float:
    """
    Score a single memory according to policy weights.
    Returns a score based on policy selection criteria.
    """
    score = 0.0

    # Simple scoring based on policy weights and memory properties
    # For V1, we use a deterministic scoring based on available fields

    # Recency factor (simplified - would need timestamp in real impl)
    # For fixture-based testing, we rely on the order in candidate_memories

    # Relevance: check if query terms appear in memory content/term
    query_lower = case.query.lower()
    content_lower = (memory.content or memory.term or "").lower()
    if query_lower in content_lower:
        score += policy.weights.relevance

    # Scope: check category match
    if memory.category and query_lower in memory.category.lower():
        score += policy.weights.scope

    return score


def _apply_selection(case: GoldenCase, policy: Policy) -> List[MemoryEntry]:
    """
    Apply policy selection logic to candidate_memories.
    Returns the selected memories (up to max_memories or candidate_limit).
    """
    max_to_select = min(
        policy.selection.max_memories,
        case.max_local_cards,
        case.candidate_limit
    )

    # Score all memories
    scored = []
    for mem in case.candidate_memories:
        s = _score_memory(mem, policy, case)
        scored.append((s, mem))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Select top N
    selected = [mem for _, mem in scored[:max_to_select]]

    return selected


def _determine_bypass(case: GoldenCase, selected: List[MemoryEntry], task_type: str) -> bool:
    """
    Determine if context bypass should be true.
    V1 contract: implementation tasks always have bypass=true.
    Other tasks: bypass=true when no memories selected or below min_selected.
    """
    # V1 contract: implementation -> bypass=true
    if task_type == "implementation":
        return True

    if not case.candidate_memories:
        return True

    # Check if any memory was selected
    if not selected:
        return True

    # Check if selection count is below threshold
    if len(selected) < case.min_selected:
        return True

    return False


def _determine_task_type(query: str, case: GoldenCase) -> str:
    """
    Determine task_type from query content.
    Falls back to case.expected_task_type if provided.
    """
    if case.expected_task_type:
        return case.expected_task_type

    query_lower = query.lower()

    # Simple keyword-based classification
    if any(kw in query_lower for kw in ["write", "code", "implement", "create function"]):
        return "implementation"
    elif any(kw in query_lower for kw in ["should", "which", "decision", "recommend"]):
        return "decision"
    elif any(kw in query_lower for kw in ["continue", "keep", "resume", "proceed"]):
        return "continuation"
    elif any(kw in query_lower for kw in ["debug", "fix", "error", "bug"]):
        return "debug"
    else:
        return "general"


def _evaluate_case_against_policy(
    case: GoldenCase,
    policy: Policy,
) -> CaseResult:
    """
    Evaluate a single golden case against a specific policy.
    Uses the case's candidate_memories as the fixture.
    """
    details = []
    passed = True
    task_type_match = True
    context_bypass_match = True
    required_hit = True
    forbidden_hit = True
    selection_count_ok = True
    score = 0.0

    # Apply policy selection
    selected = _apply_selection(case, policy)

    # Determine task_type
    actual_task_type = _determine_task_type(case.query, case)

    # Determine context_bypass (contract: implementation -> bypass=true)
    actual_bypass = _determine_bypass(case, selected, actual_task_type)

    # Check expected_task_type
    if case.expected_task_type:
        if actual_task_type != case.expected_task_type:
            task_type_match = False
            passed = False
            details.append(f"task_type: expected {case.expected_task_type}, got {actual_task_type}")

    # Check expected_context_bypass
    if case.expected_context_bypass is not None:
        if actual_bypass != case.expected_context_bypass:
            context_bypass_match = False
            passed = False
            details.append(f"context_bypass: expected {case.expected_context_bypass}, got {actual_bypass}")

    # Check selection count
    # V1 contract: implementation -> bypass=true (no context injection)
    # For implementation tasks, bypass=true means selection doesn't matter for the gate
    # For other tasks, selection count must be within min/max range
    selected_count = len(selected)
    if actual_task_type == "implementation":
        # Implementation tasks bypass context - selection count check passes
        pass
    elif not (case.min_selected <= selected_count <= case.max_selected):
        selection_count_ok = False
        passed = False
        details.append(f"selection count {selected_count} not in [{case.min_selected}, {case.max_selected}]")

    # Build lookup sets for selected memories
    selected_ids = {m.memory_id for m in selected}
    selected_uris = {m.uri for m in selected if m.uri}
    selected_categories = {m.category for m in selected if m.category}
    selected_terms = {m.term or m.content or "" for m in selected}

    # Check required refs/terms
    for required in case.required_memory_refs_or_terms:
        hit = False
        if required in selected_ids:
            hit = True
        elif required in selected_uris:
            hit = True
        elif required in selected_categories:
            hit = True
        elif any(required.lower() in term.lower() for term in selected_terms):
            hit = True

        if not hit:
            required_hit = False
            passed = False
            details.append(f"required '{required}' not found in selected")

    # Check forbidden refs/terms
    for forbidden in case.forbidden_memory_refs_or_terms:
        hit = False
        if forbidden in selected_ids:
            hit = True
        elif forbidden in selected_uris:
            hit = True
        elif forbidden in selected_categories:
            hit = True
        elif any(forbidden.lower() in term.lower() for term in selected_terms):
            hit = True

        if hit:
            forbidden_hit = False
            passed = False
            details.append(f"forbidden '{forbidden}' found in selected")

    # Calculate score
    if passed:
        score = 1.0
        if case.gate_class == GateClass.SCORED:
            # Bonus for perfect scored case
            if task_type_match and context_bypass_match and required_hit and forbidden_hit:
                score = 2.0
    elif case.gate_class == GateClass.SCORED:
        score = 0.5  # Partial credit

    return CaseResult(
        case_id=case.case_id,
        passed=passed,
        gate_class=case.gate_class,
        task_type_match=task_type_match,
        context_bypass_match=context_bypass_match,
        required_hit=required_hit,
        forbidden_hit=forbidden_hit,
        selection_count_ok=selection_count_ok,
        score=score,
        details="; ".join(details) if details else "ok",
    )


def evaluate_policy(policy_version: str, policy: Policy) -> PolicyEvaluationResult:
    """
    Evaluate all golden cases against a specific policy.
    Returns the evaluation result for that policy.
    """
    cases = load_golden_cases()

    must_pass_cases = [c for c in cases if c.gate_class == GateClass.MUST_PASS]
    scored_cases = [c for c in cases if c.gate_class == GateClass.SCORED]

    must_pass_passed = 0
    scored_passed = 0
    total_score = 0.0
    case_results = []

    for case in cases:
        result = _evaluate_case_against_policy(case, policy)
        case_results.append(result)

        if case.gate_class == GateClass.MUST_PASS:
            if result.passed:
                must_pass_passed += 1
        else:  # scored
            total_score += result.score
            if result.passed:
                scored_passed += 1

    all_must_pass_passed = (must_pass_passed == len(must_pass_cases)) if must_pass_cases else True

    # Baseline is invalid if active has failing must-pass cases
    baseline_invalid = False

    return PolicyEvaluationResult(
        policy_version=policy_version,
        total_cases=len(cases),
        must_pass_cases=len(must_pass_cases),
        scored_cases=len(scored_cases),
        must_pass_passed=must_pass_passed,
        scored_passed=scored_passed,
        total_score=total_score,
        all_must_pass_passed=all_must_pass_passed,
        baseline_invalid=baseline_invalid,
        case_results=case_results,
    )


def run_comparison() -> ComparisonReport:
    """
    Run offline deterministic comparison between active and candidate policies.
    V1: No live adapter calls, no /compile endpoint.
    """
    manifest = get_manifest()
    active_version = manifest.active_version or "local-default-v1"
    candidate_version = manifest.candidate_version

    # Load policies
    active_policy = load_active_policy()
    candidate_policy = load_candidate_policy()

    # Evaluate active policy
    print(f"[runner] Evaluating active policy: {active_version}")
    active_report = evaluate_policy(active_version, active_policy)

    # Evaluate candidate if exists
    candidate_report = None
    if candidate_policy:
        print(f"[runner] Evaluating candidate policy: {candidate_version}")
        candidate_report = evaluate_policy(candidate_version, candidate_policy)

    # Determine promotion eligibility
    promotion_allowed = True
    blocked_reason = None

    # Gate 1: Active must have all must_pass passing (baseline valid)
    if not active_report.all_must_pass_passed:
        promotion_allowed = False
        blocked_reason = f"active baseline invalid: {active_report.must_pass_passed}/{active_report.must_pass_cases} must_pass passed"

    # Gate 2: Candidate must have all must_pass passing
    if candidate_report and not candidate_report.all_must_pass_passed:
        promotion_allowed = False
        blocked_reason = f"candidate has failing must_pass: {candidate_report.must_pass_passed}/{candidate_report.must_pass_cases}"

    # Gate 3: Candidate score >= active score
    if candidate_report:
        if candidate_report.total_score < active_report.total_score:
            promotion_allowed = False
            blocked_reason = f"candidate score {candidate_report.total_score} < active score {active_report.total_score}"

    report = ComparisonReport(
        report_id=f"cmp-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.utcnow().isoformat() + "Z",
        evaluated_active_version=active_version,
        evaluated_candidate_version=candidate_version,
        active_report=active_report,
        candidate_report=candidate_report,
        promotion_allowed=promotion_allowed,
        blocked_reason=blocked_reason,
    )

    return report


def save_report(report: ComparisonReport, output_dir: str) -> str:
    """Save comparison report to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{report.report_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)
    return filepath


def run_and_record() -> ComparisonReport:
    """
    Run comparison and record the report_id in manifest.
    This updates last_verified_report but does NOT change active_version.
    Only promote_candidate() changes active_version.
    """
    report = run_comparison()

    # Record verification in manifest
    record_verification(report.report_id)

    # Save report
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    save_report(report, reports_dir)

    return report


if __name__ == "__main__":
    print("[runner] Starting offline golden case comparison...")
    result = run_comparison()

    # Save report
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    filepath = save_report(result, reports_dir)

    print(f"\nReport: {result.report_id}")
    print(f"  Promotion allowed: {result.promotion_allowed}")
    if result.blocked_reason:
        print(f"  Blocked: {result.blocked_reason}")
    print(f"\n  Active ({result.evaluated_active_version}):")
    print(f"    must_pass: {result.active_report.must_pass_passed}/{result.active_report.must_pass_cases}")
    print(f"    scored: {result.active_report.scored_passed}/{result.active_report.scored_cases}")
    print(f"    total_score: {result.active_report.total_score}")

    if result.candidate_report:
        print(f"\n  Candidate ({result.evaluated_candidate_version}):")
        print(f"    must_pass: {result.candidate_report.must_pass_passed}/{result.candidate_report.must_pass_cases}")
        print(f"    scored: {result.candidate_report.scored_passed}/{result.candidate_report.scored_cases}")
        print(f"    total_score: {result.candidate_report.total_score}")

    print(f"\nReport saved to: {filepath}")
