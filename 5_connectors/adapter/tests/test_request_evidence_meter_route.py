import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


diagnostics_surface = importlib.import_module("5_connectors.adapter.diagnostics_surface")
status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")
v2_compute = importlib.import_module("4_core.logic.v2_compute")
meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
req_evidence_resolver = importlib.import_module(
    "5_connectors.adapter.application.request_evidence_meter_read_resolver"
)


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


def _make_meter(request_id: str):
    return v2_compute.generate_meter_artifact(
        request_id=request_id,
        tenant="all",
        user="u1",
        agent="claude_code",
        client="openclaw",
        query="query",
        selected_memories=[{"content": "m1"}],
    )


def _configure(get_meter_fn):
    status_read_model.configure_diagnostics_read_model(
        config_obj=_DummyConfig(),
        get_backend_fn=lambda: None,
        get_dedup_cache_fn=lambda: _DummyDedupCache(),
        rate_limiter=_DummyRateLimiter(),
        adapter_hostname="test-host",
        adapter_started_at="2026-04-25T00:00:00Z",
        agent_metrics_module=_DummyAgentMetrics(),
        agent_identity_module=_DummyAgentIdentity(),
        get_meter_fn=get_meter_fn,
        support_schema_version="v1",
        support_error_catalog={},
    )


def test_request_evidence_route_shadow_passes_when_sqlite_and_legacy_match(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(req_evidence_resolver.READ_PATH_ENV, req_evidence_resolver.MODE_SQLITE_FIRST)
    request_id = "req-res004-shadow-pass"
    meter = _make_meter(request_id)
    meter_store_v2.upsert_meter(meter.to_dict())
    _configure(lambda rid: meter if rid == request_id else None)

    app = FastAPI()
    app.include_router(diagnostics_surface.router)
    client = TestClient(app)

    response = client.get(f"/debug/request_evidence?request_id={request_id}")
    assert response.status_code == 200
    assert response.headers["x-omnimemora-request-evidence-meter-read-source"] == "sqlite"
    assert response.headers["x-omnimemora-request-evidence-meter-shadow-status"] == "passed"
    assert response.json()["request_evidence_meter_shadow"]["status"] == "passed"


def test_request_evidence_route_sqlite_miss_fallback_legacy_and_shadow_degraded(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(req_evidence_resolver.READ_PATH_ENV, req_evidence_resolver.MODE_SQLITE_FIRST)
    request_id = "req-res004-fallback"
    meter = _make_meter(request_id)
    _configure(lambda rid: meter if rid == request_id else None)

    app = FastAPI()
    app.include_router(diagnostics_surface.router)
    client = TestClient(app)

    response = client.get(f"/debug/request_evidence?request_id={request_id}")
    assert response.status_code == 200
    assert response.headers["x-omnimemora-request-evidence-meter-read-source"] == "legacy_fallback"
    assert response.headers["x-omnimemora-request-evidence-meter-shadow-status"] == "degraded"
    assert response.json()["request_evidence_meter_shadow"]["status"] == "degraded"


def test_request_evidence_route_returns_404_when_both_sources_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(req_evidence_resolver.READ_PATH_ENV, req_evidence_resolver.MODE_SQLITE_FIRST)
    _configure(lambda _rid: None)

    app = FastAPI()
    app.include_router(diagnostics_surface.router)
    client = TestClient(app)

    response = client.get("/debug/request_evidence?request_id=req-missing")
    assert response.status_code == 404


def test_context_diff_still_uses_legacy_meter_getter(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(req_evidence_resolver.READ_PATH_ENV, req_evidence_resolver.MODE_SQLITE_FIRST)
    request_id = "req-res004-context-diff"

    legacy_meter = _make_meter(request_id)
    sqlite_payload = legacy_meter.to_dict()
    sqlite_payload["baseline_tokens_estimate"] = 999
    sqlite_payload["actual_tokens_estimate"] = 888
    meter_store_v2.upsert_meter(sqlite_payload)

    _configure(lambda rid: legacy_meter if rid == request_id else None)
    payload = status_read_model.build_context_diff_payload(request_id)
    assert payload["before_tokens"] != 999
    assert payload["after_tokens"] != 888

