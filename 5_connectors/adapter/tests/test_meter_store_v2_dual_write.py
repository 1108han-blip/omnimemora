import importlib
import json


v2_compute = importlib.import_module("4_core.logic.v2_compute")
meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")


def _build_meter(request_id: str):
    return v2_compute.generate_meter_artifact(
        request_id=request_id,
        tenant="all",
        user="u1",
        agent="claude_code",
        client="openclaw",
        query="implement request evidence",
        selected_memories=[{"content": "memory-a"}],
        remote_candidates_considered=8,
        local_cards_used=1,
        packing_enabled=True,
        task_type="implementation",
        context_bypass=False,
        bypassed_context_tokens=0,
        matched_keywords=["implement"],
    )


def _reload_meter_store():
    mod = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
    return importlib.reload(mod)


def test_dual_write_legacy_first_and_mirror_success(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_MODE", "dual_write_observe_only")
    monkeypatch.setenv("OMNIMEMORA_METER_PERSIST_INTERVAL_SECONDS", "0")

    meter_store = _reload_meter_store()
    meter_store_v2.init_schema()

    meter_store.store_meter(_build_meter("req-dual-success").to_dict())

    index_path = data_dir / "meters_index.json"
    assert index_path.exists()
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert "req-dual-success" in index_payload
    assert meter_store_v2.count_records() == 1


def test_dual_write_mirror_failure_is_non_fatal_and_ledgered(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dlp_dir = tmp_path / "dlp"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_DLP_DIR", str(dlp_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_MODE", "dual_write_observe_only")
    monkeypatch.setenv("OMNIMEMORA_METER_PERSIST_INTERVAL_SECONDS", "0")

    meter_store = _reload_meter_store()

    original = meter_store_v2.upsert_meter
    meter_store_v2.upsert_meter = lambda payload: (_ for _ in ()).throw(RuntimeError("mirror down"))
    try:
        meter_store.store_meter(_build_meter("req-dual-fail").to_dict())
    finally:
        meter_store_v2.upsert_meter = original

    index_path = data_dir / "meters_index.json"
    assert index_path.exists()
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert "req-dual-fail" in index_payload
    assert meter_store_v2.count_write_errors() >= 1
    latest = meter_store_v2.latest_write_error()
    assert latest is not None
    assert latest["error_type"] == "dual_write_mirror_failed"

    records = state_store.read_recent_records(limit=20)
    assert any(str(item.get("trigger")) == "meter_store_v2_dual_write" for item in records)


def test_dual_write_accepts_dict_and_dataclass(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_MODE", "dual_write_observe_only")
    monkeypatch.setenv("OMNIMEMORA_METER_PERSIST_INTERVAL_SECONDS", "0")

    meter_store = _reload_meter_store()
    meter_dataclass = _build_meter("req-dataclass")
    meter_store.store_meter(meter_dataclass)
    meter_store.store_meter(_build_meter("req-dict").to_dict())

    assert meter_store_v2.get_meter("req-dataclass") is not None
    assert meter_store_v2.get_meter("req-dict") is not None
