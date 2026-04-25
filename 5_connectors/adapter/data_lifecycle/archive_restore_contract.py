"""Archive restore/read-through readiness contract (readiness only)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import archive_transaction, traceability, state_store
from .policy import DataLifecyclePolicy, load_policy

ARCHIVE_RESTORE_READINESS_SCHEMA_VERSION = "dlp-archive-restore-readiness-v1"
ARCHIVE_RESTORE_READINESS_REBUILD_SCHEMA_VERSION = "dlp-archive-restore-readiness-rebuild-v1"
_READINESS_MODE = "readiness_only"


def _readiness_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.archive_restore_readiness_file).expanduser()


def _source_name_to_kind(source_name: str) -> list[str]:
    mapping = {
        "compile": ["compile_events"],
        "proxy": ["proxy_events"],
        "trace": ["trace_events"],
        "meter": ["meter_index", "meter_tenant"],
    }
    return list(mapping.get(source_name, []))


def _build_restore_lookup(preview: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    items = preview.get("items")
    if not isinstance(items, list):
        return by_kind
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if not kind:
            continue
        by_kind.setdefault(kind, []).append(item)
    return by_kind


def build_restore_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current_policy = policy or load_policy()
    now = datetime.now(timezone.utc)
    warnings: list[dict[str, Any]] = []

    preview = archive_transaction.read_preview(policy=current_policy)
    if not isinstance(preview, dict):
        return {
            "schema_version": ARCHIVE_RESTORE_READINESS_SCHEMA_VERSION,
            "readiness_id": uuid4().hex[:16],
            "generated_at": now.isoformat(),
            "mode": _READINESS_MODE,
            "transaction_preview_ref": {
                "status": "missing",
                "preview_id": None,
                "generated_at": None,
                "path": str(Path(current_policy.archive_transaction_preview_file).expanduser()),
            },
            "traceability_ref": {
                "status": "unknown",
                "report_id": None,
                "generated_at": None,
                "path": str(Path(current_policy.traceability_report_file).expanduser()),
            },
            "request_mappings": [],
            "summary": {
                "status": "blocked_missing_preview",
                "sample_count": 0,
                "mapped_request_count": 0,
                "unmapped_request_count": 0,
                "warnings_count": 1,
            },
            "warnings": [{"code": "missing_archive_transaction_preview", "message": "transaction preview not found"}],
        }

    trace_report = traceability.read_report(policy=current_policy)
    trace_samples = []
    if isinstance(trace_report, dict) and isinstance(trace_report.get("samples"), list):
        trace_samples = trace_report.get("samples") or []
    else:
        warnings.append({"code": "missing_traceability_samples", "message": "traceability report missing or invalid"})

    restore_lookup = _build_restore_lookup(preview)
    request_mappings: list[dict[str, Any]] = []
    mapped_count = 0
    unmapped_count = 0

    for sample in trace_samples:
        if not isinstance(sample, dict):
            continue
        request_id = str(sample.get("request_id") or "").strip()
        if not request_id:
            continue
        sources_found = sample.get("sources_found")
        if not isinstance(sources_found, list):
            sources_found = []

        evidence_chain: list[dict[str, Any]] = []
        for source_name in [str(item) for item in sources_found if str(item).strip()]:
            candidate_kinds = _source_name_to_kind(source_name)
            matched_item: Optional[dict[str, Any]] = None
            matched_kind: Optional[str] = None
            for kind in candidate_kinds:
                kind_items = restore_lookup.get(kind) or []
                if kind_items:
                    matched_item = kind_items[0]
                    matched_kind = kind
                    break
            if matched_item is None:
                evidence_chain.append(
                    {
                        "evidence_source": source_name,
                        "candidate_kind": candidate_kinds[0] if candidate_kinds else None,
                        "checksum": None,
                        "restore_key": None,
                        "status": "unmapped",
                    }
                )
            else:
                evidence_chain.append(
                    {
                        "evidence_source": source_name,
                        "candidate_kind": matched_kind,
                        "checksum": matched_item.get("source_sha256"),
                        "restore_key": matched_item.get("restore_key"),
                        "status": "mapped",
                    }
                )

        all_mapped = bool(evidence_chain) and all(str(item.get("status")) == "mapped" for item in evidence_chain)
        if all_mapped:
            mapped_count += 1
        else:
            unmapped_count += 1
            warnings.append(
                {
                    "code": "request_restore_chain_unmapped",
                    "request_id": request_id,
                }
            )
        request_mappings.append(
            {
                "request_id": request_id,
                "status": "mapped" if all_mapped else "partial_or_unmapped",
                "evidence_chain": evidence_chain,
            }
        )

    return {
        "schema_version": ARCHIVE_RESTORE_READINESS_SCHEMA_VERSION,
        "readiness_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": _READINESS_MODE,
        "transaction_preview_ref": {
            "status": "present",
            "preview_id": preview.get("preview_id"),
            "generated_at": preview.get("generated_at"),
            "path": str(Path(current_policy.archive_transaction_preview_file).expanduser()),
        },
        "traceability_ref": {
            "status": "present" if isinstance(trace_report, dict) else "missing",
            "report_id": trace_report.get("report_id") if isinstance(trace_report, dict) else None,
            "generated_at": trace_report.get("generated_at") if isinstance(trace_report, dict) else None,
            "path": str(Path(current_policy.traceability_report_file).expanduser()),
        },
        "request_mappings": request_mappings,
        "summary": {
            "status": "present",
            "sample_count": len(request_mappings),
            "mapped_request_count": mapped_count,
            "unmapped_request_count": unmapped_count,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_readiness_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _readiness_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_archive_restore_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def read_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
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


def rebuild_readiness_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        report = build_restore_readiness_report(policy=current_policy)
        write_readiness_atomic(report, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_restore_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            bytes_scanned=int((report.get("summary") or {}).get("sample_count", 0) or 0),
            error=None,
        )
        state_store.append_state_record(record, policy=current_policy)
        return record, report
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="archive_restore_readiness_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
