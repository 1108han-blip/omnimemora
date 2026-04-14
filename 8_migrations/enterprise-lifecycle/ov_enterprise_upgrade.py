"""Guarded upgrade tool for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_EXPECTED_PLUGIN_BASE_URL,
    DEFAULT_MIN_PLUGIN_TIMEOUT_MS,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_PLUGIN_DIR,
    DEFAULT_UPGRADE_REPORT,
    ResultRecord,
    append_execution_event,
    adapter_support_surface,
    classify_execute_reason,
    companion_artifacts,
    json_load,
    load_backup_manifest,
    make_run_id,
    merge_plugin_baseline_config,
    monotonic_ms,
    path_writable,
    plugin_entry_from_baseline,
    render_records,
    report_metadata,
    resolve_openclaw_version,
    result_counts,
    support_trace_checkpoint,
    sync_path,
    write_json_file,
    write_json_report,
)


def _current_plugin_entry(config: dict[str, Any]) -> dict[str, Any]:
    return (
        config.get("plugins", {})
        .get("entries", {})
        .get("memory-openviking", {})
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization upgrade")
    parser.add_argument("--openclaw-config", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--plugin-source-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--backup-dir", type=Path, help="Required for --execute")
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--base-url", default=DEFAULT_EXPECTED_PLUGIN_BASE_URL)
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_MIN_PLUGIN_TIMEOUT_MS)
    parser.add_argument("--agent-id", default=DEFAULT_EXPECTED_AGENT_ID)
    parser.add_argument("--from-version")
    parser.add_argument("--to-version")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_UPGRADE_REPORT)
    parser.add_argument("--execute", action="store_true", help="Apply the upgrade plan")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("upgrade")
    checks: list[ResultRecord] = []
    operations: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    config: dict[str, Any] = {}
    backup_manifest: dict[str, Any] | None = None
    support_trace: list[dict[str, Any]] = []
    execution_trace: list[dict[str, Any]] = []

    if args.openclaw_config.exists():
        try:
            config = json_load(args.openclaw_config)
            append_execution_event(
                execution_trace,
                "load_openclaw_config",
                "pass",
                {"path": str(args.openclaw_config)},
            )
            checks.append(ResultRecord("openclaw_config", "pass", "OpenClaw config loaded", {"path": str(args.openclaw_config)}))
        except Exception as exc:  # noqa: BLE001
            append_execution_event(
                execution_trace,
                "load_openclaw_config",
                "fail",
                {"path": str(args.openclaw_config), "error": str(exc)},
            )
            checks.append(ResultRecord("openclaw_config", "fail", f"Failed to parse OpenClaw config: {exc}"))
    else:
        append_execution_event(
            execution_trace,
            "load_openclaw_config",
            "fail",
            {"path": str(args.openclaw_config), "error": "missing"},
        )
        checks.append(ResultRecord("openclaw_config", "fail", "OpenClaw config file not found"))

    checks.append(
        ResultRecord(
            "plugin_target",
            "pass" if args.plugin_dir.exists() else "fail",
            "Plugin target directory exists" if args.plugin_dir.exists() else "Plugin target directory is missing",
            {"path": str(args.plugin_dir)},
        )
    )
    checks.append(
        ResultRecord(
            "plugin_source",
            "pass" if args.plugin_source_dir.exists() else "fail",
            "Plugin source directory exists" if args.plugin_source_dir.exists() else "Plugin source directory is missing",
            {"path": str(args.plugin_source_dir)},
        )
    )

    report_path_ok = path_writable(args.report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    openclaw_version = resolve_openclaw_version(config) if config else None
    checks.append(
        ResultRecord(
            "openclaw_version",
            "pass" if openclaw_version else "warn",
            f"OpenClaw version {openclaw_version} detected" if openclaw_version else "OpenClaw version could not be resolved",
        )
    )

    desired_entry = plugin_entry_from_baseline(
        base_url=args.base_url,
        timeout_ms=args.timeout_ms,
        auto_recall=True,
        auto_capture=True,
        agent_id=args.agent_id,
    )
    current_entry = _current_plugin_entry(config) if config else {}
    changes = merge_plugin_baseline_config(config, desired_entry) if config else []
    config_needs_update = bool(changes)
    operations.append(
        {
            "id": "update_plugin_entry",
            "status": "planned" if config_needs_update else "noop",
            "path": str(args.openclaw_config),
            "before": current_entry,
            "after": desired_entry,
            "changes": changes,
        }
    )
    append_execution_event(
        execution_trace,
        "plan_plugin_entry_update",
        "planned" if config_needs_update else "noop",
        {
            "path": str(args.openclaw_config),
            "change_count": len(changes),
        },
    )

    try:
        plugin_sync_needed = args.plugin_source_dir.resolve() != args.plugin_dir.resolve()
    except OSError:
        plugin_sync_needed = True
    operations.append(
        {
            "id": "sync_plugin_dir",
            "status": "planned" if plugin_sync_needed else "noop",
            "source": str(args.plugin_source_dir),
            "target": str(args.plugin_dir),
        }
    )
    append_execution_event(
        execution_trace,
        "plan_plugin_sync",
        "planned" if plugin_sync_needed else "noop",
        {
            "source": str(args.plugin_source_dir),
            "target": str(args.plugin_dir),
        },
    )

    if args.execute:
        if not args.backup_dir:
            checks.append(ResultRecord("backup_manifest", "fail", "--backup-dir is required when using --execute"))
        else:
            try:
                backup_manifest = load_backup_manifest(args.backup_dir)
                checks.append(
                    ResultRecord(
                        "backup_manifest",
                        "pass",
                        "Backup manifest loaded",
                        {"backup_dir": str(args.backup_dir), "snapshot_dir": backup_manifest.get("snapshot_dir")},
                    )
                )
                append_execution_event(
                    execution_trace,
                    "load_backup_manifest",
                    "pass",
                    {"backup_dir": str(args.backup_dir)},
                )
            except Exception as exc:  # noqa: BLE001
                append_execution_event(
                    execution_trace,
                    "load_backup_manifest",
                    "fail",
                    {"backup_dir": str(args.backup_dir), "error": str(exc)},
                )
                checks.append(ResultRecord("backup_manifest", "fail", f"Failed to load backup manifest: {exc}"))
    else:
        append_execution_event(
            execution_trace,
            "load_backup_manifest",
            "skip",
            {"reason": "dry-run"},
        )
        checks.append(ResultRecord("backup_manifest", "pass", "Dry-run mode does not require a backup manifest"))

    support_surface = adapter_support_surface(args.adapter_url)
    support_trace.append(support_trace_checkpoint("precheck", support_surface))
    support_ok = support_surface["health"]["ok"] and support_surface["error_catalog"]["ok"]
    checks.append(
        ResultRecord(
            "adapter_support_surface",
            "pass" if support_ok else "warn",
            "Adapter support surface is reachable"
            if support_ok
            else "Adapter support surface is missing or incomplete",
            support_surface,
        )
    )

    status = "fail" if any(record.status == "fail" for record in checks) else "warn" if any(record.status == "warn" for record in checks) else "pass"

    if args.execute and status != "fail":
        support_trace.append(support_trace_checkpoint("pre_execute", adapter_support_surface(args.adapter_url)))
        try:
            if plugin_sync_needed:
                append_execution_event(
                    execution_trace,
                    "sync_plugin_dir",
                    "started",
                    {"source": str(args.plugin_source_dir), "target": str(args.plugin_dir)},
                )
                sync_path(args.plugin_source_dir, args.plugin_dir)
                applied.append({"id": "sync_plugin_dir", "result": "applied"})
                append_execution_event(
                    execution_trace,
                    "sync_plugin_dir",
                    "pass",
                    {"source": str(args.plugin_source_dir), "target": str(args.plugin_dir)},
                )
            else:
                append_execution_event(
                    execution_trace,
                    "sync_plugin_dir",
                    "noop",
                    {"source": str(args.plugin_source_dir), "target": str(args.plugin_dir)},
                )
            if config_needs_update:
                append_execution_event(
                    execution_trace,
                    "write_openclaw_config",
                    "started",
                    {"path": str(args.openclaw_config), "change_count": len(changes)},
                )
                write_json_file(args.openclaw_config, config)
                applied.append({"id": "update_plugin_entry", "result": "applied"})
                append_execution_event(
                    execution_trace,
                    "write_openclaw_config",
                    "pass",
                    {"path": str(args.openclaw_config), "change_count": len(changes)},
                )
            else:
                append_execution_event(
                    execution_trace,
                    "write_openclaw_config",
                    "noop",
                    {"path": str(args.openclaw_config)},
                )
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("execute_upgrade", "fail", f"Upgrade execution failed: {exc}"))
            append_execution_event(
                execution_trace,
                "execute_upgrade",
                "fail",
                {"error": str(exc)},
            )
        finally:
            post_phase = "post_execute" if not any(record.id == "execute_upgrade" and record.status == "fail" for record in checks) else "post_execute_failure"
            support_trace.append(support_trace_checkpoint(post_phase, adapter_support_surface(args.adapter_url)))
    elif args.execute:
        append_execution_event(
            execution_trace,
            "execute_upgrade",
            "blocked",
            {"reason": "precheck_failed"},
        )
    else:
        append_execution_event(
            execution_trace,
            "execute_upgrade",
            "skip",
            {"reason": "dry-run"},
        )

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    execute_reason = classify_execute_reason(
        mode="execute" if args.execute else "dry-run",
        status=status,
        health_window_seconds=0.0,
        runtime_windows=[],
    )
    if args.execute and any(record.id == "adapter_support_surface" and record.status == "warn" for record in checks):
        execute_reason = {
            "reason_code": "OFFLINE_SUPPORT_SURFACE_DEGRADED",
            "expected_during_offline": True,
            "retry_applied": False,
            "health_window_seconds": 0.0,
        }

    report = {
        **report_metadata("ov-enterprise-upgrade", run_id, started_ms),
        "status": status,
        "mode": "execute" if args.execute else "dry-run",
        **execute_reason,
        "summary": {
            "status": status,
            "counts": counts,
            "config_needs_update": config_needs_update,
            "plugin_sync_needed": plugin_sync_needed,
            **execute_reason,
        },
        "checks": render_records(checks),
        "operations": operations,
        "applied": applied,
        "inputs": {
            "openclaw_config": str(args.openclaw_config),
            "plugin_dir": str(args.plugin_dir),
            "plugin_source_dir": str(args.plugin_source_dir),
            "backup_dir": str(args.backup_dir) if args.backup_dir else None,
            "adapter_url": args.adapter_url,
            "base_url": args.base_url,
            "timeout_ms": args.timeout_ms,
            "agent_id": args.agent_id,
            "from_version": args.from_version,
            "to_version": args.to_version,
        },
        "support_surface": support_surface,
        "support_trace": support_trace,
        "execution_trace": execution_trace,
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
