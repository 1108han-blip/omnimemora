import importlib
import sqlite3

import pytest


meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _sample_payload(request_id: str = "req-1") -> dict:
    return {
        "request_id": request_id,
        "tenant": "all",
        "agent": "claude_code",
        "family_id": "claude_code",
        "timestamp": "2026-04-25T12:00:00+00:00",
        "task_type": "coding",
        "context_state": "normal",
        "baseline_tokens_estimate": 1200,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 300,
        "savings_ratio": 0.25,
        "payload_note": "roundtrip",
    }


def test_schema_init_is_idempotent(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))

    meter_store_v2.init_schema()
    meter_store_v2.init_schema()

    assert sqlite_path.exists()
    meta = meter_store_v2.get_meta()
    assert meta["mode"] == "dual_write_observe_only"
    assert meta["schema_version"] == "meter-store-v2-schema-1"


def test_upsert_and_payload_roundtrip(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))

    payload = _sample_payload("req-roundtrip")
    meter_store_v2.upsert_meter(payload)
    loaded = meter_store_v2.get_meter("req-roundtrip")

    assert loaded is not None
    assert loaded["request_id"] == "req-roundtrip"
    assert loaded["saved_tokens_estimate"] == 300
    assert meter_store_v2.count_records() == 1


def test_index_contract_exists(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    meter_store_v2.init_schema()

    with sqlite3.connect(str(sqlite_path)) as conn:
        rows = conn.execute("PRAGMA index_list('meter_records')").fetchall()
    index_names = {row[1] for row in rows}
    assert "idx_meter_records_request_id" in index_names
    assert "idx_meter_records_tenant_ts" in index_names
    assert "idx_meter_records_family_ts" in index_names
    assert "idx_meter_records_agent_ts" in index_names
    assert "idx_meter_records_timestamp" in index_names


def test_malformed_payload_rejected(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))

    with pytest.raises(ValueError):
        meter_store_v2.upsert_meter({"tenant": "all"})
    assert meter_store_v2.count_records() == 0
