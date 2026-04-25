"""Operator approval artifact for archive execution gate (local-only helper)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_OPERATOR_APPROVAL_SCHEMA_VERSION = "dlp-archive-operator-approval-v1"


def _approval_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_operator_approval_file).expanduser()


def build_approval_artifact(
    *,
    operator_id: str,
    approved_artifact_hashes: dict[str, str],
    scope: str,
    reason: str,
    created_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
) -> dict[str, Any]:
    now = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expiry = (expires_at or (now + timedelta(hours=1))).astimezone(timezone.utc)
    return {
        "schema_version": ARCHIVE_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "approval_id": uuid4().hex[:16],
        "operator_id": str(operator_id),
        "approved_artifact_hashes": dict(approved_artifact_hashes),
        "scope": str(scope),
        "created_at": now.isoformat(),
        "expires_at": expiry.isoformat(),
        "reason": str(reason),
    }


def write_approval_atomic(approval: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _approval_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_approval_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(approval, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_approval(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _approval_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def create_local_approval(
    *,
    operator_id: str,
    approved_artifact_hashes: dict[str, str],
    scope: str,
    reason: str,
    expires_in_seconds: int = 3600,
    policy: Optional[DataLifecyclePolicy] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(seconds=max(1, int(expires_in_seconds)))
        approval = build_approval_artifact(
            operator_id=operator_id,
            approved_artifact_hashes=approved_artifact_hashes,
            scope=scope,
            reason=reason,
            created_at=created_at,
            expires_at=expires_at,
        )
        write_approval_atomic(approval, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_operator_approval_created",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=0,
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, approval
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_operator_approval_created",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
