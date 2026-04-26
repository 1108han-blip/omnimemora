"""Post-pilot stability window report for legacy meter cleanup (RES-024, observe-only)."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import state_store
from .policy import DataLifecyclePolicy, load_policy

_meter_storage_v2 = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")
_cleanup_pilot = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_quarantine_pilot")
_rollback_drill = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill")
_restore_readback = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback")
_legacy_meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
_meter_store_v2 = importlib.import_module("5_connectors.adapter.infrastructure.meter_store_v2")

METER_CLEANUP_STABILITY_WINDOW_SCHEMA_VERSION = "res-legacy-meter-cleanup-stability-window-v1"
METER_CLEANUP_STABILITY_WINDOW_REBUILD_SCHEMA_VERSION = "res-legacy-meter-cleanup-stability-window-rebuild-v1"
METER_CLEANUP_STABILITY_WINDOW_MODE = "post_pilot_stability_window_observe_only"
DEFAULT_EXPECTED_PILOT_FILENAME = "meters_phase2-meter-dir.json"


def _report_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.meter_cleanup_stability_window_file).expanduser()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_hash(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any], *, tmp_prefix: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=tmp_prefix, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _runtime_base_url() -> str:
    return str(os.getenv("OMNIMEMORA_DLP_STABILITY_WINDOW_BASE_URL", "http://127.0.0.1:18011")).strip().rstrip("/")


def _runtime_timeout_seconds() -> float:
    raw = str(os.getenv("OMNIMEMORA_DLP_STABILITY_WINDOW_TIMEOUT_SECONDS", "2.0")).strip()
    try:
        value = float(raw)
    except Exception:
        value = 2.0
    return min(10.0, max(0.1, value))


def _runtime_read_timeout_seconds() -> float:
    raw = str(os.getenv("OMNIMEMORA_DLP_STABILITY_WINDOW_RUNTIME_READ_TIMEOUT_SECONDS", "20.0")).strip()
    try:
        value = float(raw)
    except Exception:
        value = 20.0
    return min(60.0, max(1.0, value))


def _read_runtime_json(path: str, *, timeout_seconds: Optional[float] = None) -> Optional[dict[str, Any]]:
    base = _runtime_base_url()
    timeout = timeout_seconds if timeout_seconds is not None else _runtime_read_timeout_seconds()
    url = f"{base}{path}"
    try:
        request = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if int(response.getcode()) != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload
            return None
    except Exception:
        return None


def _extract_request_id_from_meter_filename(path_text: str) -> Optional[str]:
    name = Path(path_text).name
    if not (name.startswith("meters_") and name.endswith(".json")):
        return None
    request_id = name[len("meters_") : -len(".json")].strip()
    if not request_id or request_id == "index":
        return None
    return request_id


def _percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    p_clamped = min(100.0, max(0.0, float(p)))
    rank = (len(ordered) - 1) * (p_clamped / 100.0)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return float(ordered[lower])
    lower_v = float(ordered[lower])
    upper_v = float(ordered[upper])
    weight = rank - lower
    return lower_v + (upper_v - lower_v) * weight


def _sample_endpoint(url: str, *, sample_count: int, timeout_seconds: float) -> dict[str, Any]:
    latencies_ms: list[float] = []
    success_count = 0
    timeout_count = 0
    error_count = 0
    non_200_count = 0
    status_codes: dict[str, int] = {}
    errors: dict[str, int] = {}

    for _ in range(sample_count):
        started = time.perf_counter()
        code: Optional[int] = None
        try:
            request = urllib.request.Request(url=url, method="GET")
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                code = int(response.getcode())
            latency_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(latency_ms)
            status_codes[str(code)] = int(status_codes.get(str(code), 0) + 1)
            if code == 200:
                success_count += 1
            else:
                non_200_count += 1
                error_count += 1
        except urllib.error.HTTPError as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(latency_ms)
            code = int(getattr(exc, "code", 0) or 0)
            if code > 0:
                status_codes[str(code)] = int(status_codes.get(str(code), 0) + 1)
            non_200_count += 1
            error_count += 1
            key = f"http_{code}" if code > 0 else "http_error"
            errors[key] = int(errors.get(key, 0) + 1)
        except urllib.error.URLError as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(latency_ms)
            reason = str(getattr(exc, "reason", "")).lower()
            if "timed out" in reason or "timeout" in reason:
                timeout_count += 1
                errors["timeout"] = int(errors.get("timeout", 0) + 1)
            else:
                error_count += 1
                errors["url_error"] = int(errors.get("url_error", 0) + 1)
        except TimeoutError:
            latency_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(latency_ms)
            timeout_count += 1
            errors["timeout"] = int(errors.get("timeout", 0) + 1)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(latency_ms)
            error_count += 1
            key = f"exception:{exc.__class__.__name__}"
            errors[key] = int(errors.get(key, 0) + 1)

    p95_ms = _percentile(latencies_ms, 95.0)
    mean_ms = (sum(latencies_ms) / len(latencies_ms)) if latencies_ms else None
    endpoint_status = "passed" if success_count == sample_count and error_count == 0 and timeout_count == 0 else "failed"
    return {
        "status": endpoint_status,
        "url": url,
        "sample_count": sample_count,
        "success_count": int(success_count),
        "error_count": int(error_count),
        "timeout_count": int(timeout_count),
        "non_200_count": int(non_200_count),
        "status_codes": status_codes,
        "error_buckets": errors,
        "latency_ms_p95": p95_ms,
        "latency_ms_mean": mean_ms,
        "latency_ms_max": max(latencies_ms) if latencies_ms else None,
        "latency_ms_min": min(latencies_ms) if latencies_ms else None,
    }


def _request_status_code(url: str, *, timeout_seconds: float) -> Optional[int]:
    try:
        request = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.getcode())
    except urllib.error.HTTPError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        return code if code > 0 else None
    except Exception:
        return None


def _candidate_request_ids_from_legacy_index(limit: int = 12) -> list[str]:
    output: list[str] = []
    try:
        index, _aggregates = _legacy_meter_store.load_persisted_state()
    except Exception:
        return output
    if not isinstance(index, dict):
        return output
    for request_id in sorted(index.keys(), reverse=True):
        value = str(request_id or "").strip()
        if value:
            output.append(value)
        if len(output) >= max(1, int(limit)):
            break
    return output


def _candidate_request_ids_from_sqlite(limit: int = 20) -> list[str]:
    output: list[str] = []
    try:
        rows = _meter_store_v2.query_recent(limit=max(1, int(limit)))
    except Exception:
        return output
    for row in rows:
        if not isinstance(row, dict):
            continue
        request_id = str(row.get("request_id") or "").strip()
        if request_id and request_id not in output:
            output.append(request_id)
    return output


def _select_smoke_request_id(
    *,
    base_url: str,
    timeout_seconds: float,
    explicit_request_id: Optional[str],
    pilot_request_id: Optional[str],
) -> Optional[str]:
    candidates: list[str] = []
    if explicit_request_id:
        candidates.append(str(explicit_request_id))
    if pilot_request_id and pilot_request_id not in candidates:
        candidates.append(str(pilot_request_id))
    for item in _candidate_request_ids_from_sqlite():
        if item not in candidates:
            candidates.append(item)
    for item in _candidate_request_ids_from_legacy_index():
        if item not in candidates:
            candidates.append(item)

    for candidate in candidates:
        encoded = urllib.parse.quote(candidate, safe="")
        probe_url = f"{base_url}/requests/{encoded}/meter"
        code = _request_status_code(probe_url, timeout_seconds=timeout_seconds)
        if code == 200:
            return candidate
    if candidates:
        return candidates[0]
    return None


def _run_smoke_sampling(*, request_id: Optional[str]) -> dict[str, Any]:
    sample_count_raw = str(os.getenv("OMNIMEMORA_DLP_STABILITY_WINDOW_SAMPLE_COUNT", "20")).strip()
    timeout_raw = str(_runtime_timeout_seconds())
    base_url = _runtime_base_url()

    try:
        sample_count = int(sample_count_raw)
    except Exception:
        sample_count = 20
    sample_count = min(50, max(1, sample_count))

    try:
        timeout_seconds = float(timeout_raw)
    except Exception:
        timeout_seconds = 2.0
    timeout_seconds = min(10.0, max(0.1, timeout_seconds))

    explicit_request_id = str(os.getenv("OMNIMEMORA_DLP_STABILITY_WINDOW_REQUEST_ID", "")).strip() or None
    selected_request_id = _select_smoke_request_id(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        explicit_request_id=explicit_request_id,
        pilot_request_id=request_id,
    )
    request_id = selected_request_id or request_id or "unknown_request"
    encoded_request_id = urllib.parse.quote(request_id, safe="")
    endpoints = [
        ("request_meter", f"{base_url}/requests/{encoded_request_id}/meter"),
        ("request_evidence", f"{base_url}/debug/request_evidence?request_id={encoded_request_id}"),
        ("metrics_summary", f"{base_url}/metrics/summary"),
        ("metrics_summary_24h", f"{base_url}/metrics/summary_24h"),
        ("metrics_core_capabilities", f"{base_url}/metrics/core_capabilities"),
        ("agents_control", f"{base_url}/agents/control"),
    ]

    results: list[dict[str, Any]] = []
    total_success = 0
    total_errors = 0
    total_timeouts = 0
    all_p95: list[float] = []
    all_latencies: list[float] = []
    for endpoint_name, url in endpoints:
        outcome = _sample_endpoint(url, sample_count=sample_count, timeout_seconds=timeout_seconds)
        outcome["endpoint"] = endpoint_name
        results.append(outcome)
        total_success += int(outcome.get("success_count", 0) or 0)
        total_errors += int(outcome.get("error_count", 0) or 0)
        total_timeouts += int(outcome.get("timeout_count", 0) or 0)
        p95 = outcome.get("latency_ms_p95")
        if isinstance(p95, (int, float)):
            all_p95.append(float(p95))
        for key in ("latency_ms_mean", "latency_ms_max", "latency_ms_min"):
            value = outcome.get(key)
            if isinstance(value, (int, float)):
                all_latencies.append(float(value))

    status = "passed" if all((item.get("status") == "passed") for item in results) else "failed"
    return {
        "status": status,
        "sample_count_per_endpoint": sample_count,
        "timeout_seconds": timeout_seconds,
        "base_url": base_url,
        "request_id": request_id,
        "total_endpoints": len(results),
        "passed_endpoints": int(sum(1 for item in results if item.get("status") == "passed")),
        "failed_endpoints": int(sum(1 for item in results if item.get("status") != "passed")),
        "total_success_count": int(total_success),
        "total_error_count": int(total_errors),
        "total_timeout_count": int(total_timeouts),
        "latency_ms_p95_max": max(all_p95) if all_p95 else None,
        "latency_ms_mean_overall": (sum(all_latencies) / len(all_latencies)) if all_latencies else None,
        "results": results,
    }


def build_stability_window_report(*, policy: Optional[DataLifecyclePolicy] = None) -> dict[str, Any]:
    current = policy or load_policy()
    now = _utc_now()
    blocking_reasons: list[str] = []

    runtime_pilot = _read_runtime_json("/data-lifecycle/meter-storage/cleanup/pilot/latest")
    runtime_parity = _read_runtime_json("/data-lifecycle/meter-storage/parity")
    runtime_restore = _read_runtime_json("/data-lifecycle/meter-storage/backup-export/restore-readback")
    runtime_rollback = _read_runtime_json("/data-lifecycle/meter-storage/cleanup/rollback-drill")

    pilot = runtime_pilot if isinstance(runtime_pilot, dict) else _cleanup_pilot.read_latest_pilot(policy=current)
    parity = runtime_parity if isinstance(runtime_parity, dict) else _meter_storage_v2.build_parity_report()
    restore = (
        runtime_restore
        if isinstance(runtime_restore, dict)
        else _restore_readback.read_restore_readback_report(policy=current)
    )
    rollback = (
        runtime_rollback
        if isinstance(runtime_rollback, dict)
        else _rollback_drill.read_rollback_drill_report(policy=current)
    )

    expected_filename = str(
        os.getenv("OMNIMEMORA_DLP_RES024_EXPECTED_PILOT_FILENAME", DEFAULT_EXPECTED_PILOT_FILENAME)
    ).strip() or DEFAULT_EXPECTED_PILOT_FILENAME

    pilot_hash = _stable_hash(pilot)
    observed_pilot_status = str((pilot or {}).get("status") or "missing")
    original_path = str((pilot or {}).get("original_path") or "")
    quarantine_path = str((pilot or {}).get("quarantine_path") or "")
    pilot_filename = Path(original_path).name if original_path else None
    original_absent = True
    quarantine_exists = False
    quarantine_sha256 = None
    quarantine_hash_match = False

    if not isinstance(pilot, dict):
        blocking_reasons.append("cleanup_pilot_missing")
    else:
        if observed_pilot_status != "success":
            blocking_reasons.append("cleanup_pilot_not_success")
        if not bool(pilot.get("source_move_executed", False)):
            blocking_reasons.append("pilot_source_move_not_executed")
        if bool(pilot.get("delete_executed", False)):
            blocking_reasons.append("pilot_delete_executed")
        if bool(pilot.get("compress_executed", False)):
            blocking_reasons.append("pilot_compress_executed")
        if bool(pilot.get("truncate_executed", False)):
            blocking_reasons.append("pilot_truncate_executed")
        if bool(pilot.get("batch_cleanup_executed", False)):
            blocking_reasons.append("pilot_batch_cleanup_executed")
        if pilot_filename and pilot_filename != expected_filename:
            blocking_reasons.append("pilot_subject_unexpected")

        if original_path:
            original_obj = Path(original_path).expanduser()
            original_absent = not original_obj.exists()
            if not original_absent:
                blocking_reasons.append("pilot_original_path_still_present")
        if quarantine_path:
            quarantine_obj = Path(quarantine_path).expanduser()
            quarantine_exists = quarantine_obj.exists() and quarantine_obj.is_file()
            if quarantine_exists:
                quarantine_sha256 = _sha256_file(quarantine_obj)
                expected_sha = str(pilot.get("quarantine_sha256_after") or "")
                quarantine_hash_match = bool(quarantine_sha256 and expected_sha and quarantine_sha256 == expected_sha)
            if not quarantine_exists:
                blocking_reasons.append("pilot_quarantine_path_missing")
            if not quarantine_hash_match:
                blocking_reasons.append("pilot_quarantine_hash_mismatch")

    parity_status = str((parity or {}).get("status") or "missing")
    critical_mismatch_count = int((parity or {}).get("critical_mismatch_count", 0) or 0)
    if parity_status != "passed" or critical_mismatch_count != 0:
        blocking_reasons.append("parity_not_passed")

    restore_status = str((restore or {}).get("status") or "missing")
    restore_checksum_match = bool((restore or {}).get("checksum_match", False))
    restore_source_retained = bool((restore or {}).get("source_retained", False))
    restore_backup_copy_readable = bool((restore or {}).get("backup_copy_readable", False))
    restore_cleanup_started = bool((restore or {}).get("cleanup_started", False))
    restore_production_restore_started = bool((restore or {}).get("production_restore_started", False))
    if restore_status != "passed":
        blocking_reasons.append("restore_readback_not_passed")
    if not restore_checksum_match:
        blocking_reasons.append("restore_readback_checksum_mismatch")
    if not restore_backup_copy_readable:
        blocking_reasons.append("restore_readback_backup_copy_not_readable")
    if restore_cleanup_started:
        blocking_reasons.append("restore_readback_cleanup_started")
    if restore_production_restore_started:
        blocking_reasons.append("restore_readback_production_restore_started")

    rollback_status = str((rollback or {}).get("status") or "missing")
    rollback_checksum_match = bool((rollback or {}).get("checksum_match", False))
    rollback_staging_restore_readable = bool((rollback or {}).get("staging_restore_readable", False))
    rollback_cleanup_started = bool((rollback or {}).get("cleanup_started", False))
    rollback_production_restore_started = bool((rollback or {}).get("production_restore_started", False))
    if rollback_status != "passed":
        blocking_reasons.append("rollback_drill_not_passed")
    if not rollback_checksum_match:
        blocking_reasons.append("rollback_drill_checksum_mismatch")
    if not rollback_staging_restore_readable:
        blocking_reasons.append("rollback_drill_staging_restore_not_readable")
    if rollback_cleanup_started:
        blocking_reasons.append("rollback_drill_cleanup_started")
    if rollback_production_restore_started:
        blocking_reasons.append("rollback_drill_production_restore_started")

    request_id = _extract_request_id_from_meter_filename(original_path)
    smoke = _run_smoke_sampling(request_id=request_id)
    if str(smoke.get("status") or "") != "passed":
        blocking_reasons.append("smoke_failed")

    cleanup_scope_expansion_started = False
    status = "passed" if len(blocking_reasons) == 0 else "blocked"
    blocking_reasons = list(dict.fromkeys(blocking_reasons))

    return {
        "schema_version": METER_CLEANUP_STABILITY_WINDOW_SCHEMA_VERSION,
        "report_id": uuid4().hex[:16],
        "generated_at": now.isoformat(),
        "mode": METER_CLEANUP_STABILITY_WINDOW_MODE,
        "status": status,
        "observed_pilot_status": observed_pilot_status,
        "pilot_record_hash": pilot_hash,
        "pilot_subject_filename": pilot_filename,
        "expected_pilot_subject_filename": expected_filename,
        "quarantined_file": {
            "path": quarantine_path or None,
            "exists": quarantine_exists,
            "sha256": quarantine_sha256,
            "hash_match": quarantine_hash_match,
        },
        "original_path": original_path or None,
        "original_path_absence": bool(original_absent),
        "parity_summary": {
            "status": parity_status,
            "critical_mismatch_count": critical_mismatch_count,
            "payload_hash_mismatch_count": int((parity or {}).get("payload_hash_mismatch_count", 0) or 0),
            "missing_in_sqlite_count": int((parity or {}).get("missing_in_sqlite_count", 0) or 0),
            "missing_in_legacy_count": int((parity or {}).get("missing_in_legacy_count", 0) or 0),
        },
        "restore_readback_result": {
            "status": restore_status,
            "source_retained": restore_source_retained,
            "backup_copy_readable": restore_backup_copy_readable,
            "checksum_match": restore_checksum_match,
            "production_restore_started": restore_production_restore_started,
            "cleanup_started": restore_cleanup_started,
        },
        "rollback_drill_result": {
            "status": rollback_status,
            "staging_restore_readable": rollback_staging_restore_readable,
            "checksum_match": rollback_checksum_match,
            "production_restore_started": rollback_production_restore_started,
            "cleanup_started": rollback_cleanup_started,
        },
        "smoke_results": smoke,
        "latency_error_sample_summary": {
            "status": str(smoke.get("status") or "failed"),
            "sample_count_per_endpoint": int(smoke.get("sample_count_per_endpoint", 0) or 0),
            "total_error_count": int(smoke.get("total_error_count", 0) or 0),
            "total_timeout_count": int(smoke.get("total_timeout_count", 0) or 0),
            "latency_ms_p95_max": smoke.get("latency_ms_p95_max"),
        },
        "cleanup_scope_expansion_started": cleanup_scope_expansion_started,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "status": status,
            "observed_pilot_status": observed_pilot_status,
            "smoke_status": str(smoke.get("status") or "failed"),
            "critical_mismatch_count": critical_mismatch_count,
            "blocking_count": int(len(blocking_reasons)),
            "cleanup_scope_expansion_started": cleanup_scope_expansion_started,
        },
    }


def write_report_atomic(report: dict[str, Any], *, policy: Optional[DataLifecyclePolicy] = None) -> Path:
    return _write_json_atomic(_report_path(policy), report, tmp_prefix="meter_cleanup_stability_window_")


def read_stability_window_report(*, policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    return _read_json(_report_path(policy))


def rebuild_stability_window_report(*, policy: Optional[DataLifecyclePolicy] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = policy or load_policy()
    started_at = _utc_now()
    report = build_stability_window_report(policy=current)
    write_report_atomic(report, policy=current)
    completed_at = _utc_now()
    record = state_store.build_record(
        cycle_id=state_store.new_cycle_id(),
        trigger="meter_cleanup_stability_window_rebuild",
        started_at=started_at,
        completed_at=completed_at,
        status="success",
        bytes_scanned=0,
        error=None,
    )
    state_store.append_state_record(record, policy=current)
    return record, report
