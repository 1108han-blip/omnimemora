"""
Tests for status_read_model.py truth derivation functions.
"""
import pytest
import os
import sys
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
import time

# Setup path like other test files in this directory
_adapter_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_connectors_dir = os.path.dirname(_adapter_dir)
for p in (_adapter_dir, _connectors_dir):
    if p not in sys.path:
        sys.path.insert(0, p)


class MockMeter:
    def __init__(
        self,
        agent,
        timestamp,
        baseline_tokens=100,
        saved_tokens=0,
        packed_memory_count=0,
        local_cards_used=0,
        remote_used_count=0,
    ):
        self.agent = agent
        self.timestamp = timestamp
        self.baseline_tokens_estimate = baseline_tokens
        self.saved_tokens_estimate = saved_tokens
        self.packed_memory_count = packed_memory_count
        self.local_cards_used = local_cards_used
        self.remote_used_count = remote_used_count


class MockCompileStore:
    def __init__(self, summary, events=None):
        self._summary = summary
        self._events = events or []

    def summarize_compile_status(self, window_minutes=30):
        return self._summary

    def read_recent_compile_events(self, limit=200, window_minutes=None):
        return self._events[:limit]


class MockMeterStore:
    class _PersistedMeter:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def __init__(self, meters, persisted_index=None):
        self._usage_aggregates = {"default": meters}
        self._persisted_index = persisted_index or {}
        self.TokenSavingsMeter = MockMeterStore._PersistedMeter

    def _ensure_persistence_loaded(self):
        pass

    def load_persisted_state(self):
        return self._persisted_index, {}


def _make_mock_request_classifier():
    """Create a mock request classifier that returns True for is_default_overview_request."""
    mock = MagicMock()
    mock.is_default_overview_request.return_value = True
    mock.is_value_qualified.return_value = False
    mock.collapse_retry_bursts.side_effect = lambda meters: list(meters)
    return mock


def _run_derive_traffic_truth_test(family_id, compile_summary, meters, compile_events=None, window_minutes=30):
    """Helper that directly patches module-level functions and runs derive_traffic_truth."""
    import adapter.application.status_read_model as srm

    mock_cs = MockCompileStore(compile_summary, compile_events)
    mock_ms = MockMeterStore(meters)
    mock_rc = _make_mock_request_classifier()

    # Direct patch - this works
    srm._get_compile_store = lambda: mock_cs
    srm._get_meter_store = lambda: mock_ms
    srm._get_request_classifier = lambda: mock_rc

    return srm.derive_traffic_truth(family_id, window_minutes=window_minutes)


def test_derive_traffic_truth_codex_cli_with_real_meter():
    """codex_cli with real_meter_count > 0 should return real_request_observed."""
    meter = MockMeter("codex_cli", datetime.now(timezone.utc).isoformat(), 100)
    result = _run_derive_traffic_truth_test("codex_cli", {"codex_cli": {"proxied_requests": 5}}, [meter])
    assert result == "real_request_observed"


def test_derive_traffic_truth_codex_cli_no_real_meter():
    """codex_cli with real_meter_count == 0 but compile evidence exists should return internal_only."""
    compile_events = [{"agent_id": "codex_cli", "compile_status": "compile_success", "compile_reason": "runtime_compile", "timestamp": time.time()}]
    result = _run_derive_traffic_truth_test("codex_cli", {"codex_cli": {"proxied_requests": 5}}, [], compile_events=compile_events)
    assert result == "internal_only"


def test_derive_traffic_truth_openclaw_legacy_behavior():
    """openclaw with both proxied and real meter -> real_request_observed."""
    meter = MockMeter("openclaw", datetime.now(timezone.utc).isoformat(), 100)
    result = _run_derive_traffic_truth_test("openclaw", {"openclaw": {"proxied_requests": 3}}, [meter])
    assert result == "real_request_observed"


def test_derive_traffic_truth_openclaw_only_proxied():
    """openclaw with proxied > 0 but no real meter should return internal_only."""
    compile_events = [{"agent_id": "openclaw", "compile_status": "compile_success", "compile_reason": "runtime_compile", "timestamp": time.time()}]
    result = _run_derive_traffic_truth_test("openclaw", {"openclaw": {"proxied_requests": 3}}, [], compile_events=compile_events)
    assert result == "internal_only"


def test_derive_traffic_truth_compile_empty_when_only_compile_empty_events():
    """compile_empty should be surfaced distinctly from no evidence/internal-only."""
    compile_events = [
        {
            "agent_id": "codex_cli",
            "compile_status": "compile_skipped",
            "compile_reason": "empty_query",
            "timestamp": time.time(),
        }
    ]
    result = _run_derive_traffic_truth_test(
        "codex_cli",
        {"codex_cli": {"proxied_requests": 1}},
        [],
        compile_events=compile_events,
    )
    assert result == "compile_empty"


def test_derive_traffic_truth_bypassed_when_route_disabled_event_present():
    """bypassed should be surfaced distinctly from compile_empty/internal-only."""
    compile_events = [
        {
            "agent_id": "claude_code",
            "compile_status": "compile_skipped",
            "compile_reason": "agent_route_disabled",
            "timestamp": time.time(),
        }
    ]
    result = _run_derive_traffic_truth_test(
        "claude_code",
        {"claude_code": {"proxied_requests": 1}},
        [],
        compile_events=compile_events,
    )
    assert result == "bypassed"


def test_derive_traffic_truth_real_meter_has_highest_priority():
    """real_request_observed must win even if compile events include bypass/empty signals."""
    now = time.time()
    compile_events = [
        {"agent_id": "claude_code", "compile_status": "compile_skipped", "compile_reason": "agent_route_disabled", "timestamp": now},
        {"agent_id": "claude_code", "compile_status": "compile_skipped", "compile_reason": "empty_query", "timestamp": now - 1},
    ]
    meter = MockMeter("claude_code", datetime.now(timezone.utc).isoformat(), 100)
    result = _run_derive_traffic_truth_test(
        "claude_code",
        {"claude_code": {"proxied_requests": 2}},
        [meter],
        compile_events=compile_events,
    )
    assert result == "real_request_observed"


def test_derive_traffic_truth_bypassed_precedes_compile_empty():
    """bypassed should take precedence when bypass and compile-empty both exist without real meter."""
    now = time.time()
    compile_events = [
        {"agent_id": "claude_code", "compile_status": "compile_skipped", "compile_reason": "empty_query", "timestamp": now - 1},
        {"agent_id": "claude_code", "compile_status": "compile_skipped", "compile_reason": "agent_route_disabled", "timestamp": now},
    ]
    result = _run_derive_traffic_truth_test(
        "claude_code",
        {"claude_code": {"proxied_requests": 2}},
        [],
        compile_events=compile_events,
    )
    assert result == "bypassed"


def test_derive_traffic_truth_no_evidence():
    """Family with no compile evidence and no real meters should return no_recent_evidence."""
    result = _run_derive_traffic_truth_test("claude_code", {}, [])
    assert result == "no_recent_evidence"


def test_derive_traffic_truth_openclaw_observed_meter_without_compile_event():
    """OpenClaw observed meter should surface as real_request_observed even without compile events."""
    meter = MockMeter("openclaw", datetime.now(timezone.utc).isoformat(), baseline_tokens=120)
    result = _run_derive_traffic_truth_test("openclaw", {}, [meter], compile_events=[])
    assert result == "real_request_observed"


def test_derive_traffic_truth_tiny_ping_does_not_count_as_observed():
    """Tiny pings (baseline < 50) must not elevate traffic_truth to real_request_observed."""
    meter = MockMeter("openclaw", datetime.now(timezone.utc).isoformat(), baseline_tokens=20)
    result = _run_derive_traffic_truth_test("openclaw", {}, [meter], compile_events=[])
    assert result == "no_recent_evidence"


def test_compute_family_24h_metrics_observed_last_request_at_priority_and_zero_kpi():
    """
    last_request_at should prefer observed meter timestamp even if compile evidence is newer.
    KPI remains value_qualified-only (requests_24h can still be 0).
    """
    import adapter.application.status_read_model as srm

    now = datetime.now(timezone.utc)
    observed_ts = (now - timedelta(minutes=10)).isoformat()
    compile_ts = (now - timedelta(minutes=2)).timestamp()

    meter = MockMeter(
        "openclaw",
        observed_ts,
        baseline_tokens=120,
        saved_tokens=0,
        packed_memory_count=0,
        local_cards_used=0,
        remote_used_count=0,
    )
    mock_ms = MockMeterStore([meter])
    mock_rc = _make_mock_request_classifier()
    mock_cs = MockCompileStore(
        summary={"openclaw": {"proxied_requests": 1}},
        events=[{"agent_id": "openclaw", "compile_status": "compile_success", "compile_reason": "runtime_compile", "timestamp": compile_ts}],
    )

    srm._get_meter_store = lambda: mock_ms
    srm._get_request_classifier = lambda: mock_rc
    srm._get_compile_store = lambda: mock_cs

    metrics = srm.compute_family_24h_metrics("openclaw")
    assert metrics["requests_24h"] == 0
    assert metrics["saved_tokens_24h"] == 0
    assert metrics["savings_ratio_24h"] == 0.0
    assert metrics["observed_requests_24h"] == 1
    assert metrics["last_request_at"] == observed_ts


def test_derive_traffic_truth_uses_persisted_meter_fallback_when_aggregate_missing():
    """Observed truth should still be detected when meter only exists in persisted index."""
    import adapter.application.status_read_model as srm

    ts = datetime.now(timezone.utc).isoformat()
    persisted = {
        "req-openclaw-fallback-1": {
            "request_id": "req-openclaw-fallback-1",
            "tenant": "openclaw",
            "user": "openclaw",
            "agent": "openclaw",
            "timestamp": ts,
            "query": "openclaw observed fallback test",
            "baseline_tokens_estimate": 120,
        }
    }
    mock_ms = MockMeterStore([], persisted_index=persisted)
    mock_rc = _make_mock_request_classifier()
    mock_cs = MockCompileStore(summary={}, events=[])

    srm._get_meter_store = lambda: mock_ms
    srm._get_request_classifier = lambda: mock_rc
    srm._get_compile_store = lambda: mock_cs

    truth = srm.derive_traffic_truth("openclaw", window_minutes=30)
    assert truth == "real_request_observed"


def test_derive_scope_note_claude_code():
    """claude_code should have a scope_note explaining family-aggregate nature."""
    import adapter.application.status_read_model as srm
    result = srm._derive_scope_note("claude_code")
    assert result is not None
    assert "cc-haha" in result


def test_derive_scope_note_other_families():
    """Non-claude_code families should return None."""
    import adapter.application.status_read_model as srm
    assert srm._derive_scope_note("codex_cli") is None
    assert srm._derive_scope_note("openclaw") is None
    assert srm._derive_scope_note("cursor") is None


def test_derive_integration_truth_detached():
    import adapter.application.status_read_model as srm
    card = {"installed": False}
    assert srm.derive_integration_truth(card) == "detached"


def test_derive_integration_truth_mcp_attached():
    import adapter.application.status_read_model as srm
    card = {"installed": True, "backup_available": False}
    assert srm.derive_integration_truth(card) == "mcp_attached"


def test_derive_integration_truth_attached_with_backup():
    import adapter.application.status_read_model as srm
    card = {"installed": True, "backup_available": True}
    assert srm.derive_integration_truth(card) == "attached_with_backup"


def test_derive_route_truth_off():
    import adapter.application.status_read_model as srm
    assert srm.derive_route_truth(routing_enabled=False, health_state="healthy") == "off"


def test_derive_route_truth_effective():
    import adapter.application.status_read_model as srm
    assert srm.derive_route_truth(routing_enabled=True, health_state="healthy") == "effective"


def test_derive_route_truth_intent_on():
    import adapter.application.status_read_model as srm
    assert srm.derive_route_truth(routing_enabled=True, health_state="degraded") == "intent_on"
