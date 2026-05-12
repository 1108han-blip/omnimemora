import importlib


metrics = importlib.import_module("5_connectors.adapter.application.context_compiler.metrics")


def test_mixed_script_estimator_counts_cjk_more_closely_than_char_divisor():
    estimate = metrics.estimate_text_tokens_detailed("中文上下文 mixed text")

    assert estimate.tokens > 0
    assert estimate.estimator_name == "mixed_script_heuristic_v1"
    assert estimate.estimator_confidence == "medium"


def test_payload_estimate_reports_estimator_metadata():
    payload = {"model": "MiniMax-M2.7", "messages": [{"role": "user", "content": "hello"}]}

    estimate = metrics.estimate_payload_tokens_detailed(payload)

    assert estimate.tokens >= 1
    assert estimate.estimator_name
    assert estimate.estimator_confidence in {"medium", "high"}
