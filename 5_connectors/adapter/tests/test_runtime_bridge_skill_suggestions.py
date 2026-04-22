import asyncio
import importlib
from unittest import mock


runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")


class _FakeSuggestion:
    def __init__(self, skill_id: str):
        self.skill_id = skill_id

    def to_dict(self):
        return {
            "skill_id": self.skill_id,
            "title": "Checks",
            "reason": "Matched keywords",
            "confidence": 0.72,
            "source": "static_catalog_v1",
        }


class _FakeEngineResult:
    def __init__(self):
        self.selected_memories = [{"content": "hello", "category": "memory", "score": 0.9}]
        self.packed_context = "<relevant-memories>hello</relevant-memories>"
        self.candidate_count = 1
        self.selected_count = 1
        self.skill_suggestions = [_FakeSuggestion("checks")]
        self.skill_policy_name = "recommendation_local_active"
        self.skill_policy_version = "local-default-v1"
        self.skill_policy_source = "local_manifest"
        self.skill_policy_status = "active"


class _FakeOptimizationInput:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeEngineModule:
    OptimizationInput = _FakeOptimizationInput

    @staticmethod
    def FilterRules():
        return object()

    @staticmethod
    def RoutingRules():
        return object()

    @staticmethod
    def optimize_context(_input_data):
        return _FakeEngineResult()


def test_execute_runtime_compile_returns_skill_suggestions_sidecar():
    real_import = importlib.import_module

    def _fake_import(name, *args, **kwargs):
        if name == "4_core.logic.engine":
            return _FakeEngineModule
        return real_import(name, *args, **kwargs)

    with mock.patch("importlib.import_module", side_effect=_fake_import):
        result = asyncio.run(
            runtime_bridge.execute_runtime_compile(
                query="decision validation",
                candidate_memories=[{"content": "hello"}],
                agent_id="codex_cli",
                original_token_estimate=120,
            )
        )

    assert "skill_suggestions" in result
    assert result["skill_suggestions"]
    assert result["skill_suggestions"][0]["skill_id"] == "checks"
    assert result["skill_policy_name"] == "recommendation_local_active"
    assert result["skill_policy_version"] == "local-default-v1"
    assert result["skill_policy_source"] == "local_manifest"
    assert result["skill_policy_status"] == "active"
