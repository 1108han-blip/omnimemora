import importlib
from pathlib import Path


archive_approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_approval")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
state_store = importlib.import_module("5_connectors.adapter.data_lifecycle.state_store")


def _build_policy(tmp_path):
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
        archive_execution_gate_file=str(tmp_path / "archive_execution_gate.json"),
        archive_operator_approval_file=str(tmp_path / "archive_operator_approval.json"),
    )


def test_create_local_approval_writes_required_fields_and_ledger(tmp_path):
    policy = _build_policy(tmp_path)
    hashes = {
        "candidate_plan_hash": "a",
        "transaction_preview_hash": "b",
        "restore_readiness_hash": "c",
        "lifecycle_health_hash": "d",
    }
    record, approval = archive_approval_mod.create_local_approval(
        operator_id="operator-1",
        approved_artifact_hashes=hashes,
        scope="stage8-test",
        reason="local gate validation",
        expires_in_seconds=600,
        policy=policy,
    )
    assert record["trigger"] == "archive_operator_approval_created"
    assert approval["schema_version"] == "dlp-archive-operator-approval-v1"
    for field in ["operator_id", "approved_artifact_hashes", "scope", "created_at", "expires_at", "reason"]:
        assert field in approval
    loaded = archive_approval_mod.read_approval(policy=policy)
    assert loaded is not None
    assert loaded["operator_id"] == "operator-1"

    ledger_records = state_store.read_recent_records(limit=1, trigger="archive_operator_approval_created", policy=policy)
    assert len(ledger_records) == 1
    assert ledger_records[0]["trigger"] == "archive_operator_approval_created"


def test_archive_approval_atomic_write_no_half_state_on_failure(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    approval = {
        "schema_version": "dlp-archive-operator-approval-v1",
        "approval_id": "a1",
        "operator_id": "operator-1",
        "approved_artifact_hashes": {},
        "scope": "stage8-test",
        "created_at": "2026-04-25T00:00:00+00:00",
        "expires_at": "2026-04-25T01:00:00+00:00",
        "reason": "x",
    }
    monkeypatch.setattr(
        archive_approval_mod.os,
        "replace",
        lambda _src, _dst: (_ for _ in ()).throw(RuntimeError("replace failed")),
    )
    try:
        archive_approval_mod.write_approval_atomic(approval, policy=policy)
        assert False, "expected write_approval_atomic to fail"
    except RuntimeError:
        pass
    target = Path(policy.archive_operator_approval_file)
    assert not target.exists()
    assert list(target.parent.glob("dlp_archive_approval_*.tmp")) == []
