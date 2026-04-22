"""Unified runtime manager facade for the OpenViking commercialization shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_RUNTIME_MANAGER_REPORT,
    DEFAULT_TENANT_POLICY_PATH,
    DEFAULT_TENANT_REGISTRY_PATH,
    DEFAULT_TENANT_RUNTIME_ROOT,
    ResultRecord,
    companion_artifacts,
    docker_runtime_baseline_state,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)
from ov_enterprise_tool_registry import invoke_tool, list_tool_specs


def _registered_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[list[ResultRecord], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    payload = invoke_tool(tool_name, arguments)
    checks: list[ResultRecord] = [
        ResultRecord(
            f"{tool_name}_tool",
            "pass" if payload.get("status") in {"pass", "warn"} else "fail",
            f"{tool_name.replace('_', ' ').title()} completed with status {payload.get('status')}",
            {
                "exit_code": payload.get("exit_code"),
                "report_path": payload.get("report_path"),
            },
        )
    ]
    for item in payload.get("checks") or []:
        if not isinstance(item, dict):
            continue
        checks.append(
            ResultRecord(
                str(item.get("id") or f"{tool_name}_detail"),
                str(item.get("status") or "fail"),
                str(item.get("message") or ""),
                item.get("details") if isinstance(item.get("details"), dict) else None,
            )
        )
    operations: list[dict[str, Any]] = []
    for item in payload.get("operations") or []:
        if isinstance(item, dict):
            operations.append(item)
    if payload.get("context") is not None:
        operations.append({"tool": tool_name, "context": payload.get("context")})
    if payload.get("contexts") is not None:
        operations.append({"tool": tool_name, "contexts": payload.get("contexts")})
    delegated = {
        "tool": payload.get("tool"),
        "canonical_tool": payload.get("canonical_tool"),
        "status": payload.get("status"),
        "exit_code": payload.get("exit_code"),
        "report_path": payload.get("report_path"),
        "artifacts": payload.get("artifacts"),
        "summary": payload.get("summary"),
        "context_id": payload.get("context_id"),
    }
    passthrough = {
        "runtime_state": payload.get("runtime_state"),
        "support_surface": payload.get("support_surface"),
        "runtime_window": payload.get("runtime_window"),
    }
    return checks, delegated, operations, passthrough


def _tenant_tool_arguments(args: argparse.Namespace) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "context_id": getattr(args, "tenant", None),
        "tenant_id": getattr(args, "tenant", None),
        "instance_root": getattr(args, "instance_root", DEFAULT_TENANT_RUNTIME_ROOT),
        "registry_path": getattr(args, "registry_path", DEFAULT_TENANT_REGISTRY_PATH),
        "policy_path": getattr(args, "policy_path", DEFAULT_TENANT_POLICY_PATH),
        "adapter_url": getattr(args, "adapter_url", DEFAULT_ADAPTER_URL),
        "openviking_url": getattr(args, "openviking_url", DEFAULT_OPENVIKING_URL),
        "agent_id": getattr(args, "agent_id", "supervisor"),
        "display_name": getattr(args, "display_name", None),
        "namespace": getattr(args, "namespace", None),
        "policy_profile": getattr(args, "policy_profile", None),
        "config_path": getattr(args, "config_path", None),
        "workspace_root": getattr(args, "workspace_root", None),
        "request_timeout": getattr(args, "request_timeout", None),
        "search_window_seconds": getattr(args, "search_window_seconds", None),
        "poll_interval_seconds": getattr(args, "poll_interval_seconds", None),
        "snapshot_type": getattr(args, "snapshot_type", None),
        "tag": getattr(args, "tag", None),
        "snapshot": getattr(args, "snapshot", None),
        "mode": getattr(args, "mode", None),
        "to": getattr(args, "to", None),
        "output": getattr(args, "output", None),
        "input": getattr(args, "input", None),
        "target_instance": getattr(args, "target_instance", None),
        "execute": bool(getattr(args, "execute", False)),
    }
    return {key: value for key, value in arguments.items() if value is not None}


def _host_tool_arguments(args: argparse.Namespace) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "adapter_url": getattr(args, "adapter_url", DEFAULT_ADAPTER_URL),
        "openviking_url": getattr(args, "openviking_url", DEFAULT_OPENVIKING_URL),
        "backup_dir": getattr(args, "backup_dir", None),
        "archive_root": getattr(args, "archive_root", None),
        "label": getattr(args, "label", None),
        "execute": bool(getattr(args, "execute", False)),
        "startup_wait_seconds": getattr(args, "startup_wait_seconds", None),
        "poll_interval_seconds": getattr(args, "poll_interval_seconds", None),
        "request_timeout": getattr(args, "request_timeout", None),
        "search_window_seconds": getattr(args, "search_window_seconds", None),
        "minimum_support_level": getattr(args, "minimum_support_level", None),
        "from_version": getattr(args, "from_version", None),
        "to_version": getattr(args, "to_version", None),
        "execute_window_report": getattr(args, "execute_window_report", None),
        "window_packet_report": getattr(args, "window_packet_report", None),
    }
    return {key: value for key, value in arguments.items() if value is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization runtime manager")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_RUNTIME_MANAGER_REPORT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--openviking-url", default=DEFAULT_OPENVIKING_URL)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Inspect runtime state")
    status_parser.add_argument("--startup-wait-seconds", type=float, default=10.0)
    status_parser.add_argument("--poll-interval-seconds", type=float, default=2.0)

    for name in ("start", "stop", "restart"):
        action_parser = subparsers.add_parser(name, help=f"{name.capitalize()} baseline runtime containers")
        action_parser.add_argument("--execute", action="store_true", help=f"Actually {name} containers")
        action_parser.add_argument("--startup-wait-seconds", type=float, default=30.0)
        action_parser.add_argument("--poll-interval-seconds", type=float, default=3.0)

    subparsers.add_parser("install-check", help="Delegate to install-check tool")

    install_parser = subparsers.add_parser("install", help="Delegate to install tool")
    install_parser.add_argument("--backup-dir", type=Path)
    install_parser.add_argument("--execute", action="store_true")

    doctor_parser = subparsers.add_parser("doctor", help="Delegate to doctor tool")
    doctor_parser.add_argument("--minimum-support-level", default="B")

    verify_parser = subparsers.add_parser("verify", help="Delegate to verify tool")
    verify_parser.add_argument("--request-timeout", type=float, default=45.0)
    verify_parser.add_argument("--search-window-seconds", type=float, default=45.0)

    backup_parser = subparsers.add_parser("backup", help="Delegate to backup tool")
    backup_parser.add_argument("--execute", action="store_true")

    upgrade_parser = subparsers.add_parser("upgrade", help="Delegate to upgrade tool")
    upgrade_parser.add_argument("--backup-dir", type=Path)
    upgrade_parser.add_argument("--execute", action="store_true")
    upgrade_parser.add_argument("--from-version")
    upgrade_parser.add_argument("--to-version")

    restore_parser = subparsers.add_parser("restore", help="Delegate to restore tool")
    restore_parser.add_argument("--backup-dir", type=Path)
    restore_parser.add_argument("--execute", action="store_true")
    restore_parser.add_argument("--startup-wait-seconds", type=float, default=30.0)
    restore_parser.add_argument("--poll-interval-seconds", type=float, default=3.0)

    rollback_parser = subparsers.add_parser("rollback", help="Delegate to rollback tool")
    rollback_parser.add_argument("--backup-dir", type=Path)
    rollback_parser.add_argument("--execute", action="store_true")
    rollback_parser.add_argument("--startup-wait-seconds", type=float, default=30.0)
    rollback_parser.add_argument("--poll-interval-seconds", type=float, default=3.0)

    uninstall_parser = subparsers.add_parser("uninstall", help="Delegate to uninstall tool")
    uninstall_parser.add_argument("--backup-dir", type=Path)
    uninstall_parser.add_argument("--execute", action="store_true")

    rehearsal_parser = subparsers.add_parser("rehearsal", help="Delegate to rehearsal tool")
    rehearsal_parser.add_argument("--backup-dir", type=Path)

    execute_window_parser = subparsers.add_parser("execute-window", help="Delegate to execute-window tool")
    execute_window_parser.add_argument("--backup-dir", type=Path)

    window_packet_parser = subparsers.add_parser("window-packet", help="Delegate to window-packet tool")
    window_packet_parser.add_argument("--execute-window-report", type=Path)

    window_packet_verify_parser = subparsers.add_parser("window-packet-verify", help="Delegate to window-packet-verify tool")
    window_packet_verify_parser.add_argument("--window-packet-report", type=Path)

    subparsers.add_parser("execute-smoke", help="Delegate to execute-smoke tool")

    subparsers.add_parser("phase2-reserved-fields", help="Write the current Phase 2 reserved field contract")

    evidence_archive_parser = subparsers.add_parser("evidence-archive", help="Archive the current delivery evidence bundle")
    evidence_archive_parser.add_argument("--archive-root", type=Path)
    evidence_archive_parser.add_argument("--label")
    evidence_archive_parser.add_argument("--execute", action="store_true")

    tool_parser = subparsers.add_parser("tool", help="Tool registry wrapper")
    tool_subparsers = tool_parser.add_subparsers(dest="tool_command", required=True)
    tool_subparsers.add_parser("list", help="List public tools")
    tool_call_parser = tool_subparsers.add_parser("call", help="Call one tool with JSON arguments")
    tool_call_parser.add_argument("--name", required=True)
    tool_call_parser.add_argument("--arguments-json", default="{}")

    tenant_parser = subparsers.add_parser("tenant", help="Tenant-aware runtime operations")
    tenant_parser.add_argument("--instance-root", type=Path, default=DEFAULT_TENANT_RUNTIME_ROOT)
    tenant_parser.add_argument("--registry-path", type=Path, default=DEFAULT_TENANT_REGISTRY_PATH)
    tenant_parser.add_argument("--policy-path", type=Path, default=DEFAULT_TENANT_POLICY_PATH)
    tenant_parser.add_argument("--agent-id", default="supervisor")
    tenant_subparsers = tenant_parser.add_subparsers(dest="tenant_command", required=True)

    tenant_subparsers.add_parser("list", help="List tenant registry entries")

    tenant_show_parser = tenant_subparsers.add_parser("show", help="Show a tenant registry entry")
    tenant_show_parser.add_argument("--tenant", required=True)

    tenant_create_parser = tenant_subparsers.add_parser("create", help="Create a tenant registry entry")
    tenant_create_parser.add_argument("--tenant", required=True)
    tenant_create_parser.add_argument("--display-name")
    tenant_create_parser.add_argument("--namespace")
    tenant_create_parser.add_argument("--policy-profile", default="default")
    tenant_create_parser.add_argument("--config-path")
    tenant_create_parser.add_argument("--workspace-root")

    tenant_update_parser = tenant_subparsers.add_parser("update", help="Update tenant metadata")
    tenant_update_parser.add_argument("--tenant", required=True)
    tenant_update_parser.add_argument("--policy-profile", required=True)

    tenant_suspend_parser = tenant_subparsers.add_parser("suspend", help="Suspend a tenant")
    tenant_suspend_parser.add_argument("--tenant", required=True)

    tenant_resume_parser = tenant_subparsers.add_parser("resume", help="Resume a tenant")
    tenant_resume_parser.add_argument("--tenant", required=True)

    tenant_status_parser = tenant_subparsers.add_parser("status", help="Show tenant status")
    tenant_status_parser.add_argument("--tenant", required=True)

    tenant_doctor_parser = tenant_subparsers.add_parser("doctor", help="Run tenant doctor")
    tenant_doctor_parser.add_argument("--tenant", required=True)

    tenant_verify_parser = tenant_subparsers.add_parser("verify", help="Run tenant verify")
    tenant_verify_parser.add_argument("--tenant", required=True)
    tenant_verify_parser.add_argument("--request-timeout", type=float, default=45.0)
    tenant_verify_parser.add_argument("--search-window-seconds", type=float, default=45.0)

    tenant_backup_parser = tenant_subparsers.add_parser("backup", help="Create a tenant snapshot")
    tenant_backup_parser.add_argument("--tenant", required=True)
    tenant_backup_parser.add_argument("--snapshot-type", default="manual")
    tenant_backup_parser.add_argument("--tag")
    tenant_backup_parser.add_argument("--execute", action="store_true")

    tenant_restore_parser = tenant_subparsers.add_parser("restore", help="Restore a tenant snapshot")
    tenant_restore_parser.add_argument("--tenant", required=True)
    tenant_restore_parser.add_argument("--snapshot", type=Path, required=True)
    tenant_restore_parser.add_argument("--mode", choices=["merge", "replace"], default="replace")
    tenant_restore_parser.add_argument("--request-timeout", type=float, default=45.0)
    tenant_restore_parser.add_argument("--search-window-seconds", type=float, default=20.0)
    tenant_restore_parser.add_argument("--poll-interval-seconds", type=float, default=3.0)
    tenant_restore_parser.add_argument("--execute", action="store_true")

    tenant_rollback_parser = tenant_subparsers.add_parser("rollback", help="Rollback a tenant to a snapshot")
    tenant_rollback_parser.add_argument("--tenant", required=True)
    tenant_rollback_parser.add_argument("--to", default="last-known-good")
    tenant_rollback_parser.add_argument("--request-timeout", type=float, default=45.0)
    tenant_rollback_parser.add_argument("--search-window-seconds", type=float, default=20.0)
    tenant_rollback_parser.add_argument("--poll-interval-seconds", type=float, default=3.0)
    tenant_rollback_parser.add_argument("--execute", action="store_true")

    tenant_export_parser = tenant_subparsers.add_parser("export", help="Export a tenant package")
    tenant_export_parser.add_argument("--tenant", required=True)
    tenant_export_parser.add_argument("--output", type=Path)
    tenant_export_parser.add_argument("--target-instance")
    tenant_export_parser.add_argument("--execute", action="store_true")

    tenant_import_parser = tenant_subparsers.add_parser("import", help="Import a tenant package")
    tenant_import_parser.add_argument("--tenant", required=True)
    tenant_import_parser.add_argument("--input", type=Path, required=True)
    tenant_import_parser.add_argument("--mode", choices=["merge", "replace"], default="merge")
    tenant_import_parser.add_argument("--target-instance")
    tenant_import_parser.add_argument("--execute", action="store_true")

    args = parser.parse_args()
    started_ms = monotonic_ms()
    run_id = make_run_id("runtime-manager")
    checks: list[ResultRecord] = []
    operations: list[dict[str, Any]] = []
    delegated: dict[str, Any] | None = None
    runtime_window: dict[str, Any] | None = None
    runtime_state: dict[str, Any] | None = None
    support_surface: dict[str, Any] | None = None

    report_path_ok = path_writable(args.report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    if args.command in {"status", "start", "stop", "restart"}:
        runtime_tool_name = {
            "status": "runtime_status",
            "start": "runtime_start",
            "stop": "runtime_stop",
            "restart": "runtime_restart",
        }[args.command]
        delegate_checks, delegated, tool_operations, passthrough = _registered_tool(runtime_tool_name, _host_tool_arguments(args))
        checks.extend(delegate_checks)
        operations.extend(tool_operations)
        runtime_state = passthrough.get("runtime_state")
        support_surface = passthrough.get("support_surface")
        runtime_window = passthrough.get("runtime_window")
    elif args.command in {
        "install-check",
        "install",
        "doctor",
        "verify",
        "backup",
        "upgrade",
        "restore",
        "rollback",
        "uninstall",
        "rehearsal",
        "execute-window",
        "window-packet",
        "window-packet-verify",
        "execute-smoke",
        "phase2-reserved-fields",
        "evidence-archive",
    }:
        host_tool_name = {
            "install-check": "install_check",
            "install": "install",
            "doctor": "doctor",
            "verify": "verify",
            "backup": "backup",
            "upgrade": "upgrade",
            "restore": "restore",
            "rollback": "rollback",
            "uninstall": "uninstall",
            "rehearsal": "rehearsal",
            "execute-window": "execute_window",
            "window-packet": "window_packet",
            "window-packet-verify": "window_packet_verify",
            "execute-smoke": "execute_smoke",
            "phase2-reserved-fields": "phase2_reserved_fields",
            "evidence-archive": "evidence_archive",
        }[args.command]
        delegate_checks, delegated, tool_operations, passthrough = _registered_tool(host_tool_name, _host_tool_arguments(args))
        checks.extend(delegate_checks)
        operations.extend(tool_operations)
        runtime_state = passthrough.get("runtime_state")
        support_surface = passthrough.get("support_surface")
        runtime_window = passthrough.get("runtime_window") or runtime_window
    elif args.command == "tool":
        if args.tool_command == "list":
            public_tools = list_tool_specs(public_only=True)
            checks.append(ResultRecord("tool_registry", "pass", f"Loaded {len(public_tools)} public tools"))
            operations.append({"tool_command": "list", "tools": public_tools})
        elif args.tool_command == "call":
            try:
                tool_arguments = json.loads(args.arguments_json)
            except json.JSONDecodeError as exc:
                checks.append(ResultRecord("tool_call", "fail", f"Invalid --arguments-json payload: {exc}"))
            else:
                delegate_checks, delegated, tool_operations, passthrough = _registered_tool(args.name, tool_arguments)
                checks.extend(delegate_checks)
                operations.extend(tool_operations)
                runtime_state = passthrough.get("runtime_state")
                support_surface = passthrough.get("support_surface")
                runtime_window = passthrough.get("runtime_window") or runtime_window
    elif args.command == "tenant":
        tenant_tool_name = {
            "list": "context_list",
            "show": "context_show",
            "create": "context_create",
            "update": "context_update",
            "suspend": "context_suspend",
            "resume": "context_resume",
            "status": "context_status",
            "doctor": "context_doctor",
            "verify": "context_verify",
            "backup": "context_backup",
            "restore": "context_restore",
            "rollback": "context_rollback",
            "export": "context_export",
            "import": "context_import",
        }[args.tenant_command]
        delegate_checks, delegated, tool_operations, passthrough = _registered_tool(tenant_tool_name, _tenant_tool_arguments(args))
        checks.extend(delegate_checks)
        operations.extend(tool_operations)
        runtime_state = passthrough.get("runtime_state")
        support_surface = passthrough.get("support_surface")
        runtime_window = passthrough.get("runtime_window") or runtime_window

    if runtime_state is None:
        runtime_state = docker_runtime_baseline_state()
    if support_surface is None:
        support_surface = {
            "adapter": None,
            "openviking": None,
        }

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-runtime-manager", run_id, started_ms),
        "report_kind": "runtime_manager",
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "command": args.command,
            "tenant_command": getattr(args, "tenant_command", None),
            "runtime_state": runtime_state["state"],
            "delegated_tool": delegated.get("tool") if delegated else None,
        },
        "inputs": {
            "command": args.command,
            "tenant_command": getattr(args, "tenant_command", None),
            "tenant": getattr(args, "tenant", None),
            "report_path": str(args.report_path),
            "adapter_url": args.adapter_url,
            "openviking_url": args.openviking_url,
            "backup_root": str(args.backup_root),
        },
        "checks": render_records(checks),
        "runtime_state": runtime_state,
        "support_surface": support_surface,
        "operations": operations,
        "runtime_window": runtime_window,
        "delegated": delegated,
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
