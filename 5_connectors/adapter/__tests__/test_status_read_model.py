"""
Tests for status_read_model.py truth derivation functions.
"""
import pytest
import os
import sys
from unittest.mock import MagicMock
from datetime import datetime, timezone
import time

# Setup path like other test files in this directory
_adapter_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_connectors_dir = os.path.dirname(_adapter_dir)
for p in (_adapter_dir, _connectors_dir):
    if p not in sys.path:
        sys.path.insert(0, p)


class MockMeter:
    def __init__(self, agent, timestamp, baseline_tokens=100):
        self.agent = agent
        self.timestamp = timestamp
        self.baseline_tokens_estimate = baseline_tokens


class MockCompileStore:
    def __init__(self, summary):
        self._summary = summary

    def summarize_compile_status(self, window_minutes=30):
        return self._summary


class MockMeterStore:
    def __init__(self, meters):
        self._usage_aggregates = {"default": meters}

    def _ensure_persistence_loaded(self):
        pass


def _make_mock_request_classifier():
    """Create a mock request classifier that returns True for is_default_overview_request."""
    mock = MagicMock()
    mock.is_default_overview_request.return_value = True
    return mock


def _run_derive_traffic_truth_test(family_id, compile_summary, meters, window_minutes=30):
    """Helper that directly patches module-level functions and runs derive_traffic_truth."""
    import adapter.application.status_read_model as srm

    mock_cs = MockCompileStore(compile_summary)
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
    result = _run_derive_traffic_truth_test("codex_cli", {"codex_cli": {"proxied_requests": 5}}, [])
    assert result == "internal_only"


def test_derive_traffic_truth_openclaw_legacy_behavior():
    """openclaw with both proxied and real meter -> real_request_observed."""
    meter = MockMeter("openclaw", datetime.now(timezone.utc).isoformat(), 100)
    result = _run_derive_traffic_truth_test("openclaw", {"openclaw": {"proxied_requests": 3}}, [meter])
    assert result == "real_request_observed"


def test_derive_traffic_truth_openclaw_only_proxied():
    """openclaw with proxied > 0 but no real meter should return internal_only."""
    result = _run_derive_traffic_truth_test("openclaw", {"openclaw": {"proxied_requests": 3}}, [])
    assert result == "internal_only"


def test_derive_traffic_truth_no_evidence():
    """Family with no compile evidence and no real meters should return no_recent_evidence."""
    result = _run_derive_traffic_truth_test("claude_code", {}, [])
    assert result == "no_recent_evidence"


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
