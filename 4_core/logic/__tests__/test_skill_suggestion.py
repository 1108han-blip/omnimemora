import importlib
from typing import Optional


def _engine_mod():
    return importlib.import_module("4_core.logic.engine")


def _rules_mod():
    return importlib.import_module("4_core.logic.rules")


def _optimize(query: str, task_type: Optional[str]):
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
    )
    return engine.optimize_context(input_data)


def test_decision_returns_skill_suggestions():
    result = _optimize("need architecture decision and risk tradeoff validation", "decision")
    assert len(result.skill_suggestions) > 0


def test_continuation_returns_skill_suggestions():
    result = _optimize("continue next batch and handoff summary with checks", "continuation")
    assert len(result.skill_suggestions) > 0


def test_implementation_returns_empty_skill_suggestions():
    result = _optimize("implement endpoint and write code", "implementation")
    assert result.skill_suggestions == []


def test_empty_query_returns_empty_skill_suggestions():
    result = _optimize("", "decision")
    assert result.skill_suggestions == []


def test_catalog_order_is_deterministic():
    r1 = _optimize("architecture decision with validation and risk check", "decision")
    r2 = _optimize("architecture decision with validation and risk check", "decision")
    ids1 = [s.skill_id for s in r1.skill_suggestions]
    ids2 = [s.skill_id for s in r2.skill_suggestions]
    assert ids1 == ids2


def test_confidence_is_bounded_and_deterministic():
    r1 = _optimize("risk validation check", "decision")
    r2 = _optimize("risk validation check", "decision")
    conf1 = [s.confidence for s in r1.skill_suggestions]
    conf2 = [s.confidence for s in r2.skill_suggestions]
    assert conf1 == conf2
    for c in conf1:
        assert 0.0 <= c <= 1.0
