import importlib
from datetime import datetime, timezone
from typing import Optional


resolver = importlib.import_module("5_connectors.adapter.application.status_read_model_meter_read_resolver")
v2_compute = importlib.import_module("4_core.logic.v2_compute")
meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _payload(
    request_id: str,
    *,
    agent: str = "openclaw",
    timestamp: Optional[str] = None,
):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    meter = v2_compute.generate_meter_artifact(
        request_id=request_id,
        tenant="all",
        user="u1",
        agent=agent,
        client="openclaw",
        query="query",
        selected_memories=[{"content": "m1"}],
    )
    payload = meter.to_dict()
    payload["timestamp"] = timestamp
    return payload


def _family_match_fn(meter, family_id: str) -> bool:
    agent = (getattr(meter, "agent", "") or "").lower()
    if agent == "cc-haha":
        agent = "claude_code"
    return agent == family_id


def test_sqlite_hit_returns_sqlite_source(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter(_payload("req-status-sqlite", agent="openclaw"))

    result = resolver.resolve_status_read_model_meters(
        family_id="openclaw",
        window_minutes=60,
        legacy_collect_fn=lambda _family, _window: [],
        family_match_fn=_family_match_fn,
    )
    assert [m.request_id for m in result.meters] == ["req-status-sqlite"]
    assert result.source == "sqlite"
    assert result.degraded is False


def test_sqlite_miss_fallback_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    legacy_meter_cls = importlib.import_module("5_connectors.adapter.infrastructure.meter_store").TokenSavingsMeter
    legacy_meter = legacy_meter_cls(**_payload("req-status-legacy", agent="openclaw"))

    result = resolver.resolve_status_read_model_meters(
        family_id="openclaw",
        window_minutes=60,
        legacy_collect_fn=lambda _family, _window: [legacy_meter],
        family_match_fn=_family_match_fn,
    )
    assert [m.request_id for m in result.meters] == ["req-status-legacy"]
    assert result.source == "legacy_fallback"
    assert result.degraded is True
    assert result.degraded_reason == "sqlite_miss"


def test_sqlite_malformed_fallback_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter({"request_id": "req-malformed", "timestamp": datetime.now(timezone.utc).isoformat()})
    legacy_meter_cls = importlib.import_module("5_connectors.adapter.infrastructure.meter_store").TokenSavingsMeter
    legacy_meter = legacy_meter_cls(**_payload("req-status-legacy-2", agent="openclaw"))

    result = resolver.resolve_status_read_model_meters(
        family_id="openclaw",
        window_minutes=60,
        legacy_collect_fn=lambda _family, _window: [legacy_meter],
        family_match_fn=_family_match_fn,
    )
    assert [m.request_id for m in result.meters] == ["req-status-legacy-2"]
    assert result.source == "legacy_fallback"
    assert result.degraded_reason == "sqlite_payload_malformed"


def test_legacy_miss_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    result = resolver.resolve_status_read_model_meters(
        family_id="openclaw",
        window_minutes=60,
        legacy_collect_fn=lambda _family, _window: [],
        family_match_fn=_family_match_fn,
    )
    assert result.meters == []
    assert result.source == "sqlite"
    assert result.degraded is False


def test_cc_haha_alias_matches_claude_code_family(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(tmp_path / "meter_store.sqlite3"))
    monkeypatch.setenv(resolver.READ_PATH_ENV, resolver.MODE_SQLITE_FIRST)
    meter_store_v2.upsert_meter(
        _payload(
            "req-status-cc-haha",
            agent="cc-haha",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    )
    result = resolver.resolve_status_read_model_meters(
        family_id="claude_code",
        window_minutes=60,
        legacy_collect_fn=lambda _family, _window: [],
        family_match_fn=_family_match_fn,
    )
    assert [m.request_id for m in result.meters] == ["req-status-cc-haha"]
