import importlib


access_plan = importlib.import_module("5_connectors.adapter.application.access_plan")


def test_build_identity_and_access_plan_defaults_to_instance_private():
    hints = {
        "tenant_id": "tenant-a",
        "raw_agent_id": "codex-cli",
        "instance_id": "codex-instance-1",
    }
    result = access_plan.build_identity_and_access_plan(
        request_id="req-1",
        family_id="codex_cli",
        hints=hints,
    )

    assert result["identity_spine"]["tenant_id"] == "tenant-a"
    assert result["identity_spine"]["family_id"] == "codex_cli"
    assert result["identity_spine"]["instance_id"] == "codex-instance-1"
    assert result["primary_write_domain"]["scope_type"] == "instance_private"
    assert len(result["read_domains"]) == 1
    assert result["secondary_write_domains"] == []


def test_build_identity_and_access_plan_adds_workspace_domain_and_controlled_promotion():
    hints = {
        "tenant_id": "tenant-a",
        "raw_agent_id": "openclaw-agent",
        "instance_id": "openclaw-main",
        "workspace_id": "ws-task-9",
        "sharing_mode": "shared",
        "allow_shared_write": True,
    }
    result = access_plan.build_identity_and_access_plan(
        request_id="req-2",
        family_id="openclaw",
        hints=hints,
    )

    assert any(d["scope_type"] == "workspace_shared" for d in result["read_domains"])
    assert any(d["scope_type"] == "workspace_shared" for d in result["secondary_write_domains"])
    assert result["access_plan"]["identity"]["request_id"] == "req-2"


def test_extract_hints_accepts_legacy_omnimemora_headers():
    class _Req:
        headers = {
            "X-OmniMemora-Tenant": "tenant-omni",
            "X-OmniMemora-User": "user-omni",
            "X-OmniMemora-Workspace": "ws-omni",
            "X-OmniMemora-Agent": "openclaw",
            "X-OmniMemora-Sharing-Mode": "shared",
        }
        query_params = {}

    hints = access_plan.extract_hints_from_request(request=_Req(), body={})
    result = access_plan.build_identity_and_access_plan(
        request_id="req-omni-h",
        family_id="openclaw",
        hints=hints,
    )

    assert result["identity_spine"]["tenant_id"] == "tenant-omni"
    assert result["identity_spine"]["instance_id"] == "openclaw"
    assert any(d["scope_type"] == "workspace_shared" for d in result["read_domains"])
