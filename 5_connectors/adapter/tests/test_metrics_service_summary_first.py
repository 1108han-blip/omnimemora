import importlib
from datetime import datetime, timedelta, timezone


metrics_service = importlib.import_module("5_connectors.adapter.metrics_service")
summary_builder = importlib.import_module("5_connectors.adapter.data_lifecycle.summary_builder")
request_classifier = importlib.import_module("5_connectors.adapter.request_classifier")


class Meter:
    def __init__(
        self,
        *,
        request_id: str,
        timestamp: str,
        query: str,
        baseline_tokens_estimate: int,
        actual_tokens_estimate: int,
        saved_tokens_estimate: int,
        packed_memory_count: int,
        local_cards_used: int,
        remote_used_count: int,
        agent: str = "openclaw",
        savings_ratio: float = 0.0,
        task_type: str = "implementation",
    ) -> None:
        self.request_id = request_id
        self.timestamp = timestamp
        self.query = query
        self.baseline_tokens_estimate = baseline_tokens_estimate
        self.actual_tokens_estimate = actual_tokens_estimate
        self.saved_tokens_estimate = saved_tokens_estimate
        self.packed_memory_count = packed_memory_count
        self.local_cards_used = local_cards_used
        self.remote_used_count = remote_used_count
        self.agent = agent
        self.savings_ratio = savings_ratio
        self.context_bypass = False
        self.task_type = task_type


def test_metrics_summary_first_uses_dlp_summary_without_legacy(monkeypatch):
    expected_all = {"token_saving_ratio": 0.5, "tokens_saved": 50, "request_count": 2, "avg_context_reduction": 0.4}
    expected_24h = {
        "token_saving_ratio": 0.6,
        "tokens_saved": 60,
        "request_count": 3,
        "avg_context_reduction": 0.3,
        "period": "24h",
    }
    expected_core = {
        "period": "24h",
        "observed_request_count": 3,
        "non_value_count": 1,
        "internal_or_wrapper_count": 0,
        "cards": {
            "real_requests": {"count": 2, "ratio": 0.6667},
            "context_compression": {"ratio": 0.4, "baseline_tokens": 100, "actual_tokens": 60},
            "memory_enhancement": {"rate": 0.5, "memory_count": 3},
            "token_savings": {"ratio": 0.4, "saved_tokens": 40},
        },
    }

    def fake_extract(tenant: str, key: str):
        assert tenant == "all"
        if key == "metrics_summary_all":
            return expected_all
        if key == "metrics_summary_24h":
            return expected_24h
        if key == "core_capabilities_24h":
            return expected_core
        return None

    monkeypatch.setattr(metrics_service, "_extract_summary_kpi_block", fake_extract)
    monkeypatch.setattr(
        metrics_service,
        "_compute_metrics_summary_legacy",
        lambda _tenant: (_ for _ in ()).throw(AssertionError("legacy should not be called")),
    )
    monkeypatch.setattr(
        metrics_service,
        "_compute_metrics_summary_24h_legacy",
        lambda _tenant: (_ for _ in ()).throw(AssertionError("legacy should not be called")),
    )
    monkeypatch.setattr(
        metrics_service,
        "_compute_core_capabilities_legacy",
        lambda _tenant: (_ for _ in ()).throw(AssertionError("legacy should not be called")),
    )

    assert metrics_service.compute_metrics_summary("all") == expected_all
    assert metrics_service.compute_metrics_summary_24h("all") == expected_24h
    assert metrics_service.compute_core_capabilities("all") == expected_core


def test_metrics_summary_first_does_not_trigger_metrics_meter_resolver(monkeypatch):
    monkeypatch.setattr(
        metrics_service._metrics_read_resolver,
        "resolve_metrics_meters",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("resolver should not be called on summary hit")),
    )
    monkeypatch.setattr(
        metrics_service,
        "_extract_summary_kpi_block",
        lambda tenant, key: {"request_count": 1} if tenant == "all" and key == "metrics_summary_all" else None,
    )
    payload = metrics_service.compute_metrics_summary("all")
    assert payload["request_count"] == 1


def test_metrics_summary_fallback_records_metrics_read_degraded(monkeypatch):
    degraded_reasons = []
    monkeypatch.setattr(metrics_service, "_read_dlp_kpi_summary_payload", lambda: (None, "none", "summary_expired"))
    monkeypatch.setattr(metrics_service, "_record_metrics_degraded_path", lambda reason: degraded_reasons.append(reason))
    monkeypatch.setattr(
        metrics_service,
        "_compute_metrics_summary_legacy",
        lambda _tenant: {"token_saving_ratio": 0.0, "tokens_saved": 0, "request_count": 0, "avg_context_reduction": 0.0},
    )

    payload = metrics_service.compute_metrics_summary("all")
    assert payload["request_count"] == 0
    assert degraded_reasons == ["summary_expired"]


def test_summary_and_legacy_paths_match_key_kpi_fields(monkeypatch):
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=25)).isoformat()
    within_ts = (now - timedelta(minutes=20)).isoformat()
    meters = [
        Meter(
            request_id="req-1",
            timestamp=within_ts,
            query="Implement endpoint",
            baseline_tokens_estimate=100,
            actual_tokens_estimate=70,
            saved_tokens_estimate=30,
            packed_memory_count=2,
            local_cards_used=1,
            remote_used_count=0,
            savings_ratio=0.3,
        ),
        Meter(
            request_id="req-2",
            timestamp=within_ts,
            query="Analyze logs",
            baseline_tokens_estimate=200,
            actual_tokens_estimate=120,
            saved_tokens_estimate=80,
            packed_memory_count=1,
            local_cards_used=1,
            remote_used_count=0,
            savings_ratio=0.4,
        ),
        Meter(
            request_id="req-task-non-value",
            timestamp=within_ts,
            query="Task without memory value path",
            baseline_tokens_estimate=90,
            actual_tokens_estimate=90,
            saved_tokens_estimate=0,
            packed_memory_count=0,
            local_cards_used=0,
            remote_used_count=0,
            savings_ratio=0.0,
        ),
        Meter(
            request_id="req-old",
            timestamp=old_ts,
            query="Older request",
            baseline_tokens_estimate=150,
            actual_tokens_estimate=110,
            saved_tokens_estimate=40,
            packed_memory_count=1,
            local_cards_used=1,
            remote_used_count=0,
            savings_ratio=0.266,
        ),
    ]

    summary_payload = summary_builder.build_family_window_summary(
        meters=meters,
        compile_rows_30m=[],
        compile_rows_24h=[],
        proxy_rows_30m=[],
        now_utc=now,
        is_default_overview_request=request_classifier.is_default_overview_request,
        is_value_qualified=request_classifier.is_value_qualified,
        is_task_non_value=request_classifier.is_task_non_value,
        collapse_retry_bursts=request_classifier.collapse_retry_bursts,
    )

    monkeypatch.setattr(metrics_service, "_collect_meters", lambda _tenant: list(meters))
    monkeypatch.setattr(
        metrics_service,
        "_collect_meters_24h",
        lambda _tenant: [m for m in meters if m.timestamp != old_ts],
    )
    monkeypatch.setattr(metrics_service, "_extract_summary_kpi_block", lambda tenant, key: summary_payload.get(key) if tenant == "all" else None)

    summary_all = metrics_service.compute_metrics_summary("all")
    summary_24h = metrics_service.compute_metrics_summary_24h("all")
    summary_core = metrics_service.compute_core_capabilities("all")

    legacy_all = metrics_service._compute_metrics_summary_legacy("all")
    legacy_24h = metrics_service._compute_metrics_summary_24h_legacy("all")
    legacy_core = metrics_service._compute_core_capabilities_legacy("all")

    assert summary_all == legacy_all
    assert summary_24h == legacy_24h
    assert summary_core == legacy_core


def test_summary_fallback_path_uses_resolver_meters(monkeypatch):
    now = datetime.now(timezone.utc)
    meter = Meter(
        request_id="req-fallback",
        timestamp=now.isoformat(),
        query="Implement endpoint",
        baseline_tokens_estimate=100,
        actual_tokens_estimate=70,
        saved_tokens_estimate=30,
        packed_memory_count=1,
        local_cards_used=1,
        remote_used_count=0,
        savings_ratio=0.3,
    )

    class Result:
        meters = [meter]
        mode = "sqlite_first_legacy_fallback"
        source = "sqlite"
        degraded = False
        degraded_reason = None

    monkeypatch.setattr(metrics_service, "_extract_summary_kpi_block", lambda _tenant, _key: None)
    monkeypatch.setattr(
        metrics_service._metrics_read_resolver,
        "resolve_metrics_meters",
        lambda **_kwargs: Result(),
    )
    payload = metrics_service.compute_metrics_summary("all")
    assert payload["request_count"] == 1
    assert payload["tokens_saved"] == 30


def test_system_reminder_only_request_is_wrapper_internal(monkeypatch):
    now = datetime.now(timezone.utc)
    wrapper = Meter(
        request_id="req-wrapper",
        timestamp=now.isoformat(),
        query="<system-reminder>As you answer the user's questions, use this context.</system-reminder>",
        baseline_tokens_estimate=1000,
        actual_tokens_estimate=10,
        saved_tokens_estimate=990,
        packed_memory_count=0,
        local_cards_used=0,
        remote_used_count=0,
        agent="claude_code",
        savings_ratio=0.99,
    )

    monkeypatch.setattr(metrics_service, "_collect_meters_24h", lambda _tenant: [wrapper])
    payload = metrics_service.get_recent_requests("all", limit=10, include_internal=True, value_qualified_only=False)
    assert payload[0]["request_class"] == "internal"
    assert payload[0]["diagnostic_label"] == "wrapper/context envelope"
    assert payload[0]["user_visible_query"] == ""
    assert payload[0]["display_savings_as_value"] is False

    visible_payload = metrics_service.get_recent_requests("all", limit=10, include_internal=False, value_qualified_only=False)
    assert visible_payload == []


def test_non_value_recent_request_explains_missing_value_path(monkeypatch):
    now = datetime.now(timezone.utc)
    meter = Meter(
        request_id="req-non-value",
        timestamp=now.isoformat(),
        query="Explain current dashboard numbers",
        baseline_tokens_estimate=1000,
        actual_tokens_estimate=10,
        saved_tokens_estimate=990,
        packed_memory_count=0,
        local_cards_used=0,
        remote_used_count=0,
        task_type="unknown",
        savings_ratio=0.99,
    )

    monkeypatch.setattr(metrics_service, "_collect_meters_24h", lambda _tenant: [meter])
    payload = metrics_service.get_recent_requests("all", limit=10, include_internal=False, value_qualified_only=False)
    assert payload[0]["request_class"] == "task_non_value"
    assert "no memory packed" in payload[0]["qualification_reason"]
    assert "task unknown" in payload[0]["qualification_reason"]
    assert "no value path" in payload[0]["qualification_reason"]
    assert payload[0]["value_paths"] == []
    assert payload[0]["display_savings_as_value"] is False


def test_value_qualified_recent_request_lists_value_paths(monkeypatch):
    now = datetime.now(timezone.utc)
    meter = Meter(
        request_id="req-value",
        timestamp=now.isoformat(),
        query="Use the project memory to summarize the current phase",
        baseline_tokens_estimate=1000,
        actual_tokens_estimate=700,
        saved_tokens_estimate=300,
        packed_memory_count=2,
        local_cards_used=1,
        remote_used_count=0,
        savings_ratio=0.3,
    )

    monkeypatch.setattr(metrics_service, "_collect_meters_24h", lambda _tenant: [meter])
    payload = metrics_service.get_recent_requests("all", limit=10, include_internal=False, value_qualified_only=True)
    assert payload[0]["request_class"] == "value_qualified"
    assert payload[0]["value_paths"]
    assert "packed_memory" in payload[0]["value_paths"]
    assert payload[0]["display_savings_as_value"] is True
