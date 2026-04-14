"""Closed-loop rehearsal report generator for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_REHEARSAL_REPORT,
    ResultRecord,
    compatibility_report_assessment,
    companion_artifacts,
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


def _invoke_tool(tool_path: Path, args: list[str]) -> tuple[int, dict[str, Any]]:
    cmd = [sys.executable, str(tool_path), *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout = proc.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": stdout}
    else:
        payload = {"raw_stdout": ""}
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()
    return proc.returncode, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization rehearsal")
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--backup-dir", type=Path, help="Explicit snapshot directory to use")
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REHEARSAL_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("rehearsal")
    checks: list[ResultRecord] = []
    steps: list[dict[str, Any]] = []
    doctor_assessment: dict[str, Any] = {}

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
    if backup_dir and backup_dir.exists():
        try:
            manifest = load_backup_manifest(backup_dir)
            checks.append(
                ResultRecord(
                    "backup_manifest",
                    "pass",
                    "Backup manifest loaded for rehearsal",
                    {
                        "backup_dir": str(backup_dir),
                        "snapshot_dir": manifest.get("snapshot_dir"),
                        "item_count": len(manifest.get("items", [])),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                ResultRecord(
                    "backup_manifest",
                    "fail",
                    f"Failed to load rehearsal backup manifest: {exc}",
                    {"backup_dir": str(backup_dir)},
                )
            )
    else:
        checks.append(
            ResultRecord(
                "backup_manifest",
                "fail",
                "No rehearsal backup snapshot was found",
                {"backup_root": str(args.backup_root)},
            )
        )

    tool_dir = Path(__file__).resolve().parent
    rehearsal_steps = [
        ("doctor", tool_dir / "ov_enterprise_doctor.py", []),
        ("verify", tool_dir / "ov_enterprise_verify.py", []),
        ("install_check", tool_dir / "ov_enterprise_install_check.py", ["--adapter-url", args.adapter_url]),
        ("install", tool_dir / "ov_enterprise_install.py", ["--adapter-url", args.adapter_url]),
        ("upgrade", tool_dir / "ov_enterprise_upgrade.py", ["--adapter-url", args.adapter_url, "--backup-dir", str(backup_dir)] if backup_dir else ["--adapter-url", args.adapter_url]),
        ("restore", tool_dir / "ov_enterprise_restore.py", ["--adapter-url", args.adapter_url, "--backup-dir", str(backup_dir)] if backup_dir else ["--adapter-url", args.adapter_url]),
        ("rollback", tool_dir / "ov_enterprise_rollback.py", ["--adapter-url", args.adapter_url, "--backup-dir", str(backup_dir)] if backup_dir else ["--adapter-url", args.adapter_url]),
        ("uninstall_plan", tool_dir / "ov_enterprise_uninstall_plan.py", ["--adapter-url", args.adapter_url]),
        ("uninstall", tool_dir / "ov_enterprise_uninstall.py", ["--adapter-url", args.adapter_url]),
    ]

    for step_id, tool_path, extra_args in rehearsal_steps:
        if "--backup-dir" in extra_args or step_id not in {"upgrade", "restore", "rollback"} or backup_dir:
            exit_code, payload = _invoke_tool(tool_path, extra_args)
            payload_status = payload.get("status") if isinstance(payload, dict) else None
            step_status = "pass"
            if exit_code != 0 or payload_status not in {"pass", "warn"}:
                step_status = "fail"
            elif payload_status == "warn":
                step_status = "warn"
            steps.append(
                {
                    "id": step_id,
                    "tool_path": str(tool_path),
                    "command_args": extra_args,
                    "status": step_status,
                    "tool_status": payload_status,
                    "exit_code": exit_code,
                    "report_path": payload.get("report_path") if isinstance(payload, dict) else None,
                    "summary": payload.get("summary") if isinstance(payload, dict) else None,
                }
            )
            if step_id == "doctor":
                doctor_assessment = compatibility_report_assessment(payload if isinstance(payload, dict) else None)
                steps[-1]["compatibility"] = doctor_assessment
            checks.append(
                ResultRecord(
                    f"step_{step_id}",
                    step_status,
                    f"Rehearsal step {step_id} completed with tool status {payload_status}",
                    {
                        "exit_code": exit_code,
                        "tool_status": payload_status,
                        "report_path": payload.get("report_path") if isinstance(payload, dict) else None,
                    },
                )
            )

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    blocking_steps = [step["id"] for step in steps if step["status"] == "fail"]
    compatible_rehearsal_ready = not blocking_steps

    report = {
        **report_metadata("ov-enterprise-rehearsal", run_id, started_ms),
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "step_count": len(steps),
            "blocking_steps": blocking_steps,
        },
        "acceptance": {
            "verdict": "accepted" if status == "pass" else "conditional" if status == "warn" else "blocked",
            "offline_execute_rehearsal_ready": compatible_rehearsal_ready,
            "recommended_execute_rehearsal_ready": status == "pass",
            "requires_followup": bool(blocking_steps),
            "blocking_steps": blocking_steps,
        },
        "version_policy": doctor_assessment,
        "inputs": {
            "backup_root": str(args.backup_root),
            "backup_dir": str(backup_dir) if backup_dir else None,
            "adapter_url": args.adapter_url,
        },
        "checks": render_records(checks),
        "steps": steps,
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
