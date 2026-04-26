from __future__ import annotations

import hashlib
import importlib
from datetime import datetime, timezone

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
txn_preview_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_transaction_preview")


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_transaction_preview_file=str(tmp_path / "meter_cleanup_transaction_preview.json"),
    )


def _sha256(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def test_cleanup_transaction_preview_blocks_on_missing_approval(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_x.json"
    source.write_text('{"x":1}', encoding="utf-8")
    expected_sha = _sha256(source)
    expected_mtime = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc).isoformat()

    cleanup_preview = {
        "would_cleanup_files": [
            {"name": source.name, "path": str(source), "bytes": source.stat().st_size, "sha256": expected_sha, "mtime": expected_mtime}
        ]
    }
    cleanup_gate = {"blocking_reasons": ["missing_operator_approval"]}
    copy_pilot = {"status": "success", "selected_candidate": {"path": str(source)}, "target_path": "/tmp/pilot", "checksum_match": True}
    restore = {"status": "passed", "checksum_match": True, "source_retained": True}

    monkeypatch.setattr(txn_preview_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(txn_preview_mod._cleanup_gate, "read_gate", lambda policy=None: cleanup_gate)
    monkeypatch.setattr(txn_preview_mod._copy_pilot, "read_latest_copy_pilot", lambda policy=None: copy_pilot)
    monkeypatch.setattr(txn_preview_mod._restore_readback, "read_restore_readback_report", lambda policy=None: restore)
    monkeypatch.setattr(txn_preview_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "passed", "critical_mismatch_count": 0})

    preview = txn_preview_mod.build_transaction_preview(policy=policy)
    assert preview["execution_allowed"] is False
    assert preview["status"] == "blocked"
    assert "execution_not_enabled_in_res021" in preview["blocking_reasons"]
    assert preview["summary"]["candidate_count"] == 1
    item = preview["items"][0]
    assert item["operation"] == "blocked"
    assert "missing_operator_approval" in item["blocking_reasons"]
    assert item["backup_copy_ref"]["status"] == "success"


def test_cleanup_transaction_preview_blocks_hash_drift(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    source = tmp_path / "meters_tenant_y.json"
    source.write_text('{"a":1}', encoding="utf-8")

    cleanup_preview = {
        "would_cleanup_files": [
            {"name": source.name, "path": str(source), "bytes": source.stat().st_size, "sha256": "wrong", "mtime": "2000-01-01T00:00:00+00:00"}
        ]
    }
    monkeypatch.setattr(txn_preview_mod._cleanup_preview, "read_preview", lambda policy=None: cleanup_preview)
    monkeypatch.setattr(txn_preview_mod._cleanup_gate, "read_gate", lambda policy=None: {"blocking_reasons": []})
    monkeypatch.setattr(txn_preview_mod._copy_pilot, "read_latest_copy_pilot", lambda policy=None: {"selected_candidate": {"path": str(source)}})
    monkeypatch.setattr(txn_preview_mod._restore_readback, "read_restore_readback_report", lambda policy=None: {"status": "passed", "checksum_match": True, "source_retained": True})
    monkeypatch.setattr(txn_preview_mod._meter_storage_v2, "build_parity_report", lambda: {"status": "passed", "critical_mismatch_count": 0})

    preview = txn_preview_mod.build_transaction_preview(policy=policy)
    item = preview["items"][0]
    assert item["operation"] == "blocked"
    assert "source_hash_drift" in item["blocking_reasons"]
    assert "source_mtime_drift" in item["blocking_reasons"]


def test_cleanup_transaction_preview_rebuild_writes_preview(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        txn_preview_mod,
        "build_transaction_preview",
        lambda policy=None: {
            "schema_version": txn_preview_mod.METER_CLEANUP_TRANSACTION_PREVIEW_SCHEMA_VERSION,
            "status": "blocked",
            "execution_allowed": False,
            "summary": {"candidate_count": 2},
        },
    )
    record, preview = txn_preview_mod.rebuild_preview(policy=policy)
    assert record["trigger"] == "meter_cleanup_transaction_preview_rebuild"
    assert preview["execution_allowed"] is False
    assert (tmp_path / "meter_cleanup_transaction_preview.json").exists()
