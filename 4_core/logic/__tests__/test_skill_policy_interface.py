import importlib
from typing import Optional


def _engine_mod():
    return importlib.import_module("4_core.logic.engine")


def _rules_mod():
    return importlib.import_module("4_core.logic.rules")


def _optimize(
    query: str,
    task_type: Optional[str],
    recommendation_policy_snapshot: Optional[dict] = None,
):
    engine = _engine_mod()
    rules = _rules_mod()
    input_data = engine.OptimizationInput(
        query=query,
        candidate_memories=[
            {"content": "memory A: architecture tradeoff and risk context", "category": "memory", "score": 0.8},
            {"content": "memory B: validation and test result summary", "category": "memory", "score": 0.7},
        ],
        filter_rules=rules.FilterRules(),
        routing_rules=rules.RoutingRules(),
        task_type=task_type,
        agent="codex_cli",
        client="gateway",
        packing_enabled=True,
        max_local_cards=2,
        candidate_limit=8,
        recommendation_policy_snapshot=recommendation_policy_snapshot,
    )
    return engine.optimize_context(input_data)


def test_fallback_policy_default_path_returns_metadata():
    result = _optimize("need architecture decision and risk tradeoff validation", "decision", None)
    assert result.skill_policy_name == "local_fallback"
    assert result.skill_policy_version == "static_catalog_v1"
    assert result.skill_policy_source == "local_builtin"
    assert result.skill_policy_status == "fallback"
    assert len(result.skill_suggestions) > 0


def test_active_snapshot_injection_returns_active_status():
    snapshot = {
        "policy_name": "recommendation_local_active",
        "policy_version": "rec-v1",
        "policy_source": "local_manifest",
        "enabled": True,
        "catalog": [
            {
                "skill_id": "checks",
                "title": "Checks And Validation",
                "intents": ["decision", "continuation"],
                "keywords": ["validation", "check", "regression"],
                "source": "local_manifest",
                "priority": 1,
            }
        ],
        "matching_rules": {"matcher": "keyword_hits_v1"},
        "max_suggestions": 3,
    }
    result = _optimize("need validation check before merge", "decision", snapshot)
    assert result.skill_policy_name == "recommendation_local_active"
    assert result.skill_policy_version == "rec-v1"
    assert result.skill_policy_source == "local_manifest"
    assert result.skill_policy_status == "active"
    assert len(result.skill_suggestions) > 0


def test_invalid_snapshot_falls_back_and_marks_invalid():
    invalid_snapshot = {
        "policy_name": "broken",
        "policy_version": "broken-v1",
        # missing required fields
    }
    result = _optimize("need validation check before merge", "decision", invalid_snapshot)
    assert result.skill_policy_name == "local_fallback"
    assert result.skill_policy_version == "static_catalog_v1"
    assert result.skill_policy_source == "local_builtin"
    assert result.skill_policy_status == "invalid_snapshot"
    assert len(result.skill_suggestions) > 0


def test_implementation_returns_empty_suggestions():
    result = _optimize("implement endpoint and write code", "implementation", None)
    assert result.skill_suggestions == []
    assert result.skill_policy_status in {"disabled", "invalid_snapshot"}


def test_empty_query_returns_empty_suggestions_with_stable_metadata():
    result = _optimize("", "decision", None)
    assert result.skill_suggestions == []
    assert result.skill_policy_name == "local_fallback"
    assert result.skill_policy_version == "static_catalog_v1"
    assert result.skill_policy_source == "local_builtin"
