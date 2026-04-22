"""Shared context-scoped business tools used by CLI wrappers and MCP exposure."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_EXPECTED_OPENCLAW_VERSION,
    DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_SUPPORTED_OPENCLAW_VERSIONS,
    DEFAULT_VIKING_API_KEY,
    DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    ResultRecord,
    adapter_support_surface,
    directory_size_bytes,
    evaluate_openclaw_version_policy,
    extract_request_id,
    file_lock,
    http_json,
    http_json_with_meta,
    json_load,
    make_run_id,
    monotonic_ms,
    openviking_support_surface,
    path_writable,
    record_ids_by_status,
    render_records,
    report_metadata,
    result_counts,
    sha256_file,
    write_audit_event,
    write_json_file,
    write_json_report,
)
from ov_enterprise_context_kernel import resolve_context_id, resolve_runtime_paths
from ov_enterprise_tenant_memory import clear_tenant_memory_records, derived_agent_id, export_tenant_memory_records, import_tenant_memory_records
from ov_enterprise_tenant_paths import (
    ensure_tenant_dirs,
    resolve_instance_root,
    resolve_tenant_artifacts_dir,
    resolve_tenant_backups_dir,
    resolve_tenant_current_report_path,
    resolve_tenant_lock_path,
    resolve_tenant_snapshot_dir,
)
from ov_enterprise_tenant_policy import ensure_policy_profiles, resolve_tenant_policy
from ov_enterprise_tenant_registry import (
    assert_tenant_operation_allowed,
    get_tenant,
    load_tenant_registry,
    save_tenant_registry,
    upsert_tenant,
    validate_tenant_record,
)


def _toolize_report(
    report: dict[str, Any],
    *,
    tool_name: str,
    context_id: str,
    operations: list[dict[str, Any]] | None = None,
    artifacts: dict[str, Any] | None = None,
    runtime_window: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(report)
    payload["tool"] = tool_name
    payload["context_id"] = context_id
    payload["tenant_id"] = context_id
    payload["operations"] = list(operations or payload.get("operations") or [])
    merged_artifacts = dict(payload.get("artifacts") or {})
    merged_artifacts.update(artifacts or {})
    if payload.get("report_path"):
        merged_artifacts.setdefault("report", payload["report_path"])
    if payload.get("audit_path"):
        merged_artifacts.setdefault("audit_log", payload["audit_path"])
    payload["artifacts"] = merged_artifacts
    payload["runtime_window"] = runtime_window if runtime_window is not None else payload.get("runtime_window")
    payload["exit_code"] = 0 if payload.get("status") in {"pass", "warn"} else 1
    return payload


def _support_summary(checks: list[ResultRecord], version_policy: dict[str, Any]) -> tuple[str, str, str]:
    if any(record.status == "fail" for record in checks):
        return "C", version_policy.get("classification", "unsupported"), version_policy.get("reason_code", "tenant_check_failed")
    if any(record.status == "warn" for record in checks):
        return "B", version_policy.get("classification", "compatible"), version_policy.get("reason_code", "tenant_warning")
    return "A", version_policy.get("classification", "recommended"), version_policy.get("reason_code", "tenant_ready")


def _find_search_hit(payload: object, token: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("memories"), list):
        return None
    for item in payload["memories"]:
        if not isinstance(item, dict):
            continue
        if token in str(item.get("content", "")) or token in str(item.get("abstract", "")):
            return item
    return None


def _artifact_manifest(artifacts_dir: Path, current_report: Path) -> list[dict[str, Any]]:
    if not artifacts_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(artifacts_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == current_report.resolve():
            continue
        items.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(artifacts_dir)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return items


def _load_snapshot(snapshot_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads((snapshot_path / "snapshot.manifest.json").read_text(encoding="utf-8"))
    export_payload = json.loads((snapshot_path / "memory.export.json").read_text(encoding="utf-8"))
    tenant_meta = json.loads((snapshot_path / "tenant.meta.json").read_text(encoding="utf-8"))
    return manifest, export_payload.get("records", []), tenant_meta


def _resolve_snapshot_path(backups_dir: Path, target: str) -> Path:
    if target != "last-known-good":
        return Path(target)
    candidates = sorted(path for path in backups_dir.iterdir() if path.is_dir() and path.name.startswith("snapshot-"))
    if not candidates:
        raise FileNotFoundError("no tenant snapshots available")
    return candidates[-1]


def context_doctor(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "doctor")

    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    viking_api_key = str(arguments.get("viking_api_key") or DEFAULT_VIKING_API_KEY)
    namespace_root = str(arguments.get("namespace_root") or DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    expected_openclaw_version = str(arguments.get("expected_openclaw_version") or DEFAULT_EXPECTED_OPENCLAW_VERSION)
    supported_openclaw_versions = tuple(arguments.get("supported_openclaw_versions") or DEFAULT_SUPPORTED_OPENCLAW_VERSIONS)

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-doctor")
    checks: list[ResultRecord] = []

    report_path_ok = path_writable(report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(report_path)},
        )
    )

    try:
        registry = load_tenant_registry(registry_path)
        tenant = get_tenant(registry, context_id)
        record_errors = validate_tenant_record(tenant)
        checks.append(
            ResultRecord(
                "tenant_registry",
                "pass" if not record_errors else "fail",
                "Tenant registry entry is valid" if not record_errors else "Tenant registry entry is invalid",
                {"errors": record_errors},
            )
        )
    except Exception as exc:  # noqa: BLE001
        registry = {}
        tenant = {}
        checks.append(ResultRecord("tenant_registry", "fail", f"Failed to load tenant registry: {exc}"))

    config_payload: dict[str, Any] = {}
    config_path = Path(str(tenant.get("openclaw", {}).get("config_path", ""))) if tenant else Path()
    workspace_root = Path(str(tenant.get("openclaw", {}).get("workspace_root", ""))) if tenant else Path()
    if config_path and config_path.exists():
        try:
            config_payload = json_load(config_path)
            checks.append(ResultRecord("openclaw_config", "pass", "Tenant OpenClaw config loaded"))
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("openclaw_config", "fail", f"Failed to parse tenant OpenClaw config: {exc}"))
    else:
        checks.append(ResultRecord("openclaw_config", "fail", "Tenant OpenClaw config path is missing"))

    checks.append(
        ResultRecord(
            "workspace_root",
            "pass" if workspace_root.exists() else "fail",
            "Tenant workspace exists" if workspace_root.exists() else "Tenant workspace path is missing",
            {"path": str(workspace_root)},
        )
    )

    detected_version = tenant.get("openclaw", {}).get("version") or (
        config_payload.get("meta", {}).get("lastTouchedVersion") if isinstance(config_payload, dict) else None
    )
    version_policy = evaluate_openclaw_version_policy(
        detected_version,
        baseline_version=expected_openclaw_version,
        supported_versions=tuple(str(version) for version in supported_openclaw_versions),
    )
    checks.append(
        ResultRecord(
            "openclaw_version",
            version_policy["check_status"],
            version_policy["message"],
            {
                "detected": detected_version,
                "expected": expected_openclaw_version,
                "supported_versions": [str(version) for version in supported_openclaw_versions],
                "reason_code": version_policy["reason_code"],
            },
        )
    )

    resolved_policy_path, policy_profiles = ensure_policy_profiles(policy_path)
    policy = resolve_tenant_policy({}, policy_profiles, tenant or {"tenant_id": context_id})
    checks.append(
        ResultRecord(
            "policy_profile",
            "pass" if policy.get("profile_name") in policy_profiles else "warn",
            "Tenant policy profile loaded" if policy.get("profile_name") in policy_profiles else "Tenant policy profile fell back to defaults",
            {"profile": policy.get("profile_name"), "policy_path": str(resolved_policy_path)},
        )
    )

    adapter_surface = adapter_support_surface(adapter_url)
    openviking_surface = openviking_support_surface(openviking_url)
    checks.append(
        ResultRecord(
            "adapter_health",
            "pass" if adapter_surface["health"]["ok"] else "fail",
            "Adapter support surface reachable" if adapter_surface["health"]["ok"] else "Adapter support surface degraded",
            adapter_surface,
        )
    )
    checks.append(
        ResultRecord(
            "openviking_health",
            "pass" if openviking_surface["health"]["ok"] else "fail",
            "OpenViking health reachable" if openviking_surface["health"]["ok"] else "OpenViking health degraded",
            openviking_surface,
        )
    )

    artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    backups_dir = resolve_tenant_backups_dir(instance_root, context_id)
    artifact_bytes = directory_size_bytes(artifacts_dir)
    backup_bytes = directory_size_bytes(backups_dir)
    artifact_quota_mb = int(tenant.get("resources", {}).get("artifact_quota_mb", 1024) or 1024)
    snapshot_quota = int(tenant.get("resources", {}).get("snapshot_quota", 50) or 50)
    snapshot_count = sum(1 for item in backups_dir.iterdir()) if backups_dir.exists() else 0
    checks.append(
        ResultRecord(
            "artifact_quota",
            "pass" if artifact_bytes <= artifact_quota_mb * 1024 * 1024 else "warn",
            "Tenant artifact usage is within quota"
            if artifact_bytes <= artifact_quota_mb * 1024 * 1024
            else "Tenant artifact usage exceeds quota",
            {"used_bytes": artifact_bytes, "quota_mb": artifact_quota_mb},
        )
    )
    checks.append(
        ResultRecord(
            "snapshot_quota",
            "pass" if snapshot_count <= snapshot_quota else "warn",
            "Tenant snapshot count is within quota"
            if snapshot_count <= snapshot_quota
            else "Tenant snapshot count exceeds quota",
            {"snapshot_count": snapshot_count, "snapshot_quota": snapshot_quota, "backup_bytes": backup_bytes},
        )
    )

    try:
        memory_export = export_tenant_memory_records(
            context_id,
            agent_id=agent_id,
            openviking_url=openviking_url,
            api_key=viking_api_key,
            namespace_root=namespace_root,
        )
        memory_quota_mb = int(tenant.get("resources", {}).get("memory_quota_mb", 1024) or 1024)
        used_bytes = sum(len((item.get("raw_content") or "").encode("utf-8")) for item in memory_export.get("records", []))
        checks.append(
            ResultRecord(
                "memory_quota",
                "pass" if used_bytes <= memory_quota_mb * 1024 * 1024 else "warn",
                "Tenant memory usage is within quota"
                if used_bytes <= memory_quota_mb * 1024 * 1024
                else "Tenant memory usage exceeds quota",
                {"record_count": memory_export.get("record_count"), "used_bytes": used_bytes, "quota_mb": memory_quota_mb},
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(ResultRecord("memory_quota", "warn", f"Tenant memory usage scan failed: {exc}"))

    support_level, classification, reason_code = _support_summary(checks, version_policy)
    counts = result_counts(checks)
    status = "fail" if support_level == "C" else "warn" if support_level == "B" else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-doctor", run_id, started_ms),
        "report_kind": "tenant_doctor_report",
        "status": status,
        "support_level": support_level,
        "classification": classification,
        "reason_code": reason_code,
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "host_mode": registry.get("host_mode"),
        "summary": {
            "status": status,
            "support_level": support_level,
            "counts": counts,
        },
        "tenant": tenant,
        "policy": policy,
        "checks": render_records(checks),
        "evidence": record_ids_by_status(checks),
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_doctor",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(artifacts_dir),
            "backups_dir": str(backups_dir),
        },
    )


def context_verify(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "verify")

    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    request_timeout = float(arguments.get("request_timeout") or DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS)
    search_window_seconds = float(arguments.get("search_window_seconds") or DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS)
    delete_confirm_window_seconds = float(arguments.get("delete_confirm_window_seconds") or 20.0)
    poll_interval_seconds = float(arguments.get("poll_interval_seconds") or 3.0)

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-verify")
    steps: list[ResultRecord] = []

    report_path_ok = path_writable(report_path)
    steps.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(report_path)},
        )
    )

    try:
        registry = load_tenant_registry(registry_path)
        tenant = get_tenant(registry, context_id)
        steps.append(ResultRecord("tenant_registry", "pass", "Tenant loaded from registry"))
    except Exception as exc:  # noqa: BLE001
        registry = {}
        tenant = {}
        steps.append(ResultRecord("tenant_registry", "fail", f"Failed to load tenant registry: {exc}"))

    resolved_policy_path, policy_profiles = ensure_policy_profiles(policy_path)
    policy_profile = tenant.get("policy_profile", "default")
    steps.append(
        ResultRecord(
            "policy_profile",
            "pass" if policy_profile in policy_profiles else "warn",
            "Tenant policy profile is loadable" if policy_profile in policy_profiles else "Tenant policy profile fell back to defaults",
            {"profile": policy_profile, "policy_path": str(resolved_policy_path)},
        )
    )

    tenant_agent = derived_agent_id(context_id, agent_id)
    token = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    unique_text = f"Tenant verify token {token} for {context_id}. Agent={tenant_agent}."
    tags = [context_id, "tenant-verify", token]
    created_uri: str | None = None
    delete_confirmed = False
    request_ids: dict[str, str] = {}
    error_codes: list[str] = []

    status_code, payload, meta = http_json_with_meta(f"{adapter_url.rstrip('/')}/health", timeout=request_timeout)
    adapter_ok = status_code == 200 and isinstance(payload, dict) and payload.get("status") in {"healthy", "ok"}
    request_id = extract_request_id(meta)
    if request_id:
        request_ids["adapter_health"] = request_id
    steps.append(
        ResultRecord(
            "adapter_health",
            "pass" if adapter_ok else "fail",
            "Adapter health check passed" if adapter_ok else "Adapter health check failed",
            payload if isinstance(payload, dict) else {"response": payload},
        )
    )

    status_code, payload = http_json(f"{openviking_url.rstrip('/')}/health", timeout=request_timeout)
    openviking_ok = status_code == 200 and isinstance(payload, dict) and payload.get("status") == "ok"
    steps.append(
        ResultRecord(
            "openviking_health",
            "pass" if openviking_ok else "fail",
            "OpenViking health check passed" if openviking_ok else "OpenViking health check failed",
            payload if isinstance(payload, dict) else {"response": payload},
        )
    )

    artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    backups_dir = resolve_tenant_backups_dir(instance_root, context_id)
    steps.append(
        ResultRecord(
            "artifact_dir",
            "pass" if path_writable(artifacts_dir / "probe.json") else "fail",
            "Tenant artifact directory is writable" if path_writable(artifacts_dir / "probe.json") else "Tenant artifact directory is not writable",
            {"path": str(artifacts_dir)},
        )
    )
    baseline_exists = backups_dir.exists() and any(backups_dir.iterdir())
    steps.append(
        ResultRecord(
            "baseline_snapshot",
            "pass" if baseline_exists else "warn",
            "Tenant baseline snapshot exists" if baseline_exists else "Tenant baseline snapshot not found yet",
            {"path": str(backups_dir)},
        )
    )

    if any(step.status == "fail" for step in steps):
        counts = result_counts(steps)
        report = {
            **report_metadata("ov-enterprise-tenant-verify", run_id, started_ms),
            "report_kind": "tenant_verify_report",
            "status": "fail",
            "summary": {"status": "fail", "counts": counts},
            "tenant_id": context_id,
            "instance_id": registry.get("instance_id"),
            "checks": render_records(steps),
            "evidence": record_ids_by_status(steps),
            "report_path": str(report_path),
        }
        write_json_report(report_path, report)
        return _toolize_report(
            report,
            tool_name="context_verify",
            context_id=context_id,
            artifacts={
                "artifacts_dir": str(artifacts_dir),
                "backups_dir": str(backups_dir),
            },
        )

    status_code, payload, meta = http_json_with_meta(
        f"{adapter_url.rstrip('/')}/memory/write",
        method="POST",
        payload={
            "agent": tenant_agent,
            "type": "fact",
            "memory_type": "fact",
            "content": unique_text,
            "tags": tags,
        },
        timeout=request_timeout,
    )
    request_id = extract_request_id(meta)
    if request_id:
        request_ids["memory_write"] = request_id
    if isinstance(payload, dict) and isinstance(payload.get("error_code"), str):
        error_codes.append(payload["error_code"])
    if status_code == 200 and isinstance(payload, dict) and payload.get("status") in {"stored", "duplicate"}:
        created_uri = payload.get("uri")
        steps.append(ResultRecord("memory_write", "pass", "Tenant memory write passed", {"uri": created_uri, "request_id": request_id}))
    else:
        steps.append(ResultRecord("memory_write", "fail", "Tenant memory write failed", {"response": payload, "request_id": request_id}))

    deadline = time.time() + max(0.0, search_window_seconds)
    search_hit = None
    search_payload: object = None
    search_attempts = 0
    while time.time() <= deadline:
        search_attempts += 1
        status_code, search_payload, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/search",
            method="POST",
            payload={"agent": tenant_agent, "query": token, "limit": 20, "scoreThreshold": 0},
            timeout=request_timeout,
        )
        request_id = extract_request_id(meta)
        if request_id:
            request_ids["memory_search"] = request_id
        if isinstance(search_payload, dict) and isinstance(search_payload.get("error_code"), str):
            error_codes.append(search_payload["error_code"])
        search_hit = _find_search_hit(search_payload, token)
        if status_code != 200 or search_hit:
            break
        time.sleep(max(0.5, poll_interval_seconds))
    if status_code == 200 and search_hit:
        created_uri = created_uri or search_hit.get("uri")
        steps.append(ResultRecord("memory_search", "pass", "Tenant memory search passed", {"attempts": search_attempts, "uri": created_uri}))
    else:
        steps.append(ResultRecord("memory_search", "fail", "Tenant memory search failed", {"response": search_payload}))

    if created_uri:
        status_code, payload, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/read",
            method="POST",
            payload={"uri": created_uri},
            timeout=request_timeout,
        )
        request_id = extract_request_id(meta)
        if request_id:
            request_ids["memory_read"] = request_id
        if status_code == 200 and isinstance(payload, dict) and token in str(payload.get("content", "")):
            steps.append(ResultRecord("memory_read", "pass", "Tenant memory read passed", {"uri": created_uri}))
        else:
            steps.append(ResultRecord("memory_read", "fail", "Tenant memory read failed", {"response": payload}))
    else:
        steps.append(ResultRecord("memory_read", "fail", "Tenant memory read skipped because no URI was available"))

    if created_uri:
        status_code, payload, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/delete",
            method="POST",
            payload={"uri": created_uri},
            timeout=request_timeout,
        )
        request_id = extract_request_id(meta)
        if request_id:
            request_ids["memory_delete"] = request_id
        if status_code == 200:
            steps.append(ResultRecord("memory_delete", "pass", "Tenant memory delete passed", {"uri": created_uri}))
        else:
            steps.append(ResultRecord("memory_delete", "fail", "Tenant memory delete failed", {"response": payload}))
    else:
        steps.append(ResultRecord("memory_delete", "fail", "Tenant memory delete skipped because no URI was available"))

    confirm_deadline = time.time() + max(0.0, delete_confirm_window_seconds)
    confirm_attempts = 0
    remaining = None
    while created_uri and time.time() <= confirm_deadline:
        confirm_attempts += 1
        status_code, payload, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/search",
            method="POST",
            payload={"agent": tenant_agent, "query": token, "limit": 20, "scoreThreshold": 0},
            timeout=request_timeout,
        )
        request_id = extract_request_id(meta)
        if request_id:
            request_ids["post_delete_search"] = request_id
        if status_code != 200 or not isinstance(payload, dict):
            remaining = payload
            break
        remaining = [
            item
            for item in payload.get("memories", [])
            if isinstance(item, dict)
            and (token in str(item.get("content", "")) or token in str(item.get("abstract", "")))
        ]
        if not remaining:
            delete_confirmed = True
            break
        time.sleep(max(0.5, poll_interval_seconds))

    steps.append(
        ResultRecord(
            "post_delete_search",
            "pass" if delete_confirmed else "warn",
            "Tenant delete confirmation passed" if delete_confirmed else "Tenant delete confirmation was inconclusive",
            {"attempts": confirm_attempts, "remaining": remaining},
        )
    )

    counts = result_counts(steps)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-verify", run_id, started_ms),
        "report_kind": "tenant_verify_report",
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "tenant_id": context_id,
            "cleanup_confirmed": delete_confirmed,
        },
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "host_mode": registry.get("host_mode"),
        "tenant_agent_id": tenant_agent,
        "request_trace": request_ids,
        "adapter_error_codes_seen": sorted(set(error_codes)),
        "created_uri": created_uri,
        "checks": render_records(steps),
        "evidence": record_ids_by_status(steps),
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_verify",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(artifacts_dir),
            "backups_dir": str(backups_dir),
        },
    )
