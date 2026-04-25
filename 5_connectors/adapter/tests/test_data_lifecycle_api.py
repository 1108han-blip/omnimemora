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
        archive_plan_file=str(tmp_path / "archive_candidate_plan.json"),
        archive_transaction_preview_file=str(tmp_path / "archive_transaction_preview.json"),
        archive_restore_readiness_file=str(tmp_path / "archive_restore_readiness_report.json"),
        archive_execution_gate_file=str(tmp_path / "archive_execution_gate.json"),
        archive_operator_approval_file=str(tmp_path / "archive_operator_approval.json"),
        archive_pilot_root=str(tmp_path / "archive" / "pilot"),
        archive_pilot_record_file=str(tmp_path / "archive_pilot_record.json"),
        archive_readthrough_report_file=str(tmp_path / "archive_readthrough_report.json"),
        archive_fallback_simulation_file=str(tmp_path / "archive_fallback_simulation_report.json"),
        archive_quarantine_root=str(tmp_path / "quarantine" / "source"),
        archive_quarantine_readiness_file=str(tmp_path / "archive_quarantine_readiness_plan.json"),
        archive_quarantine_record_file=str(tmp_path / "archive_quarantine_record.json"),
        archive_restore_pilot_record_file=str(tmp_path / "archive_restore_pilot_record.json"),
        archive_restore_staging_root=str(tmp_path / "restore" / "staging"),
        archive_non_active_candidate_report_file=str(tmp_path / "archive_non_active_candidate_report.json"),
        archive_non_active_quarantine_readiness_file=str(tmp_path / "archive_non_active_quarantine_readiness_plan.json"),
        archive_non_active_execution_gate_file=str(tmp_path / "archive_non_active_execution_gate.json"),
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
    assert payload["raw_evidence_segments"]["status"] == "missing"


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


def test_data_lifecycle_raw_evidence_segments_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._raw_evidence_segments_mod, "read_manifest", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/raw-evidence/segments")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-raw-evidence-segments-manifest-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_raw_evidence_segments_rebuild_endpoint_returns_record_and_manifest(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)

    expected_record = {
        "cycle_id": "cycle-segments-1",
        "trigger": "raw_evidence_segments_manifest_rebuild",
        "status": "success",
        "error": None,
    }
    expected_manifest = {
        "schema_version": "dlp-raw-evidence-segments-manifest-v1",
        "manifest_id": "raw-segments-1",
        "mode": "dual_write_observe_only",
        "segments": [],
        "summary": {"total_segments": 0, "active_segments": 0, "sealed_segments": 0, "total_bytes": 0, "warnings_count": 0},
        "warnings": [],
    }
    monkeypatch.setattr(
        data_lifecycle_api._raw_evidence_segments_mod,
        "rebuild_manifest",
        lambda policy=None: (expected_record, expected_manifest),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/raw-evidence/segments/manifest/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-raw-evidence-segments-rebuild-v1"
    assert payload["record"]["trigger"] == "raw_evidence_segments_manifest_rebuild"
    assert payload["manifest"]["schema_version"] == "dlp-raw-evidence-segments-manifest-v1"


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


def test_data_lifecycle_archive_plan_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_plan_mod, "read_plan", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/plan")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-candidate-plan-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_plan_rebuild_endpoint_returns_record_and_plan(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)

    expected_record = {
        "cycle_id": "cycle-archive-1",
        "trigger": "archive_candidate_plan_rebuild",
        "status": "success",
        "error": None,
    }
    expected_plan = {
        "schema_version": "dlp-archive-candidate-plan-v1",
        "plan_id": "plan-1",
        "mode": "dry_run_only",
        "manifest_ref": {"status": "present"},
        "traceability_ref": {"status": "present"},
        "candidates": [],
        "summary": {
            "eligible_count": 0,
            "blocked_count": 0,
            "review_required_count": 0,
            "total_candidate_bytes": 0,
            "warnings_count": 0,
        },
        "warnings": [],
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_plan_mod,
        "rebuild_plan",
        lambda policy=None: (expected_record, expected_plan),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/plan/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-candidate-plan-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_candidate_plan_rebuild"
    assert payload["plan"]["schema_version"] == "dlp-archive-candidate-plan-v1"


def test_data_lifecycle_archive_transaction_preview_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_txn_mod, "read_preview", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/transaction/preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-transaction-preview-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_transaction_preview_rebuild_endpoint_returns_record_and_preview(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-preview-1",
        "trigger": "archive_transaction_preview_rebuild",
        "status": "success",
        "error": None,
    }
    expected_preview = {
        "schema_version": "dlp-archive-transaction-preview-v1",
        "preview_id": "preview-1",
        "mode": "preview_only",
        "plan_ref": {"status": "present"},
        "items": [],
        "summary": {"preview_item_count": 0, "warnings_count": 0},
        "warnings": [],
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_txn_mod,
        "rebuild_preview",
        lambda policy=None: (expected_record, expected_preview),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/transaction/preview/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-transaction-preview-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_transaction_preview_rebuild"
    assert payload["preview"]["schema_version"] == "dlp-archive-transaction-preview-v1"


def test_data_lifecycle_archive_restore_readiness_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_restore_mod, "read_readiness_report", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/restore/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-restore-readiness-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_restore_readiness_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-readiness-1",
        "trigger": "archive_restore_readiness_rebuild",
        "status": "success",
        "error": None,
    }
    expected_report = {
        "schema_version": "dlp-archive-restore-readiness-v1",
        "readiness_id": "readiness-1",
        "mode": "readiness_only",
        "request_mappings": [],
        "summary": {"sample_count": 0, "mapped_request_count": 0, "unmapped_request_count": 0, "warnings_count": 0},
        "warnings": [],
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_restore_mod,
        "rebuild_readiness_report",
        lambda policy=None: (expected_record, expected_report),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/restore/readiness/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-restore-readiness-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_restore_readiness_rebuild"
    assert payload["readiness"]["schema_version"] == "dlp-archive-restore-readiness-v1"


def test_data_lifecycle_api_has_no_archive_execute_endpoint():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/execute")
    assert response.status_code == 404


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
    assert traceability_report["unexplained_partial_count"] == 0
    assert traceability_report["current_epoch_pass_rate"] is None


def test_dlp_health_exposes_archive_plan_summary(tmp_path):
    policy = _build_policy(tmp_path)
    archive_path = tmp_path / "archive_candidate_plan.json"
    archive_path.write_text(
        '{"schema_version":"dlp-archive-candidate-plan-v1","plan_id":"p1","generated_at":"2026-04-25T00:00:00+00:00","mode":"dry_run_only","manifest_ref":{"status":"present"},"traceability_ref":{"status":"present"},"candidates":[],"summary":{"eligible_count":3,"blocked_count":2,"review_required_count":1,"total_candidate_bytes":98765,"warnings_count":4},"warnings":[]}',
        encoding="utf-8",
    )

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    archive_plan = payload.get("archive_plan") or {}
    assert archive_plan["status"] == "present"
    assert archive_plan["mode"] == "dry_run_only"
    assert archive_plan["eligible_count"] == 3
    assert archive_plan["blocked_count"] == 2
    assert archive_plan["review_required_count"] == 1
    assert archive_plan["total_candidate_bytes"] == 98765
    assert archive_plan["warnings_count"] == 4


def test_dlp_health_exposes_archive_transaction_preview_summary(tmp_path):
    policy = _build_policy(tmp_path)
    preview_path = tmp_path / "archive_transaction_preview.json"
    preview_path.write_text(
        '{"schema_version":"dlp-archive-transaction-preview-v1","preview_id":"tx1","generated_at":"2026-04-25T00:00:00+00:00","mode":"preview_only","plan_ref":{"status":"present"},"items":[],"summary":{"eligible_input_count":3,"preview_item_count":2,"excluded_blocked_count":4,"excluded_review_required_count":1,"blocked_precondition_count":0,"total_preview_bytes":3456,"warnings_count":2},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    txn = payload.get("archive_transaction_preview") or {}
    assert txn["status"] == "present"
    assert txn["mode"] == "preview_only"
    assert txn["eligible_input_count"] == 3
    assert txn["preview_item_count"] == 2
    assert txn["excluded_blocked_count"] == 4
    assert txn["excluded_review_required_count"] == 1
    assert txn["blocked_precondition_count"] == 0
    assert txn["total_preview_bytes"] == 3456
    assert txn["warnings_count"] == 2


def test_dlp_health_exposes_archive_restore_readiness_summary(tmp_path):
    policy = _build_policy(tmp_path)
    readiness_path = tmp_path / "archive_restore_readiness_report.json"
    readiness_path.write_text(
        '{"schema_version":"dlp-archive-restore-readiness-v1","readiness_id":"r1","generated_at":"2026-04-25T00:00:00+00:00","mode":"readiness_only","transaction_preview_ref":{"status":"present"},"traceability_ref":{"status":"present"},"request_mappings":[],"summary":{"sample_count":6,"mapped_request_count":5,"unmapped_request_count":1,"warnings_count":1},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    readiness = payload.get("archive_restore_readiness") or {}
    assert readiness["status"] == "present"
    assert readiness["mode"] == "readiness_only"
    assert readiness["sample_count"] == 6
    assert readiness["mapped_request_count"] == 5
    assert readiness["unmapped_request_count"] == 1
    assert readiness["warnings_count"] == 1


def test_data_lifecycle_archive_execution_gate_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_gate_mod, "read_gate", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/execution/gate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-execution-gate-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_execution_gate_rebuild_endpoint_returns_record_and_gate(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-gate-1",
        "trigger": "archive_execution_gate_rebuild",
        "status": "success",
        "error": None,
    }
    expected_gate = {
        "schema_version": "dlp-archive-execution-gate-v1",
        "gate_id": "g1",
        "mode": "gate_only",
        "allowed": False,
        "status": "blocked",
        "blocking_reasons": ["missing_operator_approval"],
        "summary": {"blocking_count": 1, "approval_status": "missing"},
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_gate_mod,
        "rebuild_gate",
        lambda policy=None: (expected_record, expected_gate),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/execution/gate/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-execution-gate-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_execution_gate_rebuild"
    assert payload["gate"]["schema_version"] == "dlp-archive-execution-gate-v1"


def test_data_lifecycle_archive_approval_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_approval_mod, "read_approval", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/approval")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-operator-approval-v1"
    assert payload["status"] == "missing"


def test_dlp_health_exposes_archive_execution_gate_summary(tmp_path):
    policy = _build_policy(tmp_path)
    gate_path = tmp_path / "archive_execution_gate.json"
    gate_path.write_text(
        '{"schema_version":"dlp-archive-execution-gate-v1","gate_id":"g1","generated_at":"2026-04-25T00:00:00+00:00","mode":"gate_only","allowed":false,"status":"blocked","blocking_reasons":["missing_operator_approval"],"approval":{"status":"missing","operator_id":null,"expires_at":null},"summary":{"allowed":false,"status":"blocked","blocking_count":1,"approval_status":"missing","expires_at":null,"warnings_count":0},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    gate = payload.get("archive_execution_gate") or {}
    assert gate["status"] == "present"
    assert gate["allowed"] is False
    assert gate["gate_status"] == "blocked"
    assert gate["blocking_count"] == 1
    assert gate["approval_status"] == "missing"


def test_data_lifecycle_archive_pilot_copy_one_endpoint_returns_record(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-pilot-1",
        "trigger": "archive_pilot_copy_one",
        "status": "success",
        "error": None,
    }
    expected_pilot = {
        "schema_version": "dlp-archive-pilot-record-v1",
        "pilot_id": "pilot-1",
        "mode": "copy_to_archive_only",
        "status": "success",
        "source_kind": "compile_events",
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_pilot_mod,
        "copy_one_pilot",
        lambda policy=None: (expected_record, expected_pilot),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/pilot/copy-one")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-pilot-record-v1"
    assert payload["record"]["trigger"] == "archive_pilot_copy_one"
    assert payload["pilot"]["pilot_id"] == "pilot-1"


def test_data_lifecycle_archive_pilot_latest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_pilot_mod, "read_latest_pilot_record", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/pilot/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-pilot-record-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_api_has_no_archive_batch_or_cleanup_endpoint():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    assert client.post("/data-lifecycle/archive/pilot/batch-copy").status_code == 404
    assert client.post("/data-lifecycle/archive/pilot/delete-source").status_code == 404
    assert client.post("/data-lifecycle/archive/pilot/compress").status_code == 404
    assert client.post("/data-lifecycle/archive/read-path/switch").status_code == 404
    assert client.post("/data-lifecycle/archive/fallback/switch").status_code == 404
    assert client.post("/data-lifecycle/archive/fallback/execute").status_code == 404
    assert client.post("/data-lifecycle/archive/quarantine/execute").status_code == 404
    assert client.post("/data-lifecycle/archive/quarantine/move-source").status_code == 404
    assert client.post("/data-lifecycle/archive/quarantine/delete-source").status_code == 404
    assert client.post("/data-lifecycle/archive/quarantine/compress").status_code == 404
    assert client.post("/data-lifecycle/archive/quarantine/batch-move").status_code == 404
    assert client.post("/data-lifecycle/archive/restore/pilot/production-overwrite").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-candidates/execute").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-candidates/move-one").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-quarantine/execute").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-quarantine/move-source").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-quarantine/delete").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-quarantine/compress").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-quarantine/execution/execute").status_code == 404
    assert client.post("/data-lifecycle/archive/non-active-quarantine/execution/move-one").status_code == 404


def test_dlp_health_exposes_archive_pilot_summary(tmp_path):
    policy = _build_policy(tmp_path)
    pilot_path = tmp_path / "archive_pilot_record.json"
    pilot_path.write_text(
        '{"schema_version":"dlp-archive-pilot-record-v1","pilot_id":"pilot-1","generated_at":"2026-04-25T00:00:00+00:00","mode":"copy_to_archive_only","status":"success","source_kind":"compile_events","source_bytes":123,"archive_bytes":123,"checksum_match":true,"source_retained":true,"read_path_unchanged":true}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    pilot = payload.get("archive_pilot") or {}
    assert pilot["status"] == "present"
    assert pilot["pilot_id"] == "pilot-1"
    assert pilot["source_kind"] == "compile_events"
    assert pilot["source_bytes"] == 123
    assert pilot["archive_bytes"] == 123
    assert pilot["checksum_match"] is True
    assert pilot["source_retained"] is True
    assert pilot["read_path_unchanged"] is True


def test_data_lifecycle_archive_readthrough_report_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_readthrough_mod, "read_report", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/readthrough/report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-readthrough-report-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_readthrough_report_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-readthrough-1",
        "trigger": "archive_readthrough_report_rebuild",
        "status": "success",
        "error": None,
    }
    expected_report = {
        "schema_version": "dlp-archive-readthrough-report-v1",
        "report_id": "rt-1",
        "mode": "shadow_validation_only",
        "status": "passed",
        "source_retained": True,
        "archive_copy_readable": True,
        "checksum_match": True,
        "read_path_unchanged": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_readthrough_mod,
        "rebuild_report",
        lambda policy=None: (expected_record, expected_report),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/readthrough/report/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-readthrough-report-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_readthrough_report_rebuild"
    assert payload["report"]["schema_version"] == "dlp-archive-readthrough-report-v1"


def test_dlp_health_exposes_archive_readthrough_summary(tmp_path):
    policy = _build_policy(tmp_path)
    report_path = tmp_path / "archive_readthrough_report.json"
    report_path.write_text(
        '{"schema_version":"dlp-archive-readthrough-report-v1","report_id":"rt-1","generated_at":"2026-04-25T00:00:00+00:00","mode":"shadow_validation_only","status":"passed","source_retained":true,"archive_copy_readable":true,"checksum_match":true,"read_path_unchanged":true}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    readthrough = payload.get("archive_readthrough") or {}
    assert readthrough["status"] == "passed"
    assert readthrough["source_retained"] is True
    assert readthrough["archive_copy_readable"] is True
    assert readthrough["checksum_match"] is True
    assert readthrough["read_path_unchanged"] is True
    assert readthrough["validated_at"] == "2026-04-25T00:00:00+00:00"


def test_data_lifecycle_archive_fallback_simulation_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_fallback_mod, "read_report", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/fallback/simulation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-fallback-simulation-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_fallback_simulation_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-fallback-1",
        "trigger": "archive_fallback_simulation_rebuild",
        "status": "success",
        "error": None,
    }
    expected_report = {
        "schema_version": "dlp-archive-fallback-simulation-v1",
        "simulation_id": "fallback-1",
        "mode": "diagnostic_fallback_only",
        "status": "passed",
        "fallback_available": True,
        "production_read_path_unchanged": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_fallback_mod,
        "rebuild_report",
        lambda policy=None: (expected_record, expected_report),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/fallback/simulation/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-fallback-simulation-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_fallback_simulation_rebuild"
    assert payload["report"]["schema_version"] == "dlp-archive-fallback-simulation-v1"


def test_dlp_health_exposes_archive_fallback_simulation_summary(tmp_path):
    policy = _build_policy(tmp_path)
    report_path = tmp_path / "archive_fallback_simulation_report.json"
    report_path.write_text(
        '{"schema_version":"dlp-archive-fallback-simulation-v1","simulation_id":"fb1","generated_at":"2026-04-25T00:00:00+00:00","mode":"diagnostic_fallback_only","status":"passed","source_missing_simulated":true,"fallback_available":true,"archive_copy_readable":true,"checksum_match":true,"production_read_path_unchanged":true,"summary":{"request_evidence_fallback_status":"mapped","validated_at":"2026-04-25T00:00:00+00:00"}}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    fallback = payload.get("archive_fallback_simulation") or {}
    assert fallback["status"] == "passed"
    assert fallback["mode"] == "diagnostic_fallback_only"
    assert fallback["fallback_available"] is True
    assert fallback["archive_copy_readable"] is True
    assert fallback["checksum_match"] is True
    assert fallback["source_missing_simulated"] is True
    assert fallback["production_read_path_unchanged"] is True
    assert fallback["request_evidence_fallback_status"] == "mapped"


def test_data_lifecycle_archive_quarantine_readiness_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_quarantine_mod, "read_plan", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/quarantine/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-source-quarantine-readiness-plan-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_quarantine_readiness_rebuild_endpoint_returns_record_and_plan(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-quarantine-1",
        "trigger": "archive_quarantine_readiness_rebuild",
        "status": "success",
        "error": None,
    }
    expected_plan = {
        "schema_version": "dlp-source-quarantine-readiness-plan-v1",
        "plan_id": "q1",
        "mode": "readiness_plan_only",
        "status": "ready_for_approval",
        "source_move_executed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_quarantine_mod,
        "rebuild_plan",
        lambda policy=None: (expected_record, expected_plan),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/quarantine/readiness/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-source-quarantine-readiness-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_quarantine_readiness_rebuild"
    assert payload["plan"]["schema_version"] == "dlp-source-quarantine-readiness-plan-v1"


def test_dlp_health_exposes_archive_quarantine_readiness_summary(tmp_path):
    policy = _build_policy(tmp_path)
    report_path = tmp_path / "archive_quarantine_readiness_plan.json"
    report_path.write_text(
        '{"schema_version":"dlp-source-quarantine-readiness-plan-v1","plan_id":"q1","generated_at":"2026-04-25T00:00:00+00:00","mode":"readiness_plan_only","status":"ready_for_approval","source_move_executed":false,"source_retained":true,"production_read_path_unchanged":true,"transaction_preview":{"planned_action":"quarantine_source_preview_only"},"summary":{"candidate_present":true,"blocking_count":0}}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    quarantine = payload.get("archive_quarantine_readiness") or {}
    assert quarantine["status"] == "ready_for_approval"
    assert quarantine["mode"] == "readiness_plan_only"
    assert quarantine["candidate_present"] is True
    assert quarantine["blocking_count"] == 0
    assert quarantine["source_move_executed"] is False
    assert quarantine["source_retained"] is True
    assert quarantine["production_read_path_unchanged"] is True
    assert quarantine["planned_action"] == "quarantine_source_preview_only"


def test_data_lifecycle_archive_quarantine_latest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_quarantine_exec_mod, "read_record", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/quarantine/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-source-quarantine-record-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_quarantine_move_one_endpoint_returns_record(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-quarantine-move-1",
        "trigger": "archive_source_quarantine_execute_one",
        "status": "blocked",
        "error": "candidate_is_active_hot_source",
    }
    expected_quarantine = {
        "schema_version": "dlp-source-quarantine-record-v1",
        "record_id": "qr1",
        "mode": "single_artifact_quarantine_only",
        "status": "blocked",
        "blocking_reasons": ["candidate_is_active_hot_source"],
        "source_move_executed": False,
        "source_retained": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_quarantine_exec_mod,
        "execute_single_artifact_quarantine",
        lambda policy=None: (expected_record, expected_quarantine),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/quarantine/move-one")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-source-quarantine-record-v1"
    assert payload["record"]["trigger"] == "archive_source_quarantine_execute_one"
    assert payload["quarantine"]["status"] == "blocked"
    assert payload["quarantine"]["source_move_executed"] is False


def test_dlp_health_exposes_archive_quarantine_record_summary(tmp_path):
    policy = _build_policy(tmp_path)
    quarantine_path = tmp_path / "archive_quarantine_record.json"
    quarantine_path.write_text(
        '{"schema_version":"dlp-source-quarantine-record-v1","record_id":"qr1","generated_at":"2026-04-25T00:00:00+00:00","mode":"single_artifact_quarantine_only","status":"blocked","blocking_reasons":["candidate_is_active_hot_source"],"source_kind":"compile_events","source_move_executed":false,"source_retained":true,"checksum_match":false,"quarantine_path":"/tmp/q","summary":{"blocking_count":1}}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    quarantine = payload.get("archive_quarantine") or {}
    assert quarantine["status"] == "blocked"
    assert quarantine["mode"] == "single_artifact_quarantine_only"
    assert quarantine["source_kind"] == "compile_events"
    assert quarantine["source_move_executed"] is False
    assert quarantine["source_retained"] is True
    assert quarantine["blocking_count"] == 1
    assert quarantine["quarantine_path"] == "/tmp/q"


def test_data_lifecycle_archive_restore_pilot_latest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_restore_pilot_mod, "read_latest_restore_pilot_record", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/restore/pilot/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-restore-pilot-record-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_restore_pilot_run_endpoint_returns_blocked_record(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-restore-1",
        "trigger": "archive_restore_pilot_execute",
        "status": "blocked",
        "error": "blocked_no_successful_quarantine",
    }
    expected_restore = {
        "schema_version": "dlp-archive-restore-pilot-record-v1",
        "restore_id": "restore-1",
        "mode": "conditional_restore_to_staging",
        "status": "blocked_no_successful_quarantine",
        "restore_target_scope": "staging",
        "production_source_overwrite": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_restore_pilot_mod,
        "execute_restore_pilot",
        lambda policy=None: (expected_record, expected_restore),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/restore/pilot/run")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-archive-restore-pilot-record-v1"
    assert payload["record"]["trigger"] == "archive_restore_pilot_execute"
    assert payload["restore"]["status"] == "blocked_no_successful_quarantine"
    assert payload["restore"]["production_source_overwrite"] is False


def test_dlp_health_exposes_archive_restore_pilot_summary(tmp_path):
    policy = _build_policy(tmp_path)
    restore_path = tmp_path / "archive_restore_pilot_record.json"
    restore_path.write_text(
        '{"schema_version":"dlp-archive-restore-pilot-record-v1","restore_id":"restore-1","generated_at":"2026-04-25T00:00:00+00:00","mode":"conditional_restore_to_staging","status":"blocked_no_successful_quarantine","restore_target_scope":"staging","restore_target_path":null,"checksum_match":false,"production_source_overwrite":false,"archive_copy_retained":true,"quarantine_copy_retained":true}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    restore = payload.get("archive_restore_pilot") or {}
    assert restore["status"] == "blocked_no_successful_quarantine"
    assert restore["mode"] == "conditional_restore_to_staging"
    assert restore["restore_target_scope"] == "staging"
    assert restore["production_source_overwrite"] is False
    assert restore["archive_copy_retained"] is True
    assert restore["quarantine_copy_retained"] is True


def test_data_lifecycle_archive_non_active_candidates_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_non_active_candidates_mod, "read_report", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/non-active-candidates/report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-candidate-report-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_non_active_candidates_rebuild_endpoint_returns_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-non-active-1",
        "trigger": "archive_non_active_candidate_report_rebuild",
        "status": "success",
        "error": None,
    }
    expected_report = {
        "schema_version": "dlp-non-active-candidate-report-v1",
        "report_id": "non-active-1",
        "mode": "non_active_selection_report_only",
        "candidates": [],
        "summary": {
            "total_scanned": 0,
            "forbidden_count": 0,
            "plausible_non_active_count": 0,
            "review_required_count": 0,
            "source_move_delete_compress_executed": False,
            "warnings_count": 0,
        },
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_non_active_candidates_mod,
        "rebuild_report",
        lambda policy=None: (expected_record, expected_report),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/non-active-candidates/report/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-candidate-report-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_non_active_candidate_report_rebuild"
    assert payload["report"]["schema_version"] == "dlp-non-active-candidate-report-v1"


def test_dlp_health_exposes_archive_non_active_candidate_summary(tmp_path):
    policy = _build_policy(tmp_path)
    report_path = tmp_path / "archive_non_active_candidate_report.json"
    report_path.write_text(
        '{"schema_version":"dlp-non-active-candidate-report-v1","report_id":"n1","generated_at":"2026-04-25T00:00:00+00:00","mode":"non_active_selection_report_only","candidates":[],"summary":{"total_scanned":3,"forbidden_count":2,"plausible_non_active_count":1,"review_required_count":0,"source_move_delete_compress_executed":false,"warnings_count":0},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    non_active = payload.get("archive_non_active_candidates") or {}
    assert non_active["status"] == "present"
    assert non_active["mode"] == "non_active_selection_report_only"
    assert non_active["total_scanned"] == 3
    assert non_active["plausible_non_active_count"] == 1
    assert non_active["forbidden_count"] == 2
    assert non_active["source_move_delete_compress_executed"] is False


def test_data_lifecycle_archive_non_active_quarantine_readiness_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_non_active_quarantine_mod, "read_plan", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/non-active-quarantine/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-quarantine-readiness-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_non_active_quarantine_readiness_rebuild_endpoint_returns_plan(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-non-active-quarantine-1",
        "trigger": "archive_non_active_quarantine_readiness_rebuild",
        "status": "success",
        "error": None,
    }
    expected_plan = {
        "schema_version": "dlp-non-active-quarantine-readiness-v1",
        "plan_id": "naq1",
        "mode": "non_active_quarantine_readiness_only",
        "status": "ready_for_operator_approval",
        "selected_candidate": {"candidate_kind": "archive_pilot_copy"},
        "summary": {
            "selected_candidate_present": True,
            "blocking_count": 0,
            "source_move_executed": False,
            "non_active_copy_move_executed": False,
            "delete_compress_executed": False,
            "warnings_count": 0,
        },
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_non_active_quarantine_mod,
        "rebuild_plan",
        lambda policy=None: (expected_record, expected_plan),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/non-active-quarantine/readiness/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-quarantine-readiness-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_non_active_quarantine_readiness_rebuild"
    assert payload["plan"]["schema_version"] == "dlp-non-active-quarantine-readiness-v1"


def test_dlp_health_exposes_archive_non_active_quarantine_readiness_summary(tmp_path):
    policy = _build_policy(tmp_path)
    plan_path = tmp_path / "archive_non_active_quarantine_readiness_plan.json"
    plan_path.write_text(
        '{"schema_version":"dlp-non-active-quarantine-readiness-v1","plan_id":"naq1","generated_at":"2026-04-25T00:00:00+00:00","mode":"non_active_quarantine_readiness_only","status":"ready_for_operator_approval","selected_candidate":{"candidate_kind":"archive_pilot_copy","candidate_path":"/tmp/archive.copy","planned_quarantine_path":"/tmp/archive.copy.quarantine"},"transaction_preview":{"planned_quarantine_path":"/tmp/archive.copy.quarantine"},"summary":{"selected_candidate_present":true,"blocking_count":0,"source_move_executed":false,"non_active_copy_move_executed":false,"delete_compress_executed":false,"warnings_count":0},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    readiness = payload.get("archive_non_active_quarantine_readiness") or {}
    assert readiness["status"] == "ready_for_operator_approval"
    assert readiness["mode"] == "non_active_quarantine_readiness_only"
    assert readiness["selected_candidate_present"] is True
    assert readiness["selected_candidate_kind"] == "archive_pilot_copy"
    assert readiness["planned_quarantine_path"] == "/tmp/archive.copy.quarantine"
    assert readiness["source_move_executed"] is False
    assert readiness["non_active_copy_move_executed"] is False
    assert readiness["delete_compress_executed"] is False


def test_data_lifecycle_archive_non_active_execution_gate_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_non_active_gate_mod, "read_gate", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/non-active-quarantine/execution/gate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-copy-execution-gate-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_non_active_execution_gate_rebuild_endpoint_returns_gate(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-non-active-gate-1",
        "trigger": "archive_non_active_execution_gate_rebuild",
        "status": "success",
        "error": None,
    }
    expected_gate = {
        "schema_version": "dlp-non-active-copy-execution-gate-v1",
        "gate_id": "ng1",
        "mode": "gate_only",
        "allowed": False,
        "status": "blocked",
        "blocking_reasons": ["missing_operator_approval"],
        "summary": {"blocking_count": 1, "source_move_allowed": False},
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_non_active_gate_mod,
        "rebuild_gate",
        lambda policy=None: (expected_record, expected_gate),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/non-active-quarantine/execution/gate/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-copy-execution-gate-rebuild-v1"
    assert payload["record"]["trigger"] == "archive_non_active_execution_gate_rebuild"
    assert payload["gate"]["schema_version"] == "dlp-non-active-copy-execution-gate-v1"


def test_dlp_health_exposes_archive_non_active_execution_gate_summary(tmp_path):
    policy = _build_policy(tmp_path)
    gate_path = tmp_path / "archive_non_active_execution_gate.json"
    gate_path.write_text(
        '{"schema_version":"dlp-non-active-copy-execution-gate-v1","gate_id":"ng1","generated_at":"2026-04-25T00:00:00+00:00","mode":"gate_only","allowed":false,"status":"blocked","blocking_reasons":["missing_operator_approval"],"approval":{"status":"missing"},"summary":{"allowed":false,"status":"blocked","blocking_count":1,"approval_status":"missing","source_move_allowed":false,"delete_allowed":false,"compress_allowed":false,"warnings_count":1},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    gate = payload.get("archive_non_active_execution_gate") or {}
    assert gate["status"] == "present"
    assert gate["allowed"] is False
    assert gate["gate_status"] == "blocked"
    assert gate["blocking_count"] == 1
    assert gate["approval_status"] == "missing"
    assert gate["source_move_allowed"] is False
    assert gate["delete_allowed"] is False
    assert gate["compress_allowed"] is False


def test_data_lifecycle_archive_non_active_quarantine_latest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._archive_non_active_quarantine_exec_mod, "read_record", lambda policy=None: None)
    client = TestClient(app)
    response = client.get("/data-lifecycle/archive/non-active-quarantine/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-copy-quarantine-record-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_archive_non_active_quarantine_move_one_endpoint_returns_record(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-non-active-move-1",
        "trigger": "archive_non_active_copy_quarantine_execute_one",
        "status": "success",
        "error": None,
    }
    expected_quarantine = {
        "schema_version": "dlp-non-active-copy-quarantine-record-v1",
        "quarantine_id": "naq1",
        "mode": "single_non_active_copy_quarantine_only",
        "status": "success",
        "source_move_executed": False,
        "non_active_copy_move_executed": True,
        "delete_compress_executed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._archive_non_active_quarantine_exec_mod,
        "execute_single_non_active_copy_quarantine",
        lambda policy=None: (expected_record, expected_quarantine),
    )
    client = TestClient(app)
    response = client.post("/data-lifecycle/archive/non-active-quarantine/move-one")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-non-active-copy-quarantine-record-v1"
    assert payload["record"]["trigger"] == "archive_non_active_copy_quarantine_execute_one"
    assert payload["quarantine"]["status"] == "success"
    assert payload["quarantine"]["source_move_executed"] is False
    assert payload["quarantine"]["non_active_copy_move_executed"] is True


def test_data_lifecycle_archive_non_active_quarantine_does_not_expose_delete_compress_or_batch_cleanup():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/archive/non-active-quarantine/delete",
        "/data-lifecycle/archive/non-active-quarantine/compress",
        "/data-lifecycle/archive/non-active-quarantine/cleanup",
        "/data-lifecycle/archive/non-active-quarantine/batch",
        "/data-lifecycle/archive/non-active-quarantine/execution/execute",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_dlp_health_exposes_archive_non_active_quarantine_record_summary(tmp_path):
    policy = _build_policy(tmp_path)
    quarantine_path = tmp_path / "archive_quarantine_record.json"
    quarantine_path.write_text(
        '{"schema_version":"dlp-non-active-copy-quarantine-record-v1","quarantine_id":"naq1","generated_at":"2026-04-25T00:00:00+00:00","mode":"single_non_active_copy_quarantine_only","status":"success","candidate_kind":"archive_pilot_copy","candidate_path":"/tmp/archive.copy","quarantine_path":"/tmp/archive.copy.quarantine","checksum_match":true,"source_move_executed":false,"non_active_copy_move_executed":true,"delete_compress_executed":false,"production_read_path_unchanged":true,"summary":{"blocking_count":0}}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    quarantine = payload.get("archive_non_active_quarantine") or {}
    assert quarantine["status"] == "success"
    assert quarantine["mode"] == "single_non_active_copy_quarantine_only"
    assert quarantine["candidate_kind"] == "archive_pilot_copy"
    assert quarantine["checksum_match"] is True
    assert quarantine["source_move_executed"] is False
    assert quarantine["non_active_copy_move_executed"] is True
    assert quarantine["delete_compress_executed"] is False
    assert quarantine["production_read_path_unchanged"] is True
