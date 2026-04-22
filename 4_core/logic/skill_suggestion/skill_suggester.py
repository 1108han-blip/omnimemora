from __future__ import annotations

from .intent_classifier import classify_intent
from .models import SkillSuggestion
from .skill_catalog import SKILL_CATALOG
from .skill_matcher import match_skills


def suggest_skills(
    query: str,
    task_type: str | None,
    agent: str,
    client: str,
    limit: int = 3,
) -> list[SkillSuggestion]:
    # agent/client kept for future policy expansion; currently rule-based only.
    _ = agent, client
    intent = classify_intent(query=query, task_type=task_type)
    return match_skills(query=query, intent=intent, catalog=SKILL_CATALOG, limit=limit)
