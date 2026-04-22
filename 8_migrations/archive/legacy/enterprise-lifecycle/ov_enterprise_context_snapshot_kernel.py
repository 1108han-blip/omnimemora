"""Shared context-scoped snapshot tools used by CLI wrappers and MCP exposure."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_VIKING_API_KEY,
    DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    ResultRecord,
    adapter_support_surface,
    extract_request_id,
    file_lock,
    http_json_with_meta,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    sha256_file,
    write_audit_event,
    write_json_file,
    write_json_report,
)
from ov_enterprise_context_kernel import resolve_context_id, resolve_runtime_paths
from ov_enterprise_context_tool_kernel import _toolize_report
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
)


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


def _record_signature(record: dict[str, Any]) -> str:
    raw_content = str(record.get("raw_content") or "").strip()
    if raw_content:
        return f"raw:{raw_content}"
    content = str(record.get("content") or "").strip()
    if content:
        return f"content:{content}"
    return f"uri:{str(record.get('uri') or '').strip()}"


def _record_probe_text(record: dict[str, Any]) -> str | None:
    content = str(record.get("content") or record.get("raw_content") or "").strip()
    if not content:
        return None
    normalized = " ".join(content.split())
    if len(normalized) < 12:
        return None
    return normalized[:160]


def _remaining_search_hits(payload: object, probe_text: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("memories"), list):
        return []
    remaining: list[dict[str, Any]] = []
    for item in payload["memories"]:
        if not isinstance(item, dict):
            continue
        haystacks = (str(item.get("content", "")), str(item.get("abstract", "")))
        if any(probe_text in haystack for haystack in haystacks):
            remaining.append(item)
    return remaining


def _removed_record_probes(
    before_records: list[dict[str, Any]],
    expected_records: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    expected_signatures = {_record_signature(record) for record in expected_records}
    probes: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for record in before_records:
        signature = _record_signature(record)
        if signature in expected_signatures:
            continue
        query = _record_probe_text(record)
        if not query or query in seen_queries:
            continue
        seen_queries.add(query)
        probes.append(
            {
                "query": query,
                "source_uri": record.get("uri"),
                "signature": signature,
            }
        )
        if len(probes) >= limit:
            break
    return probes


def _post_search_consistency_check(
    *,
    context_id: str,
    before_records: list[dict[str, Any]],
    expected_records: list[dict[str, Any]],
    adapter_url: str,
    agent_id: str,
    request_timeout: float,
    search_window_seconds: float,
    poll_interval_seconds: float,
) -> tuple[ResultRecord, dict[str, Any]]:
    probes = _removed_record_probes(before_records, expected_records)
    if not probes:
        details = {
            "probe_count": 0,
            "remaining_count": 0,
            "attempts": 0,
            "queries": [],
            "tenant_agent_id": derived_agent_id(context_id, agent_id),
        }
        return (
            ResultRecord(
                "post_search_consistency",
                "pass",
                "No removed tenant records required search confirmation",
                details,
            ),
            details,
        )

    tenant_agent = derived_agent_id(context_id, agent_id)
    deadline = time.time() + max(0.0, search_window_seconds)
    attempts = 0
    remaining = list(probes)
    last_request_ids: list[str] = []
    failed_queries: list[dict[str, Any]] = []

    while time.time() <= deadline and remaining and not failed_queries:
        attempts += 1
        next_remaining: list[dict[str, Any]] = []
        for probe in remaining:
            status_code, payload, meta = http_json_with_meta(
                f"{adapter_url.rstrip('/')}/memory/search",
                method="POST",
                payload={"agent": tenant_agent, "query": probe["query"], "limit": 20, "scoreThreshold": 0},
                timeout=request_timeout,
            )
            request_id = extract_request_id(meta)
            if request_id:
                last_request_ids.append(request_id)
            if status_code != 200 or not isinstance(payload, dict):
                failed_queries.append(
                    {
                        "query": probe["query"],
                        "status_code": status_code,
                        "response": payload,
                        "request_id": request_id,
                    }
                )
                continue
            hits = _remaining_search_hits(payload, probe["query"])
            if hits:
                next_remaining.append(
                    {
                        **probe,
                        "hits": hits[:3],
                        "request_id": request_id,
                    }
                )
        if failed_queries or not next_remaining:
            remaining = next_remaining
            break
        remaining = next_remaining
        time.sleep(max(0.5, poll_interval_seconds))

    details = {
        "probe_count": len(probes),
        "remaining_count": len(remaining),
        "attempts": attempts,
        "queries": [probe["query"] for probe in probes],
        "remaining": remaining,
        "failed_queries": failed_queries,
        "request_ids": last_request_ids[-10:],
        "tenant_agent_id": tenant_agent,
        "search_window_seconds": search_window_seconds,
    }
    if failed_queries:
        return (
            ResultRecord(
                "post_search_consistency",
                "warn",
                "Tenant search consistency check was inconclusive",
                details,
            ),
            details,
        )
    if remaining:
        return (
            ResultRecord(
                "post_search_consistency",
                "warn",
                "Removed tenant records still appear in search before the confirmation window closed",
                details,
            ),
            details,
        )
    return (
        ResultRecord(
            "post_search_consistency",
            "pass",
            "Removed tenant records no longer appear in search results",
            details,
        ),
        details,
    )


def context_backup(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "backup")

    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    viking_api_key = str(arguments.get("viking_api_key") or DEFAULT_VIKING_API_KEY)
    namespace_root = str(arguments.get("namespace_root") or DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    snapshot_type = str(arguments.get("snapshot_type") or "manual")
    tag = arguments.get("tag")
    execute = bool(arguments.get("execute"))

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-backup")
    checks: list[ResultRecord] = []

    report_ok = path_writable(report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_ok else "fail",
            "Report path is writable" if report_ok else "Report path is not writable",
            {"path": str(report_path)},
        )
    )

    try:
        registry = load_tenant_registry(registry_path)
        tenant = get_tenant(registry, context_id)
        checks.append(ResultRecord("tenant_registry", "pass", "Tenant loaded from registry"))
    except Exception as exc:  # noqa: BLE001
        registry = {}
        tenant = {}
        checks.append(ResultRecord("tenant_registry", "fail", f"Failed to load tenant from registry: {exc}"))

    resolved_policy_path, policy_profiles = ensure_policy_profiles(policy_path)
    policy = resolve_tenant_policy({}, policy_profiles, tenant or {"tenant_id": context_id})
    checks.append(
        ResultRecord(
            "policy_profile",
            "pass" if tenant else "warn",
            "Tenant policy resolved" if tenant else "Policy resolved with fallback tenant context",
            {"policy_path": str(resolved_policy_path), "profile": policy.get("profile_name")},
        )
    )

    memory_export: dict[str, Any] = {"record_count": 0, "records": []}
    export_error: str | None = None
    if tenant:
        try:
            memory_export = export_tenant_memory_records(
                context_id,
                agent_id=agent_id,
                openviking_url=openviking_url,
                api_key=viking_api_key,
                namespace_root=namespace_root,
            )
            checks.append(
                ResultRecord(
                    "memory_export",
                    "pass",
                    f"Exported {memory_export['record_count']} tenant memory records",
                    {"namespace_uri": memory_export.get("namespace_uri")},
                )
            )
        except Exception as exc:  # noqa: BLE001
            export_error = str(exc)
            checks.append(ResultRecord("memory_export", "fail", f"Tenant memory export failed: {exc}"))

    tenant_artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    tenant_backups_dir = resolve_tenant_backups_dir(instance_root, context_id)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    snapshot_id = f"snapshot-{stamp}"
    snapshot_dir = resolve_tenant_snapshot_dir(instance_root, context_id, snapshot_id)
    artifacts_manifest = _artifact_manifest(tenant_artifacts_dir, report_path)
    support_surface = adapter_support_surface(adapter_url)

    file_paths: dict[str, Path] = {
        "snapshot_manifest": snapshot_dir / "snapshot.manifest.json",
        "memory_export": snapshot_dir / "memory.export.json",
        "tenant_meta": snapshot_dir / "tenant.meta.json",
        "policy_snapshot": snapshot_dir / "policy.snapshot.json",
        "artifacts_manifest": snapshot_dir / "artifacts.manifest.json",
        "checksums": snapshot_dir / "checksums.json",
    }

    checks.append(
        ResultRecord(
            "snapshot_target",
            "pass" if path_writable(snapshot_dir / "probe.json") else "fail",
            "Snapshot directory is writable" if path_writable(snapshot_dir / "probe.json") else "Snapshot directory is not writable",
            {"path": str(snapshot_dir)},
        )
    )

    written_files: dict[str, str] = {}
    checksums: dict[str, str] = {}
    if execute and not any(item.status == "fail" for item in checks):
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        write_json_file(file_paths["memory_export"], memory_export)
        write_json_file(file_paths["tenant_meta"], tenant)
        write_json_file(
            file_paths["policy_snapshot"],
            {
                "policy_profile": tenant.get("policy_profile"),
                "resolved_policy": policy,
            },
        )
        write_json_file(
            file_paths["artifacts_manifest"],
            {
                "tenant_id": context_id,
                "artifact_count": len(artifacts_manifest),
                "items": artifacts_manifest,
            },
        )
        snapshot_manifest = {
            **report_metadata("ov-enterprise-tenant-backup", run_id, started_ms),
            "status": "pass",
            "snapshot_id": snapshot_id,
            "snapshot_type": snapshot_type,
            "tag": tag,
            "tenant_id": context_id,
            "instance_id": registry.get("instance_id"),
            "source_instance_id": tenant.get("source_instance_id"),
            "host_mode": registry.get("host_mode"),
            "record_count": memory_export.get("record_count"),
            "artifacts_count": len(artifacts_manifest),
            "namespace_uri": memory_export.get("namespace_uri"),
        }
        write_json_file(file_paths["snapshot_manifest"], snapshot_manifest)
        for key, path in file_paths.items():
            if path.exists():
                written_files[key] = str(path)
                checksums[path.name] = sha256_file(path)
        write_json_file(file_paths["checksums"], checksums)
        written_files["checksums"] = str(file_paths["checksums"])
        checksums[file_paths["checksums"].name] = sha256_file(file_paths["checksums"])
        audit_path = write_audit_event(
            tenant_artifacts_dir / "audit",
            {
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tenant_id": context_id,
                "operation": "backup",
                "instance_id": registry.get("instance_id"),
                "snapshot_id": snapshot_id,
                "snapshot_type": snapshot_type,
                "report_path": str(report_path),
            },
        )
    else:
        audit_path = None

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-backup", run_id, started_ms),
        "report_kind": "tenant_backup_report",
        "status": status,
        "mode": "execute" if execute else "dry-run",
        "summary": {
            "status": status,
            "counts": counts,
            "tenant_id": context_id,
            "record_count": memory_export.get("record_count", 0),
            "snapshot_id": snapshot_id,
        },
        "operations": [
            {
                "kind": "context_backup",
                "mode": "execute" if execute else "dry-run",
                "snapshot_id": snapshot_id,
                "snapshot_type": snapshot_type,
            }
        ],
        "tenant": tenant,
        "instance": {
            "instance_id": registry.get("instance_id"),
            "host_mode": registry.get("host_mode"),
            "instance_root": str(instance_root),
        },
        "inputs": {
            "tenant": context_id,
            "snapshot_type": snapshot_type,
            "tag": tag,
            "registry_path": str(registry_path),
            "policy_path": str(resolved_policy_path),
            "adapter_url": adapter_url,
            "openviking_url": openviking_url,
            "namespace_root": namespace_root,
            "agent_id": agent_id,
        },
        "checks": render_records(checks),
        "support_surface": support_surface,
        "memory_export": {
            "record_count": memory_export.get("record_count"),
            "namespace_uri": memory_export.get("namespace_uri"),
            "error": export_error,
        },
        "snapshot": {
            "snapshot_id": snapshot_id,
            "snapshot_dir": str(snapshot_dir),
            "snapshot_type": snapshot_type,
            "tag": tag,
            "written_files": written_files,
            "checksums": checksums,
            "artifact_count": len(artifacts_manifest),
        },
        "artifacts_manifest": {
            "artifact_count": len(artifacts_manifest),
            "items": artifacts_manifest,
        },
        "policy_snapshot": {
            "path": str(resolved_policy_path),
            "resolved_policy": policy,
        },
        "audit_path": audit_path,
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_backup",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(tenant_artifacts_dir),
            "backups_dir": str(tenant_backups_dir),
            "snapshot_dir": str(snapshot_dir),
        },
    )


def context_restore(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "restore")
    tenant_artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    tenant_backups_dir = resolve_tenant_backups_dir(instance_root, context_id)
    lock_path = resolve_tenant_lock_path(instance_root, context_id, "restore")

    snapshot_path = Path(arguments.get("snapshot") or "")
    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    request_timeout = float(arguments.get("request_timeout") or DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS)
    search_window_seconds = float(arguments.get("search_window_seconds") or 20.0)
    poll_interval_seconds = float(arguments.get("poll_interval_seconds") or 3.0)
    mode = str(arguments.get("mode") or "replace")
    execute = bool(arguments.get("execute"))

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-restore")
    checks: list[ResultRecord] = []
    precheck: list[ResultRecord] = []
    execute_items: list[ResultRecord] = []
    postcheck: list[ResultRecord] = []

    report_ok = path_writable(report_path)
    report_record = ResultRecord("report_path", "pass" if report_ok else "fail", "Report path is writable" if report_ok else "Report path is not writable", {"path": str(report_path)})
    checks.append(report_record)
    precheck.append(report_record)

    try:
        registry = load_tenant_registry(registry_path)
        tenant = get_tenant(registry, context_id)
        assert_tenant_operation_allowed(tenant, "restore")
        tenant_record = ResultRecord("tenant_registry", "pass", "Tenant loaded and restore is allowed")
    except Exception as exc:  # noqa: BLE001
        registry = {}
        tenant = {}
        tenant_record = ResultRecord("tenant_registry", "fail", f"Tenant restore precheck failed: {exc}")
    checks.append(tenant_record)
    precheck.append(tenant_record)

    resolved_policy_path, policy_profiles = ensure_policy_profiles(policy_path)
    policy = resolve_tenant_policy({}, policy_profiles, tenant or {"tenant_id": context_id})
    policy_record = ResultRecord("policy_profile", "pass", "Tenant restore policy resolved", {"profile": policy.get("profile_name"), "policy_path": str(resolved_policy_path)})
    checks.append(policy_record)
    precheck.append(policy_record)

    try:
        snapshot_manifest, snapshot_records, tenant_meta = _load_snapshot(snapshot_path)
        snapshot_record = ResultRecord(
            "snapshot",
            "pass",
            "Tenant snapshot loaded",
            {"snapshot": str(snapshot_path), "record_count": len(snapshot_records), "snapshot_id": snapshot_manifest.get("snapshot_id")},
        )
    except Exception as exc:  # noqa: BLE001
        snapshot_manifest = {}
        snapshot_records = []
        tenant_meta = {}
        snapshot_record = ResultRecord("snapshot", "fail", f"Tenant snapshot load failed: {exc}")
    checks.append(snapshot_record)
    precheck.append(snapshot_record)

    status = "fail" if any(item.status == "fail" for item in checks) else "pass"
    backup_payload: dict[str, Any] | None = None
    current_export: dict[str, Any] | None = None
    clear_result: dict[str, Any] | None = None
    import_result: dict[str, Any] | None = None
    post_export: dict[str, Any] | None = None
    post_search_consistency: dict[str, Any] | None = None
    audit_path: str | None = None

    if execute and status != "fail":
        try:
            with file_lock(lock_path):
                if policy.get("require_pre_snapshot"):
                    backup_payload = context_backup(
                        {
                            "context_id": context_id,
                            "tenant_id": context_id,
                            "instance_root": instance_root,
                            "registry_path": registry_path,
                            "policy_path": resolved_policy_path,
                            "adapter_url": adapter_url,
                            "openviking_url": openviking_url,
                            "agent_id": agent_id,
                            "execute": True,
                            "snapshot_type": "pre-restore",
                        }
                    )
                    execute_items.append(
                        ResultRecord(
                            "pre_snapshot",
                            "pass" if backup_payload.get("exit_code") == 0 else "fail",
                            "Pre-restore safety snapshot created" if backup_payload.get("exit_code") == 0 else "Pre-restore safety snapshot failed",
                            {"report_path": backup_payload.get("report_path")},
                        )
                    )
                if mode == "replace":
                    current_export = export_tenant_memory_records(context_id, agent_id=agent_id, openviking_url=openviking_url)
                    clear_result = clear_tenant_memory_records(current_export.get("records", []), adapter_url=adapter_url)
                    execute_items.append(
                        ResultRecord(
                            "clear_current_memory",
                            "pass" if not clear_result["failed"] else "warn",
                            "Existing tenant memory cleared before restore"
                            if not clear_result["failed"]
                            else "Some existing tenant memory items could not be cleared before restore",
                            {"deleted_count": clear_result["deleted_count"], "failed_count": len(clear_result["failed"])},
                        )
                    )
                import_result = import_tenant_memory_records(
                    context_id,
                    snapshot_records,
                    agent_id=agent_id,
                    adapter_url=adapter_url,
                    openviking_url=openviking_url,
                    extra_tags=["tenant-restore", snapshot_manifest.get("snapshot_id", "unknown")],
                )
                execute_items.append(
                    ResultRecord(
                        "import_snapshot",
                        "pass" if import_result["failed_count"] == 0 else "warn",
                        "Tenant snapshot records restored"
                        if import_result["failed_count"] == 0
                        else "Tenant snapshot restore completed with partial failures",
                        {"imported_count": import_result["imported_count"], "failed_count": import_result["failed_count"]},
                    )
                )
                post_export = export_tenant_memory_records(context_id, agent_id=agent_id, openviking_url=openviking_url)
                if tenant_meta:
                    restored_meta = dict(tenant_meta)
                    restored_meta["status"] = tenant.get("status", "active")
                    restored_meta["instance_id"] = registry.get("instance_id")
                    restored_meta["source_instance_id"] = tenant_meta.get("source_instance_id", registry.get("instance_id"))
                    upsert_tenant(registry, restored_meta)
                    save_tenant_registry(registry_path, registry)
                audit_path = write_audit_event(
                    tenant_artifacts_dir / "audit",
                    {
                        "tenant_id": context_id,
                        "operation": "restore",
                        "mode": mode,
                        "snapshot": str(snapshot_path),
                        "snapshot_id": snapshot_manifest.get("snapshot_id"),
                        "report_path": str(report_path),
                    },
                )
        except FileExistsError:
            execute_items.append(ResultRecord("tenant_lock", "fail", "Another tenant restore is already in progress", {"lock_path": str(lock_path)}))
        except Exception as exc:  # noqa: BLE001
            execute_items.append(ResultRecord("execute_restore", "fail", f"Tenant restore failed: {exc}"))
    elif execute:
        execute_items.append(ResultRecord("execute_restore", "blocked", "Tenant restore blocked by precheck failure"))
    else:
        execute_items.append(ResultRecord("execute_restore", "skip", "Dry-run only; no tenant restore applied"))

    if import_result is not None:
        postcheck.append(
            ResultRecord(
                "post_restore_state",
                "pass" if import_result["failed_count"] == 0 else "warn",
                "Tenant restore post-state recorded",
                {"imported_count": import_result["imported_count"], "failed_count": import_result["failed_count"]},
            )
        )
    if post_export is not None:
        postcheck.append(
            ResultRecord(
                "post_restore_export",
                "pass",
                "Tenant restore filesystem export captured",
                {"record_count": post_export.get("record_count")},
            )
        )
    if current_export is not None and post_export is not None:
        search_record, post_search_consistency = _post_search_consistency_check(
            context_id=context_id,
            before_records=current_export.get("records", []),
            expected_records=post_export.get("records", []),
            adapter_url=adapter_url,
            agent_id=agent_id,
            request_timeout=request_timeout,
            search_window_seconds=search_window_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        postcheck.append(search_record)

    all_checks = [*checks, *execute_items, *postcheck]
    counts = result_counts(all_checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-restore", run_id, started_ms),
        "report_kind": "tenant_restore_report",
        "status": status,
        "mode": "execute" if execute else "dry-run",
        "reason_code": "tenant_restore_applied" if execute and status in {"pass", "warn"} else "dry_run",
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "host_mode": registry.get("host_mode"),
        "summary": {
            "status": status,
            "counts": counts,
            "tenant_id": context_id,
            "mode": "execute" if execute else "dry-run",
            "snapshot_id": snapshot_manifest.get("snapshot_id"),
            "imported_count": import_result.get("imported_count", 0) if isinstance(import_result, dict) else 0,
            "failed_count": import_result.get("failed_count", 0) if isinstance(import_result, dict) else 0,
        },
        "snapshot": {
            "path": str(snapshot_path),
            "snapshot_id": snapshot_manifest.get("snapshot_id"),
            "record_count": len(snapshot_records),
        },
        "operations": [
            {
                "kind": "context_restore",
                "mode": "execute" if execute else "dry-run",
                "snapshot_path": str(snapshot_path),
                "clear_before_restore": mode == "replace",
            }
        ],
        "checks": render_records(all_checks),
        "execute_checklist": {
            "precheck": render_records(precheck),
            "during_execute": render_records(execute_items),
            "postcheck": render_records(postcheck),
        },
        "results": {
            "pre_snapshot": backup_payload,
            "current_export": current_export,
            "clear_result": clear_result,
            "import_result": import_result,
            "post_export": post_export,
            "post_search_consistency": post_search_consistency,
        },
        "audit_path": audit_path,
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_restore",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(tenant_artifacts_dir),
            "backups_dir": str(tenant_backups_dir),
            "snapshot_path": str(snapshot_path),
        },
    )


def context_rollback(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "rollback")
    tenant_artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    tenant_backups_dir = resolve_tenant_backups_dir(instance_root, context_id)
    lock_path = resolve_tenant_lock_path(instance_root, context_id, "rollback")

    target = str(arguments.get("to") or "last-known-good")
    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    request_timeout = float(arguments.get("request_timeout") or DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS)
    search_window_seconds = float(arguments.get("search_window_seconds") or 20.0)
    poll_interval_seconds = float(arguments.get("poll_interval_seconds") or 3.0)
    execute = bool(arguments.get("execute"))

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-rollback")
    checks: list[ResultRecord] = []
    precheck: list[ResultRecord] = []
    execute_items: list[ResultRecord] = []
    postcheck: list[ResultRecord] = []

    report_record = ResultRecord("report_path", "pass" if path_writable(report_path) else "fail", "Report path is writable" if path_writable(report_path) else "Report path is not writable", {"path": str(report_path)})
    checks.append(report_record)
    precheck.append(report_record)

    try:
        registry = load_tenant_registry(registry_path)
        tenant = get_tenant(registry, context_id)
        assert_tenant_operation_allowed(tenant, "rollback")
        tenant_record = ResultRecord("tenant_registry", "pass", "Tenant loaded and rollback is allowed")
    except Exception as exc:  # noqa: BLE001
        registry = {}
        tenant = {}
        tenant_record = ResultRecord("tenant_registry", "fail", f"Tenant rollback precheck failed: {exc}")
    checks.append(tenant_record)
    precheck.append(tenant_record)

    resolved_policy_path, policy_profiles = ensure_policy_profiles(policy_path)
    policy = resolve_tenant_policy({}, policy_profiles, tenant or {"tenant_id": context_id})
    policy_record = ResultRecord("policy_profile", "pass", "Tenant rollback policy resolved", {"profile": policy.get("profile_name"), "policy_path": str(resolved_policy_path)})
    checks.append(policy_record)
    precheck.append(policy_record)

    try:
        snapshot_path = _resolve_snapshot_path(tenant_backups_dir, target)
        snapshot_manifest, snapshot_records, _tenant_meta = _load_snapshot(snapshot_path)
        snapshot_record = ResultRecord("snapshot", "pass", "Tenant rollback snapshot resolved", {"snapshot": str(snapshot_path), "snapshot_id": snapshot_manifest.get("snapshot_id"), "record_count": len(snapshot_records)})
    except Exception as exc:  # noqa: BLE001
        snapshot_path = Path(target)
        snapshot_manifest = {}
        snapshot_records = []
        snapshot_record = ResultRecord("snapshot", "fail", f"Tenant rollback snapshot resolution failed: {exc}")
    checks.append(snapshot_record)
    precheck.append(snapshot_record)

    status = "fail" if any(item.status == "fail" for item in checks) else "pass"
    backup_payload: dict[str, Any] | None = None
    current_export: dict[str, Any] | None = None
    clear_result: dict[str, Any] | None = None
    import_result: dict[str, Any] | None = None
    post_export: dict[str, Any] | None = None
    post_search_consistency: dict[str, Any] | None = None
    audit_path: str | None = None

    if execute and status != "fail":
        try:
            with file_lock(lock_path):
                if policy.get("require_pre_snapshot"):
                    backup_payload = context_backup(
                        {
                            "context_id": context_id,
                            "tenant_id": context_id,
                            "instance_root": instance_root,
                            "registry_path": registry_path,
                            "policy_path": resolved_policy_path,
                            "adapter_url": adapter_url,
                            "openviking_url": openviking_url,
                            "agent_id": agent_id,
                            "execute": True,
                            "snapshot_type": "pre-rollback",
                        }
                    )
                    execute_items.append(
                        ResultRecord(
                            "pre_snapshot",
                            "pass" if backup_payload.get("exit_code") == 0 else "fail",
                            "Pre-rollback safety snapshot created" if backup_payload.get("exit_code") == 0 else "Pre-rollback safety snapshot failed",
                            {"report_path": backup_payload.get("report_path")},
                        )
                    )
                current_export = export_tenant_memory_records(context_id, agent_id=agent_id, openviking_url=openviking_url)
                clear_result = clear_tenant_memory_records(current_export.get("records", []), adapter_url=adapter_url)
                execute_items.append(
                    ResultRecord(
                        "clear_current_memory",
                        "pass" if not clear_result["failed"] else "warn",
                        "Current tenant memory cleared before rollback"
                        if not clear_result["failed"]
                        else "Some current tenant memory items could not be cleared before rollback",
                        {"deleted_count": clear_result["deleted_count"], "failed_count": len(clear_result["failed"])},
                    )
                )
                import_result = import_tenant_memory_records(
                    context_id,
                    snapshot_records,
                    agent_id=agent_id,
                    adapter_url=adapter_url,
                    openviking_url=openviking_url,
                    extra_tags=["tenant-rollback", snapshot_manifest.get("snapshot_id", "unknown")],
                )
                execute_items.append(
                    ResultRecord(
                        "import_snapshot",
                        "pass" if import_result["failed_count"] == 0 else "warn",
                        "Tenant rollback snapshot imported"
                        if import_result["failed_count"] == 0
                        else "Tenant rollback imported with partial failures",
                        {"imported_count": import_result["imported_count"], "failed_count": import_result["failed_count"]},
                    )
                )
                post_export = export_tenant_memory_records(context_id, agent_id=agent_id, openviking_url=openviking_url)
                audit_path = write_audit_event(
                    tenant_artifacts_dir / "audit",
                    {
                        "tenant_id": context_id,
                        "operation": "rollback",
                        "target": target,
                        "snapshot": str(snapshot_path),
                        "snapshot_id": snapshot_manifest.get("snapshot_id"),
                        "report_path": str(report_path),
                    },
                )
        except FileExistsError:
            execute_items.append(ResultRecord("tenant_lock", "fail", "Another tenant rollback is already in progress", {"lock_path": str(lock_path)}))
        except Exception as exc:  # noqa: BLE001
            execute_items.append(ResultRecord("execute_rollback", "fail", f"Tenant rollback failed: {exc}"))
    elif execute:
        execute_items.append(ResultRecord("execute_rollback", "blocked", "Tenant rollback blocked by precheck failure"))
    else:
        execute_items.append(ResultRecord("execute_rollback", "skip", "Dry-run only; no tenant rollback applied"))

    if import_result is not None:
        postcheck.append(
            ResultRecord(
                "post_rollback_state",
                "pass" if import_result["failed_count"] == 0 else "warn",
                "Tenant rollback post-state recorded",
                {"imported_count": import_result["imported_count"], "failed_count": import_result["failed_count"]},
            )
        )
    if post_export is not None:
        postcheck.append(
            ResultRecord(
                "post_rollback_export",
                "pass",
                "Tenant rollback filesystem export captured",
                {"record_count": post_export.get("record_count")},
            )
        )
    if current_export is not None and post_export is not None:
        search_record, post_search_consistency = _post_search_consistency_check(
            context_id=context_id,
            before_records=current_export.get("records", []),
            expected_records=post_export.get("records", []),
            adapter_url=adapter_url,
            agent_id=agent_id,
            request_timeout=request_timeout,
            search_window_seconds=search_window_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        postcheck.append(search_record)

    all_checks = [*checks, *execute_items, *postcheck]
    counts = result_counts(all_checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-rollback", run_id, started_ms),
        "report_kind": "tenant_rollback_report",
        "status": status,
        "mode": "execute" if execute else "dry-run",
        "reason_code": "tenant_rollback_applied" if execute and status in {"pass", "warn"} else "dry_run",
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "host_mode": registry.get("host_mode"),
        "target": target,
        "summary": {
            "status": status,
            "counts": counts,
            "tenant_id": context_id,
            "mode": "execute" if execute else "dry-run",
            "snapshot_id": snapshot_manifest.get("snapshot_id"),
            "imported_count": import_result.get("imported_count", 0) if isinstance(import_result, dict) else 0,
            "failed_count": import_result.get("failed_count", 0) if isinstance(import_result, dict) else 0,
        },
        "snapshot": {
            "path": str(snapshot_path),
            "snapshot_id": snapshot_manifest.get("snapshot_id"),
            "record_count": len(snapshot_records),
        },
        "operations": [
            {
                "kind": "context_rollback",
                "mode": "execute" if execute else "dry-run",
                "target": target,
                "snapshot_path": str(snapshot_path),
            }
        ],
        "checks": render_records(all_checks),
        "execute_checklist": {
            "precheck": render_records(precheck),
            "during_execute": render_records(execute_items),
            "postcheck": render_records(postcheck),
        },
        "results": {
            "pre_snapshot": backup_payload,
            "current_export": current_export,
            "clear_result": clear_result,
            "import_result": import_result,
            "post_export": post_export,
            "post_search_consistency": post_search_consistency,
        },
        "audit_path": audit_path,
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_rollback",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(tenant_artifacts_dir),
            "backups_dir": str(tenant_backups_dir),
            "snapshot_path": str(snapshot_path),
        },
    )
