import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


usage_surface = importlib.import_module("5_connectors.adapter.usage_surface")
v2_compute = importlib.import_module("4_core.logic.v2_compute")


def _meter(request_id: str):
    return v2_compute.generate_meter_artifact(
        request_id=request_id,
        tenant="all",
        user="u1",
        agent="claude_code",
        client="openclaw",
        query="query",
        selected_memories=[{"content": "m1"}],
    )


def _configure(legacy_get_meter):
    usage_surface.configure_usage_surface(
        config_obj=type("Cfg", (), {"omnimemora_access_registry_path": "/tmp/registry.json"})(),
        get_tenant_usage_fn=lambda *_args, **_kwargs: {},
        get_trend_data_fn=lambda *_args, **_kwargs: {},
        get_meter_fn=legacy_get_meter,
    )


def test_token_savings_all_uses_summary_first_fast_path(monkeypatch):
    app = FastAPI()
    app.include_router(usage_surface.router)
    _configure(lambda _rid: None)
    monkeypatch.setattr(
        usage_surface._metrics_service,
        "compute_metrics_summary",
        lambda tenant: {"request_count": 3, "tokens_saved": 90, "token_saving_ratio": 0.3},
    )

    client = TestClient(app)
    response = client.get("/usage/token-savings?tenant=all")

    assert response.status_code == 200
    assert response.json()["read_mode"] == "summary_first"
    assert response.json()["total_requests"] == 3


def test_request_meter_route_uses_resolver_and_headers(monkeypatch):
    app = FastAPI()
    app.include_router(usage_surface.router)
    legacy_meter = _meter("req-1")
    _configure(lambda _rid: legacy_meter)

    class Resolution:
        meter = legacy_meter
        mode = "sqlite_first_legacy_fallback"
        source = "sqlite"

    monkeypatch.setattr(
        usage_surface._request_meter_resolver,
        "resolve_request_meter",
        lambda request_id, legacy_get_meter_fn: Resolution(),
    )

    client = TestClient(app)
    response = client.get("/requests/req-1/meter")
    assert response.status_code == 200
    assert response.headers["x-omnimemora-meter-read-mode"] == "sqlite_first_legacy_fallback"
    assert response.headers["x-omnimemora-meter-read-source"] == "sqlite"
    assert response.json()["request_id"] == "req-1"


def test_request_meter_route_returns_404_when_both_sources_miss(monkeypatch):
    app = FastAPI()
    app.include_router(usage_surface.router)
    _configure(lambda _rid: None)

    class Resolution:
        meter = None
        mode = "sqlite_first_legacy_fallback"
        source = "legacy_fallback"

    monkeypatch.setattr(
        usage_surface._request_meter_resolver,
        "resolve_request_meter",
        lambda request_id, legacy_get_meter_fn: Resolution(),
    )

    client = TestClient(app)
    response = client.get("/requests/missing/meter")
    assert response.status_code == 404
