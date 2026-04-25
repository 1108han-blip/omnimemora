import importlib


resolver = importlib.import_module("5_connectors.adapter.application.request_evidence_meter_read_resolver")
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


def test_sqlite_hit_selected_in_sqlite_first_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    payload = _meter("req-res-004-sqlite").to_dict()
    meter_store_v2.upsert_meter(payload)

    result = resolver.resolve_request_evidence_meter(
        "req-res-004-sqlite",
        legacy_get_meter_fn=lambda _rid: None,
    )
    assert result.selected_meter is not None
    assert result.selected_source == "sqlite"
    assert result.degraded is False


def test_sqlite_miss_fallbacks_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    legacy_meter = _meter("req-res-004-fallback")

    result = resolver.resolve_request_evidence_meter(
        "req-res-004-fallback",
        legacy_get_meter_fn=lambda _rid: legacy_meter,
    )
    assert result.selected_meter is not None
    assert result.selected_source == "legacy_fallback"
    assert result.degraded is True
    assert result.degraded_reason == "sqlite_miss"


def test_legacy_only_mode_does_not_force_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_LEGACY_ONLY)
    legacy_meter = _meter("req-res-004-legacy-only")

    result = resolver.resolve_request_evidence_meter(
        "req-res-004-legacy-only",
        legacy_get_meter_fn=lambda _rid: legacy_meter,
    )
    assert result.selected_meter is not None
    assert result.selected_source == "legacy"
    assert result.degraded is False

