"""Low-risk install and upgrade preflight checks for OpenViking commercialization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_INSTALL_CHECK_REPORT,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_OPENCLAW_CONFIG_DIR,
    DEFAULT_PLUGIN_DIR,
    ResultRecord,
    adapter_support_surface,
    companion_artifacts,
    docker_names,
    json_load,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    run_command,
    write_json_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization install-check")
    parser.add_argument("--openclaw-config", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--openclaw-config-dir", type=Path, default=DEFAULT_OPENCLAW_CONFIG_DIR)
    parser.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_INSTALL_CHECK_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("install-check")
    checks: list[ResultRecord] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        ResultRecord(
            "python_version",
            "pass" if python_ok else "fail",
            "Python runtime meets the minimum requirement"
            if python_ok
            else "Python 3.10 or newer is required",
        )
    )

    docker_ok, docker_payload = run_command(["docker", "version", "--format", "{{.Server.Version}}"])
    checks.append(
        ResultRecord(
            "docker_cli",
            "pass" if docker_ok else "fail",
            "Docker CLI is available" if docker_ok else "Docker CLI is not available",
            {"server_version": docker_payload.strip()} if docker_ok else {"response": docker_payload},
        )
    )

    checks.append(
        ResultRecord(
            "openclaw_config",
            "pass" if args.openclaw_config.exists() else "fail",
            "OpenClaw config exists" if args.openclaw_config.exists() else "OpenClaw config is missing",
            {"path": str(args.openclaw_config)},
        )
    )
    if args.openclaw_config.exists():
        try:
            config = json_load(args.openclaw_config)
            plugins = config.get("plugins", {})
            plugin_allowed = "memory-openviking" in plugins.get("allow", [])
            checks.append(
                ResultRecord(
                    "memory_plugin_allow",
                    "pass" if plugin_allowed else "warn",
                    "memory-openviking is already allowed in OpenClaw"
                    if plugin_allowed
                    else "memory-openviking is not yet allowed in OpenClaw",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("openclaw_config_parse", "fail", f"OpenClaw config parse failed: {exc}"))

    checks.append(
        ResultRecord(
            "openclaw_config_dir",
            "pass" if args.openclaw_config_dir.exists() else "fail",
            "OpenClaw config directory exists"
            if args.openclaw_config_dir.exists()
            else "OpenClaw config directory is missing",
        )
    )
    checks.append(
        ResultRecord(
            "plugin_dir",
            "pass" if args.plugin_dir.exists() else "warn",
            "Plugin directory exists" if args.plugin_dir.exists() else "Plugin directory is missing and will need to be installed",
        )
    )
    checks.append(
        ResultRecord(
            "archive_root",
            "pass" if args.archive_root.exists() else "warn",
            "Archive root exists" if args.archive_root.exists() else "Archive root is missing; staging trace retention should be reviewed",
        )
    )
    backup_root_ok = path_writable(args.backup_root / "probe.json")
    checks.append(
        ResultRecord(
            "backup_root",
            "pass" if backup_root_ok else "fail",
            "Backup root is writable" if backup_root_ok else "Backup root is not writable",
            {"path": str(args.backup_root)},
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

    staging_running = any("staging" in name.lower() for name in docker_names())
    checks.append(
        ResultRecord(
            "staging_parallel",
            "warn" if staging_running else "pass",
            "A staging runtime is currently running" if staging_running else "No parallel staging runtime detected",
        )
    )

    support_surface = adapter_support_surface(args.adapter_url)
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
    report = {
        **report_metadata("ov-enterprise-install-check", run_id, started_ms),
        "status": status,
        "summary": {"status": status, "counts": counts},
        "checks": render_records(checks),
        "support_surface": support_surface,
        "companion_artifacts": companion_artifacts(),
        "suggestions": [
            "Create a backup before any install or upgrade action.",
            "Run doctor and verify after any change that touches config, containers, or plugin files.",
        ],
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
