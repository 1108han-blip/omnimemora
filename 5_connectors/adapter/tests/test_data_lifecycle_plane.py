import asyncio
import importlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


summary_builder = importlib.import_module("5_connectors.adapter.data_lifecycle.summary_builder")
summary_store = importlib.import_module("5_connectors.adapter.data_lifecycle.summary_store")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
maintenance_manager_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.maintenance_manager")
scheduler_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.scheduler")
status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")


class Meter:
    def __init__(
        self,
        *,
        request_id: str,
        agent: str,
        timestamp: str,
        baseline_tokens_estimate: int,
        saved_tokens_estimate: int,
        tenant: str = "default",
        user: str = "default",
    ) -> None:
        self.request_id = request_id
        self.agent = agent
        self.timestamp = timestamp
        self.baseline_tokens_estimate = baseline_tokens_estimate
        self.saved_tokens_estimate = saved_tokens_estimate
        self.tenant = tenant
        self.user = user


class MockRequestClassifier:
    def is_default_overview_request(self, _meter):
        return True

    def is_value_qualified(self, _meter):
        return True

    def collapse_retry_bursts(self, meters):
        return list(meters)


class MockMeterStore:
    def __init__(self, meters):
        self._usage_aggregates = {"default": list(meters)}
        self._meter_store = {}

    def _ensure_persistence_loaded(self):
        return None


def test_summary_builder_family_window_equivalent_to_legacy_logic(monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_STATUS_READ_MODEL_METER_READ_PATH", "legacy_only")
    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    meters = [
        Meter(
            request_id="req-openclaw-1",
            agent="openclaw",
            timestamp=ts,
            baseline_tokens_estimate=120,
            saved_tokens_estimate=30,
        )
    ]
    compile_rows_30m = [
        {
            "agent_id": "openclaw",
            "compile_status": "compile_success",
            "compile_reason": "runtime_compile",
            "timestamp": now.timestamp(),
        }
    ]
    compile_rows_24h = list(compile_rows_30m)
    classifier = MockRequestClassifier()

    built = summary_builder.build_family_window_summary(
        meters=meters,
        compile_rows_30m=compile_rows_30m,
        compile_rows_24h=compile_rows_24h,
        proxy_rows_30m=[],
        now_utc=now,
        is_default_overview_request=classifier.is_default_overview_request,
        is_value_qualified=classifier.is_value_qualified,
        collapse_retry_bursts=classifier.collapse_retry_bursts,
    )
    family = built["families"]["openclaw"]

    monkeypatch.setattr(status_read_model, "_get_meter_store", lambda: MockMeterStore(meters))
    monkeypatch.setattr(status_read_model, "_get_request_classifier", lambda: classifier)

    expected_compile_30m = status_read_model._summarize_family_compile_events(
        "openclaw",
        preloaded_rows=compile_rows_30m,
    )
    expected_compile_24h = status_read_model._summarize_family_compile_events(
        "openclaw",
        preloaded_rows=compile_rows_24h,
    )
    expected_observed_30m = status_read_model._collect_observed_family_meters("openclaw", window_minutes=30)
    expected_observed_24h = status_read_model._collect_observed_family_meters("openclaw", window_minutes=24 * 60)
    expected_metrics_24h = status_read_model.compute_family_24h_metrics(
        "openclaw",
        observed_family_meters=expected_observed_24h,
        compile_24h_summary=expected_compile_24h,
    )
    expected_truth = status_read_model.derive_traffic_truth(
        "openclaw",
        observed_meters=expected_observed_30m,
        compile_summary=expected_compile_30m,
    )

    assert family["compile_30m"] == expected_compile_30m
    assert family["compile_24h"] == expected_compile_24h
    assert family["metrics_24h"] == expected_metrics_24h
    assert family["traffic_truth_30m"] == expected_truth


def test_summary_store_atomic_read_and_freshness(tmp_path):
    custom_policy = policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=10.0,
        summary_stale_max_age_seconds=120.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
    )
    payload = {
        "schema_version": "dlp-family-window-summary-v1",
        "generated_at": 100.0,
        "families": {"openclaw": {"traffic_truth_30m": "no_recent_evidence"}},
    }

    summary_store.write_summary_atomic(payload, policy=custom_policy)
    loaded = summary_store.read_summary(policy=custom_policy)

    assert loaded == payload
    assert summary_store.is_summary_fresh(loaded, policy=custom_policy, now_ts=109.0)
    assert not summary_store.is_summary_fresh(loaded, policy=custom_policy, now_ts=111.0)
    assert summary_store.read_fresh_summary(policy=custom_policy, now_ts=111.0) is None
    stale = summary_store.read_stale_usable_summary(policy=custom_policy, now_ts=111.0)
    assert stale == payload
    assert summary_store.read_stale_usable_summary(policy=custom_policy, now_ts=221.0) is None


def test_policy_defaults_disable_background_maintenance(monkeypatch):
    monkeypatch.delenv("OMNIMEMORA_DLP_MAINTENANCE_ENABLED", raising=False)

    policy = policy_mod.load_policy()

    assert policy.maintenance_enabled is False


def test_maintenance_manager_run_once_writes_summary_and_state_without_deleting_raw(tmp_path):
    custom_policy = policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=30.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
    )

    raw_marker = tmp_path / "raw_compile_events.jsonl"
    raw_marker.write_text('{"raw": true}\n', encoding="utf-8")

    meter = Meter(
        request_id="req-1",
        agent="openclaw",
        timestamp=datetime.now(timezone.utc).isoformat(),
        baseline_tokens_estimate=100,
        saved_tokens_estimate=20,
    )
    classifier = MockRequestClassifier()

    manager = maintenance_manager_mod.MaintenanceManager(
        policy=custom_policy,
        meter_export_fn=lambda: [meter],
        compile_rows_30m_fn=lambda: [],
        compile_rows_24h_fn=lambda: [],
        proxy_rows_30m_fn=lambda: [],
        is_default_overview_request_fn=classifier.is_default_overview_request,
        is_value_qualified_fn=classifier.is_value_qualified,
        collapse_retry_bursts_fn=classifier.collapse_retry_bursts,
        bytes_scanned_fn=lambda: raw_marker.stat().st_size,
    )

    record = manager.run_once("unit-test")

    assert record["status"] == "success"
    assert record["trigger"] == "unit-test"
    assert record["bytes_scanned"] == raw_marker.stat().st_size
    assert Path(custom_policy.summary_file).exists()
    assert Path(custom_policy.maintenance_state_file).exists()
    assert raw_marker.exists()

    lines = Path(custom_policy.maintenance_state_file).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["cycle_id"] == record["cycle_id"]


def test_status_read_model_fallbacks_to_legacy_path_when_summary_missing(monkeypatch):
    async def fake_runtime_request(_method, _path, payload=None):
        return {
            "agents": [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "backup_available": False,
                    "detected": True,
                    "message": "",
                }
            ]
        }

    async def fake_health_state():
        return "healthy"

    class RouteState:
        @staticmethod
        def routing_enabled(_family_id):
            return False

    observed_calls = {"count": 0}

    def fake_collect_observed(_family_id, window_minutes=30):
        observed_calls["count"] += 1
        return []

    def fake_compile_summary(_family_id, window_minutes=30, preloaded_rows=None):
        return {"proxied_requests": 0, "compile_empty": 0, "bypassed": 0, "last_event_ts": None}

    def fake_metrics_24h(_family_id, observed_family_meters=None, compile_24h_summary=None):
        return {
            "requests_24h": 0,
            "saved_tokens_24h": 0,
            "savings_ratio_24h": 0.0,
            "last_request_at": None,
            "observed_requests_24h": 0,
        }

    class CompileStore:
        @staticmethod
        def read_recent_compile_events(limit=5000, window_minutes=30):
            return []

    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (None, "none", "summary_missing"))
    monkeypatch.setattr(status_read_model, "_runtime_request", fake_runtime_request)
    monkeypatch.setattr(status_read_model, "_runtime_health_state", fake_health_state)
    monkeypatch.setattr(status_read_model, "build_metrics_index", lambda: {"openclaw": {"active": False, "last_seen_at": None, "subagent_count_active": 0, "subagent_count_total_visible": 0}})
    monkeypatch.setattr(status_read_model, "_get_agent_routing_state", lambda: RouteState())
    monkeypatch.setattr(status_read_model, "_get_compile_store", lambda: CompileStore())
    monkeypatch.setattr(status_read_model, "_collect_observed_family_meters", fake_collect_observed)
    monkeypatch.setattr(status_read_model, "_summarize_family_compile_events", fake_compile_summary)
    monkeypatch.setattr(status_read_model, "compute_family_24h_metrics", fake_metrics_24h)

    cards = asyncio.run(status_read_model.build_control_cards())

    assert observed_calls["count"] > 0
    assert len(cards) == 1
    assert cards[0]["family_id"] == "openclaw"
    assert "requests_24h" in cards[0]
    assert "traffic_truth" in cards[0]


def test_status_read_model_prefers_fresh_summary_when_available(monkeypatch):
    async def fake_runtime_request(_method, _path, payload=None):
        return {
            "agents": [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "backup_available": False,
                    "detected": True,
                    "message": "",
                }
            ]
        }

    async def fake_health_state():
        return "healthy"

    class RouteState:
        @staticmethod
        def routing_enabled(_family_id):
            return False

    fresh_summary = {
        "openclaw": {
            "traffic_truth_30m": "real_request_observed",
            "compile_30m": {"proxied_requests": 1, "compile_empty": 0, "bypassed": 0, "last_event_ts": None},
            "compile_24h": {"proxied_requests": 1, "compile_empty": 0, "bypassed": 0, "last_event_ts": None},
            "metrics_24h": {
                "requests_24h": 1,
                "saved_tokens_24h": 20,
                "savings_ratio_24h": 0.2,
                "last_request_at": datetime.now(timezone.utc).isoformat(),
                "observed_requests_24h": 1,
            },
        }
    }

    def fail_if_called(*args, **kwargs):
        raise AssertionError("legacy aggregation should not run when fresh summary exists")

    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (fresh_summary, "fresh", None))
    monkeypatch.setattr(status_read_model, "_runtime_request", fake_runtime_request)
    monkeypatch.setattr(status_read_model, "_runtime_health_state", fake_health_state)
    monkeypatch.setattr(status_read_model, "build_metrics_index", lambda: {"openclaw": {"active": False, "last_seen_at": None, "subagent_count_active": 0, "subagent_count_total_visible": 0}})
    monkeypatch.setattr(status_read_model, "_get_agent_routing_state", lambda: RouteState())
    monkeypatch.setattr(status_read_model, "_collect_observed_family_meters", fail_if_called)
    monkeypatch.setattr(status_read_model, "_summarize_family_compile_events", fail_if_called)
    monkeypatch.setattr(status_read_model, "compute_family_24h_metrics", fail_if_called)

    cards = asyncio.run(status_read_model.build_control_cards())
    assert cards[0]["traffic_truth"] == "real_request_observed"
    assert cards[0]["requests_24h"] == 1


def test_status_read_model_surfaces_running_client_without_product_traffic(monkeypatch):
    async def fake_runtime_request(_method, _path, payload=None):
        return {
            "agents": [
                {
                    "family_id": "claude_code",
                    "display_name": "Claude Code",
                    "installed": True,
                    "running": True,
                    "backup_available": True,
                    "detected": True,
                    "message": "",
                }
            ]
        }

    async def fake_health_state():
        return "healthy"

    class RouteState:
        @staticmethod
        def routing_enabled(_family_id):
            return True

    class CompileStore:
        @staticmethod
        def read_recent_compile_events(limit=5000, window_minutes=30):
            return []

    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (None, "none", "summary_missing"))
    monkeypatch.setattr(status_read_model, "_runtime_request", fake_runtime_request)
    monkeypatch.setattr(status_read_model, "_runtime_health_state", fake_health_state)
    monkeypatch.setattr(status_read_model, "build_metrics_index", lambda: {})
    monkeypatch.setattr(status_read_model, "_get_agent_routing_state", lambda: RouteState())
    monkeypatch.setattr(status_read_model, "_get_compile_store", lambda: CompileStore())
    monkeypatch.setattr(status_read_model, "_collect_observed_family_meters", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        status_read_model,
        "_summarize_family_compile_events",
        lambda *_args, **_kwargs: {"proxied_requests": 0, "compile_empty": 0, "bypassed": 0, "last_event_ts": None},
    )
    monkeypatch.setattr(
        status_read_model,
        "compute_family_24h_metrics",
        lambda *_args, **_kwargs: {
            "requests_24h": 0,
            "saved_tokens_24h": 0,
            "savings_ratio_24h": 0.0,
            "last_request_at": None,
            "observed_requests_24h": 0,
        },
    )
    monkeypatch.setattr(status_read_model, "_record_degraded_path", lambda *_args, **_kwargs: None)

    cards = asyncio.run(status_read_model.build_control_cards())

    assert cards[0]["family_id"] == "claude_code"
    assert cards[0]["process_running"] is True
    assert cards[0]["active"] is True
    assert cards[0]["last_seen_at"] is not None
    assert cards[0]["traffic_truth"] == "no_recent_evidence"
    assert cards[0]["requests_24h"] == 0
    assert "等待真實工作請求" in cards[0]["truth_message"]


def test_status_read_model_uses_stale_summary_before_legacy_fallback(monkeypatch):
    async def fake_runtime_request(_method, _path, payload=None):
        return {
            "agents": [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "backup_available": False,
                    "detected": True,
                    "message": "",
                }
            ]
        }

    async def fake_health_state():
        return "healthy"

    class RouteState:
        @staticmethod
        def routing_enabled(_family_id):
            return False

    stale_summary = {
        "openclaw": {
            "traffic_truth_30m": "internal_only",
            "compile_30m": {"proxied_requests": 2, "compile_empty": 0, "bypassed": 0, "last_event_ts": None},
            "compile_24h": {"proxied_requests": 3, "compile_empty": 0, "bypassed": 0, "last_event_ts": None},
            "metrics_24h": {
                "requests_24h": 2,
                "saved_tokens_24h": 40,
                "savings_ratio_24h": 0.2,
                "last_request_at": datetime.now(timezone.utc).isoformat(),
                "observed_requests_24h": 2,
            },
        }
    }

    def fail_if_called(*args, **kwargs):
        raise AssertionError("legacy aggregation should not run when stale summary is usable")

    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (stale_summary, "stale", None))
    monkeypatch.setattr(status_read_model, "_runtime_request", fake_runtime_request)
    monkeypatch.setattr(status_read_model, "_runtime_health_state", fake_health_state)
    monkeypatch.setattr(status_read_model, "build_metrics_index", lambda: {"openclaw": {"active": False, "last_seen_at": None, "subagent_count_active": 0, "subagent_count_total_visible": 0}})
    monkeypatch.setattr(status_read_model, "_get_agent_routing_state", lambda: RouteState())
    monkeypatch.setattr(status_read_model, "_collect_observed_family_meters", fail_if_called)
    monkeypatch.setattr(status_read_model, "_summarize_family_compile_events", fail_if_called)
    monkeypatch.setattr(status_read_model, "compute_family_24h_metrics", fail_if_called)

    cards = asyncio.run(status_read_model.build_control_cards())
    assert cards[0]["traffic_truth"] == "internal_only"
    assert cards[0]["requests_24h"] == 2


def test_scheduler_startup_warm_calls_run_once():
    triggers = []

    class FakeManager:
        def run_once(self, trigger):
            triggers.append(trigger)
            return {"status": "success"}

    policy = policy_mod.DataLifecyclePolicy(
        maintenance_enabled=True,
        maintenance_startup_delay_seconds=0.01,
        maintenance_interval_seconds=10.0,
    )
    scheduler = scheduler_mod.DataLifecycleScheduler(manager=FakeManager(), policy=policy)

    async def _run():
        scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()

    asyncio.run(_run())
    assert "startup_warm" in triggers


def test_scheduler_interval_refresh_calls_run_once():
    triggers = []

    class FakeManager:
        def run_once(self, trigger):
            triggers.append(trigger)
            return {"status": "success"}

    policy = policy_mod.DataLifecyclePolicy(
        maintenance_enabled=True,
        maintenance_startup_delay_seconds=0.0,
        maintenance_interval_seconds=0.02,
    )
    scheduler = scheduler_mod.DataLifecycleScheduler(manager=FakeManager(), policy=policy)

    async def _run():
        scheduler.start()
        await asyncio.sleep(0.09)
        await scheduler.stop()

    asyncio.run(_run())
    assert "startup_warm" in triggers
    assert any(t == "interval_refresh" for t in triggers)


def test_maintenance_manager_singleflight_blocks_concurrent_runs(tmp_path):
    custom_policy = policy_mod.DataLifecyclePolicy(
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
    )

    start_gate = threading.Event()

    def slow_meter_export():
        start_gate.wait(timeout=0.2)
        time.sleep(0.05)
        return []

    manager = maintenance_manager_mod.MaintenanceManager(
        policy=custom_policy,
        meter_export_fn=slow_meter_export,
        compile_rows_30m_fn=lambda: [],
        compile_rows_24h_fn=lambda: [],
        proxy_rows_30m_fn=lambda: [],
        is_default_overview_request_fn=lambda _: True,
        is_value_qualified_fn=lambda _: True,
        collapse_retry_bursts_fn=lambda rows: rows,
        bytes_scanned_fn=lambda: 0,
    )

    results = []

    def _first():
        results.append(manager.run_once("first"))

    t = threading.Thread(target=_first)
    t.start()
    time.sleep(0.02)
    second = manager.run_once("second")
    start_gate.set()
    t.join()

    assert second["status"] == "skipped"
    assert second["error"] == "maintenance_cycle_in_progress"
    assert any(r["status"] == "success" for r in results)


def test_maintenance_manager_budget_exceeded_writes_failed_ledger(tmp_path):
    custom_policy = policy_mod.DataLifecyclePolicy(
        maintenance_budget_seconds=0.01,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
    )

    def slow_meter_export():
        time.sleep(0.03)
        return []

    manager = maintenance_manager_mod.MaintenanceManager(
        policy=custom_policy,
        meter_export_fn=slow_meter_export,
        compile_rows_30m_fn=lambda: [],
        compile_rows_24h_fn=lambda: [],
        proxy_rows_30m_fn=lambda: [],
        is_default_overview_request_fn=lambda _: True,
        is_value_qualified_fn=lambda _: True,
        collapse_retry_bursts_fn=lambda rows: rows,
        bytes_scanned_fn=lambda: 0,
    )

    record = manager.run_once("budget-test")
    assert record["status"] == "failed"
    assert "maintenance_budget_exceeded" in str(record["error"])

    lines = Path(custom_policy.maintenance_state_file).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["status"] == "failed"


def test_summary_builder_contract_metadata_fields():
    now = datetime.now(timezone.utc)
    payload = summary_builder.build_family_window_summary(
        meters=[],
        compile_rows_30m=[],
        compile_rows_24h=[],
        proxy_rows_30m=[],
        now_utc=now,
        builder_version="test-builder-v1",
    )
    assert payload["schema_version"] == "dlp-family-window-summary-v1"
    assert isinstance(payload["generated_at"], (int, float))
    assert payload["builder_version"] == "test-builder-v1"
    assert isinstance(payload["source_counts"], dict)
    assert payload["source_counts"]["meters"] == 0
    assert payload["source_counts"]["compile_rows_30m"] == 0
    assert isinstance(payload["metrics_summary_all"], dict)
    assert isinstance(payload["metrics_summary_24h"], dict)
    assert isinstance(payload["core_capabilities_24h"], dict)
    assert isinstance(payload["families"], dict)
    assert "degraded_reason" not in payload

    degraded = summary_builder.build_family_window_summary(
        meters=[],
        compile_rows_30m=[],
        compile_rows_24h=[],
        proxy_rows_30m=[],
        now_utc=now,
        degraded_reason="fixture_degraded",
    )
    assert degraded["degraded_reason"] == "fixture_degraded"


def test_summary_path_and_legacy_path_key_fields_match(monkeypatch):
    async def fake_runtime_request(_method, _path, payload=None):
        return {
            "agents": [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "backup_available": False,
                    "detected": True,
                    "message": "",
                }
            ]
        }

    async def fake_health_state():
        return "healthy"

    class RouteState:
        @staticmethod
        def routing_enabled(_family_id):
            return False

    metrics_24h = {
        "requests_24h": 7,
        "saved_tokens_24h": 700,
        "savings_ratio_24h": 0.35,
        "last_request_at": datetime.now(timezone.utc).isoformat(),
        "observed_requests_24h": 9,
    }
    compile_30 = {"proxied_requests": 5, "compile_empty": 0, "bypassed": 0, "last_event_ts": None}
    compile_24 = {"proxied_requests": 9, "compile_empty": 0, "bypassed": 0, "last_event_ts": None}
    traffic_truth = "internal_only"

    monkeypatch.setattr(status_read_model, "_runtime_request", fake_runtime_request)
    monkeypatch.setattr(status_read_model, "_runtime_health_state", fake_health_state)
    monkeypatch.setattr(status_read_model, "build_metrics_index", lambda: {"openclaw": {"active": False, "last_seen_at": None, "subagent_count_active": 0, "subagent_count_total_visible": 0}})
    monkeypatch.setattr(status_read_model, "_get_agent_routing_state", lambda: RouteState())
    monkeypatch.setattr(status_read_model, "_record_degraded_path", lambda *_: None)

    summary_families = {
        "openclaw": {
            "traffic_truth_30m": traffic_truth,
            "compile_30m": compile_30,
            "compile_24h": compile_24,
            "metrics_24h": metrics_24h,
        }
    }
    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (summary_families, "fresh", None))
    cards_summary = asyncio.run(status_read_model.build_control_cards())

    class CompileStore:
        @staticmethod
        def read_recent_compile_events(limit=5000, window_minutes=30):
            return []

    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (None, "none", "summary_missing"))
    monkeypatch.setattr(status_read_model, "_get_compile_store", lambda: CompileStore())
    monkeypatch.setattr(status_read_model, "_collect_observed_family_meters", lambda *_args, **_kwargs: [])
    def fake_compile_summary(_family_id, window_minutes=30, preloaded_rows=None):
        return compile_24 if window_minutes == 24 * 60 else compile_30

    monkeypatch.setattr(status_read_model, "_summarize_family_compile_events", fake_compile_summary)
    monkeypatch.setattr(status_read_model, "compute_family_24h_metrics", lambda *_args, **_kwargs: metrics_24h)
    monkeypatch.setattr(status_read_model, "derive_traffic_truth", lambda *_args, **_kwargs: traffic_truth)
    cards_legacy = asyncio.run(status_read_model.build_control_cards())

    for key in [
        "traffic_truth",
        "requests_24h",
        "saved_tokens_24h",
        "savings_ratio_24h",
        "last_request_at",
        "observed_requests_24h",
    ]:
        assert cards_summary[0][key] == cards_legacy[0][key]
    assert "24 小時內已有真實請求收益" in cards_summary[0]["truth_message"]
    assert "最近 30 分鐘僅看到內部握手" in cards_summary[0]["truth_message"]


def test_truth_message_preserves_24h_value_when_no_recent_evidence():
    message = status_read_model.derive_truth_message(
        {"installed": True, "routing_enabled": True},
        "attached_with_backup",
        "on",
        "no_recent_evidence",
        {
            "requests_24h": 12,
            "saved_tokens_24h": 37792,
            "savings_ratio_24h": 0.87,
            "last_request_at": "2026-05-09T03:29:00Z",
            "observed_requests_24h": 13,
        },
    )
    assert "24 小時內已有真實請求收益" in message
    assert "最近 30 分鐘暫無工作請求" in message


def test_legacy_fallback_records_degraded_reason(monkeypatch):
    async def fake_runtime_request(_method, _path, payload=None):
        return {"agents": []}

    async def fake_health_state():
        return "healthy"

    class FakeStateStore:
        def __init__(self):
            self.records = []

        @staticmethod
        def new_cycle_id():
            return "cycle-x"

        @staticmethod
        def build_record(**kwargs):
            return kwargs

        def append_state_record(self, record):
            self.records.append(record)

    store = FakeStateStore()

    monkeypatch.setattr(status_read_model, "_runtime_request", fake_runtime_request)
    monkeypatch.setattr(status_read_model, "_runtime_health_state", fake_health_state)
    monkeypatch.setattr(status_read_model, "build_metrics_index", lambda: {})
    monkeypatch.setattr(status_read_model, "_get_agent_routing_state", lambda: type("RouteState", (), {"routing_enabled": staticmethod(lambda _f: False)})())
    monkeypatch.setattr(status_read_model, "_read_family_window_summary", lambda: (None, "none", "summary_contract_invalid"))
    monkeypatch.setattr(
        status_read_model,
        "_get_compile_store",
        lambda: type(
            "CompileStore",
            (),
            {"read_recent_compile_events": staticmethod(lambda limit=5000, window_minutes=30: [])},
        )(),
    )
    monkeypatch.setattr(status_read_model, "_get_data_lifecycle_state_store", lambda: store)
    monkeypatch.setattr(status_read_model, "_diag_last_degraded_record_ts", 0.0)

    _ = asyncio.run(status_read_model.build_control_cards())
    assert len(store.records) == 1
    assert store.records[0]["status"] == "degraded"
    assert store.records[0]["error"] == "summary_contract_invalid"


def test_summary_builder_maps_cc_haha_meter_to_claude_code_family():
    now = datetime.now(timezone.utc)
    meter = Meter(
        request_id="req-cc-haha-meter-1",
        agent="cc-haha",
        timestamp=now.isoformat(),
        baseline_tokens_estimate=100,
        saved_tokens_estimate=30,
    )
    payload = summary_builder.build_family_window_summary(
        meters=[meter],
        compile_rows_30m=[],
        compile_rows_24h=[],
        proxy_rows_30m=[],
        now_utc=now,
    )
    families = payload["families"]
    assert "claude_code" in families
    assert "cc-haha" not in families
    assert families["claude_code"]["metrics_24h"]["observed_requests_24h"] >= 1


def test_summary_builder_maps_cc_haha_compile_rows_to_claude_code_family():
    now = datetime.now(timezone.utc)
    compile_rows = [
        {
            "agent_id": "cc-haha",
            "compile_status": "compile_success",
            "compile_reason": "runtime_compile",
            "timestamp": now.timestamp(),
        }
    ]
    payload = summary_builder.build_family_window_summary(
        meters=[],
        compile_rows_30m=compile_rows,
        compile_rows_24h=compile_rows,
        proxy_rows_30m=[],
        now_utc=now,
    )
    families = payload["families"]
    assert "claude_code" in families
    assert "cc-haha" not in families
    assert families["claude_code"]["compile_30m"]["proxied_requests"] == 1
    assert families["claude_code"]["compile_24h"]["proxied_requests"] == 1
