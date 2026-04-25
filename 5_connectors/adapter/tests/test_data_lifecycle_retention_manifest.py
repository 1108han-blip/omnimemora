import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
retention_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.retention")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        summary_ttl_seconds=30.0,
        summary_stale_max_age_seconds=3600.0,
        summary_file=str(tmp_path / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        retention_manifest_file=str(tmp_path / "retention_manifest.json"),
    )


def test_manifest_build_records_checksum_bytes_and_line_count(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    good_jsonl = tmp_path / "compile_events.jsonl"
    bad_jsonl = tmp_path / "proxy_events.jsonl"
    missing = tmp_path / "trace_events.jsonl"

    good_jsonl.write_text('{"request_id":"r1"}\n{"request_id":"r2"}\n', encoding="utf-8")
    bad_jsonl.write_text('{"request_id":"r3"}\nnot-json-line\n', encoding="utf-8")

    monkeypatch.setattr(
        retention_mod,
        "_resolve_artifact_targets",
        lambda _policy: [
            ("compile_events", "compile_events", good_jsonl),
            ("proxy_events", "proxy_events", bad_jsonl),
            ("trace_events", "trace_events", missing),
        ],
    )

    manifest = retention_mod.build_manifest(policy=policy)
    assert manifest["schema_version"] == "dlp-retention-manifest-v1"
    assert manifest["mode"] == "inventory_only"
    assert manifest["summary"]["artifact_count"] == 3

    by_name = {item["name"]: item for item in manifest["artifacts"]}
    assert by_name["compile_events"]["exists"] is True
    assert by_name["compile_events"]["bytes"] == good_jsonl.stat().st_size
    assert by_name["compile_events"]["line_count"] == 2
    assert isinstance(by_name["compile_events"]["sha256"], str)

    assert by_name["proxy_events"]["exists"] is True
    assert by_name["proxy_events"]["line_count"] == 2  # invalid JSONL line is tolerated

    assert by_name["trace_events"]["exists"] is False
    assert by_name["trace_events"]["sha256"] is None
    assert by_name["trace_events"]["line_count"] is None
    assert any(w.get("code") == "artifact_missing" and w.get("artifact") == "trace_events" for w in manifest["warnings"])


def test_manifest_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    manifest = {
        "schema_version": "dlp-retention-manifest-v1",
        "manifest_id": "manifest-x",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "mode": "inventory_only",
        "artifacts": [],
        "summary": {"artifact_count": 0, "exists_count": 0, "missing_count": 0, "total_bytes": 0, "warnings_count": 0},
        "warnings": [],
    }

    def fail_replace(_src, _dst):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(retention_mod.os, "replace", fail_replace)

    try:
        retention_mod.write_manifest_atomic(manifest, policy=policy)
        assert False, "expected write_manifest_atomic to fail"
    except RuntimeError:
        pass

    target = Path(policy.retention_manifest_file)
    assert not target.exists()
    tmp_files = list(target.parent.glob("dlp_retention_*.tmp"))
    assert tmp_files == []


def test_rebuild_manifest_writes_ledger_with_trigger(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    evidence = tmp_path / "compile_events.jsonl"
    evidence.write_text('{"request_id":"r1"}\n', encoding="utf-8")

    monkeypatch.setattr(
        retention_mod,
        "_resolve_artifact_targets",
        lambda _policy: [("compile_events", "compile_events", evidence)],
    )

    record, manifest = retention_mod.rebuild_manifest(policy=policy)
    assert record["trigger"] == "retention_manifest_rebuild"
    assert record["status"] == "success"
    assert manifest["summary"]["artifact_count"] == 1

    manifest_path = Path(policy.retention_manifest_file)
    assert manifest_path.exists()
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "dlp-retention-manifest-v1"

    ledger_records = state_store.read_recent_records(limit=1, trigger="retention_manifest_rebuild", policy=policy)
    assert len(ledger_records) == 1
    assert ledger_records[0]["trigger"] == "retention_manifest_rebuild"
