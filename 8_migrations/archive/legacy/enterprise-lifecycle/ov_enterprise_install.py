"""Guarded install tool for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    merge_plugin_baseline_config,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_EXPECTED_PLUGIN_BASE_URL,
    DEFAULT_INSTALL_REPORT,
    DEFAULT_MIN_PLUGIN_TIMEOUT_MS,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_PLUGIN_DIR,
    ResultRecord,
    adapter_support_surface,
    companion_artifacts,
    json_load,
    load_backup_manifest,
    make_run_id,
    monotonic_ms,
    path_writable,
    plugin_entry_from_baseline,
    render_records,
    report_metadata,
    resolve_known_agents,
    result_counts,
    support_trace_checkpoint,
    sync_path,
    write_json_file,
    write_json_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization install")
    parser.add_argument("--openclaw-config", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--plugin-source-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--backup-dir", type=Path, help="Required for --execute")
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--base-url", default=DEFAULT_EXPECTED_PLUGIN_BASE_URL)
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_MIN_PLUGIN_TIMEOUT_MS)
    parser.add_argument("--agent-id", default=DEFAULT_EXPECTED_AGENT_ID)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_INSTALL_REPORT)
    parser.add_argument("--execute", action="store_true", help="Apply the install plan")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("install")
    checks: list[ResultRecord] = []
    operations: list[dict[str, Any]] = []
    config: dict[str, Any] = {}
    config_changed = False
    plugin_sync_needed = False
    backup_manifest: dict[str, Any] | None = None
    support_trace: list[dict[str, Any]] = []

    if args.openclaw_config.exists():
        try:
            config = json_load(args.openclaw_config)
            checks.append(ResultRecord("openclaw_config", "pass", "OpenClaw config loaded", {"path": str(args.openclaw_config)}))
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("openclaw_config", "fail", f"Failed to parse OpenClaw config: {exc}"))
    else:
        checks.append(ResultRecord("openclaw_config", "fail", "OpenClaw config file not found", {"path": str(args.openclaw_config)}))

    source_exists = args.plugin_source_dir.exists()
    checks.append(
        ResultRecord(
            "plugin_source",
            "pass" if source_exists else "fail",
            "Plugin source directory exists" if source_exists else "Plugin source directory is missing",
            {"path": str(args.plugin_source_dir)},
        )
    )

    target_exists = args.plugin_dir.exists()
    checks.append(
        ResultRecord(
            "plugin_target",
            "pass" if target_exists else "warn",
            "Plugin target directory exists" if target_exists else "Plugin target directory will be created during install",
            {"path": str(args.plugin_dir)},
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

    known_agents = resolve_known_agents(config) if config else []
    if known_agents:
        checks.append(
            ResultRecord(
                "agent_id_registry",
                "pass" if args.agent_id in known_agents else "warn",
                "Requested agentId is present in the OpenClaw agent registry"
                if args.agent_id in known_agents
                else "Requested agentId is not present in the OpenClaw agent registry",
                {"agentId": args.agent_id, "knownAgents": known_agents},
            )
        )

    if config:
        desired_entry = plugin_entry_from_baseline(
            base_url=args.base_url,
            timeout_ms=args.timeout_ms,
            auto_recall=True,
            auto_capture=True,
            agent_id=args.agent_id,
        )
        changes = merge_plugin_baseline_config(config, desired_entry)
        config_changed = bool(changes)
        operations.append(
            {
                "id": "patch_openclaw_config",
                "status": "planned" if changes else "noop",
                "path": str(args.openclaw_config),
                "changes": changes,
            }
        )

    try:
        plugin_sync_needed = args.plugin_source_dir.resolve() != args.plugin_dir.resolve() or not target_exists
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
            except Exception as exc:  # noqa: BLE001
                checks.append(ResultRecord("backup_manifest", "fail", f"Failed to load backup manifest: {exc}"))
    else:
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

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"

    applied: list[dict[str, Any]] = []
    if args.execute and status != "fail":
        support_trace.append(support_trace_checkpoint("pre_execute", adapter_support_surface(args.adapter_url)))
        if plugin_sync_needed:
            sync_path(args.plugin_source_dir, args.plugin_dir)
            applied.append({"id": "sync_plugin_dir", "result": "applied"})
        if config_changed:
            write_json_file(args.openclaw_config, config)
            applied.append({"id": "patch_openclaw_config", "result": "applied"})
        support_trace.append(support_trace_checkpoint("post_execute", adapter_support_surface(args.adapter_url)))

    report = {
        **report_metadata("ov-enterprise-install", run_id, started_ms),
        "status": status,
        "mode": "execute" if args.execute and status != "fail" else "dry-run",
        "summary": {
            "status": status,
            "counts": counts,
            "config_changed": config_changed,
            "plugin_sync_needed": plugin_sync_needed,
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
        },
        "support_surface": support_surface,
        "support_trace": support_trace,
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
