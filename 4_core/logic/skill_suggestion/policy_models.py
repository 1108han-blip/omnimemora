from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .models import SkillSuggestion


@dataclass(frozen=True)
class RecommendationPolicyInput:
    query: str
    task_type: str | None
    agent: str
    client: str
    limit: int = 3


@dataclass(frozen=True)
class RecommendationPolicySnapshot:
    policy_name: str
    policy_version: str
    policy_source: str
    enabled: bool
    catalog: List[Dict[str, Any]] = field(default_factory=list)
    matching_rules: Dict[str, Any] = field(default_factory=dict)
    max_suggestions: int = 3


@dataclass(frozen=True)
class RecommendationPolicyResult:
    skill_suggestions: List[SkillSuggestion] = field(default_factory=list)
    policy_name: str = "local_fallback"
    policy_version: str = "static_catalog_v1"
    policy_source: str = "local_builtin"
    policy_status: str = "fallback"
