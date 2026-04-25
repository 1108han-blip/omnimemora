"""Local operator approval artifact reader/validator for meter backup export gate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .policy import DataLifecyclePolicy, load_policy

METER_BACKUP_EXPORT_OPERATOR_APPROVAL_SCHEMA_VERSION = "res-legacy-meter-backup-export-operator-approval-v1"


def _approval_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_backup_export_operator_approval_file).expanduser()


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def build_approval_artifact(
    *,
    operator_id: str,
    destination_path: str,
    approved_plan_hash: str,
    approved_package_manifest_hash: str,
    approved_readiness_hash: str,
    approved_cleanup_preview_hash: str,
    reason: str,
    approved_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
) -> dict[str, Any]:
    now = (approved_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expiry = (expires_at or now).astimezone(timezone.utc)
    return {
        "schema_version": METER_BACKUP_EXPORT_OPERATOR_APPROVAL_SCHEMA_VERSION,
        "approval_id": uuid4().hex[:16],
        "operator_id": str(operator_id).strip(),
        "approved_at": now.isoformat(),
        "expires_at": expiry.isoformat(),
        "approved_plan_hash": str(approved_plan_hash),
        "approved_package_manifest_hash": str(approved_package_manifest_hash),
        "approved_readiness_hash": str(approved_readiness_hash),
        "approved_cleanup_preview_hash": str(approved_cleanup_preview_hash),
        "destination_path": str(destination_path),
        "reason": str(reason),
    }


def read_operator_approval(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def validate_operator_approval(
    *,
    approval: Optional[dict[str, Any]],
    expected_plan_hash: Optional[str],
    expected_package_manifest_hash: Optional[str],
    expected_readiness_hash: Optional[str],
    expected_cleanup_preview_hash: Optional[str],
    expected_destination_path: Optional[str],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    check_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    blocking_reasons: list[str] = []

    if not isinstance(approval, dict):
        return {
            "status": "missing",
            "operator_id": None,
            "expires_at": None,
            "destination_path": None,
            "blocking_reasons": ["missing_operator_approval"],
        }

    if str(approval.get("schema_version") or "") != METER_BACKUP_EXPORT_OPERATOR_APPROVAL_SCHEMA_VERSION:
        blocking_reasons.append("operator_approval_schema_mismatch")

    operator_id = str(approval.get("operator_id") or "").strip()
    if not operator_id:
        blocking_reasons.append("operator_approval_operator_id_missing")

    approved_at = _parse_iso_utc(approval.get("approved_at"))
    expires_at = _parse_iso_utc(approval.get("expires_at"))
    if approved_at is None:
        blocking_reasons.append("operator_approval_approved_at_invalid")
    if expires_at is None:
        blocking_reasons.append("operator_approval_expires_at_invalid")
    elif expires_at <= check_now:
        blocking_reasons.append("operator_approval_expired")

    destination_path = str(approval.get("destination_path") or "")
    if not destination_path:
        blocking_reasons.append("operator_approval_destination_missing")
    elif (expected_destination_path or "") and destination_path != str(expected_destination_path):
        blocking_reasons.append("operator_approval_destination_mismatch")

    hash_mismatch = False
    if str(approval.get("approved_plan_hash") or "") != str(expected_plan_hash or ""):
        blocking_reasons.append("operator_approval_plan_hash_mismatch")
        hash_mismatch = True
    if str(approval.get("approved_package_manifest_hash") or "") != str(expected_package_manifest_hash or ""):
        blocking_reasons.append("operator_approval_package_manifest_hash_mismatch")
        hash_mismatch = True
    if str(approval.get("approved_readiness_hash") or "") != str(expected_readiness_hash or ""):
        blocking_reasons.append("operator_approval_readiness_hash_mismatch")
        hash_mismatch = True
    if str(approval.get("approved_cleanup_preview_hash") or "") != str(expected_cleanup_preview_hash or ""):
        blocking_reasons.append("operator_approval_cleanup_preview_hash_mismatch")
        hash_mismatch = True
    if hash_mismatch:
        blocking_reasons.append("operator_approval_artifact_hash_mismatch")

    status = "valid" if not blocking_reasons else "invalid"
    return {
        "status": status,
        "operator_id": operator_id or None,
        "expires_at": approval.get("expires_at"),
        "destination_path": destination_path or None,
        "blocking_reasons": blocking_reasons,
    }

