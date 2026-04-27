import importlib
import json
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
summary_store = importlib.import_module("5_connectors.adapter.data_lifecycle.summary_store")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")
health_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.health")
data_lifecycle_api = importlib.import_module("5_connectors.adapter.data_lifecycle_api")
compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")
proxy_store = importlib.import_module("5_connectors.adapter.infrastructure.proxy_store")
trace_events = importlib.import_module("5_connectors.adapter.trace_events")
log_segments = importlib.import_module("5_connectors.adapter.log_segments")


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


def test_internal_event_logs_are_capped_to_recent_tail(tmp_path, monkeypatch):
    now = time.time()
    old = {"request_id": "old", "timestamp": now - 9 * 86400}
    recent = {"request_id": "recent", "timestamp": now}

    compile_path = tmp_path / "compile_events.jsonl"
    proxy_path = tmp_path / "proxy_events.jsonl"
    trace_path = tmp_path / "trace_events.jsonl"
    for path in (compile_path, proxy_path, trace_path):
        path.write_text(
            "".join(json.dumps(old) + "\n" for _ in range(3))
            + "".join(json.dumps(recent) + "\n" for _ in range(8)),
            encoding="utf-8",
        )

    monkeypatch.setattr(compile_store, "COMPILE_EVENTS_PATH", str(compile_path))
    monkeypatch.setattr(compile_store, "RETENTION_DAYS", 7)
    monkeypatch.setattr(compile_store, "MAX_RECENT_READ_LINES", 5)
    monkeypatch.setattr(proxy_store, "EVENTS_PATH", proxy_path)
    monkeypatch.setattr(proxy_store, "RETENTION_DAYS", 7)
    monkeypatch.setattr(proxy_store, "MAX_RECENT_READ_LINES", 5)
    monkeypatch.setattr(trace_events, "TRACE_EVENTS_PATH", str(trace_path))
    monkeypatch.setattr(trace_events, "RETENTION_DAYS", 7)
    monkeypatch.setattr(trace_events, "MAX_RECENT_READ_LINES", 5)

    compile_store.append_compile_event({"request_id": "new-compile", "timestamp": now})
    proxy_store.append_event({"request_id": "new-proxy", "timestamp": now})
    trace_events.append_trace_event({"request_id": "new-trace", "timestamp": now})

    assert all(json.loads(line)["request_id"] != "old" for line in compile_path.read_text(encoding="utf-8").splitlines())
    assert all(json.loads(line)["request_id"] != "old" for line in proxy_path.read_text(encoding="utf-8").splitlines())
    assert all(json.loads(line)["request_id"] != "old" for line in trace_path.read_text(encoding="utf-8").splitlines())
    assert len(compile_path.read_text(encoding="utf-8").splitlines()) <= 5
    assert len(proxy_path.read_text(encoding="utf-8").splitlines()) <= 5
    assert len(trace_path.read_text(encoding="utf-8").splitlines()) <= 5


def test_segment_tail_reader_returns_newest_lines_across_rotated_files(tmp_path):
    base = tmp_path / "trace_events.jsonl"
    older = tmp_path / "trace_events.20260425010101.jsonl"
    newer = tmp_path / "trace_events.20260426010101.jsonl"
    older.write_text('{"id":"old-1"}\n{"id":"old-2"}\n', encoding="utf-8")
    newer.write_text('{"id":"new-1"}\n{"id":"new-2"}\n', encoding="utf-8")
    base.write_text('{"id":"active-1"}\n{"id":"active-2"}\n', encoding="utf-8")
    log_segments.os.utime(older, (1, 1))
    log_segments.os.utime(newer, (2, 2))
    log_segments.os.utime(base, (3, 3))

    lines = log_segments.read_segment_lines(base, max_lines=3)

    assert [json.loads(line)["id"] for line in lines] == ["new-2", "active-1", "active-2"]


def test_dlp_health_fast_status_does_not_read_frozen_governance_artifacts(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)

    def fail_import(name):
        if name.startswith("5_connectors.adapter.data_lifecycle.archive_"):
            raise AssertionError(name)
        if name.startswith("5_connectors.adapter.data_lifecycle.raw_evidence_segments"):
            raise AssertionError(name)
        if name.startswith("5_connectors.adapter.data_lifecycle.retention"):
            raise AssertionError(name)
        return importlib.import_module(name)

    monkeypatch.setattr(health_mod.meter_storage_v2, "get_status_payload", lambda: {"status": "healthy"})
    monkeypatch.setattr(importlib, "import_module", fail_import)

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    assert payload["retention_manifest"]["status"] == "frozen"
    assert payload["archive_plan"]["status"] == "frozen"
    assert payload["raw_log_retention"]["status"] == "bounded"


def test_maintenance_state_retention_prunes_old_records(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(state_store, "RETENTION_DAYS", 7)
    monkeypatch.setattr(state_store, "MAX_RECENT_READ_LINES", 5)

    now = datetime.now(timezone.utc)
    _append_record(policy, trigger="old", status="success", completed_at=now - timedelta(days=9))
    _append_record(policy, trigger="recent", status="success", completed_at=now)

    records = state_store.read_recent_records(limit=10, policy=policy)
    assert [record["trigger"] for record in records] == ["recent"]


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
    assert payload["raw_evidence_segments"]["status"] == "frozen"


def test_dlp_health_status_degraded_for_invalid_summary(tmp_path):
    policy = _build_policy(tmp_path)
    summary_store.write_summary_atomic({"foo": "bar"}, policy=policy)
    payload = health_mod.build_health_payload(policy=policy, now_ts=100.0)
    assert payload["status"] == "degraded"


def test_dlp_health_status_maintenance_failed(tmp_path):
    policy = _build_policy(tmp_path)
    original_retention_days = state_store.RETENTION_DAYS
    state_store.RETENTION_DAYS = 36500
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
    try:
        _append_record(
            policy,
            trigger="manual_refresh",
            status="failed",
            completed_at=datetime.fromtimestamp(101.0, tz=timezone.utc),
        )
        payload = health_mod.build_health_payload(policy=policy, now_ts=102.0)
    finally:
        state_store.RETENTION_DAYS = original_retention_days
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


def test_dlp_health_uses_fast_frozen_retention_manifest_summary(tmp_path):
    policy = _build_policy(tmp_path)
    manifest_path = tmp_path / "retention_manifest.json"
    manifest_path.write_text(
        '{"schema_version":"dlp-retention-manifest-v1","manifest_id":"m1","generated_at":"2026-04-25T00:00:00+00:00","mode":"inventory_only","artifacts":[],"summary":{"artifact_count":3,"exists_count":2,"missing_count":1,"total_bytes":1234,"warnings_count":1},"warnings":[{"code":"artifact_missing"}]}',
        encoding="utf-8",
    )

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    retention_manifest = payload.get("retention_manifest") or {}
    assert retention_manifest["status"] == "frozen"
    assert retention_manifest["artifact_count"] == 0
    assert retention_manifest["total_bytes"] == 0
    assert retention_manifest["warnings_count"] == 0


def test_dlp_health_uses_fast_frozen_traceability_report_summary(tmp_path):
    policy = _build_policy(tmp_path)
    traceability_path = tmp_path / "traceability_report.json"
    traceability_path.write_text(
        '{"schema_version":"dlp-traceability-report-v1","report_id":"r1","generated_at":"2026-04-25T00:00:00+00:00","manifest_ref":{"status":"present","manifest_id":"m1","generated_at":"2026-04-25T00:00:00+00:00"},"samples":[],"summary":{"sample_count":12,"pass_count":9,"partial_count":2,"fail_count":1,"missing_manifest":false,"warnings_count":3},"warnings":[{"code":"x"}]}',
        encoding="utf-8",
    )

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    traceability_report = payload.get("traceability_report") or {}
    assert traceability_report["status"] == "frozen"
    assert traceability_report["sample_count"] == 0
    assert traceability_report["fail_count"] == 0
    assert traceability_report["warnings_count"] == 0
    assert traceability_report["unexplained_partial_count"] == 0
    assert traceability_report["current_epoch_pass_rate"] is None


def test_dlp_health_uses_fast_frozen_archive_plan_summary(tmp_path):
    policy = _build_policy(tmp_path)
    archive_path = tmp_path / "archive_candidate_plan.json"
    archive_path.write_text(
        '{"schema_version":"dlp-archive-candidate-plan-v1","plan_id":"p1","generated_at":"2026-04-25T00:00:00+00:00","mode":"dry_run_only","manifest_ref":{"status":"present"},"traceability_ref":{"status":"present"},"candidates":[],"summary":{"eligible_count":3,"blocked_count":2,"review_required_count":1,"total_candidate_bytes":98765,"warnings_count":4},"warnings":[]}',
        encoding="utf-8",
    )

    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    archive_plan = payload.get("archive_plan") or {}
    assert archive_plan["status"] == "frozen"
    assert archive_plan["mode"] == "automatic_cleanup_expansion_paused"
    assert archive_plan["eligible_count"] == 0
    assert archive_plan["blocked_count"] == 0
    assert archive_plan["review_required_count"] == 0
    assert archive_plan["total_candidate_bytes"] == 0
    assert archive_plan["warnings_count"] == 0


def test_dlp_health_exposes_archive_transaction_preview_summary(tmp_path):
    policy = _build_policy(tmp_path)
    preview_path = tmp_path / "archive_transaction_preview.json"
    preview_path.write_text(
        '{"schema_version":"dlp-archive-transaction-preview-v1","preview_id":"tx1","generated_at":"2026-04-25T00:00:00+00:00","mode":"preview_only","plan_ref":{"status":"present"},"items":[],"summary":{"eligible_input_count":3,"preview_item_count":2,"excluded_blocked_count":4,"excluded_review_required_count":1,"blocked_precondition_count":0,"total_preview_bytes":3456,"warnings_count":2},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    txn = payload.get("archive_transaction_preview") or {}
    assert txn["status"] == "frozen"
    assert txn["mode"] == "automatic_cleanup_expansion_paused"
    assert txn["eligible_input_count"] == 0
    assert txn["preview_item_count"] == 0
    assert txn["excluded_blocked_count"] == 0
    assert txn["excluded_review_required_count"] == 0
    assert txn["blocked_precondition_count"] == 0
    assert txn["total_preview_bytes"] == 0
    assert txn["warnings_count"] == 0


def test_dlp_health_exposes_archive_restore_readiness_summary(tmp_path):
    policy = _build_policy(tmp_path)
    readiness_path = tmp_path / "archive_restore_readiness_report.json"
    readiness_path.write_text(
        '{"schema_version":"dlp-archive-restore-readiness-v1","readiness_id":"r1","generated_at":"2026-04-25T00:00:00+00:00","mode":"readiness_only","transaction_preview_ref":{"status":"present"},"traceability_ref":{"status":"present"},"request_mappings":[],"summary":{"sample_count":6,"mapped_request_count":5,"unmapped_request_count":1,"warnings_count":1},"warnings":[]}',
        encoding="utf-8",
    )
    payload = health_mod.build_health_payload(policy=policy, now_ts=101.0)
    readiness = payload.get("archive_restore_readiness") or {}
    assert readiness["status"] == "frozen"
    assert readiness["mode"] == "automatic_cleanup_expansion_paused"
    assert readiness["sample_count"] == 0
    assert readiness["mapped_request_count"] == 0
    assert readiness["unmapped_request_count"] == 0
    assert readiness["warnings_count"] == 0


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
    assert gate["status"] == "frozen"
    assert gate["allowed"] is False
    assert gate["gate_status"] == "frozen"
    assert gate["blocking_count"] == 0
    assert gate["approval_status"] == "frozen"


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
    assert pilot["status"] == "frozen"
    assert pilot["pilot_id"] is None
    assert pilot["source_kind"] is None
    assert pilot["source_bytes"] == 0
    assert pilot["archive_bytes"] == 0
    assert pilot["checksum_match"] is False
    assert pilot["source_retained"] is False
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
    assert readthrough["status"] == "frozen"
    assert readthrough["source_retained"] is False
    assert readthrough["archive_copy_readable"] is False
    assert readthrough["checksum_match"] is False
    assert readthrough["read_path_unchanged"] is True
    assert readthrough["validated_at"] is None


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
    assert fallback["status"] == "frozen"
    assert fallback["mode"] == "automatic_cleanup_expansion_paused"
    assert fallback["fallback_available"] is False
    assert fallback["archive_copy_readable"] is False
    assert fallback["checksum_match"] is False
    assert fallback["source_missing_simulated"] is False
    assert fallback["production_read_path_unchanged"] is True
    assert fallback["request_evidence_fallback_status"] is None


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
    assert quarantine["status"] == "frozen"
    assert quarantine["mode"] == "automatic_cleanup_expansion_paused"
    assert quarantine["candidate_present"] is False
    assert quarantine["blocking_count"] == 0
    assert quarantine["source_move_executed"] is False
    assert quarantine["source_retained"] is False
    assert quarantine["production_read_path_unchanged"] is True
    assert quarantine["planned_action"] is None


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
    assert quarantine["status"] == "frozen"
    assert quarantine["mode"] == "automatic_cleanup_expansion_paused"
    assert quarantine["source_kind"] is None
    assert quarantine["source_move_executed"] is False
    assert quarantine["source_retained"] is False
    assert quarantine["blocking_count"] == 0
    assert quarantine["quarantine_path"] is None


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
    assert restore["status"] == "frozen"
    assert restore["mode"] == "automatic_cleanup_expansion_paused"
    assert restore["restore_target_scope"] is None
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
    assert non_active["status"] == "frozen"
    assert non_active["mode"] == "automatic_cleanup_expansion_paused"
    assert non_active["total_scanned"] == 0
    assert non_active["plausible_non_active_count"] == 0
    assert non_active["forbidden_count"] == 0
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
    assert readiness["status"] == "frozen"
    assert readiness["mode"] == "automatic_cleanup_expansion_paused"
    assert readiness["selected_candidate_present"] is False
    assert readiness["selected_candidate_kind"] is None
    assert readiness["planned_quarantine_path"] is None
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
    assert gate["status"] == "frozen"
    assert gate["allowed"] is False
    assert gate["gate_status"] == "frozen"
    assert gate["blocking_count"] == 0
    assert gate["approval_status"] == "frozen"
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
    assert quarantine["status"] == "frozen"
    assert quarantine["mode"] == "automatic_cleanup_expansion_paused"
    assert quarantine["candidate_kind"] is None
    assert quarantine["checksum_match"] is False
    assert quarantine["source_move_executed"] is False
    assert quarantine["non_active_copy_move_executed"] is False
    assert quarantine["delete_compress_executed"] is False
    assert quarantine["production_read_path_unchanged"] is True


def test_data_lifecycle_meter_storage_status_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected = {
        "schema_version": "dlp-meter-storage-v2-status-v1",
        "status": "healthy",
        "mode": "dual_write_observe_only",
    }
    monkeypatch.setattr(data_lifecycle_api._meter_storage_v2_mod, "get_status_payload", lambda: expected)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/status")
    assert response.status_code == 200
    assert response.json() == expected


def test_data_lifecycle_meter_storage_rebuild_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)

    expected_record = {
        "schema_version": "dlp-meter-storage-v2-rebuild-v1",
        "trigger": "meter_storage_v2_rebuild",
        "status": "success",
    }
    expected_parity = {
        "schema_version": "dlp-meter-storage-v2-parity-v1",
        "status": "passed",
        "critical_mismatch_count": 0,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_storage_v2_mod,
        "rebuild_from_legacy",
        lambda: (expected_record, expected_parity),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dlp-meter-storage-v2-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_storage_v2_rebuild"
    assert payload["parity"]["critical_mismatch_count"] == 0


def test_data_lifecycle_meter_storage_parity_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected = {
        "schema_version": "dlp-meter-storage-v2-parity-v1",
        "status": "passed",
        "critical_mismatch_count": 0,
        "read_mode": "snapshot_first",
    }
    monkeypatch.setattr(data_lifecycle_api._meter_storage_v2_mod, "read_parity_snapshot", lambda: expected)
    monkeypatch.setattr(
        data_lifecycle_api._meter_storage_v2_mod,
        "build_parity_report",
        lambda: (_ for _ in ()).throw(AssertionError("default parity GET must use snapshot")),
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/parity")
    assert response.status_code == 200
    assert response.json() == expected


def test_data_lifecycle_meter_storage_parity_fresh_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected = {
        "schema_version": "dlp-meter-storage-v2-parity-v1",
        "status": "passed",
        "critical_mismatch_count": 0,
    }
    monkeypatch.setattr(data_lifecycle_api._meter_storage_v2_mod, "build_parity_report", lambda: expected)
    monkeypatch.setattr(
        data_lifecycle_api._meter_storage_v2_mod,
        "read_parity_snapshot",
        lambda: (_ for _ in ()).throw(AssertionError("fresh parity GET must full-scan")),
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/parity?fresh=true")
    assert response.status_code == 200
    assert response.json() == expected


def test_data_lifecycle_meter_storage_parity_rebuild_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)

    expected = {
        "schema_version": "dlp-meter-storage-v2-parity-rebuild-v1",
        "record": {"trigger": "meter_storage_v2_rebuild"},
        "parity": {"critical_mismatch_count": 0},
        "snapshot": {"schema_version": "dlp-meter-storage-v2-parity-snapshot-v1"},
    }
    monkeypatch.setattr(data_lifecycle_api._meter_storage_v2_mod, "parity_with_rebuild", lambda: expected)

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/parity/rebuild")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "dlp-meter-storage-v2-parity-rebuild-v1"


def test_data_lifecycle_meter_cleanup_preview_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_cleanup_preview_mod, "read_preview", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-preview-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "preview_only"
    assert payload["cleanup_allowed"] is False


def test_data_lifecycle_meter_cleanup_preview_rebuild_endpoint_returns_record_and_preview(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-preview",
        "trigger": "meter_cleanup_preview_rebuild",
        "status": "success",
    }
    expected_preview = {
        "schema_version": "res-legacy-meter-cleanup-preview-v1",
        "mode": "preview_only",
        "status": "blocked",
        "cleanup_allowed": False,
        "estimated_reclaim_bytes": 123,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_preview_mod,
        "rebuild_preview",
        lambda policy=None: (expected_record, expected_preview),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/preview/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-preview-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_preview_rebuild"
    assert payload["preview"]["mode"] == "preview_only"
    assert payload["preview"]["cleanup_allowed"] is False


def test_meter_cleanup_preview_does_not_expose_execute_or_destructive_endpoints():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/cleanup/execute",
        "/data-lifecycle/meter-storage/cleanup/delete",
        "/data-lifecycle/meter-storage/cleanup/move",
        "/data-lifecycle/meter-storage/cleanup/compress",
        "/data-lifecycle/meter-storage/cleanup/truncate",
        "/data-lifecycle/meter-storage/cleanup/pilot/delete",
        "/data-lifecycle/meter-storage/cleanup/pilot/compress",
        "/data-lifecycle/meter-storage/cleanup/pilot/truncate",
        "/data-lifecycle/meter-storage/cleanup/pilot/batch",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_cleanup_gate_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_cleanup_execution_gate_mod, "read_gate", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/gate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-execution-gate-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "cleanup_gate_only"
    assert payload["cleanup_allowed"] is False
    assert payload["rollback_required"] is True


def test_data_lifecycle_meter_cleanup_gate_rebuild_endpoint_returns_record_and_gate(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-gate",
        "trigger": "meter_cleanup_execution_gate_rebuild",
        "status": "success",
    }
    expected_gate = {
        "schema_version": "res-legacy-meter-cleanup-execution-gate-v1",
        "mode": "cleanup_gate_only",
        "cleanup_gate_status": "blocked",
        "cleanup_allowed": False,
        "rollback_required": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_execution_gate_mod,
        "rebuild_gate",
        lambda policy=None: (expected_record, expected_gate),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/gate/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-execution-gate-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_execution_gate_rebuild"
    assert payload["cleanup_gate"]["cleanup_allowed"] is False


def test_data_lifecycle_meter_cleanup_transaction_preview_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_cleanup_transaction_preview_mod, "read_preview", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/transaction-preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-transaction-preview-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "cleanup_transaction_preview_only"
    assert payload["execution_allowed"] is False


def test_data_lifecycle_meter_cleanup_transaction_preview_rebuild_endpoint_returns_record_and_preview(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-transaction-preview",
        "trigger": "meter_cleanup_transaction_preview_rebuild",
        "status": "success",
    }
    expected_preview = {
        "schema_version": "res-legacy-meter-cleanup-transaction-preview-v1",
        "mode": "cleanup_transaction_preview_only",
        "status": "blocked",
        "execution_allowed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_transaction_preview_mod,
        "rebuild_preview",
        lambda policy=None: (expected_record, expected_preview),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/transaction-preview/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-transaction-preview-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_transaction_preview_rebuild"
    assert payload["transaction_preview"]["execution_allowed"] is False


def test_data_lifecycle_meter_cleanup_rollback_drill_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_rollback_drill_mod,
        "read_rollback_drill_report",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/rollback-drill")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-rollback-drill-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "rollback_readback_drill_only"
    assert payload["staging_restore_readable"] is False
    assert payload["production_restore_started"] is False


def test_data_lifecycle_meter_cleanup_rollback_drill_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-rollback-drill",
        "trigger": "meter_cleanup_rollback_drill_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-legacy-meter-cleanup-rollback-drill-v1",
        "mode": "rollback_readback_drill_only",
        "status": "passed",
        "staging_restore_readable": True,
        "checksum_match": True,
        "source_retained": True,
        "production_restore_started": False,
        "cleanup_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_rollback_drill_mod,
        "rebuild_rollback_drill_report",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/rollback-drill/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-rollback-drill-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_rollback_drill_rebuild"
    assert payload["rollback_drill"]["checksum_match"] is True


def test_data_lifecycle_meter_cleanup_pilot_latest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_cleanup_pilot_mod, "read_latest_pilot", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/pilot/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-pilot-record-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "single_reversible_quarantine_only"
    assert payload["source_move_executed"] is False
    assert payload["delete_executed"] is False


def test_data_lifecycle_meter_cleanup_pilot_quarantine_one_returns_record(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-pilot-one",
        "trigger": "meter_cleanup_quarantine_pilot_quarantine_one",
        "status": "success",
    }
    expected_pilot = {
        "schema_version": "res-legacy-meter-cleanup-pilot-record-v1",
        "mode": "single_reversible_quarantine_only",
        "status": "success",
        "source_move_executed": True,
        "delete_executed": False,
        "compress_executed": False,
        "truncate_executed": False,
        "batch_cleanup_executed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_pilot_mod,
        "execute_single_file_quarantine",
        lambda policy=None: (expected_record, expected_pilot),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/pilot/quarantine-one")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-pilot-record-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_quarantine_pilot_quarantine_one"
    assert payload["pilot"]["status"] == "success"
    assert payload["pilot"]["source_move_executed"] is True


def test_data_lifecycle_meter_cleanup_stability_window_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_stability_window_mod,
        "read_stability_window_report",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/stability-window")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-stability-window-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "post_pilot_stability_window_observe_only"
    assert payload["observed_pilot_status"] == "missing"
    assert payload["cleanup_scope_expansion_started"] is False


def test_data_lifecycle_meter_cleanup_stability_window_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-stability-window",
        "trigger": "meter_cleanup_stability_window_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-legacy-meter-cleanup-stability-window-v1",
        "mode": "post_pilot_stability_window_observe_only",
        "status": "passed",
        "observed_pilot_status": "success",
        "cleanup_scope_expansion_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_stability_window_mod,
        "rebuild_stability_window_report",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/stability-window/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-stability-window-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_stability_window_rebuild"
    assert payload["stability_window"]["status"] == "passed"
    assert payload["stability_window"]["cleanup_scope_expansion_started"] is False


def test_meter_cleanup_stability_window_does_not_expose_execute_delete_move_compress_truncate_batch():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/cleanup/stability-window/execute",
        "/data-lifecycle/meter-storage/cleanup/stability-window/delete",
        "/data-lifecycle/meter-storage/cleanup/stability-window/move",
        "/data-lifecycle/meter-storage/cleanup/stability-window/compress",
        "/data-lifecycle/meter-storage/cleanup/stability-window/truncate",
        "/data-lifecycle/meter-storage/cleanup/stability-window/batch",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_cleanup_scaleup_readiness_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_scaleup_readiness_mod,
        "read_readiness_report",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/scaleup-readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-scaleup-readiness-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "scaleup_readiness_only"
    assert payload["ready_for_scaleup"] is False
    assert payload["cleanup_scope_expansion_started"] is False


def test_data_lifecycle_meter_cleanup_scaleup_readiness_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-cleanup-scaleup-readiness",
        "trigger": "meter_cleanup_scaleup_readiness_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-legacy-meter-cleanup-scaleup-readiness-v1",
        "mode": "scaleup_readiness_only",
        "status": "blocked",
        "ready_for_scaleup": False,
        "cleanup_scope_expansion_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_scaleup_readiness_mod,
        "rebuild_readiness_report",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/scaleup-readiness/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-cleanup-scaleup-readiness-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_scaleup_readiness_rebuild"
    assert payload["scaleup_readiness"]["status"] == "blocked"
    assert payload["scaleup_readiness"]["ready_for_scaleup"] is False
    assert payload["scaleup_readiness"]["cleanup_scope_expansion_started"] is False


def test_meter_cleanup_scaleup_readiness_does_not_expose_execute_delete_move_compress_truncate_batch():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/cleanup/scaleup-readiness/execute",
        "/data-lifecycle/meter-storage/cleanup/scaleup-readiness/delete",
        "/data-lifecycle/meter-storage/cleanup/scaleup-readiness/move",
        "/data-lifecycle/meter-storage/cleanup/scaleup-readiness/compress",
        "/data-lifecycle/meter-storage/cleanup/scaleup-readiness/truncate",
        "/data-lifecycle/meter-storage/cleanup/scaleup-readiness/batch",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_cleanup_repeatable_pilot_protocol_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_repeatable_pilot_protocol_mod,
        "read_protocol",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-repeatable-cleanup-pilot-protocol-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "proposal_only"
    assert payload["second_file_pilot_allowed"] is False
    assert payload["execution_started"] is False
    assert payload["cleanup_scope_expansion_started"] is False


def test_data_lifecycle_meter_cleanup_repeatable_pilot_protocol_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-repeatable-protocol",
        "trigger": "meter_cleanup_repeatable_pilot_protocol_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-repeatable-cleanup-pilot-protocol-v1",
        "mode": "proposal_only",
        "status": "blocked",
        "second_file_pilot_allowed": False,
        "execution_started": False,
        "cleanup_scope_expansion_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_repeatable_pilot_protocol_mod,
        "rebuild_protocol",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-repeatable-cleanup-pilot-protocol-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_repeatable_pilot_protocol_rebuild"
    assert payload["repeatable_pilot_protocol"]["status"] == "blocked"


def test_meter_cleanup_repeatable_pilot_protocol_does_not_expose_execute_delete_move_compress_truncate_batch():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/execute",
        "/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/delete",
        "/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/move",
        "/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/compress",
        "/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/truncate",
        "/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/batch",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_cleanup_second_file_pilot_proposal_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_second_file_pilot_proposal_mod,
        "read_proposal",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-second-file-cleanup-pilot-proposal-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "proposal_only"
    assert payload["second_file_pilot_allowed"] is False
    assert payload["execution_started"] is False
    assert payload["cleanup_scope_expansion_started"] is False


def test_data_lifecycle_meter_cleanup_second_file_pilot_proposal_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-second-file-proposal",
        "trigger": "meter_cleanup_second_file_pilot_proposal_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-second-file-cleanup-pilot-proposal-v1",
        "mode": "proposal_only",
        "status": "blocked",
        "second_file_pilot_allowed": False,
        "execution_started": False,
        "cleanup_scope_expansion_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_second_file_pilot_proposal_mod,
        "rebuild_proposal",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-second-file-cleanup-pilot-proposal-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_second_file_pilot_proposal_rebuild"
    assert payload["second_file_pilot_proposal"]["status"] == "blocked"


def test_meter_cleanup_second_file_pilot_proposal_does_not_expose_execute_delete_move_compress_truncate_batch():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/execute",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/delete",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/move",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/compress",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/truncate",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/batch",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_cleanup_second_file_pilot_approval_readiness_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_second_file_pilot_approval_readiness_mod,
        "read_approval_readiness",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-second-file-cleanup-pilot-approval-readiness-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "approval_readiness_only"
    assert payload["required_operator_approval"] is True
    assert payload["operator_approval_written"] is False
    assert payload["second_file_pilot_allowed"] is False
    assert payload["execution_started"] is False
    assert payload["cleanup_scope_expansion_started"] is False


def test_data_lifecycle_meter_cleanup_second_file_pilot_approval_readiness_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-second-file-approval-readiness",
        "trigger": "meter_cleanup_second_file_pilot_approval_readiness_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-second-file-cleanup-pilot-approval-readiness-v1",
        "mode": "approval_readiness_only",
        "status": "ready_for_operator_decision",
        "operator_approval_written": False,
        "second_file_pilot_allowed": False,
        "execution_started": False,
        "cleanup_scope_expansion_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_cleanup_second_file_pilot_approval_readiness_mod,
        "rebuild_approval_readiness",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-second-file-cleanup-pilot-approval-readiness-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_cleanup_second_file_pilot_approval_readiness_rebuild"
    assert payload["second_file_pilot_approval_readiness"]["status"] == "ready_for_operator_decision"
    assert payload["second_file_pilot_approval_readiness"]["second_file_pilot_allowed"] is False


def test_meter_cleanup_second_file_pilot_approval_readiness_does_not_expose_execute_delete_move_compress_truncate_batch():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/execute",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/delete",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/move",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/compress",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/truncate",
        "/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/batch",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_backup_export_readiness_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_backup_export_readiness_mod, "read_readiness", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-readiness-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "backup_export_readiness_only"
    assert payload["backup_export_allowed"] is False
    assert payload["cleanup_allowed"] is False


def test_data_lifecycle_meter_backup_export_readiness_rebuild_endpoint_returns_record_and_readiness(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-readiness",
        "trigger": "meter_backup_export_readiness_rebuild",
        "status": "success",
    }
    expected_readiness = {
        "schema_version": "res-legacy-meter-backup-export-readiness-v1",
        "mode": "backup_export_readiness_only",
        "status": "blocked",
        "backup_export_allowed": False,
        "cleanup_allowed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_readiness_mod,
        "rebuild_readiness",
        lambda policy=None: (expected_record, expected_readiness),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/readiness/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-readiness-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_readiness_rebuild"
    assert payload["readiness"]["mode"] == "backup_export_readiness_only"
    assert payload["readiness"]["backup_export_allowed"] is False
    assert payload["readiness"]["cleanup_allowed"] is False


def test_meter_backup_export_readiness_does_not_expose_execute_copy_archive_or_cleanup_delete():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/backup-export/execute",
        "/data-lifecycle/meter-storage/backup-export/copy",
        "/data-lifecycle/meter-storage/backup-export/archive",
        "/data-lifecycle/meter-storage/cleanup/execute",
        "/data-lifecycle/meter-storage/cleanup/delete",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_backup_export_plan_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_backup_export_plan_mod, "read_plan", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/plan")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-plan-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "dry_run_preview_only"
    assert payload["backup_export_allowed"] is False
    assert payload["cleanup_allowed"] is False
    assert payload["execution_allowed"] is False


def test_data_lifecycle_meter_backup_export_plan_rebuild_endpoint_returns_record_and_plan(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-plan",
        "trigger": "meter_backup_export_plan_rebuild",
        "status": "success",
    }
    expected_plan = {
        "schema_version": "res-legacy-meter-backup-export-plan-v1",
        "mode": "dry_run_preview_only",
        "status": "blocked",
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "execution_allowed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_plan_mod,
        "rebuild_plan",
        lambda policy=None: (expected_record, expected_plan),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/plan/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-plan-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_plan_rebuild"
    assert payload["plan"]["mode"] == "dry_run_preview_only"
    assert payload["plan"]["execution_allowed"] is False


def test_meter_backup_export_plan_does_not_expose_execute_copy_archive_delete_move_compress_truncate():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/backup-export/execute",
        "/data-lifecycle/meter-storage/backup-export/copy",
        "/data-lifecycle/meter-storage/backup-export/archive",
        "/data-lifecycle/meter-storage/backup-export/delete",
        "/data-lifecycle/meter-storage/backup-export/move",
        "/data-lifecycle/meter-storage/backup-export/compress",
        "/data-lifecycle/meter-storage/backup-export/truncate",
        "/data-lifecycle/meter-storage/backup-export/plan/execute",
        "/data-lifecycle/meter-storage/cleanup/execute",
        "/data-lifecycle/meter-storage/cleanup/delete",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_backup_export_package_manifest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_package_manifest_mod,
        "read_package_manifest",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/package-manifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-package-manifest-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "package_manifest_preview_only"
    assert payload["backup_export_allowed"] is False
    assert payload["cleanup_allowed"] is False
    assert payload["execution_allowed"] is False


def test_data_lifecycle_meter_backup_export_package_manifest_rebuild_endpoint_returns_record_and_manifest(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-package-manifest",
        "trigger": "meter_backup_export_package_manifest_rebuild",
        "status": "success",
    }
    expected_manifest = {
        "schema_version": "res-legacy-meter-backup-export-package-manifest-v1",
        "mode": "package_manifest_preview_only",
        "status": "blocked",
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "execution_allowed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_package_manifest_mod,
        "rebuild_package_manifest",
        lambda policy=None: (expected_record, expected_manifest),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/package-manifest/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-package-manifest-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_package_manifest_rebuild"
    assert payload["package_manifest"]["mode"] == "package_manifest_preview_only"
    assert payload["package_manifest"]["execution_allowed"] is False


def test_data_lifecycle_meter_backup_export_approval_template_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_approval_template_mod,
        "read_approval_template",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/approval-template")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-approval-template-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "approval_template_only"
    assert payload["approval_valid"] is False
    assert payload["backup_export_allowed"] is False
    assert payload["cleanup_allowed"] is False
    assert payload["execution_allowed"] is False


def test_data_lifecycle_meter_backup_export_approval_template_rebuild_endpoint_returns_record_and_template(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-approval-template",
        "trigger": "meter_backup_export_approval_template_rebuild",
        "status": "success",
    }
    expected_template = {
        "schema_version": "res-legacy-meter-backup-export-approval-template-v1",
        "mode": "approval_template_only",
        "status": "blocked",
        "approval_valid": False,
        "backup_export_allowed": False,
        "cleanup_allowed": False,
        "execution_allowed": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_approval_template_mod,
        "rebuild_approval_template",
        lambda policy=None: (expected_record, expected_template),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/approval-template/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-approval-template-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_approval_template_rebuild"
    assert payload["approval_template"]["mode"] == "approval_template_only"
    assert payload["approval_template"]["approval_valid"] is False


def test_meter_backup_export_approval_and_manifest_do_not_expose_execute_copy_archive_delete_move_compress_truncate():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/backup-export/approval-template/execute",
        "/data-lifecycle/meter-storage/backup-export/approval-template/approve",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/execute",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/copy",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/archive",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/delete",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/move",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/compress",
        "/data-lifecycle/meter-storage/backup-export/package-manifest/truncate",
        "/data-lifecycle/meter-storage/backup-export/execution/gate/execute",
        "/data-lifecycle/meter-storage/backup-export/operator-approval/create",
        "/data-lifecycle/meter-storage/backup-export/operator-approval/approve",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_backup_export_execution_gate_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(data_lifecycle_api._meter_backup_export_execution_gate_mod, "read_gate", lambda policy=None: None)

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/execution/gate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-execution-gate-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "execution_gate_only"
    assert payload["allowed"] is False
    assert payload["backup_export_execution_started"] is False
    assert payload["cleanup_execution_started"] is False


def test_data_lifecycle_meter_backup_export_execution_gate_rebuild_endpoint_returns_record_and_gate(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-execution-gate",
        "trigger": "meter_backup_export_execution_gate_rebuild",
        "status": "success",
    }
    expected_gate = {
        "schema_version": "res-legacy-meter-backup-export-execution-gate-v1",
        "mode": "execution_gate_only",
        "status": "blocked",
        "allowed": False,
        "backup_export_execution_started": False,
        "cleanup_execution_started": False,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_execution_gate_mod,
        "rebuild_gate",
        lambda policy=None: (expected_record, expected_gate),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/execution/gate/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-execution-gate-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_execution_gate_rebuild"
    assert payload["execution_gate"]["mode"] == "execution_gate_only"
    assert payload["execution_gate"]["allowed"] is False


def test_data_lifecycle_meter_backup_export_operator_approval_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_operator_approval_mod,
        "read_operator_approval",
        lambda policy=None: None,
    )
    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/operator-approval")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-operator-approval-v1"
    assert payload["status"] == "missing"


def test_data_lifecycle_meter_backup_export_execution_proposal_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_execution_proposal_mod,
        "read_execution_proposal",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/execution/proposal")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-execution-proposal-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "proposal_only"
    assert payload["proposal_status"] == "blocked"
    assert payload["execution_started"] is False
    assert payload["cleanup_started"] is False
    assert payload["operator_decision_required"] is True


def test_data_lifecycle_meter_backup_export_execution_proposal_rebuild_endpoint_returns_record_and_proposal(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-execution-proposal",
        "trigger": "meter_backup_export_execution_proposal_rebuild",
        "status": "success",
    }
    expected_proposal = {
        "schema_version": "res-legacy-meter-backup-export-execution-proposal-v1",
        "mode": "proposal_only",
        "proposal_status": "ready_for_operator_decision",
        "execution_started": False,
        "cleanup_started": False,
        "operator_decision_required": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_execution_proposal_mod,
        "rebuild_execution_proposal",
        lambda policy=None: (expected_record, expected_proposal),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/execution/proposal/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-execution-proposal-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_execution_proposal_rebuild"
    assert payload["execution_proposal"]["mode"] == "proposal_only"
    assert payload["execution_proposal"]["execution_started"] is False
    assert payload["execution_proposal"]["cleanup_started"] is False


def test_meter_backup_export_execution_proposal_does_not_expose_execute_run_copy_archive_cleanup_delete_move_compress_truncate():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/execute",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/run",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/copy",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/archive",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/cleanup",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/delete",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/move",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/compress",
        "/data-lifecycle/meter-storage/backup-export/execution/proposal/truncate",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_backup_export_copy_pilot_latest_endpoint_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_copy_pilot_mod,
        "read_latest_copy_pilot",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/copy-pilot/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-copy-pilot-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "single_copy_pilot_only"
    assert payload["source_retained"] is True
    assert payload["checksum_match"] is False
    assert payload["cleanup_started"] is False
    assert payload["read_path_unchanged"] is True


def test_data_lifecycle_meter_backup_export_copy_pilot_run_one_endpoint_returns_record_and_pilot(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-copy-pilot",
        "trigger": "meter_backup_export_copy_pilot_run_one",
        "status": "success",
    }
    expected_pilot = {
        "schema_version": "res-legacy-meter-backup-export-copy-pilot-v1",
        "mode": "single_copy_pilot_only",
        "status": "success",
        "source_retained": True,
        "checksum_match": True,
        "cleanup_started": False,
        "read_path_unchanged": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_copy_pilot_mod,
        "run_one_copy_pilot",
        lambda policy=None: (expected_record, expected_pilot),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/copy-pilot/run-one")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-copy-pilot-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_copy_pilot_run_one"
    assert payload["copy_pilot"]["mode"] == "single_copy_pilot_only"
    assert payload["copy_pilot"]["source_retained"] is True
    assert payload["copy_pilot"]["checksum_match"] is True
    assert payload["copy_pilot"]["cleanup_started"] is False


def test_meter_backup_export_copy_pilot_does_not_expose_execute_full_export_cleanup_delete_move_compress_truncate():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/execute",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/full-export",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/cleanup",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/delete",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/move",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/compress",
        "/data-lifecycle/meter-storage/backup-export/copy-pilot/truncate",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404


def test_data_lifecycle_meter_backup_export_restore_readback_report_returns_missing_when_absent(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_restore_readback_mod,
        "read_restore_readback_report",
        lambda policy=None: None,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/restore-readback")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-restore-readback-v1"
    assert payload["status"] == "missing"
    assert payload["mode"] == "restore_readback_validation_only"
    assert payload["source_retained"] is True
    assert payload["checksum_match"] is False
    assert payload["production_restore_started"] is False
    assert payload["cleanup_started"] is False


def test_data_lifecycle_meter_backup_export_restore_readback_report_read_endpoint_returns_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_report = {
        "schema_version": "res-legacy-meter-backup-export-restore-readback-v1",
        "mode": "restore_readback_validation_only",
        "status": "passed",
        "source_retained": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
        "read_path_unchanged": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_restore_readback_mod,
        "read_restore_readback_report",
        lambda policy=None: expected_report,
    )

    client = TestClient(app)
    response = client.get("/data-lifecycle/meter-storage/backup-export/restore-readback")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-restore-readback-v1"
    assert payload["status"] == "passed"
    assert payload["source_retained"] is True
    assert payload["checksum_match"] is True
    assert payload["production_restore_started"] is False
    assert payload["cleanup_started"] is False
    assert payload["read_path_unchanged"] is True


def test_data_lifecycle_meter_backup_export_restore_readback_rebuild_endpoint_returns_record_and_report(monkeypatch):
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    expected_record = {
        "cycle_id": "cycle-backup-restore-readback",
        "trigger": "meter_backup_export_restore_readback_rebuild",
        "status": "success",
    }
    expected_report = {
        "schema_version": "res-legacy-meter-backup-export-restore-readback-v1",
        "mode": "restore_readback_validation_only",
        "status": "passed",
        "source_retained": True,
        "checksum_match": True,
        "production_restore_started": False,
        "cleanup_started": False,
        "read_path_unchanged": True,
    }
    monkeypatch.setattr(
        data_lifecycle_api._meter_backup_export_restore_readback_mod,
        "rebuild_restore_readback_report",
        lambda policy=None: (expected_record, expected_report),
    )

    client = TestClient(app)
    response = client.post("/data-lifecycle/meter-storage/backup-export/restore-readback/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "res-legacy-meter-backup-export-restore-readback-rebuild-v1"
    assert payload["record"]["trigger"] == "meter_backup_export_restore_readback_rebuild"
    assert payload["restore_readback"]["mode"] == "restore_readback_validation_only"
    assert payload["restore_readback"]["source_retained"] is True
    assert payload["restore_readback"]["checksum_match"] is True
    assert payload["restore_readback"]["production_restore_started"] is False
    assert payload["restore_readback"]["cleanup_started"] is False
    assert payload["restore_readback"]["read_path_unchanged"] is True


def test_meter_backup_export_restore_readback_does_not_expose_execute_delete_move_compress_truncate_cleanup():
    app = FastAPI()
    app.include_router(data_lifecycle_api.router)
    client = TestClient(app)
    forbidden_paths = [
        "/data-lifecycle/meter-storage/backup-export/restore-readback/execute",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/restore",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/production-restore",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/delete",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/move",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/compress",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/truncate",
        "/data-lifecycle/meter-storage/backup-export/restore-readback/cleanup",
    ]
    for path in forbidden_paths:
        response = client.post(path)
        assert response.status_code == 404
