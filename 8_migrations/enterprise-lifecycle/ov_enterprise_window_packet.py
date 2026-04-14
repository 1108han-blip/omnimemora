"""Generate execute-window scripts and a runbook for offline rehearsal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_EXECUTE_WINDOW_REPORT,
    DEFAULT_WINDOW_PACKET_REPORT,
    ResultRecord,
    companion_artifacts,
    json_load,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _script_header(title: str) -> str:
    return "\n".join(
        [
            f"# {title}",
            "$ErrorActionPreference = 'Stop'",
            "",
        ]
    )


def _join_command(parts: list[str]) -> str:
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization window packet")
    parser.add_argument("--execute-window-report", type=Path, default=DEFAULT_EXECUTE_WINDOW_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_ROOT / "window-packet")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_WINDOW_PACKET_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("window-packet")
    checks: list[ResultRecord] = []

    report_path_ok = path_writable(args.report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    output_dir_ok = path_writable(args.output_dir / ".packet_probe")
    checks.append(
        ResultRecord(
            "output_dir",
            "pass" if output_dir_ok else "fail",
            "Output directory is writable" if output_dir_ok else "Output directory is not writable",
            {"path": str(args.output_dir)},
        )
    )

    if not args.execute_window_report.exists():
        checks.append(
            ResultRecord(
                "execute_window_report",
                "fail",
                "Execute-window report is missing",
                {"path": str(args.execute_window_report)},
            )
        )
        counts = result_counts(checks)
        report = {
            **report_metadata("ov-enterprise-window-packet", run_id, started_ms),
            "status": "fail",
            "summary": {"status": "fail", "counts": counts},
            "checks": render_records(checks),
            "companion_artifacts": companion_artifacts(),
            "report_path": str(args.report_path),
        }
        write_json_report(args.report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    try:
        execute_window = json_load(args.execute_window_report)
        checks.append(
            ResultRecord(
                "execute_window_report",
                "pass",
                "Execute-window report loaded",
                {
                    "path": str(args.execute_window_report),
                    "status": execute_window.get("status"),
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            ResultRecord(
                "execute_window_report",
                "fail",
                f"Failed to parse execute-window report: {exc}",
                {"path": str(args.execute_window_report)},
            )
        )
        counts = result_counts(checks)
        report = {
            **report_metadata("ov-enterprise-window-packet", run_id, started_ms),
            "status": "fail",
            "summary": {"status": "fail", "counts": counts},
            "checks": render_records(checks),
            "companion_artifacts": companion_artifacts(),
            "report_path": str(args.report_path),
        }
        write_json_report(args.report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    runtime_state = execute_window.get("runtime_state", {}) if isinstance(execute_window, dict) else {}
    active_containers = runtime_state.get("active_baseline_containers", []) if isinstance(runtime_state, dict) else []
    commands = execute_window.get("commands", {}) if isinstance(execute_window, dict) else {}
    backup_snapshot = execute_window.get("evidence", {}).get("backup_snapshot") if isinstance(execute_window, dict) and isinstance(execute_window.get("evidence"), dict) else None
    acceptance = execute_window.get("acceptance", {}) if isinstance(execute_window, dict) else {}
    pre_window_actions = acceptance.get("pre_window_actions", []) if isinstance(acceptance, dict) else []
    version_policy = execute_window.get("version_policy", {}) if isinstance(execute_window, dict) and isinstance(execute_window.get("version_policy"), dict) else {}

    args.output_dir.mkdir(parents=True, exist_ok=True)

    pre_stop_path = args.output_dir / "execute_window.pre-stop.ps1"
    offline_upgrade_path = args.output_dir / "execute_window.offline-upgrade.ps1"
    offline_restore_path = args.output_dir / "execute_window.offline-restore.ps1"
    offline_rollback_path = args.output_dir / "execute_window.offline-rollback.ps1"
    offline_uninstall_path = args.output_dir / "execute_window.offline-uninstall.ps1"
    post_check_path = args.output_dir / "execute_window.post-check.ps1"
    runbook_path = args.output_dir / "execute_window.runbook.md"

    pre_stop_lines = [_script_header("OpenViking Execute Window Pre-Stop")]
    if active_containers:
        quoted = ", ".join(_powershell_quote(name) for name in active_containers)
        pre_stop_lines.extend(
            [
                "Write-Host 'Running doctor before execute actions...'",
                commands.get("doctor", "# doctor command unavailable"),
                "",
                "Write-Host 'Running verify before execute actions...'",
                commands.get("verify", "# verify command unavailable"),
                "",
                "Write-Host 'Refreshing the execute-window backup snapshot...'",
                commands.get("backup", "# backup command unavailable"),
                "",
                f"$containers = @({quoted})",
                "Write-Host 'Stopping baseline containers for the execute window...'",
                "docker stop $containers",
                "",
            ]
        )
    else:
        pre_stop_lines.extend(
            [
                "Write-Host 'Baseline runtime is already quiesced; no docker stop is required.'",
                "",
                "Write-Host 'Running doctor before execute actions...'",
                commands.get("doctor", "# doctor command unavailable"),
                "",
                "Write-Host 'Running verify before execute actions...'",
                commands.get("verify", "# verify command unavailable"),
                "",
                "Write-Host 'Refreshing the execute-window backup snapshot...'",
                commands.get("backup", "# backup command unavailable"),
                "",
            ]
        )
    _write_text(pre_stop_path, "\n".join(pre_stop_lines).rstrip() + "\n")

    def _offline_script(title: str, execute_command: str | None) -> str:
        lines = [_script_header(title)]
        lines.extend(
            [
                "Write-Host 'Running doctor immediately before the execute action...'",
                commands.get("doctor", "# doctor command unavailable"),
                "",
                "Write-Host 'Running verify immediately before the execute action...'",
                commands.get("verify", "# verify command unavailable"),
                "",
                "Write-Host 'Applying the guarded execute action...'",
                execute_command or "# execute command unavailable",
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    _write_text(offline_upgrade_path, _offline_script("OpenViking Offline Upgrade", commands.get("upgrade_execute")))
    _write_text(offline_restore_path, _offline_script("OpenViking Offline Restore", commands.get("restore_execute")))
    _write_text(offline_rollback_path, _offline_script("OpenViking Offline Rollback", commands.get("rollback_execute")))
    _write_text(offline_uninstall_path, _offline_script("OpenViking Offline Uninstall", commands.get("uninstall_execute")))

    post_check_lines = [
        _script_header("OpenViking Execute Window Post-Check"),
        "Write-Host 'Running doctor after the execute action...'",
        commands.get("doctor", "# doctor command unavailable"),
        "",
        "Write-Host 'Running verify after the execute action...'",
        commands.get("verify", "# verify command unavailable"),
        "",
    ]
    _write_text(post_check_path, "\n".join(post_check_lines).rstrip() + "\n")

    runbook_lines = [
        "# OpenViking Execute Window Runbook",
        "",
        f"- Execute-window report: `{args.execute_window_report}`",
        f"- Backup snapshot: `{backup_snapshot}`",
        f"- Current execute-window status: `{execute_window.get('status')}`",
        f"- Current verdict: `{acceptance.get('verdict')}`",
        f"- Pre-window actions: `{', '.join(pre_window_actions) if pre_window_actions else 'none'}`",
        f"- Version classification: `{version_policy.get('classification') or 'unknown'}`",
        f"- Recommended version: `{version_policy.get('is_recommended')}`",
        f"- Supported version: `{version_policy.get('is_supported')}`",
        "",
        "## Packet Files",
        "",
        f"- Pre-stop script: `{pre_stop_path}`",
        f"- Offline upgrade script: `{offline_upgrade_path}`",
        f"- Offline restore script: `{offline_restore_path}`",
        f"- Offline rollback script: `{offline_rollback_path}`",
        f"- Offline uninstall script: `{offline_uninstall_path}`",
        f"- Post-check script: `{post_check_path}`",
        "",
        "## Recommended Use",
        "",
        "1. Run the pre-stop script during the approved execute window.",
        "2. Choose exactly one offline execute script for the change being rehearsed.",
        "3. Run the post-check script before reopening the environment.",
        "",
        "## Active Baseline Containers",
        "",
    ]
    if active_containers:
        runbook_lines.extend(f"- `{name}`" for name in active_containers)
    else:
        runbook_lines.append("- `none`")
    runbook_lines.append("")
    _write_text(runbook_path, "\n".join(runbook_lines))

    generated_files = {
        "pre_stop_script": str(pre_stop_path),
        "offline_upgrade_script": str(offline_upgrade_path),
        "offline_restore_script": str(offline_restore_path),
        "offline_rollback_script": str(offline_rollback_path),
        "offline_uninstall_script": str(offline_uninstall_path),
        "post_check_script": str(post_check_path),
        "runbook": str(runbook_path),
    }

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "pass"
    report = {
        **report_metadata("ov-enterprise-window-packet", run_id, started_ms),
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "generated_file_count": len(generated_files),
        },
        "acceptance": {
            "verdict": "generated" if status == "pass" else "blocked",
            "packet_ready": status == "pass",
        },
        "inputs": {
            "execute_window_report": str(args.execute_window_report),
            "output_dir": str(args.output_dir),
        },
        "checks": render_records(checks),
        "generated_files": generated_files,
        "source_evidence": {
            "execute_window_status": execute_window.get("status"),
            "execute_window_acceptance": acceptance,
            "backup_snapshot": backup_snapshot,
            "version_policy": version_policy,
        },
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
