"""Verify the generated offline execute-window packet before any real downtime action."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_WINDOW_PACKET_REPORT,
    DEFAULT_WINDOW_PACKET_VERIFY_REPORT,
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


def _powershell_parses(path: Path) -> tuple[bool, str]:
    quoted_path = str(path).replace("'", "''")
    command = (
        "$content = Get-Content "
        + f"'{quoted_path}'"
        + " -Raw; "
        + "[scriptblock]::Create($content) | Out-Null; "
        + "Write-Output 'ok'"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    ok = proc.returncode == 0 and proc.stdout.strip().endswith("ok")
    detail = proc.stderr.strip() or proc.stdout.strip()
    return ok, detail


def _runbook_links(content: str) -> list[str]:
    return re.findall(r"`([^`]+)`", content)


def _pre_stop_order_ok(content: str) -> tuple[bool, dict[str, int]]:
    backup_script = content.find("ov_enterprise_backup.py")
    backup_execute = content.find("--execute", backup_script if backup_script >= 0 else 0)
    patterns = {
        "doctor": content.find("ov_enterprise_doctor.py"),
        "verify": content.find("ov_enterprise_verify.py"),
        "backup": backup_script if backup_script >= 0 and backup_execute > backup_script else -1,
        "stop": content.find("docker stop $containers"),
    }
    ordered = all(position >= 0 for position in patterns.values())
    if ordered:
        ordered = patterns["doctor"] < patterns["verify"] < patterns["backup"] < patterns["stop"]
    return ordered, patterns


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization window-packet verify")
    parser.add_argument("--window-packet-report", type=Path, default=DEFAULT_WINDOW_PACKET_REPORT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_WINDOW_PACKET_VERIFY_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("window-packet-verify")
    checks: list[ResultRecord] = []
    generated_files: dict[str, str] = {}
    version_policy: dict[str, Any] = {}

    report_path_ok = path_writable(args.report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    if not args.window_packet_report.exists():
        checks.append(
            ResultRecord(
                "window_packet_report",
                "fail",
                "Window-packet report is missing",
                {"path": str(args.window_packet_report)},
            )
        )
        counts = result_counts(checks)
        report = {
            **report_metadata("ov-enterprise-window-packet-verify", run_id, started_ms),
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
        packet_report = json_load(args.window_packet_report)
        generated_files = packet_report.get("generated_files", {}) if isinstance(packet_report.get("generated_files"), dict) else {}
        source_evidence = packet_report.get("source_evidence", {}) if isinstance(packet_report.get("source_evidence"), dict) else {}
        version_policy = source_evidence.get("version_policy", {}) if isinstance(source_evidence.get("version_policy"), dict) else {}
        checks.append(
            ResultRecord(
                "window_packet_report",
                "pass",
                "Window-packet report loaded",
                {
                    "path": str(args.window_packet_report),
                    "status": packet_report.get("status"),
                    "generated_file_count": len(generated_files),
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            ResultRecord(
                "window_packet_report",
                "fail",
                f"Failed to parse window-packet report: {exc}",
                {"path": str(args.window_packet_report)},
            )
        )
        counts = result_counts(checks)
        report = {
            **report_metadata("ov-enterprise-window-packet-verify", run_id, started_ms),
            "status": "fail",
            "summary": {"status": "fail", "counts": counts},
            "checks": render_records(checks),
            "companion_artifacts": companion_artifacts(),
            "report_path": str(args.report_path),
        }
        write_json_report(args.report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    if version_policy:
        checks.append(
            ResultRecord(
                "version_policy",
                "pass" if version_policy.get("accepted") is True else "warn",
                "Packet inherits an accepted version policy classification"
                if version_policy.get("accepted") is True
                else "Packet version policy metadata is incomplete",
                version_policy,
            )
        )

    all_exist = True
    ps1_paths: list[Path] = []
    runbook_path: Path | None = None
    for key, raw_path in generated_files.items():
        path = Path(raw_path)
        exists = path.exists()
        all_exist = all_exist and exists
        if path.suffix.lower() == ".ps1":
            ps1_paths.append(path)
        if path.suffix.lower() == ".md":
            runbook_path = path
        checks.append(
            ResultRecord(
                f"file_{key}",
                "pass" if exists else "fail",
                f"Generated file {key} exists" if exists else f"Generated file {key} is missing",
                {"path": str(path)},
            )
        )

    ps_parse_failures: list[dict[str, Any]] = []
    for path in ps1_paths:
        ok, detail = _powershell_parses(path)
        if not ok:
            ps_parse_failures.append({"path": str(path), "detail": detail})
        checks.append(
            ResultRecord(
                f"powershell_parse_{path.stem}",
                "pass" if ok else "fail",
                f"PowerShell script {path.name} parses successfully"
                if ok
                else f"PowerShell script {path.name} failed to parse",
                {"path": str(path), "detail": detail},
            )
        )

    pre_stop_path = next((path for path in ps1_paths if path.name == "execute_window.pre-stop.ps1"), None)
    if pre_stop_path and pre_stop_path.exists():
        pre_stop_content = pre_stop_path.read_text(encoding="utf-8")
        order_ok, positions = _pre_stop_order_ok(pre_stop_content)
        checks.append(
            ResultRecord(
                "pre_stop_order",
                "pass" if order_ok else "fail",
                "Pre-stop script runs doctor, verify, and backup before stopping containers"
                if order_ok
                else "Pre-stop script order is invalid for the execute window",
                {"path": str(pre_stop_path), "positions": positions},
            )
        )

    if runbook_path and runbook_path.exists():
        runbook_content = runbook_path.read_text(encoding="utf-8")
        links = _runbook_links(runbook_content)
        missing_links = [link for link in links if (":" in link or "\\" in link) and not Path(link).exists()]
        checks.append(
            ResultRecord(
                "runbook_links",
                "pass" if not missing_links else "fail",
                "Runbook references existing packet files"
                if not missing_links
                else "Runbook contains missing file references",
                {"runbook": str(runbook_path), "missing_links": missing_links},
            )
        )
    else:
        checks.append(
            ResultRecord(
                "runbook_links",
                "fail",
                "Runbook file is missing",
                {"runbook": str(runbook_path) if runbook_path else None},
            )
        )

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "pass"
    report = {
        **report_metadata("ov-enterprise-window-packet-verify", run_id, started_ms),
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "generated_file_count": len(generated_files),
            "powershell_script_count": len(ps1_paths),
        },
        "acceptance": {
            "verdict": "accepted" if status == "pass" else "blocked",
            "packet_parse_ready": status == "pass",
            "parse_failures": ps_parse_failures,
            "version_policy": version_policy,
        },
        "inputs": {
            "window_packet_report": str(args.window_packet_report),
        },
        "checks": render_records(checks),
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
