import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval")
policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")


def _policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        meter_backup_export_operator_approval_file=str(tmp_path / "meter_backup_export_operator_approval.json"),
    )


def _expected():
    return {
        "plan": "plan-h1",
        "manifest": "manifest-h1",
        "readiness": "readiness-h1",
        "cleanup": "cleanup-h1",
        "destination": "/tmp/backup-destination",
    }


def test_missing_operator_approval_is_blocked(tmp_path):
    exp = _expected()
    result = approval_mod.validate_operator_approval(
        approval=None,
        expected_plan_hash=exp["plan"],
        expected_package_manifest_hash=exp["manifest"],
        expected_readiness_hash=exp["readiness"],
        expected_cleanup_preview_hash=exp["cleanup"],
        expected_destination_path=exp["destination"],
    )
    assert result["status"] == "missing"
    assert "missing_operator_approval" in result["blocking_reasons"]


def test_expired_operator_approval_is_blocked(tmp_path):
    exp = _expected()
    approval = approval_mod.build_approval_artifact(
        operator_id="op1",
        destination_path=exp["destination"],
        approved_plan_hash=exp["plan"],
        approved_package_manifest_hash=exp["manifest"],
        approved_readiness_hash=exp["readiness"],
        approved_cleanup_preview_hash=exp["cleanup"],
        reason="test",
        approved_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    result = approval_mod.validate_operator_approval(
        approval=approval,
        expected_plan_hash=exp["plan"],
        expected_package_manifest_hash=exp["manifest"],
        expected_readiness_hash=exp["readiness"],
        expected_cleanup_preview_hash=exp["cleanup"],
        expected_destination_path=exp["destination"],
    )
    assert result["status"] == "invalid"
    assert "operator_approval_expired" in result["blocking_reasons"]


def test_malformed_or_schema_mismatch_approval_is_blocked(tmp_path):
    exp = _expected()
    malformed = {"schema_version": "wrong", "operator_id": "", "expires_at": "not-iso"}
    result = approval_mod.validate_operator_approval(
        approval=malformed,
        expected_plan_hash=exp["plan"],
        expected_package_manifest_hash=exp["manifest"],
        expected_readiness_hash=exp["readiness"],
        expected_cleanup_preview_hash=exp["cleanup"],
        expected_destination_path=exp["destination"],
    )
    assert result["status"] == "invalid"
    assert "operator_approval_schema_mismatch" in result["blocking_reasons"]
    assert "operator_approval_operator_id_missing" in result["blocking_reasons"]
    assert "operator_approval_expires_at_invalid" in result["blocking_reasons"]


def test_hash_mismatch_and_destination_mismatch_are_blocked(tmp_path):
    exp = _expected()
    approval = approval_mod.build_approval_artifact(
        operator_id="op1",
        destination_path="/tmp/another-destination",
        approved_plan_hash="plan-h2",
        approved_package_manifest_hash=exp["manifest"],
        approved_readiness_hash=exp["readiness"],
        approved_cleanup_preview_hash="cleanup-h2",
        reason="test",
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    result = approval_mod.validate_operator_approval(
        approval=approval,
        expected_plan_hash=exp["plan"],
        expected_package_manifest_hash=exp["manifest"],
        expected_readiness_hash=exp["readiness"],
        expected_cleanup_preview_hash=exp["cleanup"],
        expected_destination_path=exp["destination"],
    )
    assert result["status"] == "invalid"
    assert "operator_approval_destination_mismatch" in result["blocking_reasons"]
    assert "operator_approval_plan_hash_mismatch" in result["blocking_reasons"]
    assert "operator_approval_cleanup_preview_hash_mismatch" in result["blocking_reasons"]
    assert "operator_approval_artifact_hash_mismatch" in result["blocking_reasons"]


def test_valid_fixture_is_accepted(tmp_path):
    exp = _expected()
    approval = approval_mod.build_approval_artifact(
        operator_id="op1",
        destination_path=exp["destination"],
        approved_plan_hash=exp["plan"],
        approved_package_manifest_hash=exp["manifest"],
        approved_readiness_hash=exp["readiness"],
        approved_cleanup_preview_hash=exp["cleanup"],
        reason="unit-test",
        approved_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    result = approval_mod.validate_operator_approval(
        approval=approval,
        expected_plan_hash=exp["plan"],
        expected_package_manifest_hash=exp["manifest"],
        expected_readiness_hash=exp["readiness"],
        expected_cleanup_preview_hash=exp["cleanup"],
        expected_destination_path=exp["destination"],
    )
    assert result["status"] == "valid"
    assert result["blocking_reasons"] == []


def test_read_operator_approval_loads_json_file(tmp_path):
    policy = _policy(tmp_path)
    payload = {"schema_version": approval_mod.METER_BACKUP_EXPORT_OPERATOR_APPROVAL_SCHEMA_VERSION, "operator_id": "opx"}
    Path(policy.meter_backup_export_operator_approval_file).write_text(json.dumps(payload), encoding="utf-8")
    loaded = approval_mod.read_operator_approval(policy=policy)
    assert loaded == payload

