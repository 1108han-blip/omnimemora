import hashlib
import importlib
import json
from pathlib import Path


policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
cleanup_preview = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
backup_readiness = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_readiness")
backup_plan = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_plan")
package_manifest = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest")
approval_template = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template")
execution_gate = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate")
copy_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot")
meter_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")


def _payload(request_id: str, query: str) -> dict:
    return {
        "request_id": request_id,
        "tenant": "all",
        "agent": "openclaw",
        "family_id": "openclaw",
        "timestamp": "2026-04-26T12:00:00+00:00",
        "task_type": "implementation",
        "context_state": "normal",
        "baseline_tokens_estimate": 1000,
        "actual_tokens_estimate": 900,
        "saved_tokens_estimate": 100,
        "savings_ratio": 0.1,
        "query": query,
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
        meter_backup_export_execution_proposal_file=str(tmp_path / "dlp" / "meter_backup_export_execution_proposal.json"),
        meter_backup_export_copy_pilot_root=str(tmp_path / "dlp" / "backup_export" / "pilot"),
        meter_backup_export_copy_pilot_record_file=str(tmp_path / "dlp" / "meter_backup_export_copy_pilot_record.json"),
        meter_backup_export_copy_pilot_allow_override=True,
        meter_backup_export_destination=str(destination),
    )


def _seed(tmp_path, monkeypatch, *, allow_override: bool = True):
    data_dir = tmp_path / "meter_data"
    sqlite_path = tmp_path / "meter_store.sqlite3"
    destination = tmp_path / "backup_destination"
    destination.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OMNIMEMORA_METER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OMNIMEMORA_METER_STORE_V2_FILE", str(sqlite_path))

    policy = _build_policy(tmp_path, destination)
    policy = policy_mod.DataLifecyclePolicy(
        **{**policy.__dict__, "meter_backup_export_copy_pilot_allow_override": allow_override}
    )
    p1 = _payload("req-1", "a")
    p2 = _payload("req-2", "this-is-a-larger-query-to-change-byte-size")
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
    execution_gate.rebuild_gate(policy=policy)
    return policy, index_file, tenant_file


def test_copy_pilot_success_with_override_and_source_retained(tmp_path, monkeypatch):
    policy, index_file, _tenant_file = _seed(tmp_path, monkeypatch, allow_override=True)
    before_sha = _sha(index_file)
    before_mtime = index_file.stat().st_mtime_ns

    record, pilot = copy_pilot.run_one_copy_pilot(policy=policy)
    assert record["trigger"] == "meter_backup_export_copy_pilot_run_one"
    assert pilot["status"] in {"success", "already_copied"}
    assert pilot["pilot_scope_override"] is True
    assert pilot["source_retained"] is True
    assert pilot["checksum_match"] is True
    assert pilot["cleanup_started"] is False
    assert pilot["read_path_unchanged"] is True
    assert Path(str(pilot["target_path"])).exists()

    after_sha = _sha(index_file)
    after_mtime = index_file.stat().st_mtime_ns
    assert before_sha == after_sha
    assert before_mtime == after_mtime


def test_copy_pilot_blocks_when_manifest_missing(tmp_path, monkeypatch):
    policy, _index_file, _tenant_file = _seed(tmp_path, monkeypatch, allow_override=True)
    Path(policy.meter_backup_export_package_manifest_file).unlink()
    _record, pilot = copy_pilot.run_one_copy_pilot(policy=policy)
    assert pilot["status"] == "blocked"
    assert "backup_export_package_manifest_missing" in pilot["blocking_reasons"]


def test_copy_pilot_blocks_when_selected_source_missing(tmp_path, monkeypatch):
    policy, index_file, tenant_file = _seed(tmp_path, monkeypatch, allow_override=True)
    index_file.unlink()
    tenant_file.unlink()
    _record, pilot = copy_pilot.run_one_copy_pilot(policy=policy)
    assert pilot["status"] == "blocked"
    assert "selected_source_missing" in pilot["blocking_reasons"]


def test_copy_pilot_blocks_on_checksum_mismatch(tmp_path, monkeypatch):
    policy, _index_file, _tenant_file = _seed(tmp_path, monkeypatch, allow_override=True)

    def _corrupt_copy(src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"corrupted-by-test")

    monkeypatch.setattr(copy_pilot, "_copy_file", _corrupt_copy)
    _record, pilot = copy_pilot.run_one_copy_pilot(policy=policy)
    assert pilot["status"] == "blocked"
    assert "checksum_mismatch" in pilot["blocking_reasons"]
    assert pilot["checksum_match"] is False


def test_copy_pilot_idempotent_already_copied(tmp_path, monkeypatch):
    policy, _index_file, _tenant_file = _seed(tmp_path, monkeypatch, allow_override=True)
    _record1, pilot1 = copy_pilot.run_one_copy_pilot(policy=policy)
    _record2, pilot2 = copy_pilot.run_one_copy_pilot(policy=policy)
    assert pilot1["target_path"] == pilot2["target_path"]
    assert pilot2["status"] == "already_copied"
    assert pilot2["checksum_match"] is True


def test_copy_pilot_target_conflict_no_overwrite(tmp_path, monkeypatch):
    policy, _index_file, _tenant_file = _seed(tmp_path, monkeypatch, allow_override=True)
    _record1, pilot1 = copy_pilot.run_one_copy_pilot(policy=policy)
    target = Path(str(pilot1["target_path"]))
    target.write_bytes(b"conflict-data")
    _record2, pilot2 = copy_pilot.run_one_copy_pilot(policy=policy)
    assert pilot2["status"] == "blocked"
    assert "target_conflict" in pilot2["blocking_reasons"]


def test_copy_pilot_blocks_missing_operator_approval_when_override_disabled(tmp_path, monkeypatch):
    policy, _index_file, _tenant_file = _seed(tmp_path, monkeypatch, allow_override=False)
    _record, pilot = copy_pilot.run_one_copy_pilot(policy=policy)
    assert pilot["status"] == "blocked"
    assert "blocked_missing_operator_approval" in pilot["blocking_reasons"]
