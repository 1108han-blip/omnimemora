from __future__ import annotations

import importlib
from pathlib import Path

policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
readiness_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_approval_readiness"
)


def _build_policy(tmp_path):
    return policy_mod.DataLifecyclePolicy(
        maintenance_state_file=str(tmp_path / "maintenance_state.jsonl"),
        meter_cleanup_second_file_pilot_proposal_file=str(tmp_path / "meter_cleanup_second_file_pilot_proposal.json"),
        meter_cleanup_second_file_pilot_approval_readiness_file=str(
            tmp_path / "meter_cleanup_second_file_pilot_approval_readiness.json"
        ),
        meter_cleanup_transaction_preview_file=str(tmp_path / "meter_cleanup_transaction_preview.json"),
        meter_cleanup_pilot_record_file=str(tmp_path / "meter_cleanup_pilot_record.json"),
    )


def test_approval_readiness_recommends_missing_approval_candidate_only(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    proposal = {
        "status": "blocked",
        "blocking_reasons": ["missing_operator_approval"],
        "candidate_pool": [],
        "excluded_candidates": [
            {
                "path": "/tmp/meters_openclaw.json",
                "name": "meters_openclaw.json",
                "bytes": 300000,
                "txn_blocking_reasons": ["missing_operator_approval"],
            },
            {
                "path": "/tmp/meters_index.json",
                "name": "meters_index.json",
                "bytes": 1000,
                "txn_blocking_reasons": ["core_index_retained_for_future_explicit_scope"],
            },
        ],
    }
    txn_preview = {
        "items": [
            {
                "source": {"path": "/tmp/meters_openclaw.json", "bytes": 300000},
                "operation": "blocked",
                "blocking_reasons": ["missing_operator_approval"],
            },
            {
                "source": {"path": "/tmp/meters_index.json", "bytes": 1000},
                "operation": "retain",
                "blocking_reasons": ["core_index_retained_for_future_explicit_scope"],
            },
        ]
    }
    monkeypatch.setattr(readiness_mod._proposal_mod, "read_proposal", lambda policy=None: proposal)
    monkeypatch.setattr(readiness_mod._txn_preview_mod, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(readiness_mod._cleanup_pilot_mod, "read_latest_pilot", lambda policy=None: None)

    report = readiness_mod.build_approval_readiness(policy=policy)

    assert report["schema_version"] == "res-second-file-cleanup-pilot-approval-readiness-v1"
    assert report["mode"] == "approval_readiness_only"
    assert report["status"] == "ready_for_operator_decision"
    assert report["recommended_approval_target"]["path"] == "/tmp/meters_openclaw.json"
    assert report["second_file_pilot_allowed"] is False
    assert report["operator_approval_written"] is False
    assert report["execution_started"] is False
    assert report["cleanup_scope_expansion_started"] is False
    assert any(item["path"] == "/tmp/meters_index.json" for item in report["excluded_from_recommendation"])


def test_approval_readiness_excludes_res023_quarantined_source(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    proposal = {
        "status": "blocked",
        "candidate_pool": [],
        "excluded_candidates": [
            {
                "path": "/tmp/meters_res023.json",
                "name": "meters_res023.json",
                "bytes": 200000,
                "txn_blocking_reasons": ["missing_operator_approval"],
            },
            {
                "path": "/tmp/meters_tenant_small.json",
                "name": "meters_tenant_small.json",
                "bytes": 50000,
                "txn_blocking_reasons": ["missing_operator_approval"],
            },
        ],
    }
    txn_preview = {
        "items": [
            {
                "source": {"path": "/tmp/meters_res023.json", "bytes": 200000},
                "operation": "blocked",
                "blocking_reasons": ["missing_operator_approval"],
            },
            {
                "source": {"path": "/tmp/meters_tenant_small.json", "bytes": 50000},
                "operation": "blocked",
                "blocking_reasons": ["missing_operator_approval"],
            },
        ]
    }
    monkeypatch.setattr(readiness_mod._proposal_mod, "read_proposal", lambda policy=None: proposal)
    monkeypatch.setattr(readiness_mod._txn_preview_mod, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(
        readiness_mod._cleanup_pilot_mod,
        "read_latest_pilot",
        lambda policy=None: {"status": "success", "original_path": "/tmp/meters_res023.json"},
    )

    report = readiness_mod.build_approval_readiness(policy=policy)

    assert report["recommended_approval_target"]["path"] == "/tmp/meters_tenant_small.json"
    excluded = {item["path"]: item["recommendation_excluded_reason"] for item in report["excluded_from_recommendation"]}
    assert excluded["/tmp/meters_res023.json"] == "already_quarantined_in_res023"


def test_approval_readiness_blocks_when_no_safe_candidate(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    proposal = {
        "status": "blocked",
        "candidate_pool": [],
        "excluded_candidates": [
            {
                "path": "/tmp/meters_index.json",
                "name": "meters_index.json",
                "bytes": 1000,
                "txn_blocking_reasons": ["core_index_retained_for_future_explicit_scope"],
            }
        ],
    }
    txn_preview = {
        "items": [
            {
                "source": {"path": "/tmp/meters_index.json", "bytes": 1000},
                "operation": "retain",
                "blocking_reasons": ["core_index_retained_for_future_explicit_scope"],
            }
        ]
    }
    monkeypatch.setattr(readiness_mod._proposal_mod, "read_proposal", lambda policy=None: proposal)
    monkeypatch.setattr(readiness_mod._txn_preview_mod, "read_preview", lambda policy=None: txn_preview)
    monkeypatch.setattr(readiness_mod._cleanup_pilot_mod, "read_latest_pilot", lambda policy=None: None)

    report = readiness_mod.build_approval_readiness(policy=policy)

    assert report["status"] == "blocked"
    assert report["recommended_approval_target"] is None
    assert "no_safe_approval_target_available" in report["blocking_reasons"]
    assert report["second_file_pilot_allowed"] is False


def test_approval_readiness_rebuild_writes_artifact(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    monkeypatch.setattr(
        readiness_mod,
        "build_approval_readiness",
        lambda policy=None: {
            "schema_version": readiness_mod.METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_SCHEMA_VERSION,
            "mode": readiness_mod.METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_MODE,
            "status": "ready_for_operator_decision",
            "summary": {"recommendation_candidate_count": 1},
            "operator_approval_written": False,
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        },
    )

    record, report = readiness_mod.rebuild_approval_readiness(policy=policy)

    assert record["trigger"] == "meter_cleanup_second_file_pilot_approval_readiness_rebuild"
    assert report["second_file_pilot_allowed"] is False
    assert Path(policy.meter_cleanup_second_file_pilot_approval_readiness_file).exists()
