"""Guarded uninstall tool for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    BASELINE_CONTAINERS,
    DEFAULT_ADAPTER_URL,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_MEMORY_ADAPTER_DIR,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_PLUGIN_DIR,
    DEFAULT_UNINSTALL_REPORT,
    ResultRecord,
    adapter_support_surface,
    append_execution_event,
    classify_execute_reason,
    companion_artifacts,
    copy_path,
    docker_names,
    json_load,
    load_backup_manifest,
    make_run_id,
    monotonic_ms,
    move_path,
    path_writable,
    render_records,
    report_metadata,
    resolve_plugin_config,
    result_counts,
    support_trace_checkpoint,
    write_json_file,
    write_json_report,
)


def _remove_plugin_baseline(config: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    plugins = config.setdefault("plugins", {})

    allow = plugins.get("allow")
    if isinstance(allow, list) and "memory-openviking" in allow:
        before = list(allow)
        allow[:] = [item for item in allow if item != "memory-openviking"]
        changes.append({"path": "plugins.allow", "before": before, "after": list(allow)})

    slots = plugins.setdefault("slots", {})
    if slots.get("memory") == "memory-openviking":
        changes.append({"path": "plugins.slots.memory", "before": "memory-openviking", "after": None})
        slots.pop("memory", None)

    entries = plugins.setdefault("entries", {})
    if "memory-openviking" in entries:
        before = entries.get("memory-openviking")
        entries.pop("memory-openviking", None)
        changes.append({"path": "plugins.entries.memory-openviking", "before": before, "after": None})

    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization uninstall")
    parser.add_argument("--openclaw-config", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--memory-adapter-dir", type=Path, default=DEFAULT_MEMORY_ADAPTER_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--backup-dir", type=Path, help="Required for --execute")
    parser.add_argument("--safety-backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_UNINSTALL_REPORT)
    parser.add_argument("--execute", action="store_true", help="Apply the uninstall plan")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("uninstall")
    checks: list[ResultRecord] = []
    operations: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    support_trace: list[dict[str, Any]] = []
    execution_trace: list[dict[str, Any]] = []
    safety_snapshot_dir: Path | None = None
    archive_dir: Path | None = None
    config: dict[str, Any] = {}

    report_path_ok = path_writable(args.report_path)
    append_execution_event(
        execution_trace,
        "validate_report_path",
        "pass" if report_path_ok else "fail",
        {"path": str(args.report_path)},
    )
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    archive_path_ok = path_writable(args.archive_root / ".ov_uninstall_archive_probe")
    append_execution_event(
        execution_trace,
        "validate_archive_root",
        "pass" if archive_path_ok else "fail",
        {"path": str(args.archive_root)},
    )
    checks.append(
        ResultRecord(
            "archive_root",
            "pass" if archive_path_ok else "fail",
            "Archive root is writable" if archive_path_ok else "Archive root is not writable",
            {"path": str(args.archive_root)},
        )
    )

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
        checks.append(ResultRecord("openclaw_config", "fail", "OpenClaw config file not found", {"path": str(args.openclaw_config)}))

    plugin_exists = args.plugin_dir.exists()
    memory_adapter_exists = args.memory_adapter_dir.exists()
    checks.append(
        ResultRecord(
            "plugin_dir",
            "pass" if plugin_exists else "warn",
            "Plugin directory exists" if plugin_exists else "Plugin directory is already absent",
            {"path": str(args.plugin_dir)},
        )
    )
    checks.append(
        ResultRecord(
            "memory_adapter_dir",
            "pass" if memory_adapter_exists else "warn",
            "Memory Adapter directory exists" if memory_adapter_exists else "Memory Adapter directory is already absent",
            {"path": str(args.memory_adapter_dir)},
        )
    )

    running_containers = docker_names()
    affected_containers = sorted(name for name in BASELINE_CONTAINERS if name in running_containers)
    runtime_quiesced = not affected_containers
    checks.append(
        ResultRecord(
            "runtime_guard",
            "pass",
            "Uninstall execute requires runtime quiescence; current active containers have been enumerated",
            {
                "runtime_quiesced": runtime_quiesced,
                "affected_containers": affected_containers,
            },
        )
    )
    append_execution_event(
        execution_trace,
        "inspect_runtime_guard",
        "pass",
        {
            "runtime_quiesced": runtime_quiesced,
            "affected_containers": affected_containers,
        },
    )

    current_plugin_config = resolve_plugin_config(config) if config else {}
    config_changes = _remove_plugin_baseline(config) if config else []
    config_needs_update = bool(config_changes)
    operations.append(
        {
            "id": "patch_openclaw_config",
            "status": "planned" if config_needs_update else "noop",
            "path": str(args.openclaw_config),
            "before": current_plugin_config,
            "changes": config_changes,
        }
    )
    append_execution_event(
        execution_trace,
        "plan_config_uninstall",
        "planned" if config_needs_update else "noop",
        {"path": str(args.openclaw_config), "change_count": len(config_changes)},
    )

    operations.append(
        {
            "id": "archive_plugin_dir",
            "status": "planned" if plugin_exists else "noop",
            "source": str(args.plugin_dir),
        }
    )
    operations.append(
        {
            "id": "archive_memory_adapter_dir",
            "status": "planned" if memory_adapter_exists else "noop",
            "source": str(args.memory_adapter_dir),
        }
    )

    if args.execute:
        if not args.backup_dir:
            checks.append(ResultRecord("backup_manifest", "fail", "--backup-dir is required when using --execute"))
            append_execution_event(
                execution_trace,
                "load_backup_manifest",
                "fail",
                {"error": "missing_backup_dir"},
            )
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
                checks.append(ResultRecord("backup_manifest", "fail", f"Failed to load backup manifest: {exc}"))
                append_execution_event(
                    execution_trace,
                    "load_backup_manifest",
                    "fail",
                    {"backup_dir": str(args.backup_dir), "error": str(exc)},
                )
        if not runtime_quiesced:
            checks.append(
                ResultRecord(
                    "runtime_quiesced",
                    "fail",
                    "Runtime must be stopped before uninstall execute",
                    {"affected_containers": affected_containers},
                )
            )
    else:
        checks.append(ResultRecord("backup_manifest", "pass", "Dry-run mode does not require a backup manifest"))
        append_execution_event(
            execution_trace,
            "load_backup_manifest",
            "skip",
            {"reason": "dry-run"},
        )

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
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safety_snapshot_dir = args.safety_backup_root / f"pre-uninstall-{stamp}"
            safety_snapshot_dir.mkdir(parents=True, exist_ok=False)
            append_execution_event(
                execution_trace,
                "create_safety_snapshot_dir",
                "pass",
                {"path": str(safety_snapshot_dir)},
            )

            safety_items: list[dict[str, object]] = []
            safety_sources = [
                ("openclaw_config", args.openclaw_config),
                ("plugin_dir", args.plugin_dir),
                ("memory_adapter_dir", args.memory_adapter_dir),
            ]
            for item_id, source in safety_sources:
                target = safety_snapshot_dir / item_id
                record = {
                    "id": item_id,
                    "source": str(source),
                    "target": str(target),
                    "exists": source.exists(),
                    "copied": False,
                }
                if source.exists():
                    copy_path(source, target)
                    record["copied"] = True
                    append_execution_event(
                        execution_trace,
                        "snapshot_target_before_uninstall",
                        "pass",
                        {"id": item_id, "source": str(source), "target": str(target)},
                    )
                else:
                    append_execution_event(
                        execution_trace,
                        "snapshot_target_before_uninstall",
                        "skip",
                        {"id": item_id, "source": str(source), "reason": "source_missing"},
                    )
                safety_items.append(record)

            write_json_report(
                safety_snapshot_dir / "manifest.json",
                {
                    **report_metadata("ov-enterprise-pre-uninstall-backup", run_id, started_ms),
                    "status": "pass",
                    "mode": "execute",
                    "snapshot_dir": str(safety_snapshot_dir),
                    "items": safety_items,
                },
            )
            append_execution_event(
                execution_trace,
                "write_safety_snapshot_manifest",
                "pass",
                {"path": str(safety_snapshot_dir / 'manifest.json')},
            )

            archive_dir = args.archive_root / f"openviking-uninstall-{stamp}"
            archive_dir.mkdir(parents=True, exist_ok=False)
            append_execution_event(
                execution_trace,
                "create_archive_dir",
                "pass",
                {"path": str(archive_dir)},
            )

            if config_needs_update:
                write_json_file(args.openclaw_config, config)
                applied.append({"id": "patch_openclaw_config", "result": "applied"})
                append_execution_event(
                    execution_trace,
                    "write_openclaw_config",
                    "pass",
                    {"path": str(args.openclaw_config), "change_count": len(config_changes)},
                )
            else:
                append_execution_event(
                    execution_trace,
                    "write_openclaw_config",
                    "noop",
                    {"path": str(args.openclaw_config)},
                )

            if plugin_exists:
                plugin_archive_target = archive_dir / "plugin_dir"
                move_path(args.plugin_dir, plugin_archive_target)
                applied.append({"id": "archive_plugin_dir", "result": "archived", "target": str(plugin_archive_target)})
                append_execution_event(
                    execution_trace,
                    "archive_plugin_dir",
                    "pass",
                    {"source": str(args.plugin_dir), "target": str(plugin_archive_target)},
                )
            else:
                append_execution_event(
                    execution_trace,
                    "archive_plugin_dir",
                    "noop",
                    {"source": str(args.plugin_dir)},
                )

            if memory_adapter_exists:
                adapter_archive_target = archive_dir / "memory_adapter_dir"
                move_path(args.memory_adapter_dir, adapter_archive_target)
                applied.append({"id": "archive_memory_adapter_dir", "result": "archived", "target": str(adapter_archive_target)})
                append_execution_event(
                    execution_trace,
                    "archive_memory_adapter_dir",
                    "pass",
                    {"source": str(args.memory_adapter_dir), "target": str(adapter_archive_target)},
                )
            else:
                append_execution_event(
                    execution_trace,
                    "archive_memory_adapter_dir",
                    "noop",
                    {"source": str(args.memory_adapter_dir)},
                )
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("execute_uninstall", "fail", f"Uninstall execution failed: {exc}"))
            append_execution_event(
                execution_trace,
                "execute_uninstall",
                "fail",
                {"error": str(exc)},
            )
        finally:
            post_phase = "post_execute" if not any(record.id == "execute_uninstall" and record.status == "fail" for record in checks) else "post_execute_failure"
            support_trace.append(support_trace_checkpoint(post_phase, adapter_support_surface(args.adapter_url)))
    elif args.execute:
        append_execution_event(
            execution_trace,
            "execute_uninstall",
            "blocked",
            {"reason": "precheck_failed"},
        )
    else:
        append_execution_event(
            execution_trace,
            "execute_uninstall",
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
    if args.execute and any(record.id == "runtime_quiesced" and record.status == "fail" for record in checks):
        execute_reason = {
            "reason_code": "RUNTIME_GUARD_BLOCKED",
            "expected_during_offline": False,
            "retry_applied": False,
            "health_window_seconds": 0.0,
        }
    elif args.execute and any(record.id == "adapter_support_surface" and record.status == "warn" for record in checks):
        execute_reason = {
            "reason_code": "OFFLINE_SUPPORT_SURFACE_DEGRADED",
            "expected_during_offline": True,
            "retry_applied": False,
            "health_window_seconds": 0.0,
        }

    report = {
        **report_metadata("ov-enterprise-uninstall", run_id, started_ms),
        "status": status,
        "mode": "execute" if args.execute else "dry-run",
        **execute_reason,
        "summary": {
            "status": status,
            "counts": counts,
            "runtime_quiesced": runtime_quiesced,
            "affected_containers": affected_containers,
            "config_needs_update": config_needs_update,
            "plugin_dir_exists": plugin_exists,
            "memory_adapter_dir_exists": memory_adapter_exists,
            **execute_reason,
        },
        "checks": render_records(checks),
        "operations": operations,
        "applied": applied,
        "inputs": {
            "openclaw_config": str(args.openclaw_config),
            "plugin_dir": str(args.plugin_dir),
            "memory_adapter_dir": str(args.memory_adapter_dir),
            "archive_root": str(args.archive_root),
            "backup_dir": str(args.backup_dir) if args.backup_dir else None,
            "safety_backup_root": str(args.safety_backup_root),
            "adapter_url": args.adapter_url,
        },
        "archive_dir": str(archive_dir) if archive_dir else None,
        "safety_snapshot_dir": str(safety_snapshot_dir) if safety_snapshot_dir else None,
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
