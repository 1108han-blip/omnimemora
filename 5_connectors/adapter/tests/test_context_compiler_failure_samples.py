import importlib
import json


failure_samples = importlib.import_module("5_connectors.adapter.application.context_compiler.failure_samples")


def test_failure_sampling_is_disabled_by_default(tmp_path, monkeypatch):
    path = tmp_path / "samples.jsonl"
    monkeypatch.setattr(failure_samples, "FAILURE_SAMPLES_PATH", str(path))
    monkeypatch.delenv("OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLES", raising=False)

    recorded = failure_samples.record_failure_sample(
        status="structured_compile_passthrough",
        reason="invalid_tool_graph",
        issues=["unknown_tool_result_id"],
        protocol="anthropic",
        agent_family="openclaw",
        original_token_estimate=100,
        compiled_token_estimate=100,
    )

    assert recorded is False
    assert not path.exists()


def test_failure_sample_keeps_only_anonymous_minimal_fields(tmp_path, monkeypatch):
    path = tmp_path / "samples.jsonl"
    monkeypatch.setattr(failure_samples, "FAILURE_SAMPLES_PATH", str(path))
    monkeypatch.setenv("OMNIMEMORA_STRUCTURED_COMPILE_FAILURE_SAMPLES", "1")

    recorded = failure_samples.record_failure_sample(
        status="structured_compile_passthrough",
        reason="invalid_tool_graph",
        issues=["unknown_tool_result_id"],
        protocol="anthropic",
        agent_family="claude_code",
        original_token_estimate=120,
        compiled_token_estimate=120,
        token_estimator_name="mixed_script_heuristic_v1",
        token_estimator_confidence="medium",
    )

    assert recorded is True
    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["schema_version"] == "structured_compile_failure_sample_v1"
    assert payload["compile_status"] == "structured_compile_passthrough"
    assert payload["compile_reason"] == "invalid_tool_graph"
    assert payload["issue_codes"] == ["unknown_tool_result_id"]
    assert payload["agent_family"] == "claude_code"
    assert "prompt" not in payload
    assert "messages" not in payload
    assert "tool_result" not in payload
    assert "memory" not in payload
