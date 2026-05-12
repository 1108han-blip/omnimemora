import importlib
import time


compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")


def test_summarize_compile_status_reports_structured_distribution(tmp_path, monkeypatch):
    events_path = tmp_path / "compile_events.jsonl"
    monkeypatch.setattr(compile_store, "COMPILE_EVENTS_PATH", str(events_path))
    monkeypatch.setattr(compile_store, "MAX_RECENT_READ_LINES", 100)

    now = time.time()
    rows = [
        {
            "request_id": "req-1",
            "agent_id": "openclaw",
            "timestamp": now,
            "compile_status": "structured_compile_success",
            "original_token_estimate": 100,
            "compiled_token_estimate": 40,
            "compression_ratio": 0.6,
        },
        {
            "request_id": "req-2",
            "agent_id": "openclaw",
            "timestamp": now + 1,
            "compile_status": "structured_compile_passthrough",
            "original_token_estimate": 80,
            "compiled_token_estimate": 80,
            "compression_ratio": 0.0,
        },
        {
            "request_id": "req-3",
            "agent_id": "openclaw",
            "timestamp": now + 2,
            "compile_status": "compile_skipped",
            "original_token_estimate": 20,
            "compiled_token_estimate": 0,
            "compression_ratio": 0.0,
        },
    ]
    for row in rows:
        compile_store.append_compile_event(row)

    summary = compile_store.summarize_compile_status(window_minutes=30)

    assert summary["openclaw"]["proxied_requests"] == 3
    assert summary["openclaw"]["structured_compile_success"] == 1
    assert summary["openclaw"]["structured_compile_passthrough"] == 1
    assert summary["openclaw"]["compile_skipped"] == 1
    assert summary["openclaw"]["status_counts"] == {
        "compile_skipped": 1,
        "structured_compile_passthrough": 1,
        "structured_compile_success": 1,
    }
    assert summary["openclaw"]["status_shares"]["structured_compile_success"] == 0.3333
    assert summary["openclaw"]["structured_compile"]["success_share"] == 0.3333
    assert summary["openclaw"]["compile_token_savings"] == {
        "original_token_estimate": 200,
        "compiled_token_estimate": 140,
        "saved_token_estimate": 60,
        "savings_ratio": 0.3,
    }
