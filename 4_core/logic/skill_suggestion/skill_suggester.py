from __future__ import annotations

from .policy import LocalFallbackRecommendationPolicy
from .policy_models import RecommendationPolicyInput
from .models import SkillSuggestion


def suggest_skills(
    query: str,
    task_type: str | None,
    agent: str,
    client: str,
    limit: int = 3,
) -> list[SkillSuggestion]:
    result = LocalFallbackRecommendationPolicy.evaluate(
        RecommendationPolicyInput(
            query=query,
            task_type=task_type,
            agent=agent,
            client=client,
            limit=limit,
        )
    )
    return result.skill_suggestions
