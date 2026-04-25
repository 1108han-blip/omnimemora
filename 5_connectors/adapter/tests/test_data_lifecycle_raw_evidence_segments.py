import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
segments_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.raw_evidence_segments")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")
compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")


def _build_policy(tmp_path, *, max_bytes=32 * 1024 * 1024, max_age_seconds=6 * 60 * 60):
    return policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=30.0,
        summary_stale_max_age_seconds=3600.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        retention_manifest_file=str(tmp_path / "retention_manifest.json"),
        traceability_report_file=str(tmp_path / "traceability_report.json"),
        archive_plan_file=str(tmp_path / "archive_candidate_plan.json"),
        archive_transaction_preview_file=str(tmp_path / "archive_transaction_preview.json"),
        archive_restore_readiness_file=str(tmp_path / "archive_restore_readiness_report.json"),
        raw_evidence_segments_manifest_file=str(tmp_path / "raw_evidence_segments_manifest.json"),
        raw_evidence_segments_root=str(tmp_path / "raw_segments"),
        raw_evidence_segments_mode="dual_write_observe_only",
        raw_evidence_segment_max_bytes=max_bytes,
        raw_evidence_segment_max_age_seconds=max_age_seconds,
    )


def test_segment_append_and_rotation_by_size(tmp_path):
    policy = _build_policy(tmp_path, max_bytes=120, max_age_seconds=3600)
    base_ts = datetime(2026, 4, 25, tzinfo=timezone.utc).timestamp()
    event = {"request_id": "r1", "timestamp": base_ts, "payload": "x" * 80}

    segments_mod.append_event_dual_write_observe_only(kind="compile_events", event=event, policy=policy)
    segments_mod.append_event_dual_write_observe_only(kind="compile_events", event=event, policy=policy)
    segments_mod.append_event_dual_write_observe_only(kind="compile_events", event=event, policy=policy)

    manifest = segments_mod.read_manifest(policy=policy)
    assert manifest is not None
    assert manifest["schema_version"] == "dlp-raw-evidence-segments-manifest-v1"
    assert manifest["summary"]["total_segments"] >= 2
    assert manifest["summary"]["sealed_segments"] >= 1
    assert manifest["summary"]["active_segments"] >= 1


def test_segment_rotation_by_age(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path, max_bytes=1024 * 1024, max_age_seconds=1)
    now = datetime(2026, 4, 25, 0, 0, 0, tzinfo=timezone.utc)
    later = now + timedelta(seconds=2)
    calls = {"count": 0}

    def fake_now():
        calls["count"] += 1
        return now if calls["count"] <= 1 else later

    monkeypatch.setattr(segments_mod, "_utc_now", fake_now)
    event = {"request_id": "r1", "timestamp": now.timestamp()}
    segments_mod.append_event_dual_write_observe_only(kind="proxy_events", event=event, policy=policy)
    segments_mod.append_event_dual_write_observe_only(kind="proxy_events", event=event, policy=policy)

    manifest = segments_mod.read_manifest(policy=policy)
    assert manifest is not None
    by_kind = [x for x in manifest["segments"] if x["kind"] == "proxy_events"]
    assert any(item["state"] == "sealed" for item in by_kind)


def test_manifest_rebuild_computes_checksums_line_count(tmp_path):
    policy = _build_policy(tmp_path)
    root = Path(policy.raw_evidence_segments_root)
    path = root / "trace_events" / "trace_events-1.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"timestamp": 1}\n{"timestamp": 2}\n', encoding="utf-8")

    record, manifest = segments_mod.rebuild_manifest(policy=policy)
    assert record["trigger"] == "raw_evidence_segments_manifest_rebuild"
    assert record["status"] == "success"
    assert manifest["summary"]["total_segments"] == 1
    segment = manifest["segments"][0]
    assert segment["line_count"] == 2
    assert isinstance(segment["sha256"], str)


def test_manifest_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    manifest = {
        "schema_version": "dlp-raw-evidence-segments-manifest-v1",
        "manifest_id": "manifest-1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "dual_write_observe_only",
        "segments": [],
        "summary": {"total_segments": 0, "active_segments": 0, "sealed_segments": 0, "total_bytes": 0, "warnings_count": 0},
        "warnings": [],
    }

    def fail_replace(_src, _dst):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(segments_mod.os, "replace", fail_replace)

    try:
        segments_mod.write_manifest_atomic(manifest, policy=policy)
        assert False, "expected write_manifest_atomic failure"
    except RuntimeError:
        pass

    target = Path(policy.raw_evidence_segments_manifest_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_raw_evidence_segments_*.tmp")) == []


def test_failure_path_segment_write_non_fatal_legacy_write_kept(tmp_path):
    legacy_path = tmp_path / "compile_events.jsonl"
    bad_root_file = tmp_path / "not_a_dir"
    bad_root_file.write_text("x", encoding="utf-8")
    policy = _build_policy(tmp_path)
    broken_policy = policy_mod.DataLifecyclePolicy(
        **{**policy.__dict__, "raw_evidence_segments_root": str(bad_root_file)}
    )

    old_path = compile_store.COMPILE_EVENTS_PATH
    compile_store.COMPILE_EVENTS_PATH = str(legacy_path)
    event = {"request_id": "legacy-ok", "timestamp": datetime.now(timezone.utc).timestamp()}
    try:
        compile_store.append_compile_event(event)
    finally:
        compile_store.COMPILE_EVENTS_PATH = old_path
    segments_mod.append_event_dual_write_observe_only(
        kind="compile_events",
        event=event,
        policy=broken_policy,
    )

    assert legacy_path.exists()
    lines = legacy_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["request_id"] == "legacy-ok"

    degraded = state_store.read_recent_records(
        limit=5,
        trigger="raw_evidence_segments_dual_write",
        policy=broken_policy,
    )
    assert degraded
    assert degraded[0]["status"] == "degraded"
