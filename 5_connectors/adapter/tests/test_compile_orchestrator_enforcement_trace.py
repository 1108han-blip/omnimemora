import importlib


compile_orchestrator = importlib.import_module("5_connectors.adapter.application.compile_orchestrator")


class _DummyAccessPlan:
    @staticmethod
    def extract_hints_from_request(request=None, body=None):
        return {
            "tenant_id": "tenant-a",
            "raw_agent_id": "openclaw",
            "instance_id": "openclaw-instance",
        }

    @staticmethod
    def build_identity_and_access_plan(*, request_id, family_id, hints, sharing_policy_source):
        identity = {
            "tenant_id": hints.get("tenant_id") or "tenant-a",
            "family_id": family_id,
            "instance_id": hints.get("instance_id") or family_id,
            "window_id": None,
            "session_id": None,
            "request_id": request_id,
            "raw_agent_id": hints.get("raw_agent_id") or family_id,
        }
        primary = {
            "domain_id": "tenant-a:instance_private:openclaw-instance",
            "tenant_id": "tenant-a",
            "scope_type": "instance_private",
            "scope_key": "openclaw-instance",
            "sharing_mode": "isolated",
        }
        return {
            "identity_spine": identity,
            "access_plan": {
                "identity": identity,
                "read_domains": [primary],
                "primary_write_domain": primary,
                "secondary_write_domains": [],
                "allow_secondary_writes": False,
                "sharing_policy_source": sharing_policy_source,
            },
            "tenant_id": "tenant-a",
            "family_id": family_id,
            "instance_id": "openclaw-instance",
            "session_id": None,
            "window_id": None,
            "raw_agent_id": "openclaw",
            "workspace_id": None,
            "primary_write_domain": primary,
            "read_domains": [primary],
            "secondary_write_domains": [],
            "sharing_policy_source": sharing_policy_source,
        }


class _CaptureStore:
    def __init__(self):
        self.meter = None

    def store_meter(self, meter):
        self.meter = meter


def test_persist_gateway_meter_keeps_actual_enforcement_trace_separate_from_access_plan():
    capture = _CaptureStore()

    old_get_meter_store = compile_orchestrator._get_meter_store
    old_get_access_plan = compile_orchestrator._get_access_plan
    try:
        compile_orchestrator._get_meter_store = lambda: capture
        compile_orchestrator._get_access_plan = lambda: _DummyAccessPlan

        compile_orchestrator._persist_gateway_meter(
            request_id="req-enforcement-trace-1",
            agent_id="openclaw",
            route="/llm/chat",
            compile_meta={
                "compile_status": "compile_success",
                "selected_memory_count": 1,
                "original_token_estimate": 120,
                "compiled_token_estimate": 80,
                "enforcement_trace": {
                    "actual_enforced_domains": [
                        {
                            "domain_id": "tenant-a:instance_private:openclaw-instance",
                            "operation": "search",
                            "decision": "applied",
                            "result_count": 1,
                        }
                    ]
                },
            },
            truth_contract={},
            payload={
                "messages": [
                    {"role": "user", "content": "hello"},
                ]
            },
            identity_and_plan=None,
        )
    finally:
        compile_orchestrator._get_meter_store = old_get_meter_store
        compile_orchestrator._get_access_plan = old_get_access_plan

    assert capture.meter is not None
    meter = capture.meter.to_dict()
    assert isinstance(meter.get("access_plan"), dict)
    assert meter["access_plan"]["primary_write_domain"]["scope_type"] == "instance_private"
    assert isinstance(meter.get("enforcement_trace"), dict)
    assert meter["enforcement_trace"]["actual_enforced_domains"][0]["operation"] == "search"
    assert isinstance(meter.get("actual_enforcement"), dict)
    assert meter["actual_enforcement"]["actual_enforced_domains"][0]["decision"] == "applied"
