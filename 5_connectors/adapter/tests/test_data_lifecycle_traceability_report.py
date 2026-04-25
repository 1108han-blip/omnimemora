import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
traceability_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.traceability")
retention_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.retention")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=30.0,
        summary_stale_max_age_seconds=3600.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        retention_manifest_file=str(tmp_path / "retention_manifest.json"),
        traceability_report_file=str(tmp_path / "traceability_report.json"),
    )


def _write_manifest(policy, artifacts):
    payload = {
        "schema_version": "dlp-retention-manifest-v1",
        "manifest_id": "manifest-test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "inventory_only",
        "artifacts": artifacts,
        "summary": {
            "artifact_count": len(artifacts),
            "exists_count": len(artifacts),
            "missing_count": 0,
            "total_bytes": 0,
            "warnings_count": 0,
        },
        "warnings": [],
    }
    retention_mod.write_manifest_atomic(payload, policy=policy)


def test_traceability_report_missing_manifest(tmp_path):
    policy = _build_policy(tmp_path)
    report = traceability_mod.build_report(policy=policy)
    assert report["schema_version"] == "dlp-traceability-report-v1"
    assert report["summary"]["missing_manifest"] is True
    assert report["summary"]["sample_count"] == 0


def test_traceability_report_sample_pass_when_all_sources_present(tmp_path):
    policy = _build_policy(tmp_path)
    meter_index = tmp_path / "meters_index.json"
    compile_events = tmp_path / "compile_events.jsonl"
    proxy_events = tmp_path / "proxy_events.jsonl"
    trace_events = tmp_path / "trace_events.jsonl"

    meter_index.write_text(json.dumps({"req-pass": {"request_id": "req-pass"}}), encoding="utf-8")
    compile_events.write_text('{"request_id":"req-pass"}\n', encoding="utf-8")
    proxy_events.write_text('{"request_id":"req-pass"}\n', encoding="utf-8")
    trace_events.write_text('{"request_id":"req-pass","trace_id":"trace-pass"}\n', encoding="utf-8")

    _write_manifest(
        policy,
        [
            {"kind": "meter_index", "path": str(meter_index)},
            {"kind": "compile_events", "path": str(compile_events)},
            {"kind": "proxy_events", "path": str(proxy_events)},
            {"kind": "trace_events", "path": str(trace_events)},
        ],
    )

    report = traceability_mod.build_report(policy=policy, request_evidence_buildable_fn=lambda _rid: True)
    assert report["summary"]["sample_count"] == 1
    assert report["summary"]["pass_count"] == 1
    sample = report["samples"][0]
    assert sample["status"] == "pass"
    assert sample["trace_id_found"] == "trace-pass"
    assert sample["request_evidence_buildable"] is True


def test_traceability_report_sample_partial_when_meter_only(tmp_path):
    policy = _build_policy(tmp_path)
    meter_index = tmp_path / "meters_index.json"
    meter_index.write_text(json.dumps({"req-partial": {"request_id": "req-partial"}}), encoding="utf-8")

    _write_manifest(policy, [{"kind": "meter_index", "path": str(meter_index)}])
    report = traceability_mod.build_report(policy=policy, request_evidence_buildable_fn=lambda _rid: True)
    assert report["summary"]["sample_count"] == 1
    assert report["summary"]["partial_count"] == 1
    sample = report["samples"][0]
    assert sample["status"] == "partial"
    assert "compile" in sample["missing_sources"]
    assert "trace" in sample["missing_sources"]


def test_traceability_report_sample_fail_when_meter_missing_or_unbuildable(tmp_path):
    policy = _build_policy(tmp_path)
    compile_events = tmp_path / "compile_events.jsonl"
    compile_events.write_text('{"request_id":"req-fail"}\n', encoding="utf-8")

    _write_manifest(policy, [{"kind": "compile_events", "path": str(compile_events)}])
    report = traceability_mod.build_report(policy=policy, request_evidence_buildable_fn=lambda _rid: False)
    assert report["summary"]["sample_count"] == 1
    assert report["summary"]["fail_count"] == 1
    sample = report["samples"][0]
    assert sample["status"] == "fail"
    assert "meter" in sample["missing_sources"]


def test_traceability_report_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    report = {
        "schema_version": "dlp-traceability-report-v1",
        "report_id": "report-1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "manifest_ref": {"status": "missing", "manifest_id": None, "generated_at": None},
        "samples": [],
        "summary": {"sample_count": 0, "pass_count": 0, "partial_count": 0, "fail_count": 0, "missing_manifest": True, "warnings_count": 0},
        "warnings": [],
    }

    monkeypatch.setattr(traceability_mod.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")))
    try:
        traceability_mod.write_report_atomic(report, policy=policy)
        assert False, "expected write_report_atomic to fail"
    except RuntimeError:
        pass

    target = Path(policy.traceability_report_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_traceability_*.tmp")) == []


def test_traceability_rebuild_writes_ledger_trigger(tmp_path):
    policy = _build_policy(tmp_path)
    meter_index = tmp_path / "meters_index.json"
    meter_index.write_text(json.dumps({"req-rebuild": {"request_id": "req-rebuild"}}), encoding="utf-8")
    _write_manifest(policy, [{"kind": "meter_index", "path": str(meter_index)}])

    record, report = traceability_mod.rebuild_report(policy=policy)
    assert record["trigger"] == "traceability_report_rebuild"
    assert record["status"] == "success"
    assert report["schema_version"] == "dlp-traceability-report-v1"

    ledger_records = state_store.read_recent_records(limit=1, trigger="traceability_report_rebuild", policy=policy)
    assert len(ledger_records) == 1
    assert ledger_records[0]["trigger"] == "traceability_report_rebuild"
