"""
Tests for agent_metrics.py — JSONL Persistence & Replay
===============================================================
"""
import json
import os
import pytest
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_metrics import (
    AgentMetricsStore,
    AgentMetricsSnapshot,
    get_agent_metrics_store,
    reset_agent_metrics_store,
    get_live_agents,
    get_agent_metrics,
    record_agent_request,
    record_agent_result,
)


class MockIdentity:
    """Mock identity object for testing — per ADR-0005 canonical_agent_id."""
    def __init__(self, canonical_agent_id="test-agent", session_id="test-session",
                 workspace_id="test-workspace", user_id="test-user",
                 integration_type="tool_caller", raw_agent_id=None):
        self.canonical_agent_id = canonical_agent_id
        self.raw_agent_id = raw_agent_id
        self.session_id = session_id
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.integration_type = integration_type


class MockMeterArtifact:
    """Mock meter artifact dict for testing."""
    def __init__(self, saved=100, baseline=200, actual=100):
        self._d = {
            "saved_tokens_estimate": saved,
            "baseline_tokens_estimate": baseline,
            "actual_tokens_estimate": actual,
        }
    def get(self, key, default=0):
        return self._d.get(key, default)


@pytest.fixture
def temp_events_file():
    """Create a temp JSONL file, clean up after."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)
    # Also clean up rotated files
    for f in Path(Path(path).parent).glob(f"{Path(path).name}.*"):
        f.unlink()


@pytest.fixture
def store(temp_events_file):
    """Create a fresh store with temp file."""
    reset_agent_metrics_store()
    store = get_agent_metrics_store(
        events_path=temp_events_file,
        flush_interval_seconds=0.1,
        max_file_size_mb=50,
        retention_days=30,
    )
    yield store
    store.flush()
    reset_agent_metrics_store()


class TestJsonlWrite:
    def test_request_event_written(self, temp_events_file):
        """Request event is appended to JSONL file."""
        store = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        identity = MockIdentity(canonical_agent_id="write-test-agent")
        store.record_request(identity, mode="observe")
        store.flush()

        assert os.path.exists(temp_events_file)
        with open(temp_events_file, "r") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert len(lines) >= 1
        assert lines[0]["event"] == "request"
        assert lines[0]["agent_id"] == "write-test-agent"

    def test_result_event_written(self, temp_events_file):
        """Result event is appended to JSONL file."""
        store = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        identity = MockIdentity(canonical_agent_id="result-test-agent")
        store.record_result(identity, mode="observe", optimized=True, bypassed=False,
                            meter_artifact={"saved_tokens_estimate": 50, "baseline_tokens_estimate": 100, "actual_tokens_estimate": 50},
                            quality_delta_pct=40.0)
        store.flush()

        with open(temp_events_file, "r") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        result_events = [l for l in lines if l["event"] == "result"]
        assert len(result_events) >= 1
        assert result_events[0]["saved_tokens"] == 50

    def test_both_events_for_one_request(self, temp_events_file):
        """One request should produce both a request and result event."""
        store = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        identity = MockIdentity(canonical_agent_id="both-events-agent")
        store.record_request(identity, mode="guided")
        store.record_result(identity, mode="guided", optimized=True, bypassed=False,
                            meter_artifact={"saved_tokens_estimate": 80, "baseline_tokens_estimate": 160, "actual_tokens_estimate": 80},
                            quality_delta_pct=50.0)
        store.flush()

        with open(temp_events_file, "r") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert len(lines) >= 2


class TestJsonlReadOnStartup:
    def test_replay_rebuilds_memory_state(self, temp_events_file):
        """Starting a new store with existing JSONL replays events correctly."""
        # Write some events directly to JSONL
        with open(temp_events_file, "w") as f:
            f.write(json.dumps({"event": "request", "agent_id": "replay-agent",
                                 "session_id": "sess-replay", "mode": "observe",
                                 "workspace_id": "ws1", "user_id": "u1",
                                 "integration_type": "tool_caller",
                                 "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}) + "\n")
            f.write(json.dumps({"event": "result", "agent_id": "replay-agent",
                                 "session_id": "sess-replay", "optimized": True,
                                 "bypassed": False, "saved_tokens": 75,
                                 "raw_tokens": 150, "compressed_tokens": 75,
                                 "quality_delta_pct": 50.0,
                                 "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}) + "\n")

        # Create new store — should replay
        store2 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=1.0, retention_days=30)
        metrics = store2.get_metrics(agent_id="replay-agent")
        assert len(metrics) == 1
        assert metrics[0].request_count == 1
        assert metrics[0].optimized_count == 1

    def test_old_events_pruned_on_replay(self, temp_events_file):
        """Events older than retention_days are skipped during replay."""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat().replace("+00:00", "Z")
        with open(temp_events_file, "w") as f:
            f.write(json.dumps({"event": "request", "agent_id": "old-agent",
                                 "session_id": "sess-old", "mode": "observe",
                                 "workspace_id": "ws1", "user_id": "u1",
                                 "integration_type": "unknown",
                                 "ts": old_ts}) + "\n")

        # 30 day retention — old event should be skipped
        store = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=1.0, retention_days=30)
        metrics = store.get_metrics(agent_id="old-agent")
        assert len(metrics) == 0  # pruned


class TestEventsAggregatedCorrectly:
    def test_multiple_events_aggregated(self, store):
        """Multiple events for same agent/session are aggregated."""
        identity = MockIdentity(canonical_agent_id="agg-agent", session_id="sess-agg")

        # 3 requests, 2 optimized
        for i in range(3):
            store.record_request(identity, mode="guided")
        store.record_result(identity, mode="guided", optimized=True, bypassed=False,
                             meter_artifact={"saved_tokens_estimate": 30, "baseline_tokens_estimate": 60, "actual_tokens_estimate": 30},
                             quality_delta_pct=30.0)
        store.record_result(identity, mode="guided", optimized=True, bypassed=False,
                             meter_artifact={"saved_tokens_estimate": 40, "baseline_tokens_estimate": 80, "actual_tokens_estimate": 40},
                             quality_delta_pct=40.0)
        store.record_result(identity, mode="guided", optimized=False, bypassed=True,
                             meter_artifact={"saved_tokens_estimate": 0, "baseline_tokens_estimate": 50, "actual_tokens_estimate": 50},
                             quality_delta_pct=0.0)

        metrics = store.get_metrics(agent_id="agg-agent")
        assert len(metrics) == 1
        assert metrics[0].request_count == 3
        assert metrics[0].optimized_count == 2
        assert metrics[0].bypass_count == 1
        assert metrics[0].saved_tokens == 70
        assert metrics[0].entry_rate == pytest.approx(2/3, rel=0.01)


class TestRestartRecovery:
    def test_request_count_preserved_after_reinit(self, temp_events_file):
        """After store reinit, request_count is preserved."""
        identity = MockIdentity(canonical_agent_id="recovery-agent", session_id="sess-recovery")

        # Record 5 requests in first store
        store1 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        for i in range(5):
            store1.record_request(identity, mode="observe")
            store1.record_result(identity, mode="observe", optimized=True, bypassed=False,
                                 meter_artifact={"saved_tokens_estimate": 20, "baseline_tokens_estimate": 40, "actual_tokens_estimate": 20},
                                 quality_delta_pct=30.0)
        store1.flush()

        # Reinit store (simulating restart)
        store2 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=1.0, retention_days=30)
        metrics = store2.get_metrics(agent_id="recovery-agent")
        assert len(metrics) == 1
        assert metrics[0].request_count == 5
        assert metrics[0].optimized_count == 5

    def test_accumulated_saved_tokens_preserved(self, temp_events_file):
        """saved_tokens accumulates correctly across restarts."""
        identity = MockIdentity(canonical_agent_id="tokens-agent", session_id="sess-tokens")

        store1 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        for i in range(3):
            store1.record_request(identity, mode="guided")
            store1.record_result(identity, mode="guided", optimized=True, bypassed=False,
                                 meter_artifact={"saved_tokens_estimate": 50 * (i+1),
                                                "baseline_tokens_estimate": 100 * (i+1),
                                                "actual_tokens_estimate": 50 * (i+1)},
                                 quality_delta_pct=35.0)
        store1.flush()

        store2 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=1.0, retention_days=30)
        metrics = store2.get_metrics(agent_id="tokens-agent")
        assert metrics[0].saved_tokens == 300  # 50 + 100 + 150

    def test_live_agents_after_restart(self, temp_events_file):
        """Live agents list is correctly restored after restart."""
        identity = MockIdentity(canonical_agent_id="live-agent", session_id="sess-live")

        store1 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        store1.record_request(identity, mode="guided")
        store1.record_result(identity, mode="guided", optimized=True, bypassed=False,
                              meter_artifact={"saved_tokens_estimate": 25, "baseline_tokens_estimate": 50, "actual_tokens_estimate": 25},
                              quality_delta_pct=30.0)
        store1.flush()

        # Restart
        store2 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=1.0, retention_days=30)
        live = store2.get_live_agents(window_minutes=30)
        assert len(live) == 1
        assert live[0]["agent_id"] == "live-agent"
        assert live[0]["request_count"] == 1

    def test_full_restart_cycle(self, temp_events_file):
        """
        Complete restart cycle:
        1. Send 3 requests
        2. Restart store
        3. Send 2 more requests
        4. Verify total = 5
        """
        identity = MockIdentity(canonical_agent_id="cycle-agent", session_id="sess-cycle")

        # Phase 1: 3 requests
        store1 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)
        for i in range(3):
            store1.record_request(identity, mode="observe")
            store1.record_result(identity, mode="observe", optimized=True, bypassed=False,
                                  meter_artifact={"saved_tokens_estimate": 10, "baseline_tokens_estimate": 20, "actual_tokens_estimate": 10},
                                  quality_delta_pct=25.0)
        store1.flush()

        # Restart
        store2 = AgentMetricsStore(events_path=temp_events_file, flush_interval_seconds=0.05)

        # Phase 2: 2 more requests
        for i in range(2):
            store2.record_request(identity, mode="observe")
            store2.record_result(identity, mode="observe", optimized=True, bypassed=False,
                                  meter_artifact={"saved_tokens_estimate": 10, "baseline_tokens_estimate": 20, "actual_tokens_estimate": 10},
                                  quality_delta_pct=25.0)
        store2.flush()

        metrics = store2.get_metrics(agent_id="cycle-agent")
        assert metrics[0].request_count == 5
        assert metrics[0].optimized_count == 5


class TestFileRotation:
    def test_file_rotation_triggered(self, temp_events_file):
        """When file exists and exceeds max size, rotation occurs on next write."""
        # Pre-populate file to exceed 100 byte threshold
        big_line = json.dumps({"event": "request", "agent_id": "pre-agent",
                               "session_id": "pre-sess", "mode": "x" * 200,
                               "workspace_id": "ws", "user_id": "u",
                               "integration_type": "tool_caller",
                               "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
        with open(temp_events_file, "w") as f:
            f.write(big_line + "\n")

        # File is now ~250 bytes (> 100 byte threshold)
        store = AgentMetricsStore(
            events_path=temp_events_file,
            flush_interval_seconds=0.05,
            max_file_size_mb=0.0001,  # ~100 bytes
            retention_days=30,
        )

        # Write a small event — this should trigger rotation since file is already over threshold
        identity = MockIdentity(canonical_agent_id="rotate-agent", session_id="sess-rotate")
        store.record_request(identity, mode="observe")
        store.flush()

        parent = Path(temp_events_file).parent
        rotated = list(parent.glob(f"{Path(temp_events_file).name}.*"))
        # After flush with pre-existing oversized file, rotation should occur
        assert os.path.exists(temp_events_file) and (len(rotated) >= 1 or os.path.getsize(temp_events_file) < 300)


class TestAPICompatibility:
    def test_get_live_agents_returns_correct_schema(self, store):
        """get_live_agents returns list of dicts with expected fields."""
        identity = MockIdentity(canonical_agent_id="schema-agent", session_id="sess-schema")
        store.record_request(identity, mode="guided")
        store.record_result(identity, mode="guided", optimized=True, bypassed=False,
                             meter_artifact={"saved_tokens_estimate": 50, "baseline_tokens_estimate": 100, "actual_tokens_estimate": 50},
                             quality_delta_pct=40.0)

        live = store.get_live_agents(window_minutes=30)
        assert len(live) == 1
        entry = live[0]
        for field in ["agent_id", "session_id", "workspace_id", "integration_type",
                      "mode", "request_count", "optimized_count", "entry_rate",
                      "saved_tokens", "quality_delta_pct", "last_seen_at"]:
            assert field in entry, f"Missing field: {field}"

    def test_get_metrics_returns_correct_schema(self, store):
        """get_metrics returns list of AgentMetricsSnapshot."""
        identity = MockIdentity(canonical_agent_id="metrics-schema-agent", session_id="sess-ms")
        store.record_request(identity, mode="observe")
        store.record_result(identity, mode="observe", optimized=True, bypassed=False,
                             meter_artifact={"saved_tokens_estimate": 30, "baseline_tokens_estimate": 60, "actual_tokens_estimate": 30},
                             quality_delta_pct=35.0)

        metrics = store.get_metrics(agent_id="metrics-schema-agent")
        assert len(metrics) == 1
        assert isinstance(metrics[0], AgentMetricsSnapshot)
        assert metrics[0].agent_id == "metrics-schema-agent"
        assert metrics[0].request_count == 1
        assert metrics[0].optimized_count == 1


class TestQualityDelta:
    def test_quality_delta_running_average(self, store):
        """quality_delta_pct is a running average, not cumulative."""
        identity = MockIdentity(canonical_agent_id="qd-agent", session_id="sess-qd")

        store.record_request(identity, mode="guided")
        store.record_result(identity, mode="guided", optimized=True, bypassed=False,
                             meter_artifact={"saved_tokens_estimate": 50, "baseline_tokens_estimate": 100, "actual_tokens_estimate": 50},
                             quality_delta_pct=20.0)
        store.record_request(identity, mode="guided")
        store.record_result(identity, mode="guided", optimized=True, bypassed=False,
                             meter_artifact={"saved_tokens_estimate": 50, "baseline_tokens_estimate": 100, "actual_tokens_estimate": 50},
                             quality_delta_pct=60.0)

        metrics = store.get_metrics(agent_id="qd-agent")
        # Average of 20 and 60 = 40
        assert abs(metrics[0].quality_delta_pct - 40.0) < 0.1