"""Shared context-scoped package tools used by CLI wrappers and MCP exposure."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_VIKING_API_KEY,
    DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT,
    ResultRecord,
    file_lock,
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
from ov_enterprise_tenant_memory import clear_tenant_memory_records, export_tenant_memory_records, import_tenant_memory_records
from ov_enterprise_tenant_paths import (
    ensure_tenant_dirs,
    resolve_instance_root,
    resolve_tenant_artifacts_dir,
    resolve_tenant_current_report_path,
    resolve_tenant_exports_dir,
    resolve_tenant_lock_path,
)
from ov_enterprise_tenant_policy import ensure_policy_profiles
from ov_enterprise_tenant_registry import create_tenant_record, get_tenant, load_tenant_registry, save_tenant_registry, upsert_tenant


def _artifact_manifest(artifacts_dir: Path, current_report: Path) -> list[dict[str, Any]]:
    if not artifacts_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(artifacts_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == current_report.resolve():
            continue
        items.append({"path": str(path), "relative_path": str(path.relative_to(artifacts_dir)), "size_bytes": path.stat().st_size})
    return items


def context_export(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "export")

    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    viking_api_key = str(arguments.get("viking_api_key") or DEFAULT_VIKING_API_KEY)
    namespace_root = str(arguments.get("namespace_root") or DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    target_instance = arguments.get("target_instance")
    execute = bool(arguments.get("execute"))

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-export")
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
        checks.append(ResultRecord("tenant_registry", "fail", f"Failed to load tenant registry: {exc}"))

    ensure_policy_profiles(policy_path)
    output_dir = Path(arguments["output"]) if arguments.get("output") else (resolve_tenant_exports_dir(instance_root, context_id) / f"export-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
    artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    artifact_index = _artifact_manifest(artifacts_dir, report_path)
    package_payload: dict[str, Any] = {}
    written_files: dict[str, str] = {}

    if tenant:
        try:
            memory_export = export_tenant_memory_records(
                context_id,
                agent_id=agent_id,
                openviking_url=openviking_url,
                api_key=viking_api_key,
                namespace_root=namespace_root,
            )
            checks.append(ResultRecord("memory_export", "pass", f"Exported {memory_export['record_count']} tenant records"))
        except Exception as exc:  # noqa: BLE001
            memory_export = {"record_count": 0, "records": []}
            checks.append(ResultRecord("memory_export", "fail", f"Tenant export failed: {exc}"))
    else:
        memory_export = {"record_count": 0, "records": []}

    if execute and not any(item.status == "fail" for item in checks):
        output_dir.mkdir(parents=True, exist_ok=False)
        memory_path = output_dir / "memory.export.json"
        artifacts_path = output_dir / "artifacts.manifest.json"
        tenant_meta_path = output_dir / "tenant.meta.json"
        checksums_path = output_dir / "checksums.json"
        package_path = output_dir / "tenant.package.json"
        write_json_file(memory_path, memory_export)
        write_json_file(artifacts_path, {"tenant_id": context_id, "items": artifact_index})
        write_json_file(tenant_meta_path, tenant)
        package_payload = {
            "schema_version": "1.0",
            "tenant_id": context_id,
            "display_name": tenant.get("display_name"),
            "source_instance_id": registry.get("instance_id"),
            "target_instance": target_instance,
            "target_instance_id": target_instance,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "host_mode": registry.get("host_mode"),
            "migration_state": tenant.get("migration_state"),
            "policy_profile": tenant.get("policy_profile"),
            "memory_records_path": memory_path.name,
            "artifacts_manifest_path": artifacts_path.name,
            "tenant_meta_path": tenant_meta_path.name,
            "checksums_path": checksums_path.name,
        }
        write_json_file(package_path, package_payload)
        checksums = {}
        for path in (memory_path, artifacts_path, tenant_meta_path, package_path):
            checksums[path.name] = sha256_file(path)
            written_files[path.stem] = str(path)
        write_json_file(checksums_path, checksums)
        written_files["checksums"] = str(checksums_path)
        audit_path = write_audit_event(
            artifacts_dir / "audit",
            {
                "tenant_id": context_id,
                "operation": "export",
                "output_dir": str(output_dir),
                "target_instance": target_instance,
                "report_path": str(report_path),
            },
        )
        checks.append(
            ResultRecord(
                "export_execute",
                "pass",
                "Tenant package export written",
                {"output_dir": str(output_dir), "file_count": len(written_files)},
            )
        )
    else:
        audit_path = None
        if not execute:
            checks.append(ResultRecord("export_execute", "skip", "Dry-run only; no tenant export package written"))

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-export", run_id, started_ms),
        "report_kind": "tenant_export_report",
        "status": status,
        "mode": "execute" if execute else "dry-run",
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "target_instance": target_instance,
        "output_dir": str(output_dir),
        "summary": {
            "status": status,
            "counts": counts,
            "tenant_id": context_id,
            "mode": "execute" if execute else "dry-run",
            "record_count": memory_export.get("record_count", 0),
            "output_dir": str(output_dir),
        },
        "operations": [
            {
                "kind": "context_export",
                "mode": "execute" if execute else "dry-run",
                "output_dir": str(output_dir),
                "target_instance": target_instance,
            }
        ],
        "checks": render_records(checks),
        "package": package_payload,
        "written_files": written_files,
        "audit_path": audit_path,
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_export",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(artifacts_dir),
            "exports_dir": str(resolve_tenant_exports_dir(instance_root, context_id)),
            "output_dir": str(output_dir),
        },
    )


def context_import(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    instance_root = resolve_instance_root(instance_root)
    ensure_tenant_dirs(instance_root, context_id)
    report_path = Path(arguments["report_path"]) if arguments.get("report_path") else resolve_tenant_current_report_path(instance_root, context_id, "import")
    tenant_artifacts_dir = resolve_tenant_artifacts_dir(instance_root, context_id)
    lock_path = resolve_tenant_lock_path(instance_root, context_id, "import")

    input_dir = Path(arguments.get("input") or "").resolve()
    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    agent_id = str(arguments.get("agent_id") or DEFAULT_EXPECTED_AGENT_ID)
    mode = str(arguments.get("mode") or "merge")
    target_instance = arguments.get("target_instance")
    execute = bool(arguments.get("execute"))

    started_ms = monotonic_ms()
    run_id = make_run_id("tenant-import")
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

    package_path = input_dir / "tenant.package.json"
    try:
        package_payload = json.loads(package_path.read_text(encoding="utf-8"))
        memory_export = json.loads((input_dir / str(package_payload["memory_records_path"])).read_text(encoding="utf-8"))
        tenant_meta = json.loads((input_dir / str(package_payload["tenant_meta_path"])).read_text(encoding="utf-8"))
        checks.append(ResultRecord("package", "pass", "Tenant package loaded", {"package": str(package_path)}))
    except Exception as exc:  # noqa: BLE001
        package_payload = {}
        memory_export = {"records": []}
        tenant_meta = {}
        checks.append(ResultRecord("package", "fail", f"Failed to load tenant package: {exc}"))

    ensure_policy_profiles(policy_path)
    registry = load_tenant_registry(registry_path)
    try:
        existing_tenant = get_tenant(registry, context_id)
        checks.append(ResultRecord("target_tenant", "pass", "Target tenant already exists in registry"))
    except KeyError:
        existing_tenant = None
        checks.append(ResultRecord("target_tenant", "pass", "Target tenant will be created from package metadata"))

    import_result: dict[str, Any] | None = None
    clear_result: dict[str, Any] | None = None
    audit_path: str | None = None
    if execute and not any(item.status == "fail" for item in checks):
        try:
            with file_lock(lock_path):
                if existing_tenant is None:
                    tenant_record = create_tenant_record(
                        tenant_id=context_id,
                        display_name=tenant_meta.get("display_name") or context_id,
                        namespace=tenant_meta.get("namespace") or context_id,
                        policy_profile=tenant_meta.get("policy_profile", "default"),
                        config_path=tenant_meta.get("openclaw", {}).get("config_path", ""),
                        workspace_root=tenant_meta.get("openclaw", {}).get("workspace_root", ""),
                        openclaw_version=tenant_meta.get("openclaw", {}).get("version"),
                        instance_id=registry.get("instance_id", "main"),
                        source_instance_id=package_payload.get("source_instance_id"),
                        migration_state=tenant_meta.get("migration_state") or package_payload.get("migration_state"),
                        resources=tenant_meta.get("resources"),
                        retention=tenant_meta.get("retention"),
                    )
                    upsert_tenant(registry, tenant_record)
                elif mode == "replace":
                    current_export = export_tenant_memory_records(context_id, agent_id=agent_id, openviking_url=openviking_url)
                    clear_result = clear_tenant_memory_records(current_export.get("records", []), adapter_url=adapter_url)
                import_result = import_tenant_memory_records(
                    context_id,
                    memory_export.get("records", []),
                    agent_id=agent_id,
                    adapter_url=adapter_url,
                    openviking_url=openviking_url,
                    extra_tags=["tenant-import", package_payload.get("source_instance_id", "unknown")],
                )
                save_tenant_registry(registry_path, registry)
                audit_path = write_audit_event(
                    tenant_artifacts_dir / "audit",
                    {
                        "tenant_id": context_id,
                        "operation": "import",
                        "package": str(package_path),
                        "mode": mode,
                        "target_instance": target_instance,
                        "report_path": str(report_path),
                    },
                )
                checks.append(
                    ResultRecord(
                        "import_execute",
                        "pass",
                        "Tenant package import applied",
                        {
                            "imported_count": import_result.get("imported_count") if isinstance(import_result, dict) else 0,
                            "failed_count": import_result.get("failed_count") if isinstance(import_result, dict) else 0,
                        },
                    )
                )
        except FileExistsError:
            checks.append(ResultRecord("tenant_lock", "fail", "Another tenant import is already in progress", {"lock_path": str(lock_path)}))
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("import_execute", "fail", f"Tenant import failed: {exc}"))
    elif execute:
        checks.append(ResultRecord("import_execute", "blocked", "Tenant import blocked by precheck failure"))
    else:
        checks.append(ResultRecord("import_execute", "skip", "Dry-run only; no tenant import applied"))

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-tenant-import", run_id, started_ms),
        "report_kind": "tenant_import_report",
        "status": status,
        "mode": "execute" if execute else "dry-run",
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "target_instance": target_instance,
        "summary": {
            "status": status,
            "counts": counts,
            "tenant_id": context_id,
            "mode": "execute" if execute else "dry-run",
            "imported_count": import_result.get("imported_count", 0) if isinstance(import_result, dict) else 0,
            "failed_count": import_result.get("failed_count", 0) if isinstance(import_result, dict) else 0,
            "input_dir": str(input_dir),
        },
        "operations": [
            {
                "kind": "context_import",
                "mode": "execute" if execute else "dry-run",
                "input_dir": str(input_dir),
                "target_instance": target_instance,
                "replace_mode": mode == "replace",
            }
        ],
        "package": package_payload,
        "reserved_fields": {
            "source_instance_id": package_payload.get("source_instance_id"),
            "target_instance": package_payload.get("target_instance", package_payload.get("target_instance_id")),
            "host_mode": package_payload.get("host_mode"),
            "migration_state": package_payload.get("migration_state"),
        },
        "checks": render_records(checks),
        "results": {
            "clear_result": clear_result,
            "import_result": import_result,
        },
        "audit_path": audit_path,
        "report_path": str(report_path),
    }
    write_json_report(report_path, report)
    return _toolize_report(
        report,
        tool_name="context_import",
        context_id=context_id,
        artifacts={
            "artifacts_dir": str(tenant_artifacts_dir),
            "input_dir": str(input_dir),
        },
    )
