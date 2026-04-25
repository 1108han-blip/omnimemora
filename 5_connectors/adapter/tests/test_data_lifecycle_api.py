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
        retention_manifest_file=str(tmp_path / "retention_manifest.json"),
        traceability_report_file=str(tmp_path / "traceability_report.json"),
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


def test_data_lifecycle_retention_manifest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._retention_mod, "read_manifest", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/retention/manifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-retention-manifest-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_retention_manifest_rebuild_endpoint_returns_record_and_manifest(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)

    expected_record = {
        "cycle_id": "cycle-retention-1",
        "trigger": "retention_manifest_rebuild",
        "status": "success",
        "error": None,
    }
    expected_manifest = {
        "schema_version": "dlp-retention-manifest-v1",
        "manifest_id": "manifest-1",
        "mode": "inventory_only",
        "artifacts": [],
        "summary": {"artifact_count": 0, "total_bytes": 0, "warnings_count": 0},
        "warnings": [],
    }
    monkeypatch.setattr(
        data_lifecycle_api._retention_mod,
        "rebuild_manifest",
        lambda policy=None: (expected_record, expected_manifest),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/retention/manifest/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-retention-manifest-rebuild-v1"
    assert payload["record"]["trigger"] == "retention_manifest_rebuild"
    assert payload["manifest"]["schema_version"] == "dlp-retention-manifest-v1"


def test_data_lifecycle_traceability_report_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._traceability_mod, "read_report", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/traceability/report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-traceability-report-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_traceability_report_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)

    expected_record = {
        "cycle_id": "cycle-traceability-1",
        "trigger": "traceability_report_rebuild",
        "status": "success",
        "error": None,
    }
    expected_report = {
        "schema_version": "dlp-traceability-report-v1",
        "report_id": "report-1",
        "samples": [],
        "summary": {"sample_count": 0, "pass_count": 0, "partial_count": 0, "fail_count": 0, "missing_manifest": True, "warnings_count": 0},
        "warnings": [],
    }
    monkeypatch.setattr(
        data_lifecycle_api._traceability_mod,
        "rebuild_report",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/traceability/report/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-traceability-report-rebuild-v1"
    assert payload["record"]["trigger"] == "traceability_report_rebuild"
    assert payload["report"]["schema_version"] == "dlp-traceability-report-v1"


def test_dlp_health_exposes_storage_pressure_without_cleanup(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    summary_store.write_summary_atomic(
        {
            "schema_version": "dlp-family-window-summary-v1",
            "generated_at": 100.0,
            "source_counts": {},
            "builder_version": "test-builder",
            "families": {},
            "metrics_summary_all": {"token_saving_ratio": 0.0, "tokens_saved": 0, "request_count": 0, "avg_context_reduction": 0.0},
            "metrics_summary_24h": {"token_saving_ratio": 0.0, "tokens_saved": 0, "request_count": 0, "avg_context_reduction": 0.0, "period": "24h"},
            "core_capabilities_24h": {
                "period": "24h",
                "observed_request_count": 0,
                "non_value_count": 0,
                "cards": {
                    "real_requests": {"count": 0, "ratio": 0.0},
                    "context_compression": {"ratio": 0.0, "baseline_tokens": 0, "actual_tokens": 0},
                    "memory_enhancement": {"rate": 0.0, "memory_count": 0},
                    "token_savings": {"ratio": 0.0, "saved_tokens": 0},
                },
            },
        },
        policy=policy,
    )
    summary_path = tmp_path / "family_window_summary.json"
    assert summary_path.exists()

    monkeypatch.setattr(health_mod, "STORAGE_PRESSURE_WARNING_BYTES", 1)
    monkeypatch.setattr(health_mod, "STORAGE_PRESSURE_CRITICAL_BYTES", 10**12)

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    assert payload["storage_pressure"] == "warning"
    assert payload["storage"]["total_bytes"] >= 1
    assert summary_path.exists()


def test_dlp_health_exposes_retention_manifest_summary(tmp_path):
    policy = _build_policy(tmp_path)
    manifest_path = tmp_path / "retention_manifest.json"
    manifest_path.write_text(
        '{"schema_version":"dlp-retention-manifest-v1","manifest_id":"m1","generated_at":"2026-04-25T00:00:00+00:00","mode":"inventory_only","artifacts":[],"summary":{"artifact_count":3,"exists_count":2,"missing_count":1,"total_bytes":1234,"warnings_count":1},"warnings":[{"code":"artifact_missing"}]}',
        encoding="utf-8",
    )

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    retention_manifest = payload.get("retention_manifest") or {}
    assert retention_manifest["status"] == "present"
    assert retention_manifest["artifact_count"] == 3
    assert retention_manifest["total_bytes"] == 1234
    assert retention_manifest["warnings_count"] == 1


def test_dlp_health_exposes_traceability_report_summary(tmp_path):
    policy = _build_policy(tmp_path)
    traceability_path = tmp_path / "traceability_report.json"
    traceability_path.write_text(
        '{"schema_version":"dlp-traceability-report-v1","report_id":"r1","generated_at":"2026-04-25T00:00:00+00:00","manifest_ref":{"status":"present","manifest_id":"m1","generated_at":"2026-04-25T00:00:00+00:00"},"samples":[],"summary":{"sample_count":12,"pass_count":9,"partial_count":2,"fail_count":1,"missing_manifest":false,"warnings_count":3},"warnings":[{"code":"x"}]}',
        encoding="utf-8",
    )

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    traceability_report = payload.get("traceability_report") or {}
    assert traceability_report["status"] == "present"
    assert traceability_report["sample_count"] == 12
    assert traceability_report["fail_count"] == 1
    assert traceability_report["warnings_count"] == 3
