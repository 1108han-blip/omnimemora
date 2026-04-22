from __future__ import annotations

from typing import Any

from .intent_classifier import classify_intent
from .policy_models import (
    RecommendationPolicyInput,
    RecommendationPolicyResult,
    RecommendationPolicySnapshot,
)
from .skill_catalog import SKILL_CATALOG
from .skill_matcher import match_skills


def _normalize_limit(value: int) -> int:
    if value <= 0:
        return 0
    return value


def parse_snapshot(raw_snapshot: Any) -> RecommendationPolicySnapshot | None:
    if not isinstance(raw_snapshot, dict):
        return None
    required = ("policy_name", "policy_version", "policy_source", "enabled", "catalog", "matching_rules", "max_suggestions")
    if any(key not in raw_snapshot for key in required):
        return None
    if not isinstance(raw_snapshot.get("catalog"), list):
        return None
    if not isinstance(raw_snapshot.get("matching_rules"), dict):
        return None
    if not isinstance(raw_snapshot.get("enabled"), bool):
        return None
    try:
        max_suggestions = int(raw_snapshot.get("max_suggestions", 3))
    except (TypeError, ValueError):
        return None
    return RecommendationPolicySnapshot(
        policy_name=str(raw_snapshot.get("policy_name", "")),
        policy_version=str(raw_snapshot.get("policy_version", "")),
        policy_source=str(raw_snapshot.get("policy_source", "")),
        enabled=bool(raw_snapshot.get("enabled", True)),
        catalog=list(raw_snapshot.get("catalog", [])),
        matching_rules=dict(raw_snapshot.get("matching_rules", {})),
        max_suggestions=max_suggestions,
    )


class LocalFallbackRecommendationPolicy:
    """
    Deterministic local fallback policy.
    """

    policy_name = "local_fallback"
    policy_version = "static_catalog_v1"
    policy_source = "local_builtin"
    policy_status = "fallback"

    @classmethod
    def evaluate(cls, policy_input: RecommendationPolicyInput) -> RecommendationPolicyResult:
        intent = classify_intent(query=policy_input.query, task_type=policy_input.task_type)
        suggestions = match_skills(
            query=policy_input.query,
            intent=intent,
            catalog=SKILL_CATALOG,
            limit=_normalize_limit(policy_input.limit),
        )
        return RecommendationPolicyResult(
            skill_suggestions=suggestions,
            policy_name=cls.policy_name,
            policy_version=cls.policy_version,
            policy_source=cls.policy_source,
            policy_status=cls.policy_status,
        )


def evaluate_local_fallback_policy(policy_input: RecommendationPolicyInput) -> RecommendationPolicyResult:
    return LocalFallbackRecommendationPolicy.evaluate(policy_input)


def evaluate_recommendation_policy(
    policy_input: RecommendationPolicyInput,
    snapshot_dict: dict | None,
) -> RecommendationPolicyResult:
    if snapshot_dict is None:
        return evaluate_local_fallback_policy(policy_input)

    snapshot = parse_snapshot(snapshot_dict)
    if snapshot is None:
        fallback = evaluate_local_fallback_policy(policy_input)
        return RecommendationPolicyResult(
            skill_suggestions=fallback.skill_suggestions,
            policy_name=fallback.policy_name,
            policy_version=fallback.policy_version,
            policy_source=fallback.policy_source,
            policy_status="invalid_snapshot",
        )

    if not snapshot.enabled:
        return RecommendationPolicyResult(
            skill_suggestions=[],
            policy_name=snapshot.policy_name,
            policy_version=snapshot.policy_version,
            policy_source=snapshot.policy_source,
            policy_status="disabled",
        )

    intent = classify_intent(query=policy_input.query, task_type=policy_input.task_type)
    final_limit = min(_normalize_limit(policy_input.limit), _normalize_limit(snapshot.max_suggestions))
    suggestions = match_skills(
        query=policy_input.query,
        intent=intent,
        catalog=snapshot.catalog,
        limit=final_limit,
    )
    return RecommendationPolicyResult(
        skill_suggestions=suggestions,
        policy_name=snapshot.policy_name,
        policy_version=snapshot.policy_version,
        policy_source=snapshot.policy_source,
        policy_status="active",
    )
