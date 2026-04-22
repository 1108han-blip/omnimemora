import importlib
import types
from unittest import mock


status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")


class _DummyConfig:
    enable_rate_limit = True
    rate_limit_per_minute = 60
    viking_url = ""


class _DummyDedupCache:
    def get_stats(self):
        return {"size": 0}


class _DummyRateLimiter:
    def get_current_count(self):
        return 0


class _DummyAgentMetrics:
    def get_live_agents(self, window_minutes=30):
        return []

    def get_agent_metrics(self, agent_id=None, session_id=None):
        return []


class _DummyAgentIdentity:
    def resolve_canonical_agent_id(self, value):
        return value


class _DummyMeter:
    def __init__(self, request_id: str, task_type: str):
        self.request_id = request_id
        self.timestamp = "2026-04-22T00:00:00Z"
        self.agent = "codex_cli"
        self.task_type = task_type
        self.query = "need decision validation"
        self.baseline_tokens_estimate = 100
        self.actual_tokens_estimate = 80
        self.savings_ratio = 0.2
        self.candidate_memories = [{"content": "x", "score": 0.8}]
        self.dropped_memories = []
        self.context_bypass = False
        self.packed_memory_count = 1
        self.local_cards_used = 1
        self.remote_used_count = 0

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "task_type": self.task_type,
            "query": self.query,
            "baseline_tokens_estimate": self.baseline_tokens_estimate,
            "actual_tokens_estimate": self.actual_tokens_estimate,
            "savings_ratio": self.savings_ratio,
            "candidate_memories": self.candidate_memories,
            "dropped_memories": self.dropped_memories,
            "context_bypass": self.context_bypass,
            "packed_memory_count": self.packed_memory_count,
            "local_cards_used": self.local_cards_used,
            "remote_used_count": self.remote_used_count,
        }


def _configure(get_meter_fn):
    status_read_model.configure_diagnostics_read_model(
        config_obj=_DummyConfig(),
        get_backend_fn=lambda: None,
        get_dedup_cache_fn=lambda: _DummyDedupCache(),
        rate_limiter=_DummyRateLimiter(),
        adapter_hostname="test-host",
        adapter_started_at="2026-04-22T00:00:00Z",
        agent_metrics_module=_DummyAgentMetrics(),
        agent_identity_module=_DummyAgentIdentity(),
        get_meter_fn=get_meter_fn,
        support_schema_version="v1",
        support_error_catalog={},
    )


def _build_payload(request_id: str, meter: _DummyMeter, compile_events):
    _configure(lambda rid: meter if rid == request_id else None)
    fake_trace_store = types.SimpleNamespace(get_trace_dict=lambda rid: {"trace_id": rid, "stages": []})
    fake_compile_store = types.SimpleNamespace(read_recent_compile_events=lambda limit=5000: compile_events)
    with mock.patch.dict(
        "sys.modules",
        {
            "5_connectors.adapter.infrastructure.trace_store": fake_trace_store,
            "5_connectors.adapter.infrastructure.compile_store": fake_compile_store,
        },
    ):
        return status_read_model.build_request_evidence_payload(request_id)


def test_request_evidence_returns_real_skill_policy_metadata():
    request_id = "req-policy-meta"
    meter = _DummyMeter(request_id=request_id, task_type="decision")
    payload = _build_payload(
        request_id,
        meter,
        compile_events=[
            {
                "request_id": request_id,
                "skill_suggestions": [],
                "skill_policy_name": "recommendation_local_active",
                "skill_policy_version": "local-default-v1",
                "skill_policy_source": "local_manifest",
                "skill_policy_status": "active",
            }
        ],
    )
    assert payload["skill_policy_name"] == "recommendation_local_active"
    assert payload["skill_policy_version"] == "local-default-v1"
    assert payload["skill_policy_source"] == "local_manifest"
    assert payload["skill_policy_status"] == "active"


def test_request_evidence_without_suggestions_keeps_policy_metadata_stable():
    request_id = "req-no-suggestions"
    meter = _DummyMeter(request_id=request_id, task_type="continuation")
    payload = _build_payload(
        request_id,
        meter,
        compile_events=[
            {
                "request_id": request_id,
                "skill_policy_name": "local_fallback",
                "skill_policy_version": "static_catalog_v1",
                "skill_policy_source": "local_builtin",
                "skill_policy_status": "fallback",
            }
        ],
    )
    assert payload["skill_suggestions"] == []
    assert payload["skill_policy_name"] == "local_fallback"
    assert payload["skill_policy_status"] == "fallback"


def test_request_evidence_implementation_keeps_empty_suggestions_and_policy_status():
    request_id = "req-implementation-policy"
    meter = _DummyMeter(request_id=request_id, task_type="implementation")
    payload = _build_payload(
        request_id,
        meter,
        compile_events=[
            {
                "request_id": request_id,
                "skill_suggestions": [],
                "skill_policy_name": "local_fallback",
                "skill_policy_version": "static_catalog_v1",
                "skill_policy_source": "local_builtin",
                "skill_policy_status": "disabled",
            }
        ],
    )
    assert payload["request"]["task_type"] == "implementation"
    assert payload["skill_suggestions"] == []
    assert payload["skill_policy_status"] == "disabled"
