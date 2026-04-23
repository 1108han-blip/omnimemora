import importlib


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
