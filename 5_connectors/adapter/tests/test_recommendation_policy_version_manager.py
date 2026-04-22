import asyncio
import importlib
import json
import tempfile
from pathlib import Path
from unittest import mock


manager = importlib.import_module("5_connectors.adapter.recommendation_policy_version_manager")
loader = importlib.import_module("5_connectors.adapter.infrastructure.recommendation_policy_loader")
runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot(version: str, enabled: bool = True) -> dict:
    return {
        "policy_name": "recommendation_local_active",
        "policy_version": version,
        "policy_source": "local_manifest",
        "enabled": enabled,
        "max_suggestions": 3,
        "matching_rules": {"matcher": "keyword_hits_v1"},
        "catalog": [
            {
                "skill_id": "checks",
                "title": "Checks And Validation",
                "intents": ["decision", "continuation"],
                "keywords": ["validation", "check"],
                "source": "local_manifest",
                "priority": 1,
            }
        ],
    }


def test_load_active_and_candidate_recommendation_policy():
    with tempfile.TemporaryDirectory(prefix="omnimemora-rec-policy-") as tmpdir:
        policies_dir = Path(tmpdir)
        manifest_path = policies_dir / "manifest.json"
        _write_json(
            manifest_path,
            {
                "active_version": "rec-v1",
                "candidate_version": "rec-v2",
                "last_verified_report": None,
                "last_promoted_at": None,
            },
        )
        _write_json(policies_dir / "rec-v1.json", _snapshot("rec-v1"))
        _write_json(policies_dir / "rec-v2.json", _snapshot("rec-v2"))

        manager._inject_path(
            {
                "policies_dir": str(policies_dir),
                "manifest_path": str(manifest_path),
            }
        )
        try:
            active = loader.load_recommendation_policy()
            active2, candidate = loader.load_recommendation_policy_with_candidate()
        finally:
            manager._clear_injection()

    assert active is not None
    assert active["policy_version"] == "rec-v1"
    assert active2 is not None
    assert active2["policy_version"] == "rec-v1"
    assert candidate is not None
    assert candidate["policy_version"] == "rec-v2"


def test_missing_manifest_returns_none_and_engine_fallback_still_works():
    with tempfile.TemporaryDirectory(prefix="omnimemora-rec-policy-missing-") as tmpdir:
        policies_dir = Path(tmpdir)
        manifest_path = policies_dir / "manifest.json"
        manager._inject_path(
            {
                "policies_dir": str(policies_dir),
                "manifest_path": str(manifest_path),
            }
        )
        try:
            active = loader.load_recommendation_policy()
        finally:
            manager._clear_injection()

    assert active is None


def test_invalid_snapshot_falls_back_without_breaking_compile_chain():
    invalid_snapshot = {"policy_name": "broken-only"}
    with mock.patch(
        "5_connectors.adapter.infrastructure.recommendation_policy_loader.load_recommendation_policy",
        return_value=invalid_snapshot,
    ):
        result = asyncio.run(
            runtime_bridge.execute_runtime_compile(
                query="need decision validation check",
                candidate_memories=[{"content": "memory validation context", "category": "memory", "score": 0.9}],
                agent_id="codex_cli",
                original_token_estimate=120,
            )
        )

    assert "skill_suggestions" in result
    assert result["skill_policy_name"] == "local_fallback"
    assert result["skill_policy_version"] == "static_catalog_v1"
    assert result["skill_policy_source"] == "local_builtin"
    assert result["skill_policy_status"] == "invalid_snapshot"
