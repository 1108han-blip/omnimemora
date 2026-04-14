"""
agent_metrics.py - Agent-level Metrics Aggregation & Persistence
================================================================
Stores per-agent per-session metrics in memory with JSONL persistence.
Thread-safe. Supports startup replay from JSONL events.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class AgentMetricsSnapshot(BaseModel):
    """Per-agent metrics snapshot."""
    agent_id: str = "unknown"
    session_id: str = "unknown"
    workspace_id: str = "unknown"
    integration_type: str = "unknown"
    mode: str = "unknown"
    request_count: int = 0
    optimized_count: int = 0
    bypass_count: int = 0
    saved_tokens: int = 0
    raw_tokens: int = 0
    compressed_tokens: int = 0
    entry_rate: float = 0.0
    avg_compression_ratio: float = 0.0
    quality_delta_pct: float = 0.0
    last_seen_at: Optional[str] = None


class AgentMetricsStore:
    """
    In-memory store for agent metrics with JSONL persistence.
    Thread-safe.
    """

    def __init__(
        self,
        events_path: Optional[str] = None,
        flush_interval_seconds: float = 5.0,
        max_file_size_mb: int = 50,
        retention_days: int = 30,
    ):
        self._lock = threading.Lock()
        self._events_path = events_path
        self._flush_interval = flush_interval_seconds
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self._retention_days = retention_days
        self._pending_events: list[dict] = []
        self._last_flush_time = time.time()
        self._writer_lock = threading.Lock()

        # agent_id -> session_id -> metrics dict
        self._store: dict[str, dict[str, dict]] = {}

        # Ensure directory exists
        if self._events_path:
            Path(self._events_path).parent.mkdir(parents=True, exist_ok=True)

        # Load existing events on startup
        self._replay_events()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _replay_events(self) -> None:
        """Replay events from JSONL file to rebuild in-memory state."""
        if not self._events_path or not os.path.exists(self._events_path):
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        try:
            with open(self._events_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        # Prune old events
                        ts = event.get("ts", "")
                        if ts:
                            try:
                                event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                if event_time < cutoff:
                                    continue
                            except Exception:
                                pass
                        self._apply_event(event)
                    except Exception:
                        continue
        except Exception:
            pass

    def _apply_event(self, event: dict) -> None:
        """Apply a single event to in-memory store."""
        event_type = event.get("event", "")
        agent_id = event.get("agent_id", "unknown")
        session_id = event.get("session_id", "unknown")
        workspace_id = event.get("workspace_id", "unknown")
        integration_type = event.get("integration_type", "unknown")

        if agent_id not in self._store:
            self._store[agent_id] = {}
        if session_id not in self._store[agent_id]:
            self._store[agent_id][session_id] = {
                "agent_id": agent_id,
                "session_id": session_id,
                "workspace_id": workspace_id,
                "integration_type": integration_type,
                "mode": event.get("mode", "observe"),
                "request_count": 0,
                "optimized_count": 0,
                "bypass_count": 0,
                "saved_tokens": 0,
                "raw_tokens": 0,
                "compressed_tokens": 0,
                "quality_delta_pct": 0.0,
                "last_seen_at": None,
            }

        entry = self._store[agent_id][session_id]
        entry["workspace_id"] = workspace_id or entry.get("workspace_id", "unknown")
        entry["integration_type"] = integration_type or entry.get("integration_type", "unknown")

        if event_type == "request":
            entry["request_count"] = entry.get("request_count", 0) + 1
            entry["mode"] = event.get("mode", entry.get("mode", "observe"))
            entry["last_seen_at"] = event.get("ts", entry.get("last_seen_at"))

        elif event_type == "result":
            if event.get("optimized"):
                entry["optimized_count"] = entry.get("optimized_count", 0) + 1
            if event.get("bypassed"):
                entry["bypass_count"] = entry.get("bypass_count", 0) + 1
            entry["saved_tokens"] = entry.get("saved_tokens", 0) + event.get("saved_tokens", 0)
            entry["raw_tokens"] = entry.get("raw_tokens", 0) + event.get("raw_tokens", 0)
            entry["compressed_tokens"] = entry.get("compressed_tokens", 0) + event.get("compressed_tokens", 0)

            # Running average for quality_delta_pct
            n = entry["optimized_count"]
            old_avg = entry.get("quality_delta_pct", 0.0)
            new_delta = event.get("quality_delta_pct", 0.0)
            entry["quality_delta_pct"] = (old_avg * (n - 1) + new_delta) / n if n > 0 else 0.0

            # Recalculate derived
            req_count = entry["request_count"]
            opt_count = entry["optimized_count"]
            entry["entry_rate"] = opt_count / req_count if req_count > 0 else 0.0
            raw_total = entry.get("raw_tokens", 0)
            compressed_total = entry.get("compressed_tokens", 0)
            entry["avg_compression_ratio"] = (
                (raw_total - compressed_total) / raw_total if raw_total > 0 else 0.0
            )
            entry["last_seen_at"] = event.get("ts", entry.get("last_seen_at"))

    def _write_event(self, event: dict) -> None:
        """Write a single event to JSONL file asynchronously."""
        if not self._events_path:
            return

        self._pending_events.append(event)

        # Check if we should flush
        now = time.time()
        should_flush = (
            len(self._pending_events) >= 10
            or (now - self._last_flush_time) >= self._flush_interval
        )

        if should_flush:
            self._flush_events()

    def _flush_events(self) -> None:
        """Flush pending events to disk. Called with writer_lock held."""
        if not self._pending_events or not self._events_path:
            return

        events_to_write = self._pending_events[:]
        self._pending_events.clear()
        self._last_flush_time = time.time()

        try:
            # Check file size for rotation
            if os.path.exists(self._events_path):
                size = os.path.getsize(self._events_path)
                if size >= self._max_file_size_bytes:
                    # Rotate: rename with timestamp
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                    rotated = self._events_path + f".{timestamp}"
                    os.rename(self._events_path, rotated)

            with open(self._events_path, "a", encoding="utf-8") as f:
                for event in events_to_write:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            # On write failure, put events back (at front) and degrade to memory-only
            self._pending_events = events_to_write + self._pending_events

    def record_request(self, identity, mode: str) -> None:
        """Record a new request from an agent."""
        event = {
            "event": "request",
            "agent_id": identity.canonical_agent_id,
            "session_id": identity.session_id or "unknown",
            "workspace_id": identity.workspace_id or "unknown",
            "user_id": identity.user_id or "unknown",
            "integration_type": identity.integration_type,
            "mode": mode,
            "ts": self._now_iso(),
        }

        with self._lock:
            self._apply_event(event)

        self._write_event(event)

    def record_result(
        self,
        identity,
        mode: str,
        optimized: bool,
        bypassed: bool,
        meter_artifact: Optional[dict] = None,
        quality_delta_pct: float = 0.0,
    ) -> None:
        """Record result after processing."""
        event = {
            "event": "result",
            "agent_id": identity.canonical_agent_id,
            "session_id": identity.session_id or "unknown",
            "workspace_id": identity.workspace_id or "unknown",
            "integration_type": identity.integration_type,
            "mode": mode,
            "optimized": optimized,
            "bypassed": bypassed,
            "saved_tokens": meter_artifact.get("saved_tokens_estimate", 0) if meter_artifact else 0,
            "raw_tokens": meter_artifact.get("baseline_tokens_estimate", 0) if meter_artifact else 0,
            "compressed_tokens": meter_artifact.get("actual_tokens_estimate", 0) if meter_artifact else 0,
            "quality_delta_pct": quality_delta_pct,
            "ts": self._now_iso(),
        }

        with self._lock:
            self._apply_event(event)

        self._write_event(event)

    def get_metrics(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[AgentMetricsSnapshot]:
        """Query metrics, optionally filtered by agent_id / session_id."""
        with self._lock:
            results = []
            for ag, sessions in self._store.items():
                if agent_id and ag != agent_id:
                    continue
                for sess, data in sessions.items():
                    if session_id and sess != session_id:
                        continue
                    results.append(AgentMetricsSnapshot(**data))
            return results

    def get_live_agents(self, window_minutes: int = 30) -> list[dict]:
        """Return agents with activity within window_minutes."""
        cutoff = time.time() - window_minutes * 60
        now_iso = self._now_iso()

        with self._lock:
            results = []
            for agent_id, sessions in self._store.items():
                for session_id, data in sessions.items():
                    last_seen = data.get("last_seen_at", "")
                    if not last_seen:
                        continue
                    try:
                        ts = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        if ts.timestamp() < cutoff:
                            continue
                    except Exception:
                        continue

                    req_count = data["request_count"]
                    opt_count = data["optimized_count"]
                    entry = {
                        "agent_id": data["agent_id"],
                        "session_id": data["session_id"],
                        "workspace_id": data.get("workspace_id", "unknown"),
                        "integration_type": data.get("integration_type", "unknown"),
                        "mode": data.get("mode", "observe"),
                        "request_count": req_count,
                        "optimized_count": opt_count,
                        "entry_rate": round(opt_count / req_count, 3) if req_count > 0 else 0.0,
                        "saved_tokens": data.get("saved_tokens", 0),
                        "quality_delta_pct": round(data.get("quality_delta_pct", 0.0), 2),
                        "last_seen_at": data.get("last_seen_at", now_iso),
                    }
                    results.append(entry)
            return results

    def flush(self) -> None:
        """Force flush of pending events."""
        with self._writer_lock:
            self._flush_events()


# Global singleton
_agent_metrics_store: Optional[AgentMetricsStore] = None


def get_agent_metrics_store(
    events_path: Optional[str] = None,
    flush_interval_seconds: float = 5.0,
    max_file_size_mb: int = 50,
    retention_days: int = 30,
) -> AgentMetricsStore:
    global _agent_metrics_store
    if _agent_metrics_store is None:
        _agent_metrics_store = AgentMetricsStore(
            events_path=events_path,
            flush_interval_seconds=flush_interval_seconds,
            max_file_size_mb=max_file_size_mb,
            retention_days=retention_days,
        )
    return _agent_metrics_store


def reset_agent_metrics_store() -> None:
    """Reset singleton — for testing only."""
    global _agent_metrics_store
    if _agent_metrics_store is not None:
        _agent_metrics_store.flush()
    _agent_metrics_store = None


def record_agent_request(identity, mode: str) -> None:
    store = get_agent_metrics_store()
    store.record_request(identity, mode)


def record_agent_result(
    identity,
    mode: str,
    optimized: bool,
    bypassed: bool,
    meter_artifact: Optional[dict] = None,
    quality_delta_pct: float = 0.0,
) -> None:
    store = get_agent_metrics_store()
    store.record_result(identity, mode, optimized, bypassed, meter_artifact, quality_delta_pct)


def get_live_agents(window_minutes: int = 30) -> list[dict]:
    store = get_agent_metrics_store()
    return store.get_live_agents(window_minutes)


def get_agent_metrics(
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> list[AgentMetricsSnapshot]:
    store = get_agent_metrics_store()
    return store.get_metrics(agent_id, session_id)