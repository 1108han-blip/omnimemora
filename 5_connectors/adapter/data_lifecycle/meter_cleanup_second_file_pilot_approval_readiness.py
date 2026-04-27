"""Second-file cleanup pilot approval readiness (RES-028, approval package only)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_proposal_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_proposal")
_txn_preview_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_transaction_preview")
_cleanup_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_quarantine_pilot")

METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_SCHEMA_VERSION = (
    "res-second-file-cleanup-pilot-approval-readiness-v1"
)
METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_REBUILD_SCHEMA_VERSION = (
    "res-second-file-cleanup-pilot-approval-readiness-rebuild-v1"
)
METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_MODE = "approval_readiness_only"


def _readiness_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_second_file_pilot_approval_readiness_file).expanduser()


def _json_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_path(candidate: dict[str, Any]) -> str:
    source = candidate.get("source")
    if isinstance(source, dict):
        return str(source.get("path") or "").strip()
    return str(candidate.get("path") or "").strip()


def _source_name(path: str, candidate: dict[str, Any]) -> str:
    return str(candidate.get("name") or candidate.get("candidate_id") or Path(path).name)


def _source_bytes(candidate: dict[str, Any]) -> int:
    source = candidate.get("source")
    if isinstance(source, dict):
        return int(source.get("bytes", 0) or 0)
    return int(candidate.get("bytes", 0) or candidate.get("estimated_reclaim_bytes", 0) or 0)


def _blocking_reasons(candidate: dict[str, Any]) -> list[str]:
    reasons = candidate.get("txn_blocking_reasons")
    if reasons is None:
        reasons = candidate.get("blocking_reasons")
    return [str(item) for item in (reasons or []) if isinstance(item, str)]


def _pilot_source_path(cleanup_pilot: Optional[dict[str, Any]]) -> str:
    if not isinstance(cleanup_pilot, dict):
        return ""
    path = str(cleanup_pilot.get("original_path") or "").strip()
    if path:
        return path
    selected = cleanup_pilot.get("selected_candidate")
    if isinstance(selected, dict):
        return str(selected.get("path") or "").strip()
    return ""


def _candidate_is_core_index(path: str) -> bool:
    return Path(path).name == "meters_index.json"


def _candidate_is_approval_target(candidate: dict[str, Any]) -> bool:
    reasons = set(_blocking_reasons(candidate))
    if not reasons:
        return True
    return reasons.issubset({"missing_operator_approval"})


def _recommendation_score(candidate: dict[str, Any]) -> tuple[int, int]:
    path = _source_path(candidate)
    name = Path(path).name
    bytes_value = _source_bytes(candidate)
    preferred_name = int(name.startswith("meters_openclaw") or ("tenant" in name and name.endswith(".json")))
    medium_size = -abs(bytes_value - (512 * 1024))
    return preferred_name, medium_size


def _collect_candidate_records(proposal: Optional[dict[str, Any]], txn_preview: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(proposal, dict):
        for key in ("candidate_pool", "excluded_candidates"):
            for item in proposal.get(key) or []:
                if isinstance(item, dict):
                    record = dict(item)
                    record["source_collection"] = f"proposal.{key}"
                    records.append(record)
    if isinstance(txn_preview, dict):
        for item in txn_preview.get("items") or []:
            if isinstance(item, dict):
                record = dict(item)
                record["source_collection"] = "transaction_preview.items"
                records.append(record)
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        path = _source_path(record)
        if path and path not in deduped:
            deduped[path] = record
    return list(deduped.values())


def build_approval_readiness(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = datetime.now(timezone.utc)
    proposal = _proposal_mod.read_proposal(policy=current)
    txn_preview = _txn_preview_mod.read_preview(policy=current)
    cleanup_pilot = _cleanup_pilot_mod.read_latest_pilot(policy=current)
    res023_source = _pilot_source_path(cleanup_pilot)

    blocking_reasons: list[str] = []
    if not isinstance(proposal, dict):
        blocking_reasons.append("second_file_pilot_proposal_missing")
    if not isinstance(txn_preview, dict):
        blocking_reasons.append("cleanup_transaction_preview_missing")

    proposal_blocking_reasons = [str(item) for item in ((proposal or {}).get("blocking_reasons") or []) if isinstance(item, str)]
    candidate_pool = [item for item in ((proposal or {}).get("candidate_pool") or []) if isinstance(item, dict)]
    excluded_candidates = [item for item in ((proposal or {}).get("excluded_candidates") or []) if isinstance(item, dict)]
    source_records = _collect_candidate_records(proposal, txn_preview)

    recommendation_candidates: list[dict[str, Any]] = []
    excluded_from_recommendation: list[dict[str, Any]] = []
    for record in source_records:
        path = _source_path(record)
        if not path:
            continue
        normalized = {
            "path": path,
            "name": _source_name(path, record),
            "bytes": _source_bytes(record),
            "source_collection": str(record.get("source_collection") or "unknown"),
            "blocking_reasons": _blocking_reasons(record),
            "recommendation_excluded_reason": None,
        }
        if _candidate_is_core_index(path):
            normalized["recommendation_excluded_reason"] = "core_index_retained"
            excluded_from_recommendation.append(normalized)
            continue
        if res023_source and path == res023_source:
            normalized["recommendation_excluded_reason"] = "already_quarantined_in_res023"
            excluded_from_recommendation.append(normalized)
            continue
        if not _candidate_is_approval_target(record):
            normalized["recommendation_excluded_reason"] = "not_operator_approval_only"
            excluded_from_recommendation.append(normalized)
            continue
        recommendation_candidates.append(normalized)

    recommendation_candidates.sort(key=_recommendation_score, reverse=True)
    recommended = recommendation_candidates[0] if recommendation_candidates else None
    if recommended is None:
        blocking_reasons.append("no_safe_approval_target_available")

    status = "ready_for_operator_decision" if recommended is not None and not blocking_reasons else "blocked"

    return {
        "schema_version": METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_SCHEMA_VERSION,
        "readiness_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_MODE,
        "status": status,
        "proposal_status": str((proposal or {}).get("status") or "missing"),
        "proposal_blocking_reasons": proposal_blocking_reasons,
        "candidate_pool": candidate_pool,
        "excluded_candidates": excluded_candidates,
        "recommendation_source": "existing_proposal_and_transaction_preview_only",
        "recommendation_candidates": recommendation_candidates,
        "excluded_from_recommendation": excluded_from_recommendation,
        "recommended_approval_target": recommended,
        "recommended_operator_action": "review_and_inject_operator_approval_in_res029" if recommended else None,
        "required_operator_approval": True,
        "operator_approval_written": False,
        "second_file_pilot_allowed": False,
        "execution_started": False,
        "cleanup_scope_expansion_started": False,
        "allowed_next_step": "RES-029 operator approval injection or approval contract test",
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
        "input_refs": {
            "second_file_pilot_proposal_hash": _json_hash(proposal),
            "cleanup_transaction_preview_hash": _json_hash(txn_preview),
            "cleanup_pilot_hash": _json_hash(cleanup_pilot),
        },
        "summary": {
            "status": status,
            "candidate_pool_count": len(candidate_pool),
            "excluded_candidate_count": len(excluded_candidates),
            "recommendation_candidate_count": len(recommendation_candidates),
            "recommended_approval_target_present": recommended is not None,
            "second_file_pilot_allowed": False,
            "operator_approval_written": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        },
    }


def write_approval_readiness_atomic(
    readiness: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None
) -> Path:
    path = _readiness_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="meter_cleanup_second_file_approval_readiness_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(readiness, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_approval_readiness(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _readiness_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_approval_readiness(
    *, policy: Optional[DataLifecyclePolicy] = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        readiness = build_approval_readiness(policy=current)
        write_approval_readiness_atomic(readiness, policy=current)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_second_file_pilot_approval_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((readiness.get("summary") or {}).get("recommendation_candidate_count", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current)
        return record, readiness
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="meter_cleanup_second_file_pilot_approval_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current)
        raise
