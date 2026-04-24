import importlib
import types
from unittest import mock
from typing import Optional


status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")


class _DummyConfig:
    enable_rate_limit = True
    rate_limit_per_minute = 60
    memory_backend_url = ""


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
    def __init__(
        self,
        request_id: str,
        *,
        baseline_tokens: int = 100,
        actual_tokens: int = 40,
        saved_tokens_estimate: Optional[int] = None,
        savings_ratio: Optional[float] = None,
        include_trace: bool = True,
    ):
        self.request_id = request_id
        self.timestamp = "2026-04-24T00:00:00Z"
        self.agent = "claude_code"
        self.task_type = "decision"
        self.query = "check evidence contract"
        self.baseline_tokens_estimate = baseline_tokens
        self.actual_tokens_estimate = actual_tokens
        self.saved_tokens_estimate = (
            saved_tokens_estimate
            if saved_tokens_estimate is not None
            else (baseline_tokens - actual_tokens)
        )
        self.savings_ratio = (
            savings_ratio
            if savings_ratio is not None
            else (
                round(self.saved_tokens_estimate / baseline_tokens, 3)
                if baseline_tokens > 0
                else 0.0
            )
        )
        self.candidate_memories = [{"content": "memory-a", "score": 0.8}]
        self.dropped_memories = []
        self.context_bypass = False
        self.packed_memory_count = 1
        self.local_cards_used = 1
        self.remote_used_count = 0

        self.identity_spine = {
            "tenant_id": "tenant-a",
            "family_id": "claude_code",
            "instance_id": "claude-instance-a",
            "window_id": "window-a",
            "session_id": "session-a",
            "request_id": request_id,
            "raw_agent_id": "claude_code",
        }
        primary_domain = {
            "domain_id": "tenant-a:instance_private:claude-instance-a",
            "tenant_id": "tenant-a",
            "scope_type": "instance_private",
            "scope_key": "claude-instance-a",
            "sharing_mode": "isolated",
        }
        self.access_plan = {
            "identity": self.identity_spine,
            "read_domains": [primary_domain],
            "primary_write_domain": primary_domain,
            "secondary_write_domains": [],
            "allow_secondary_writes": False,
            "sharing_policy_source": "ingress_private_first",
        }
        self.enforcement_trace = (
            {
                "planned_read_domains": [primary_domain],
                "planned_write_domains": [primary_domain],
                "actual_enforced_domains": [
                    {
                        "domain_id": primary_domain["domain_id"],
                        "operation": "search",
                        "decision": "applied",
                        "result_count": 1,
                    }
                ],
            }
            if include_trace
            else None
        )

    def to_dict(self):
        payload = {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "task_type": self.task_type,
            "query": self.query,
            "baseline_tokens_estimate": self.baseline_tokens_estimate,
            "actual_tokens_estimate": self.actual_tokens_estimate,
            "saved_tokens_estimate": self.saved_tokens_estimate,
            "savings_ratio": self.savings_ratio,
            "candidate_memories": self.candidate_memories,
            "dropped_memories": self.dropped_memories,
            "context_bypass": self.context_bypass,
            "packed_memory_count": self.packed_memory_count,
            "local_cards_used": self.local_cards_used,
            "remote_used_count": self.remote_used_count,
            "identity_spine": self.identity_spine,
            "read_domains": self.access_plan["read_domains"],
            "primary_write_domain": self.access_plan["primary_write_domain"],
            "secondary_write_domains": self.access_plan["secondary_write_domains"],
            "sharing_policy_source": self.access_plan["sharing_policy_source"],
            "access_plan": self.access_plan,
        }
        if isinstance(self.enforcement_trace, dict):
            payload["enforcement_trace"] = self.enforcement_trace
            payload["actual_enforcement"] = self.enforcement_trace
        return payload


def _configure(get_meter_fn):
    status_read_model.configure_diagnostics_read_model(
        config_obj=_DummyConfig(),
        get_backend_fn=lambda: None,
        get_dedup_cache_fn=lambda: _DummyDedupCache(),
        rate_limiter=_DummyRateLimiter(),
        adapter_hostname="test-host",
        adapter_started_at="2026-04-24T00:00:00Z",
        agent_metrics_module=_DummyAgentMetrics(),
        agent_identity_module=_DummyAgentIdentity(),
        get_meter_fn=get_meter_fn,
        support_schema_version="v1",
        support_error_catalog={},
    )


def _build_payload(request_id: str, meter: _DummyMeter):
    _configure(lambda rid: meter if rid == request_id else None)
    fake_trace_store = types.SimpleNamespace(get_trace_dict=lambda rid: {"trace_id": rid, "stages": []})
    fake_compile_store = types.SimpleNamespace(read_recent_compile_events=lambda limit=5000: [{"request_id": request_id, "task_type": "decision"}])
    with mock.patch.dict(
        "sys.modules",
        {
            "5_connectors.adapter.infrastructure.trace_store": fake_trace_store,
            "5_connectors.adapter.infrastructure.compile_store": fake_compile_store,
        },
    ):
        return status_read_model.build_request_evidence_payload(request_id)


def test_request_evidence_contract_separates_planned_and_actual_surfaces():
    request_id = "req-evidence-separation"
    meter = _DummyMeter(request_id)
    payload = _build_payload(request_id, meter)

    assert payload["access_plan"]["primary_write_domain"]["scope_type"] == "instance_private"
    assert "actual_enforced_domains" not in payload["access_plan"]
    assert isinstance(payload["enforcement_trace"], dict)
    assert isinstance(payload["actual_enforcement"], dict)
    assert payload["actual_enforcement"]["actual_enforced_domains"][0]["operation"] == "search"


def test_request_evidence_contract_marks_unavailable_when_runtime_trace_missing():
    request_id = "req-evidence-no-trace"
    meter = _DummyMeter(request_id, include_trace=False)
    payload = _build_payload(request_id, meter)

    assert payload["enforcement_trace"] is None
    assert payload["actual_enforcement"]["status"] == "unavailable"
    assert payload["actual_enforcement"]["reason"] == "runtime_enforcement_trace_unavailable"


def test_request_evidence_and_meter_keep_planned_actual_contract_consistent():
    request_id = "req-meter-consistency"
    meter = _DummyMeter(request_id, baseline_tokens=140, actual_tokens=90)
    meter_dict = meter.to_dict()
    payload = _build_payload(request_id, meter)

    assert payload["request"]["request_id"] == request_id
    assert payload["request"]["identity"]["family_id"] == meter_dict["identity_spine"]["family_id"]
    assert payload["access_plan"] == meter_dict["access_plan"]
    assert payload["actual_enforcement"] == meter_dict["enforcement_trace"]

    assert payload["context"]["before_tokens"] == meter_dict["baseline_tokens_estimate"]
    assert payload["context"]["after_tokens"] == meter_dict["actual_tokens_estimate"]
    assert payload["context"]["saved_tokens"] == meter_dict["saved_tokens_estimate"]
    assert payload["context"]["savings_ratio"] == meter_dict["savings_ratio"]


def test_token_saving_fields_remain_recordable_and_negative_is_marked_not_effective():
    request_id = "req-negative-saving"
    meter = _DummyMeter(
        request_id,
        baseline_tokens=80,
        actual_tokens=100,
        saved_tokens_estimate=-20,
        savings_ratio=-0.25,
    )
    payload = _build_payload(request_id, meter)

    # meter-side raw evidence stays readable for post-hoc reasoning
    meter_dict = meter.to_dict()
    assert meter_dict["saved_tokens_estimate"] == -20
    assert meter_dict["baseline_tokens_estimate"] == 80
    assert meter_dict["actual_tokens_estimate"] == 100

    # request_evidence remains explainable for templates and marks no optimization
    assert payload["context"]["before_tokens"] == 80
    assert payload["context"]["after_tokens"] == 100
    assert payload["context"]["saved_tokens"] == 0
    assert payload["context"]["context_state"] == "traffic_but_no_optimization"


def test_quality_and_non_interference_templates_can_reference_required_fields():
    request_id = "req-template-fields"
    meter = _DummyMeter(request_id)
    payload = _build_payload(request_id, meter)

    assert payload["request"]["request_id"] == request_id
    assert payload["request"]["agent_family"] == "claude_code"
    assert payload["request"]["identity"]["instance_id"] == "claude-instance-a"

    assert isinstance(payload["access_plan"], dict)
    assert isinstance(payload["actual_enforcement"], dict)

    assert "before_tokens" in payload["context"]
    assert "after_tokens" in payload["context"]
    assert "saved_tokens" in payload["context"]
    assert "savings_ratio" in payload["context"]

    assert "request_status" in payload["status"]
    assert "bypass" in payload["status"]
    assert "failure_stage" in payload["status"]
