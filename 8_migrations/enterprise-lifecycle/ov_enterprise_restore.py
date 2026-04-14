"""Guarded restore tool for OpenViking commercialization backups."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_EXECUTE_POLL_INTERVAL_SECONDS,
    DEFAULT_EXECUTE_STARTUP_WAIT_SECONDS,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_RESTORE_REPORT,
    ResultRecord,
    apply_restore_operation,
    adapter_support_surface,
    append_execution_event,
    classify_execute_reason,
    companion_artifacts,
    copy_path,
    load_backup_manifest,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    restore_policy_for,
    result_counts,
    support_trace_checkpoint,
    wait_for_runtime_ready,
    write_json_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization restore")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--safety-backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--openviking-url", default=DEFAULT_OPENVIKING_URL)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_RESTORE_REPORT)
    parser.add_argument("--startup-wait-seconds", type=float, default=DEFAULT_EXECUTE_STARTUP_WAIT_SECONDS)
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULT_EXECUTE_POLL_INTERVAL_SECONDS)
    parser.add_argument("--execute", action="store_true", help="Actually restore files from the backup manifest")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("restore")
    checks: list[ResultRecord] = []
    operations: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    support_trace: list[dict[str, Any]] = []
    execution_trace: list[dict[str, Any]] = []
    safety_snapshot_dir: Path | None = None
    precheck_items: list[ResultRecord] = []
    execute_items: list[ResultRecord] = []
    postcheck_items: list[ResultRecord] = []
    runtime_window_execute: dict[str, Any] | None = None
    runtime_window_post: dict[str, Any] | None = None

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
    precheck_items.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    try:
        manifest = load_backup_manifest(args.backup_dir)
        append_execution_event(
            execution_trace,
            "load_backup_manifest",
            "pass",
            {"backup_dir": str(args.backup_dir)},
        )
        checks.append(
            ResultRecord(
                "backup_manifest",
                "pass",
                "Backup manifest loaded",
                {"backup_dir": str(args.backup_dir), "snapshot_dir": manifest.get("snapshot_dir")},
            )
        )
        precheck_items.append(
            ResultRecord(
                "backup_manifest",
                "pass",
                "Backup manifest loaded",
                {"backup_dir": str(args.backup_dir), "snapshot_dir": manifest.get("snapshot_dir")},
            )
        )
    except Exception as exc:  # noqa: BLE001
        manifest = {}
        append_execution_event(
            execution_trace,
            "load_backup_manifest",
            "fail",
            {"backup_dir": str(args.backup_dir), "error": str(exc)},
        )
        checks.append(ResultRecord("backup_manifest", "fail", f"Failed to load backup manifest: {exc}"))
        precheck_items.append(ResultRecord("backup_manifest", "fail", f"Failed to load backup manifest: {exc}"))

    items = manifest.get("items", []) if isinstance(manifest, dict) else []
    checks.append(
        ResultRecord(
            "backup_items",
            "pass" if items else "fail",
            "Backup manifest contains restorable items" if items else "Backup manifest contains no restorable items",
            {"count": len(items)},
        )
    )
    precheck_items.append(
        ResultRecord(
            "backup_items",
            "pass" if items else "fail",
            "Backup manifest contains restorable items" if items else "Backup manifest contains no restorable items",
            {"count": len(items)},
        )
    )
    append_execution_event(
        execution_trace,
        "plan_restore_operations",
        "pass" if items else "fail",
        {"item_count": len(items)},
    )

    restore_sources_exist = True
    for item in items:
        source = Path(str(item.get("target", "")))
        target = Path(str(item.get("source", "")))
        restore_sources_exist = restore_sources_exist and source.exists()
        operations.append(
            {
                "id": str(item.get("id")),
                "restore_from": str(source),
                "restore_to": str(target),
                "backup_exists": source.exists(),
                "target_exists": target.exists(),
            }
        )
        append_execution_event(
            execution_trace,
            "plan_restore_item",
            "planned" if source.exists() else "fail",
            {
                "id": str(item.get("id")),
                "restore_from": str(source),
                "restore_to": str(target),
                "backup_exists": source.exists(),
                "target_exists": target.exists(),
            },
        )

    checks.append(
        ResultRecord(
            "backup_sources",
            "pass" if restore_sources_exist else "fail",
            "Restore sources exist in the selected backup snapshot"
            if restore_sources_exist
            else "One or more restore sources are missing from the selected backup snapshot",
            {"missing_count": sum(1 for op in operations if not op["backup_exists"])},
        )
    )
    precheck_items.append(
        ResultRecord(
            "backup_sources",
            "pass" if restore_sources_exist else "fail",
            "Restore sources exist in the selected backup snapshot"
            if restore_sources_exist
            else "One or more restore sources are missing from the selected backup snapshot",
            {"missing_count": sum(1 for op in operations if not op["backup_exists"])},
        )
    )

    target_writable = True
    target_writable_details: list[dict[str, Any]] = []
    for op in operations:
        target = Path(str(op["restore_to"]))
        writable = path_writable(target)
        target_writable = target_writable and writable
        target_writable_details.append({"id": op["id"], "target": str(target), "writable": writable})
    target_record = ResultRecord(
        "target_write_access",
        "pass" if target_writable else "fail",
        "Restore targets are writable" if target_writable else "One or more restore targets are not writable",
        {"targets": target_writable_details},
    )
    checks.append(target_record)
    precheck_items.append(target_record)

    runtime_window_pre = wait_for_runtime_ready(
        adapter_url=args.adapter_url,
        openviking_url=args.openviking_url,
        wait_seconds=args.startup_wait_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    support_surface = runtime_window_pre["adapter_surface"] if isinstance(runtime_window_pre.get("adapter_surface"), dict) else adapter_support_surface(args.adapter_url)
    support_trace.append(support_trace_checkpoint("precheck", support_surface))
    append_execution_event(
        execution_trace,
        "runtime_readiness_precheck",
        "pass" if runtime_window_pre.get("ready") else "warn",
        runtime_window_pre,
    )
    runtime_pre_record = ResultRecord(
        "runtime_readiness_precheck",
        "pass" if runtime_window_pre.get("ready") else "warn",
        "Runtime reached ready state within the startup window"
        if runtime_window_pre.get("ready")
        else "Runtime did not fully reach ready state within the startup window; degraded mode tolerance applied",
        runtime_window_pre,
    )
    checks.append(runtime_pre_record)
    precheck_items.append(runtime_pre_record)

    policy_details = [
        {
            "id": op["id"],
            "policy": restore_policy_for(str(op["id"]), Path(str(op["restore_from"]))),
        }
        for op in operations
    ]
    execute_items.append(
        ResultRecord(
            "directory_restore_rules",
            "pass",
            "Directory-level recovery rules are active for execute mode",
            {"policies": policy_details},
        )
    )
    execute_items.append(
        ResultRecord(
            "degraded_mode_tolerance",
            "pass",
            "Execute mode uses startup-window polling and degraded-mode tolerance instead of failing immediately on transient refused responses",
            {
                "startup_wait_seconds": args.startup_wait_seconds,
                "poll_interval_seconds": args.poll_interval_seconds,
            },
        )
    )
    execute_items.append(
        ResultRecord(
            "runtime_sensitive_directory_exclusions",
            "pass",
            "Runtime-sensitive directories are excluded from directory-level recovery",
            {
                "excluded_names": sorted(
                    {
                        name
                        for item in policy_details
                        for name in item["policy"].get("excluded_names", [])
                    }
                )
            },
        )
    )

    status = "fail" if any(record.status == "fail" for record in checks) else "warn" if any(record.status == "warn" for record in checks) else "pass"

    if args.execute and status != "fail":
        runtime_window_execute = wait_for_runtime_ready(
            adapter_url=args.adapter_url,
            openviking_url=args.openviking_url,
            wait_seconds=args.startup_wait_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )
        support_trace.append(
            support_trace_checkpoint(
                "pre_execute",
                runtime_window_execute["adapter_surface"] if isinstance(runtime_window_execute.get("adapter_surface"), dict) else adapter_support_surface(args.adapter_url),
            )
        )
        append_execution_event(
            execution_trace,
            "runtime_readiness_pre_execute",
            "pass" if runtime_window_execute.get("ready") else "warn",
            runtime_window_execute,
        )
        try:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safety_snapshot_dir = args.safety_backup_root / f"pre-restore-{stamp}"
            safety_snapshot_dir.mkdir(parents=True, exist_ok=False)
            append_execution_event(
                execution_trace,
                "create_safety_snapshot_dir",
                "pass",
                {"path": str(safety_snapshot_dir)},
            )

            safety_items: list[dict[str, object]] = []
            for op in operations:
                target = Path(str(op["restore_to"]))
                safety_target = safety_snapshot_dir / str(op["id"])
                record = {
                    "id": op["id"],
                    "source": str(target),
                    "target": str(safety_target),
                    "exists": target.exists(),
                    "copied": False,
                }
                if target.exists():
                    copy_path(target, safety_target)
                    record["copied"] = True
                    append_execution_event(
                        execution_trace,
                        "snapshot_target_before_restore",
                        "pass",
                        {"id": op["id"], "source": str(target), "target": str(safety_target)},
                    )
                else:
                    append_execution_event(
                        execution_trace,
                        "snapshot_target_before_restore",
                        "skip",
                        {"id": op["id"], "source": str(target), "reason": "target_missing"},
                    )
                safety_items.append(record)

            write_json_report(
                safety_snapshot_dir / "manifest.json",
                {
                    **report_metadata("ov-enterprise-pre-restore-backup", run_id, started_ms),
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

            for op in operations:
                source = Path(str(op["restore_from"]))
                target = Path(str(op["restore_to"]))
                outcome = apply_restore_operation(str(op["id"]), source, target)
                applied.append({"id": op["id"], "result": "applied"})
                append_execution_event(
                    execution_trace,
                    "restore_item",
                    "pass",
                    {
                        "id": op["id"],
                        "source": str(source),
                        "target": str(target),
                        "policy": outcome["policy"],
                        "result": outcome["result"],
                    },
                )
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("execute_restore", "fail", f"Restore execution failed: {exc}"))
            append_execution_event(
                execution_trace,
                "execute_restore",
                "fail",
                {"error": str(exc)},
            )
        finally:
            runtime_window_post = wait_for_runtime_ready(
                adapter_url=args.adapter_url,
                openviking_url=args.openviking_url,
                wait_seconds=args.startup_wait_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            post_phase = "post_execute" if not any(record.id == "execute_restore" and record.status == "fail" for record in checks) else "post_execute_failure"
            support_trace.append(
                support_trace_checkpoint(
                    post_phase,
                    runtime_window_post["adapter_surface"] if isinstance(runtime_window_post.get("adapter_surface"), dict) else adapter_support_surface(args.adapter_url),
                )
            )
            append_execution_event(
                execution_trace,
                "runtime_readiness_post_execute",
                "pass" if runtime_window_post.get("ready") else "warn",
                runtime_window_post,
            )
            postcheck_items.append(
                ResultRecord(
                    "runtime_readiness_post_execute",
                    "pass" if runtime_window_post.get("ready") else "warn",
                    "Runtime returned to ready state within the startup window"
                    if runtime_window_post.get("ready")
                    else "Runtime is still degraded or offline after execute; run post-restart checks instead of treating this as immediate failure",
                    runtime_window_post,
                )
            )
    elif args.execute:
        append_execution_event(
            execution_trace,
            "execute_restore",
            "blocked",
            {"reason": "precheck_failed"},
        )
    else:
        append_execution_event(
            execution_trace,
            "execute_restore",
            "skip",
            {"reason": "dry-run"},
        )

    if safety_snapshot_dir:
        postcheck_items.append(
            ResultRecord(
                "safety_snapshot",
                "pass",
                "Pre-restore safety snapshot was created",
                {"path": str(safety_snapshot_dir)},
            )
        )
    if args.execute:
        postcheck_items.append(
            ResultRecord(
                "post_execute_validation_triad",
                "pass",
                "Post-execute validation should use the compatibility + verify + backup triad after runtime restart",
                {
                    "recommended_commands": [
                        "python E:\\AI\\OpenViking-main\\examples\\commercialization\\ov_enterprise_doctor.py",
                        "python E:\\AI\\OpenViking-main\\examples\\commercialization\\ov_enterprise_verify.py",
                        "python E:\\AI\\OpenViking-main\\examples\\commercialization\\ov_enterprise_backup.py --execute",
                    ]
                },
            )
        )

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    execute_reason = classify_execute_reason(
        mode="execute" if args.execute else "dry-run",
        status=status,
        health_window_seconds=args.startup_wait_seconds,
        runtime_windows=[runtime_window_pre, runtime_window_execute, runtime_window_post],
    )

    report = {
        **report_metadata("ov-enterprise-restore", run_id, started_ms),
        "status": status,
        "mode": "execute" if args.execute else "dry-run",
        **execute_reason,
        "summary": {
            "status": status,
            "counts": counts,
            "operation_count": len(operations),
            **execute_reason,
        },
        "checks": render_records(checks),
        "operations": operations,
        "applied": applied,
        "inputs": {
            "backup_dir": str(args.backup_dir),
            "safety_backup_root": str(args.safety_backup_root),
            "adapter_url": args.adapter_url,
            "openviking_url": args.openviking_url,
            "startup_wait_seconds": args.startup_wait_seconds,
            "poll_interval_seconds": args.poll_interval_seconds,
        },
        "safety_snapshot_dir": str(safety_snapshot_dir) if safety_snapshot_dir else None,
        "support_surface": support_surface,
        "support_trace": support_trace,
        "execute_checklist": {
            "precheck": render_records(precheck_items),
            "during_execute": render_records(execute_items),
            "postcheck": render_records(postcheck_items),
        },
        "execution_trace": execution_trace,
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
