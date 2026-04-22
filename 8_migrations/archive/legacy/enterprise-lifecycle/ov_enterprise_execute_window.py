"""Offline execute-window readiness packet for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    BASELINE_CONTAINERS,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_COMPATIBILITY_REPORT,
    DEFAULT_EXECUTE_WINDOW_REPORT,
    DEFAULT_REHEARSAL_REPORT,
    ResultRecord,
    compatibility_report_assessment,
    companion_artifacts,
    docker_names,
    json_load,
    load_backup_manifest,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)


def _latest_snapshot(backup_root: Path) -> Path | None:
    snapshots = sorted(
        (item for item in backup_root.glob("snapshot-*") if item.is_dir()),
        key=lambda item: item.name,
    )
    return snapshots[-1] if snapshots else None


def _python() -> str:
    return sys.executable


def _cmd(script: Path, *args: str) -> str:
    parts = [_python(), str(script), *args]
    return " ".join(f'"{part}"' if " " in part else part for part in parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization execute-window readiness")
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--backup-dir", type=Path, help="Explicit snapshot directory to use")
    parser.add_argument("--rehearsal-report", type=Path, default=DEFAULT_REHEARSAL_REPORT)
    parser.add_argument("--compatibility-report", type=Path, default=DEFAULT_COMPATIBILITY_REPORT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_EXECUTE_WINDOW_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("execute-window")
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

    backup_dir = args.backup_dir or _latest_snapshot(args.backup_root)
    backup_manifest: dict[str, Any] | None = None
    if backup_dir and backup_dir.exists():
        try:
            backup_manifest = load_backup_manifest(backup_dir)
            checks.append(
                ResultRecord(
                    "backup_manifest",
                    "pass",
                    "Backup manifest loaded for execute-window planning",
                    {
                        "backup_dir": str(backup_dir),
                        "snapshot_dir": backup_manifest.get("snapshot_dir"),
                        "item_count": len(backup_manifest.get("items", [])),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                ResultRecord(
                    "backup_manifest",
                    "fail",
                    f"Failed to load execute-window backup manifest: {exc}",
                    {"backup_dir": str(backup_dir)},
                )
            )
    else:
        checks.append(
            ResultRecord(
                "backup_manifest",
                "fail",
                "No backup snapshot is available for execute-window planning",
                {"backup_root": str(args.backup_root)},
            )
        )

    rehearsal_payload: dict[str, Any] | None = None
    version_policy: dict[str, Any] = {}
    if args.rehearsal_report.exists():
        try:
            rehearsal_payload = json_load(args.rehearsal_report)
            rehearsal_status = rehearsal_payload.get("status")
            accepted = (
                isinstance(rehearsal_payload.get("acceptance"), dict)
                and rehearsal_payload["acceptance"].get("offline_execute_rehearsal_ready") is True
            )
            checks.append(
                ResultRecord(
                    "rehearsal_report",
                    "pass" if rehearsal_status == "pass" and accepted else "warn" if accepted else "fail",
                    "Rehearsal report is present and approves offline execute rehearsal"
                    if accepted
                    else "Rehearsal report is missing approval for offline execute rehearsal",
                    {
                        "path": str(args.rehearsal_report),
                        "status": rehearsal_status,
                        "accepted": accepted,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                ResultRecord(
                    "rehearsal_report",
                    "fail",
                    f"Failed to parse rehearsal report: {exc}",
                    {"path": str(args.rehearsal_report)},
                )
            )
    else:
        checks.append(
            ResultRecord(
                "rehearsal_report",
                "fail",
                "Rehearsal report is missing",
                {"path": str(args.rehearsal_report)},
            )
        )

    if args.compatibility_report.exists():
        try:
            compatibility_payload = json_load(args.compatibility_report)
            version_policy = compatibility_report_assessment(compatibility_payload)
            checks.append(
                ResultRecord(
                    "compatibility_report",
                    "pass" if version_policy.get("accepted") else "fail",
                    "Compatibility report is present and within the supported version policy"
                    if version_policy.get("accepted")
                    else "Compatibility report is outside the supported version policy",
                    {
                        "path": str(args.compatibility_report),
                        **version_policy,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                ResultRecord(
                    "compatibility_report",
                    "fail",
                    f"Failed to parse compatibility report: {exc}",
                    {"path": str(args.compatibility_report)},
                )
            )
    else:
        checks.append(
            ResultRecord(
                "compatibility_report",
                "fail",
                "Compatibility report is missing",
                {"path": str(args.compatibility_report)},
            )
        )

    running = docker_names()
    active_baseline = sorted(name for name in BASELINE_CONTAINERS if name in running)
    runtime_quiesced = not active_baseline
    checks.append(
        ResultRecord(
            "runtime_state",
            "warn" if active_baseline else "pass",
            "Primary runtime is still online and must be stopped before execute-window actions"
            if active_baseline
            else "Primary runtime is already quiesced",
            {
                "runtime_quiesced": runtime_quiesced,
                "active_baseline_containers": active_baseline,
            },
        )
    )

    counts = result_counts(checks)
    blocking_items = [record.id for record in checks if record.status == "fail"]
    pre_window_actions = [record.id for record in checks if record.status == "warn"]
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"

    tool_dir = Path(__file__).resolve().parent
    commands = {
        "doctor": _cmd(tool_dir / "ov_enterprise_doctor.py"),
        "verify": _cmd(tool_dir / "ov_enterprise_verify.py"),
        "backup": _cmd(tool_dir / "ov_enterprise_backup.py", "--execute"),
        "install_execute": _cmd(tool_dir / "ov_enterprise_install.py", "--execute", "--backup-dir", str(backup_dir)) if backup_dir else None,
        "upgrade_execute": _cmd(tool_dir / "ov_enterprise_upgrade.py", "--execute", "--backup-dir", str(backup_dir)) if backup_dir else None,
        "restore_execute": _cmd(tool_dir / "ov_enterprise_restore.py", "--execute", "--backup-dir", str(backup_dir)) if backup_dir else None,
        "rollback_execute": _cmd(tool_dir / "ov_enterprise_rollback.py", "--execute", "--backup-dir", str(backup_dir)) if backup_dir else None,
        "uninstall_execute": _cmd(tool_dir / "ov_enterprise_uninstall.py", "--execute", "--backup-dir", str(backup_dir)) if backup_dir else None,
    }

    recommended_sequence = [
        {
            "step": 1,
            "title": "Freeze execute window",
            "mode": "manual",
            "details": "Stop baseline containers and confirm no primary runtime remains online.",
            "target_containers": active_baseline or BASELINE_CONTAINERS,
        },
        {
            "step": 2,
            "title": "Confirm baseline before action",
            "mode": "command",
            "command": commands["doctor"],
        },
        {
            "step": 3,
            "title": "Run runtime acceptance before action",
            "mode": "command",
            "command": commands["verify"],
        },
        {
            "step": 4,
            "title": "Refresh execute-window backup",
            "mode": "command",
            "command": commands["backup"],
        },
        {
            "step": 5,
            "title": "Apply guarded execute action",
            "mode": "choice",
            "choices": [
                {"action": "upgrade", "command": commands["upgrade_execute"]},
                {"action": "restore", "command": commands["restore_execute"]},
                {"action": "rollback", "command": commands["rollback_execute"]},
                {"action": "uninstall", "command": commands["uninstall_execute"]},
            ],
        },
        {
            "step": 6,
            "title": "Re-run baseline diagnosis",
            "mode": "command",
            "command": commands["doctor"],
        },
        {
            "step": 7,
            "title": "Re-run runtime acceptance",
            "mode": "command",
            "command": commands["verify"],
        },
    ]

    report = {
        **report_metadata("ov-enterprise-execute-window", run_id, started_ms),
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "blocking_items": blocking_items,
            "pre_window_actions": pre_window_actions,
            "runtime_quiesced": runtime_quiesced,
        },
        "acceptance": {
            "verdict": "ready" if status == "pass" else "prepare" if status == "warn" else "blocked",
            "offline_window_ready_now": status == "pass",
            "offline_window_ready_after_pre_actions": not blocking_items,
            "recommended_version_ready_now": status == "pass" and version_policy.get("is_recommended") is True,
            "blocking_items": blocking_items,
            "pre_window_actions": pre_window_actions,
        },
        "version_policy": version_policy,
        "inputs": {
            "backup_root": str(args.backup_root),
            "backup_dir": str(backup_dir) if backup_dir else None,
            "rehearsal_report": str(args.rehearsal_report),
            "compatibility_report": str(args.compatibility_report),
        },
        "checks": render_records(checks),
        "runtime_state": {
            "runtime_quiesced": runtime_quiesced,
            "active_baseline_containers": active_baseline,
        },
        "recommended_sequence": recommended_sequence,
        "commands": commands,
        "evidence": {
            "backup_snapshot": str(backup_dir) if backup_dir else None,
            "rehearsal_report": str(args.rehearsal_report) if args.rehearsal_report.exists() else None,
            "rehearsal_status": rehearsal_payload.get("status") if isinstance(rehearsal_payload, dict) else None,
            "compatibility_report": str(args.compatibility_report) if args.compatibility_report.exists() else None,
        },
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
