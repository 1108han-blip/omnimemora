"""Traceability verification report for evidence/telemetry chain coverage."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .policy import DataLifecyclePolicy, load_policy
from . import state_store, retention

TRACEABILITY_REPORT_SCHEMA_VERSION = "dlp-traceability-report-v1"
TRACEABILITY_REBUILD_SCHEMA_VERSION = "dlp-traceability-report-rebuild-v1"
MAX_DEFAULT_SAMPLES = 50


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.traceability_report_file).expanduser()


def _read_jsonl_tolerant(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except Exception:
        return []
    return rows


def _resolve_paths_from_manifest(manifest: dict[str, Any]) -> dict[str, list[Path]]:
    result = {"meter_index": [], "compile_events": [], "proxy_events": [], "trace_events": []}
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return result
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        kind = str(artifact.get("kind") or "").strip()
        path = Path(str(artifact.get("path") or "")).expanduser()
        if kind in result:
            result[kind].append(path)
    return result


def _collect_meter_index_request_ids(paths: list[Path]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        request_ids = [str(key) for key in payload.keys() if str(key).strip()]
        request_ids.sort()
        return request_ids, payload
    return [], {}


def _collect_request_id_set_from_events(paths: list[Path]) -> set[str]:
    request_ids: set[str] = set()
    for path in paths:
        for row in _read_jsonl_tolerant(path):
            value = row.get("request_id")
            if isinstance(value, str) and value.strip():
                request_ids.add(value.strip())
    return request_ids


def _collect_trace_lookup(paths: list[Path]) -> tuple[set[str], dict[str, str]]:
    request_ids: set[str] = set()
    trace_map: dict[str, str] = {}
    for path in paths:
        for row in _read_jsonl_tolerant(path):
            request_id = row.get("request_id")
            if isinstance(request_id, str) and request_id.strip():
                request_id = request_id.strip()
                request_ids.add(request_id)
                trace_id = row.get("trace_id")
                if isinstance(trace_id, str) and trace_id.strip():
                    trace_map[request_id] = trace_id.strip()
    return request_ids, trace_map


def _request_evidence_buildable(request_id: str) -> bool:
    try:
        srm = importlib.import_module("5_connectors.adapter.application.status_read_model")
        _ = srm.build_request_evidence_payload(request_id)
        return True
    except Exception:
        return False


def _sample_status(
    *,
    meter_found: bool,
    compile_found: bool,
    proxy_found: bool,
    trace_found: bool,
    request_evidence_buildable: bool,
) -> str:
    if not meter_found or not request_evidence_buildable:
        return "fail"
    if compile_found and proxy_found and trace_found:
        return "pass"
    return "partial"


def build_report(
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    max_samples: int = MAX_DEFAULT_SAMPLES,
    request_evidence_buildable_fn: Optional[callable] = None,
) -> dict[str, Any]:
    current_policy = policy or load_policy()
    report_time = datetime.now(timezone.utc)
    evidence_buildable = request_evidence_buildable_fn or _request_evidence_buildable
    manifest = retention.read_manifest(policy=current_policy)
    warnings: list[dict[str, Any]] = []

    if not isinstance(manifest, dict):
        return {
            "schema_version": TRACEABILITY_REPORT_SCHEMA_VERSION,
            "report_id": uuid4().hex[:16],
            "generated_at": report_time.isoformat(),
            "manifest_ref": {"status": "missing", "manifest_id": None, "generated_at": None},
            "samples": [],
            "summary": {
                "sample_count": 0,
                "pass_count": 0,
                "partial_count": 0,
                "fail_count": 0,
                "missing_manifest": True,
                "warnings_count": 1,
            },
            "warnings": [{"code": "missing_manifest", "message": "retention manifest not found"}],
        }

    paths = _resolve_paths_from_manifest(manifest)
    meter_ids, _meter_index_payload = _collect_meter_index_request_ids(paths["meter_index"])
    compile_ids = _collect_request_id_set_from_events(paths["compile_events"])
    proxy_ids = _collect_request_id_set_from_events(paths["proxy_events"])
    trace_ids, trace_map = _collect_trace_lookup(paths["trace_events"])

    sample_limit = max(1, int(max_samples))
    if meter_ids:
        sample_ids = meter_ids[:sample_limit]
    else:
        fallback_ids = sorted(set().union(compile_ids, proxy_ids, trace_ids))
        sample_ids = fallback_ids[:sample_limit]
    if not sample_ids:
        warnings.append({"code": "no_meter_samples", "message": "meter index had no request ids"})

    samples: list[dict[str, Any]] = []
    pass_count = 0
    partial_count = 0
    fail_count = 0

    meter_id_set = set(meter_ids)
    for request_id in sample_ids:
        meter_found = request_id in meter_id_set
        compile_found = request_id in compile_ids
        proxy_found = request_id in proxy_ids
        trace_found = request_id in trace_ids
        buildable = bool(evidence_buildable(request_id))
        trace_id_found = trace_map.get(request_id)

        sources_found: list[str] = []
        missing_sources: list[str] = []
        for name, found in [
            ("meter", meter_found),
            ("compile", compile_found),
            ("proxy", proxy_found),
            ("trace", trace_found),
        ]:
            if found:
                sources_found.append(name)
            else:
                missing_sources.append(name)

        status = _sample_status(
            meter_found=meter_found,
            compile_found=compile_found,
            proxy_found=proxy_found,
            trace_found=trace_found,
            request_evidence_buildable=buildable,
        )
        if status == "pass":
            pass_count += 1
        elif status == "partial":
            partial_count += 1
        else:
            fail_count += 1

        samples.append(
            {
                "request_id": request_id,
                "sources_found": sources_found,
                "missing_sources": missing_sources,
                "request_evidence_buildable": buildable,
                "trace_id_found": trace_id_found,
                "status": status,
            }
        )

    return {
        "schema_version": TRACEABILITY_REPORT_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": report_time.isoformat(),
        "manifest_ref": {
            "status": "present",
            "manifest_id": manifest.get("manifest_id"),
            "generated_at": manifest.get("generated_at"),
        },
        "samples": samples,
        "summary": {
            "sample_count": len(samples),
            "pass_count": pass_count,
            "partial_count": partial_count,
            "fail_count": fail_count,
            "missing_manifest": False,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    path = _report_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_traceability_", suffix=".tmp", dir=str(path.parent))
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


def read_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _report_path(policy)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def rebuild_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_policy = policy or load_policy()
    started_at = datetime.now(timezone.utc)
    cycle_id = state_store.new_cycle_id()
    try:
        report = build_report(policy=current_policy)
        write_report_atomic(report, policy=current_policy)
        completed_at = datetime.now(timezone.utc)
        record = state_store.build_record(
            cycle_id=cycle_id,
            trigger="traceability_report_rebuild",
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
            trigger="traceability_report_rebuild",
            started_at=started_at,
            completed_at=completed_at,
            status="failed",
            bytes_scanned=0,
            error=str(exc),
        )
        state_store.append_state_record(record, policy=current_policy)
        raise
