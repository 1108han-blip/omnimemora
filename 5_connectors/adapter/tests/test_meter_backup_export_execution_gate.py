import hashlib
import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
approval_template = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template")
execution_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate")
operator_approval = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval")
meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _payload(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "tenant": "all",
        "agent": "openclaw",
        "family_id": "openclaw",
        "timestamp": "2026-04-25T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 100,
        "savings_ratio": 0.1,
        "query": "hello",
    }


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_policy(tmp_path, destination: Path):
    return policy_mod.DataLifecyclePolicy(
        summary_file=str(tmp_path / "dlp" / "family_window_summary.json"),
        maintenance_state_file=str(tmp_path / "dlp" / "maintenance_state.jsonl"),
        meter_cleanup_preview_file=str(tmp_path / "dlp" / "meter_cleanup_preview.json"),
        meter_backup_export_readiness_file=str(tmp_path / "dlp" / "meter_backup_export_readiness.json"),
        meter_backup_export_plan_file=str(tmp_path / "dlp" / "meter_backup_export_plan.json"),
        meter_backup_export_package_manifest_file=str(tmp_path / "dlp" / "meter_backup_export_package_manifest.json"),
        meter_backup_export_approval_template_file=str(tmp_path / "dlp" / "meter_backup_export_approval_template.json"),
        meter_backup_export_execution_gate_file=str(tmp_path / "dlp" / "meter_backup_export_execution_gate.json"),
        meter_backup_export_operator_approval_file=str(tmp_path / "dlp" / "meter_backup_export_operator_approval.json"),
        meter_backup_export_destination=str(destination),
    )


def _seed(tmp_path, monkeypatch):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    destination = tmp_path / "backup_destination"
    destination.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))

    policy = _build_policy(tmp_path, destination)
    p1 = _payload("req-1")
    p2 = _payload("req-2")
    index_file = data_dir / "meters_index.json"
    tenant_file = data_dir / "meters_all.json"
    _write_json(index_file, {"req-1": p1, "req-2": p2})
    _write_json(tenant_file, [p1, p2])
    meter_v2.upsert_meter(p1)
    meter_v2.upsert_meter(p2)
    cleanup_preview.rebuild_preview(policy=policy)
    backup_readiness.rebuild_readiness(policy=policy)
    backup_plan.rebuild_plan(policy=policy)
    package_manifest.rebuild_package_manifest(policy=policy)
    approval_template.rebuild_approval_template(policy=policy)
    return policy, index_file, tenant_file


def test_gate_missing_approval_is_blocked(tmp_path, monkeypatch):
    policy, _, _ = _seed(tmp_path, monkeypatch)
    gate = execution_gate.build_execution_gate(policy=policy)
    assert gate["allowed"] is False
    assert "missing_operator_approval" in gate["blocking_reasons"]
    assert gate["approval"]["status"] == "missing"


def test_gate_allows_when_valid_approval_hashes_match(tmp_path, monkeypatch):
    policy, _, _ = _seed(tmp_path, monkeypatch)
    gate_before = execution_gate.build_execution_gate(policy=policy)
    hashes = gate_before["artifact_hashes"]
    approval = operator_approval.build_approval_artifact(
        operator_id="op-test",
        destination_path=str(policy.meter_backup_export_destination),
        approved_plan_hash=hashes["plan_hash"],
        approved_package_manifest_hash=hashes["package_manifest_hash"],
        approved_readiness_hash=hashes["readiness_hash"],
        approved_cleanup_preview_hash=hashes["cleanup_preview_hash"],
        reason="unit-test-valid-approval",
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    Path(policy.meter_backup_export_operator_approval_file).write_text(json.dumps(approval), encoding="utf-8")

    gate = execution_gate.build_execution_gate(policy=policy)
    assert gate["allowed"] is True
    assert gate["status"] == "allowed"
    assert gate["approval"]["status"] == "valid"


def test_gate_invalidates_on_upstream_hash_drift(tmp_path, monkeypatch):
    policy, _, _ = _seed(tmp_path, monkeypatch)
    gate_before = execution_gate.build_execution_gate(policy=policy)
    hashes = gate_before["artifact_hashes"]
    approval = operator_approval.build_approval_artifact(
        operator_id="op-test",
        destination_path=str(policy.meter_backup_export_destination),
        approved_plan_hash=hashes["plan_hash"],
        approved_package_manifest_hash=hashes["package_manifest_hash"],
        approved_readiness_hash=hashes["readiness_hash"],
        approved_cleanup_preview_hash=hashes["cleanup_preview_hash"],
        reason="unit-test-drift",
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    Path(policy.meter_backup_export_operator_approval_file).write_text(json.dumps(approval), encoding="utf-8")

    plan_path = Path(policy.meter_backup_export_plan_file)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["plan_id"] = "changed-plan-id"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    gate = execution_gate.build_execution_gate(policy=policy)
    assert gate["allowed"] is False
    assert "operator_approval_plan_hash_mismatch" in gate["blocking_reasons"]
    assert "operator_approval_artifact_hash_mismatch" in gate["blocking_reasons"]


def test_gate_blocks_on_missing_plan_or_package_manifest(tmp_path, monkeypatch):
    policy, _, _ = _seed(tmp_path, monkeypatch)
    Path(policy.meter_backup_export_plan_file).unlink()
    gate_missing_plan = execution_gate.build_execution_gate(policy=policy)
    assert gate_missing_plan["allowed"] is False
    assert "backup_export_plan_missing" in gate_missing_plan["blocking_reasons"]

    policy2, _, _ = _seed(tmp_path, monkeypatch)
    Path(policy2.meter_backup_export_package_manifest_file).unlink()
    gate_missing_manifest = execution_gate.build_execution_gate(policy=policy2)
    assert gate_missing_manifest["allowed"] is False
    assert "backup_export_package_manifest_missing" in gate_missing_manifest["blocking_reasons"]


def test_gate_blocks_on_expired_or_destination_mismatch_approval(tmp_path, monkeypatch):
    policy, _, _ = _seed(tmp_path, monkeypatch)
    gate_before = execution_gate.build_execution_gate(policy=policy)
    hashes = gate_before["artifact_hashes"]
    expired = operator_approval.build_approval_artifact(
        operator_id="op-test",
        destination_path=str(policy.meter_backup_export_destination),
        approved_plan_hash=hashes["plan_hash"],
        approved_package_manifest_hash=hashes["package_manifest_hash"],
        approved_readiness_hash=hashes["readiness_hash"],
        approved_cleanup_preview_hash=hashes["cleanup_preview_hash"],
        reason="expired",
        approved_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    Path(policy.meter_backup_export_operator_approval_file).write_text(json.dumps(expired), encoding="utf-8")
    gate_expired = execution_gate.build_execution_gate(policy=policy)
    assert gate_expired["allowed"] is False
    assert "operator_approval_expired" in gate_expired["blocking_reasons"]

    valid_wrong_destination = operator_approval.build_approval_artifact(
        operator_id="op-test",
        destination_path="/tmp/another-destination",
        approved_plan_hash=hashes["plan_hash"],
        approved_package_manifest_hash=hashes["package_manifest_hash"],
        approved_readiness_hash=hashes["readiness_hash"],
        approved_cleanup_preview_hash=hashes["cleanup_preview_hash"],
        reason="destination-mismatch",
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    Path(policy.meter_backup_export_operator_approval_file).write_text(
        json.dumps(valid_wrong_destination), encoding="utf-8"
    )
    gate_dest = execution_gate.build_execution_gate(policy=policy)
    assert gate_dest["allowed"] is False
    assert "operator_approval_destination_mismatch" in gate_dest["blocking_reasons"]


def test_gate_rebuild_writes_only_gate_artifact_and_keeps_legacy_unchanged(tmp_path, monkeypatch):
    policy, index_file, tenant_file = _seed(tmp_path, monkeypatch)
    before = {
        "index_sha": _sha(index_file),
        "tenant_sha": _sha(tenant_file),
        "index_mtime": index_file.stat().st_mtime_ns,
        "tenant_mtime": tenant_file.stat().st_mtime_ns,
    }
    record, gate = execution_gate.rebuild_gate(policy=policy)
    assert record["trigger"] == "meter_backup_export_execution_gate_rebuild"
    assert gate["mode"] == "execution_gate_only"
    assert Path(policy.meter_backup_export_execution_gate_file).exists()
    after = {
        "index_sha": _sha(index_file),
        "tenant_sha": _sha(tenant_file),
        "index_mtime": index_file.stat().st_mtime_ns,
        "tenant_mtime": tenant_file.stat().st_mtime_ns,
    }
    assert before == after
