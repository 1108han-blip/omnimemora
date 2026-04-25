import importlib


resolver = importlib.import_module("5_connectors.adapter.application.metrics_meter_read_resolver")
v2_compute = importlib.import_module("4_core.logic.v2_compute")
meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _meter(request_id: str, *, tenant: str = "all", timestamp: str = "2026-04-25T10:00:00+00:00"):
    m = v2_compute.generate_meter_artifact(
        request_id=request_id,
        tenant=tenant,
        user="u1",
        agent="openclaw",
        client="openclaw",
        query="query",
        selected_memories=[{"content": "m1"}],
    )
    payload = m.to_dict()
    payload["timestamp"] = timestamp
    return payload


def _legacy_collect_factory(rows):
    meter_cls = importlib.import_module("5_connectors.adapter.infrastructure.meter_store").TokenSavingsMeter
    meters = [meter_cls(**row) for row in rows]
    return lambda _tenant: meters


def test_sqlite_hit_with_tenant_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter(_meter("req-a1", tenant="tenant-a"))
    meter_store_v2.upsert_meter(_meter("req-b1", tenant="tenant-b"))

    result = resolver.resolve_metrics_meters(
        tenant="tenant-a",
        since_utc=None,
        limit=100,
        legacy_collect_fn=lambda _tenant: [],
    )
    assert len(result.meters) == 1
    assert result.meters[0].request_id == "req-a1"
    assert result.source == "sqlite"
    assert result.degraded is False


def test_sqlite_hit_with_24h_window(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter(_meter("req-old", timestamp="2026-04-20T10:00:00+00:00"))
    meter_store_v2.upsert_meter(_meter("req-new", timestamp="2026-04-25T10:00:00+00:00"))

    result = resolver.resolve_metrics_meters(
        tenant="all",
        since_utc=datetime(2026, 4, 24, 0, 0, 0, tzinfo=timezone.utc),
        limit=100,
        legacy_collect_fn=lambda _tenant: [],
    )
    assert [m.request_id for m in result.meters] == ["req-new"]


def test_sqlite_miss_fallback_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    legacy_row = _meter("req-legacy-only")
    result = resolver.resolve_metrics_meters(
        tenant="all",
        since_utc=None,
        limit=100,
        legacy_collect_fn=_legacy_collect_factory([legacy_row]),
    )
    assert [m.request_id for m in result.meters] == ["req-legacy-only"]
    assert result.source == "legacy_fallback"
    assert result.degraded is True
    assert result.degraded_reason == "sqlite_miss"


def test_malformed_sqlite_payload_fallback_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    # request_id-only payload is valid for sqlite insert but malformed for TokenSavingsMeter hydration.
    meter_store_v2.upsert_meter({"request_id": "req-bad"})
    legacy_row = _meter("req-good-legacy")
    result = resolver.resolve_metrics_meters(
        tenant="all",
        since_utc=None,
        limit=100,
        legacy_collect_fn=_legacy_collect_factory([legacy_row]),
    )
    assert [m.request_id for m in result.meters] == ["req-good-legacy"]
    assert result.source == "legacy_fallback"
    assert result.degraded_reason == "sqlite_payload_malformed"


def test_tenants_sqlite_hit_and_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter(_meter("req-a", tenant="tenant-a"))
    meter_store_v2.upsert_meter(_meter("req-b", tenant="tenant-b"))
    hit = resolver.resolve_metrics_tenants(legacy_list_tenants_fn=lambda: ["legacy-tenant"])
    assert hit.tenants == ["tenant-a", "tenant-b"]
    assert hit.source == "sqlite"

    # Clear sqlite file to force miss path; legacy should be used.
    (tmp_path / "meter_store.sqlite3").unlink()
    miss = resolver.resolve_metrics_tenants(legacy_list_tenants_fn=lambda: ["legacy-tenant"])
    assert miss.tenants == ["legacy-tenant"]
    assert miss.source == "legacy_fallback"
