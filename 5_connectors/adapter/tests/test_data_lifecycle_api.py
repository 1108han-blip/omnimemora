import importlib
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
summary_store = importlib.import_module("5_connectors.adapter.data_lifecycle.summary_store")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")
health_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.health")
data_lifecycle_api = importlib.import_module("5_connectors.adapter.data_lifecycle_api")


def _build_policy(tmp_path, *, ttl_seconds=10.0, stale_max_age_seconds=300.0):
    return policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=ttl_seconds,
        summary_stale_max_age_seconds=stale_max_age_seconds,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
    )


def _append_record(policy, *, trigger: str, status: str, completed_at: datetime):
    started_at = completed_at - timedelta(seconds=1)
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger=trigger,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        bytes_scanned=0,
        error=None if status == "success" else "failed",
    )
    state_store.append_state_record(record, policy=policy)
    return record


def test_state_store_read_recent_and_latest_with_filters(tmp_path):
    policy = _build_policy(tmp_path)
    now = datetime.now(timezone.utc)
    _append_record(policy, trigger="startup_warm", status="success", completed_at=now - timedelta(minutes=3))
    last_manual = _append_record(policy, trigger="manual_refresh", status="failed", completed_at=now - timedelta(minutes=2))
    _append_record(policy, trigger="manual_refresh", status="success", completed_at=now - timedelta(minutes=1))

    success = state_store.read_recent_records(
        limit=5,
        trigger="manual_refresh",
        status="success",
        policy=policy,
    )
    assert len(success) == 1
    assert success[0]["trigger"] == "manual_refresh"
    assert success[0]["status"] == "success"

    latest_failed = state_store.latest_record(trigger="manual_refresh", status="failed", policy=policy)
    assert latest_failed is not None
    assert latest_failed["cycle_id"] == last_manual["cycle_id"]


def test_dlp_health_status_healthy(tmp_path):
    policy = _build_policy(tmp_path, ttl_seconds=10.0, stale_max_age_seconds=300.0)
    now_ts = 105.0
    summary_store.write_summary_atomic(
        {
            "schema_version": "dlp-family-window-summary-v1",
            "generated_at": 100.0,
            "source_counts": {},
            "builder_version": "test-builder",
            "families": {},
        },
        policy=policy,
    )
    _append_record(
        policy,
        trigger="interval_refresh",
        status="success",
        completed_at=datetime.fromtimestamp(104.0, tz=timezone.utc),
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=now_ts)
    assert payload["schema_version"] == "dlp-lifecycle-health-v1"
    assert payload["status"] == "healthy"


def test_dlp_health_status_stale_usable(tmp_path):
    policy = _build_policy(tmp_path, ttl_seconds=10.0, stale_max_age_seconds=300.0)
    summary_store.write_summary_atomic(
        {
            "schema_version": "dlp-family-window-summary-v1",
            "generated_at": 100.0,
            "source_counts": {},
            "builder_version": "test-builder",
            "families": {},
        },
        policy=policy,
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=130.0)
    assert payload["status"] == "stale_usable"


def test_dlp_health_status_uninitialized(tmp_path):
    policy = _build_policy(tmp_path)
    payload = health_mod.build_health_payload(policy=policy, now_ts=100.0)
    assert payload["status"] == "uninitialized"


def test_dlp_health_status_degraded_for_invalid_summary(tmp_path):
    policy = _build_policy(tmp_path)
    summary_store.write_summary_atomic({"foo": "bar"}, policy=policy)
    payload = health_mod.build_health_payload(policy=policy, now_ts=100.0)
    assert payload["status"] == "degraded"


def test_dlp_health_status_maintenance_failed(tmp_path):
    policy = _build_policy(tmp_path)
    summary_store.write_summary_atomic(
        {
            "schema_version": "dlp-family-window-summary-v1",
            "generated_at": 100.0,
            "source_counts": {},
            "builder_version": "test-builder",
            "families": {},
        },
        policy=policy,
    )
    _append_record(
        policy,
        trigger="manual_refresh",
        status="failed",
        completed_at=datetime.fromtimestamp(101.0, tz=timezone.utc),
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=102.0)
    assert payload["status"] == "maintenance_failed"


def test_data_lifecycle_status_endpoint_returns_health_payload(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected = {"schema_version": "dlp-lifecycle-health-v1", "status": "healthy"}
    monkeypatch.setattr(data_lifecycle_api._health, "build_health_payload", lambda policy=None: expected)

    client = TestClient(app)
    response = client.get("/data-lifecycle/status")
    assert response.status_code == 200
    assert response.json() == expected


def test_data_lifecycle_manual_refresh_endpoint_returns_cycle_record(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    invalidated = {"count": 0}

    class FakeManager:
        def __init__(self, *, policy):
            self.policy = policy

        def run_once(self, trigger: str):
            return {
                "cycle_id": "cycle-api-refresh",
                "trigger": trigger,
                "status": "success",
                "error": None,
            }

    monkeypatch.setattr(data_lifecycle_api._maintenance_manager_mod, "MaintenanceManager", FakeManager)
    monkeypatch.setattr(
        data_lifecycle_api._snapshot_cache,
        "invalidate_agents_control_snapshot",
        lambda: invalidated.__setitem__("count", invalidated["count"] + 1),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/maintenance/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-manual-refresh-v1"
    assert payload["record"]["trigger"] == "manual_refresh"
    assert payload["record"]["status"] == "success"
    assert invalidated["count"] == 1
