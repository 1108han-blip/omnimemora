import importlib


resolver = importlib.import_module("5_connectors.adapter.application.request_meter_read_resolver")
v2_compute = importlib.import_module("4_core.logic.v2_compute")
meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


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


def test_sqlite_hit_returns_sqlite_source(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    payload = _meter("req-sqlite-hit").to_dict()
    meter_store_v2.upsert_meter(payload)

    result = resolver.resolve_request_meter("req-sqlite-hit", legacy_get_meter_fn=lambda _rid: None)
    assert result.meter is not None
    assert result.source == "sqlite"
    assert result.degraded is False


def test_sqlite_miss_fallback_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    legacy_meter = _meter("req-fallback")

    result = resolver.resolve_request_meter("req-fallback", legacy_get_meter_fn=lambda _rid: legacy_meter)
    assert result.meter is not None
    assert result.source == "legacy_fallback"
    assert result.degraded is True
    assert result.degraded_reason == "sqlite_miss"


def test_sqlite_malformed_fallback_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter({"request_id": "req-malformed", "tenant": "all", "timestamp": "2026-04-25T00:00:00+00:00"})
    legacy_meter = _meter("req-malformed")

    result = resolver.resolve_request_meter("req-malformed", legacy_get_meter_fn=lambda _rid: legacy_meter)
    assert result.meter is not None
    assert result.source == "legacy_fallback"
    assert result.degraded is True
    assert result.degraded_reason == "sqlite_payload_malformed"


def test_legacy_miss_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)

    result = resolver.resolve_request_meter("req-missing", legacy_get_meter_fn=lambda _rid: None)
    assert result.meter is None
    assert result.degraded is True


def test_legacy_only_mode_uses_legacy_direct(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_LEGACY_ONLY)
    legacy_meter = _meter("req-legacy-only")
    result = resolver.resolve_request_meter("req-legacy-only", legacy_get_meter_fn=lambda _rid: legacy_meter)
    assert result.meter is not None
    assert result.source == "legacy"
    assert result.degraded is False
