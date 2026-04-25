import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


archive_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_pilot")
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
        archive_pilot_root=str(tmp_path / "archive" / "pilot"),
        archive_pilot_record_file=str(tmp_path / "archive_pilot_record.json"),
    )


def _write_gate(policy, *, allowed: bool, approval_status: str = "valid"):
    payload = {
        "schema_version": "dlp-archive-execution-gate-v1",
        "gate_id": "g1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "gate_only",
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
        "blocking_reasons": [] if allowed else ["missing_operator_approval"],
        "approval": {
            "status": approval_status,
            "operator_id": "op",
            "expires_at": "2099-01-01T00:00:00+00:00",
        },
    }
    Path(policy.archive_execution_gate_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_preview(policy, items):
    payload = {
        "schema_version": "dlp-archive-transaction-preview-v1",
        "preview_id": "p1",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "mode": "preview_only",
        "items": items,
        "summary": {"status": "present", "preview_item_count": len(items)},
    }
    Path(policy.archive_transaction_preview_file).write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_approval(policy, hashes=None):
    if hashes is None:
        hashes = {}
    approval = archive_approval_mod.build_approval_artifact(
        operator_id="operator-1",
        approved_artifact_hashes=hashes,
        scope="stage9-test",
        reason="pilot test",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    archive_approval_mod.write_approval_atomic(approval, policy=policy)


def test_pilot_blocked_without_gate_approval(tmp_path):
    policy = _build_policy(tmp_path)
    _write_gate(policy, allowed=False, approval_status="missing")
    _write_preview(policy, [])
    record, pilot = archive_pilot_mod.copy_one_pilot(policy=policy)
    assert record["trigger"] == "archive_pilot_copy_one"
    assert record["status"] == "blocked"
    assert pilot["status"] == "blocked"
    assert pilot["message"] == "execution_gate_not_allowed"


def test_pilot_blocked_on_preview_checksum_mismatch(tmp_path):
    policy = _build_policy(tmp_path)
    _write_gate(policy, allowed=True)
    _write_valid_approval(policy)
    source = tmp_path / "compile_events.jsonl"
    source.write_text('{"request_id":"req1"}\n', encoding="utf-8")
    _write_preview(
        policy,
        [
            {
                "kind": "compile_events",
                "source_path": str(source),
                "source_sha256": "not-real",
                "source_bytes": source.stat().st_size,
                "restore_key": "restore:x",
            }
        ],
    )
    record, pilot = archive_pilot_mod.copy_one_pilot(policy=policy)
    assert record["status"] == "blocked"
    assert pilot["message"] == "preview_source_checksum_mismatch"


def test_pilot_deterministic_selection_excludes_non_allowed_kinds(tmp_path):
    policy = _build_policy(tmp_path)
    _write_gate(policy, allowed=True)
    _write_valid_approval(policy)
    a = tmp_path / "a_proxy.jsonl"
    b = tmp_path / "b_compile.jsonl"
    c = tmp_path / "c_trace.jsonl"
    a.write_text("x", encoding="utf-8")
    b.write_text("xx", encoding="utf-8")
    c.write_text("", encoding="utf-8")
    _write_preview(
        policy,
        [
            {
                "kind": "trace_events",
                "source_path": str(c),
                "source_sha256": archive_pilot_mod._sha256_file(c),
                "source_bytes": c.stat().st_size,
                "restore_key": "restore:t",
            },
            {
                "kind": "compile_events",
                "source_path": str(b),
                "source_sha256": archive_pilot_mod._sha256_file(b),
                "source_bytes": b.stat().st_size,
                "restore_key": "restore:b",
            },
            {
                "kind": "proxy_events",
                "source_path": str(a),
                "source_sha256": archive_pilot_mod._sha256_file(a),
                "source_bytes": a.stat().st_size,
                "restore_key": "restore:a",
            },
        ],
    )
    record, pilot = archive_pilot_mod.copy_one_pilot(policy=policy)
    assert record["status"] == "success"
    assert pilot["status"] == "success"
    assert pilot["source_kind"] == "proxy_events"
    assert pilot["source_path"] == str(a)


def test_pilot_copy_creates_archive_and_source_retained(tmp_path):
    policy = _build_policy(tmp_path)
    _write_gate(policy, allowed=True)
    _write_valid_approval(policy)
    source = tmp_path / "compile_events.jsonl"
    source.write_text('{"request_id":"req-copy"}\n', encoding="utf-8")
    sha = archive_pilot_mod._sha256_file(source)
    _write_preview(
        policy,
        [
            {
                "kind": "compile_events",
                "source_path": str(source),
                "source_sha256": sha,
                "source_bytes": source.stat().st_size,
                "restore_key": "restore:copy",
            }
        ],
    )
    _, pilot = archive_pilot_mod.copy_one_pilot(policy=policy)
    archive_path = Path(pilot["archive_path"])
    assert archive_path.exists()
    assert source.exists()
    assert pilot["checksum_match"] is True
    assert pilot["source_retained"] is True
    assert pilot["read_path_unchanged"] is True


def test_pilot_checksum_mismatch_after_copy_fails_source_retained(tmp_path, monkeypatch):
    policy = _build_policy(tmp_path)
    _write_gate(policy, allowed=True)
    _write_valid_approval(policy)
    source = tmp_path / "proxy_events.jsonl"
    source.write_text("ok", encoding="utf-8")
    sha = archive_pilot_mod._sha256_file(source)
    _write_preview(
        policy,
        [
            {
                "kind": "proxy_events",
                "source_path": str(source),
                "source_sha256": sha,
                "source_bytes": source.stat().st_size,
                "restore_key": "restore:proxy",
            }
        ],
    )

    original_copy = archive_pilot_mod._copy_file_atomic

    def copy_and_corrupt(src, dst):
        original_copy(src, dst)
        Path(dst).write_text("corrupt", encoding="utf-8")

    monkeypatch.setattr(archive_pilot_mod, "_copy_file_atomic", copy_and_corrupt)
    _, pilot = archive_pilot_mod.copy_one_pilot(policy=policy)
    assert pilot["status"] == "failed"
    assert pilot["source_retained"] is True
    assert Path(pilot["source_path"]).exists()


def test_pilot_second_call_idempotent_without_duplicate_copy(tmp_path):
    policy = _build_policy(tmp_path)
    _write_gate(policy, allowed=True)
    _write_valid_approval(policy)
    source = tmp_path / "compile_events.jsonl"
    source.write_text("hello", encoding="utf-8")
    sha = archive_pilot_mod._sha256_file(source)
    _write_preview(
        policy,
        [
            {
                "kind": "compile_events",
                "source_path": str(source),
                "source_sha256": sha,
                "source_bytes": source.stat().st_size,
                "restore_key": "restore:idempotent",
            }
        ],
    )
    _, first = archive_pilot_mod.copy_one_pilot(policy=policy)
    _, second = archive_pilot_mod.copy_one_pilot(policy=policy)
    root = Path(policy.archive_pilot_root)
    copies = [p for p in root.rglob("*") if p.is_file()]
    assert len(copies) == 1
    assert second["status"] in {"already_copied", "success"}
    assert first["source_path"] == second["source_path"]

    ledger = state_store.read_recent_records(limit=2, trigger="archive_pilot_copy_one", policy=policy)
    assert len(ledger) >= 1
