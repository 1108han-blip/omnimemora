import asyncio
import importlib
import json


def test_main_registers_expected_router_groups():
    """
    Batch 3B assembly smoke:
    verify main.py grouped assembly still registers core router surfaces.
    """
    main_mod = importlib.import_module("5_connectors.adapter.main")
    route_paths = {getattr(route, "path", "") for route in main_mod.app.routes}

    # product data path
    assert "/v1/chat/completions" in route_paths
    assert "/mcp" in route_paths
    assert "/tools/search" in route_paths

    # control plane
    assert "/agents/control" in route_paths

    # read-model / diagnostics
    assert "/compile/status" in route_paths
    assert "/debug/request_evidence" in route_paths
    assert "/usage/token-savings" in route_paths
    assert "/scope/capabilities" in route_paths
    assert "/billing/overview" in route_paths
    assert "/cloud/status" in route_paths


def test_main_support_error_catalog_uses_current_memory_backend_codes():
    main_mod = importlib.import_module("5_connectors.adapter.main")

    assert "ADAPTER_MEMORY_BACKEND_UNAVAILABLE" in main_mod.SUPPORT_ERROR_CATALOG
    assert "ADAPTER_MEMORY_BACKEND_TIMEOUT" in main_mod.SUPPORT_ERROR_CATALOG


def test_default_internal_get_paths_skip_trace_writes():
    main_mod = importlib.import_module("5_connectors.adapter.main")

    class URL:
        path = "/data-lifecycle/status"

    class Request:
        method = "GET"
        url = URL()

    assert main_mod._skip_default_trace_write(Request()) is True

    Request.method = "POST"
    assert main_mod._skip_default_trace_write(Request()) is False

    Request.method = "GET"
    Request.url.path = "/debug/request_evidence"
    assert main_mod._skip_default_trace_write(Request()) is False

    Request.url.path = "/data-lifecycle/meter-storage/status"
    assert main_mod._skip_default_trace_write(Request()) is True

    Request.url.path = "/usage/token-savings"
    assert main_mod._skip_default_trace_write(Request()) is True


def test_diagnostics_health_defaults_to_local_fast_mode():
    diagnostics_surface = importlib.import_module("5_connectors.adapter.diagnostics_surface")

    assert diagnostics_surface.health.__defaults__ == ("local",)


def test_local_usage_status_is_not_quota_observation_path():
    quota_observer = importlib.import_module("5_connectors.adapter.quota_observer")

    assert quota_observer.is_quota_related_path("/usage/token-savings") is False


def test_mcp_tools_list_hides_deprecated_context_tools():
    mcp_surface = importlib.import_module("5_connectors.adapter.mcp_surface")

    tool_names = {tool["name"] for tool in mcp_surface._mcp_tools_payload()["tools"]}

    assert "memory.context" not in tool_names
    assert "memory.recall" not in tool_names
    assert "omnimemora_search_memory" not in tool_names
    assert "memory.search" in tool_names
    assert "memory.write" in tool_names


def test_deprecated_mcp_context_tool_returns_no_packed_context():
    mcp_surface = importlib.import_module("5_connectors.adapter.mcp_surface")

    blocks = asyncio.run(
        mcp_surface._mcp_call_tool("memory.context", {"query": "hello"})
    )

    joined = "\n".join(block["text"] for block in blocks)
    assert "deprecated" in joined
    assert "http://127.0.0.1:18011" in joined
    assert "packed_context" not in joined

    meta = json.loads(blocks[1]["text"])
    assert meta == {
        "status": "deprecated",
        "tool": "memory.context",
        "product_ingress": "http://127.0.0.1:18011",
    }
