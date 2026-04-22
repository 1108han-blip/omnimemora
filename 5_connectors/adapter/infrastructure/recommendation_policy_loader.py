"""Recommendation policy loader (local-first, cloud-candidate optional)."""
from __future__ import annotations

from typing import Optional, Tuple

from ..recommendation_policy_version_manager import (
    load_active_recommendation_policy,
    load_candidate_recommendation_policy,
)


def load_recommendation_policy() -> Optional[dict]:
    return load_active_recommendation_policy()


def load_cloud_candidate_recommendation_policy() -> Optional[dict]:
    """
    Optional cloud candidate source.
    Never changes local active policy, only provides candidate fallback.
    """
    try:
        from ..cloud.candidate_sources import load_cloud_candidate_policy
    except Exception:
        return None
    try:
        return load_cloud_candidate_policy()
    except Exception:
        return None


def load_recommendation_policy_with_candidate() -> Tuple[Optional[dict], Optional[dict]]:
    active = load_active_recommendation_policy()
    candidate = load_candidate_recommendation_policy()
    if candidate is None:
        candidate = load_cloud_candidate_recommendation_policy()
    return active, candidate
