"""Validate product-package installation success against commercialization acceptance criteria."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_INSTALL_VALIDATOR_REPORT,
    DEFAULT_OPENVIKING_URL,
    ResultRecord,
    adapter_support_surface,
    companion_artifacts,
    make_run_id,
    monotonic_ms,
    openviking_support_surface,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)


def _invoke_tool(tool_path: Path, args: list[str]) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(tool_path), *args],
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


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _copy_if_exists(source: Path, destination: Path) -> str | None:
    if not source.exists():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _load_json_if_exists(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking package installation validator")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--openviking-url", default=DEFAULT_OPENVIKING_URL)
    parser.add_argument("--minimum-doctor-support-level", choices=["A", "B", "C", "D"], default="B")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_INSTALL_VALIDATOR_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("install-validator")
    checks: list[ResultRecord] = []
    package_root = args.package_root.resolve()
    runtime_manager = package_root / "runtime" / "engine" / "ov_enterprise_runtime_manager.py"
    manifest_dir = package_root / "manifest"
    baseline_current_dir = package_root / "artifacts" / "baseline" / "current"
    last_verify_dir = package_root / "artifacts" / "last_verify" / "current"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    baseline_snapshot_dir = package_root / "artifacts" / "baseline" / f"install-validated-{timestamp}"

    report_path_ok = path_writable(args.report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )
    checks.append(
        ResultRecord(
            "package_root",
            "pass" if package_root.exists() else "fail",
            "Package root exists" if package_root.exists() else "Package root is missing",
            {"path": str(package_root)},
        )
    )
    checks.append(
        ResultRecord(
            "runtime_manager",
            "pass" if runtime_manager.exists() else "fail",
            "Runtime manager exists in package" if runtime_manager.exists() else "Runtime manager is missing from package",
            {"path": str(runtime_manager)},
        )
    )

    delegated: dict[str, Any] = {}
    doctor_assessment: dict[str, Any] = {}
    if runtime_manager.exists():
        status_exit, status_payload = _invoke_tool(runtime_manager, ["status"])
        doctor_exit, doctor_payload = _invoke_tool(
            runtime_manager,
            ["doctor", "--minimum-support-level", args.minimum_doctor_support_level],
        )
        verify_exit, verify_payload = _invoke_tool(runtime_manager, ["verify"])
        doctor_report_path = doctor_payload.get("delegated", {}).get("report_path")
        doctor_report = _load_json_if_exists(Path(doctor_report_path)) if isinstance(doctor_report_path, str) else {}
        doctor_support_level = doctor_report.get("support_level")
        doctor_classification = doctor_report.get("classification")
        doctor_is_supported = doctor_report.get("is_supported")
        doctor_is_recommended = doctor_report.get("is_recommended")
        doctor_reason_code = doctor_report.get("reason_code")
        doctor_acceptable = bool(doctor_is_supported) and doctor_support_level in {"A", "B"}
        doctor_check_status = "pass" if doctor_is_recommended else "warn" if doctor_acceptable else "fail"
        doctor_message = (
            f"doctor classified the environment as {doctor_classification}"
            if doctor_classification
            else f"doctor returned {doctor_payload.get('status')}"
        )
        doctor_assessment = {
            "support_level": doctor_support_level,
            "classification": doctor_classification,
            "is_supported": doctor_is_supported,
            "is_recommended": doctor_is_recommended,
            "reason_code": doctor_reason_code,
            "report_path": doctor_report_path,
            "minimum_support_level": args.minimum_doctor_support_level,
        }
        delegated = {
            "status": {
                "exit_code": status_exit,
                "status": status_payload.get("status"),
                "report_path": status_payload.get("report_path"),
                "summary": status_payload.get("summary"),
            },
            "doctor": {
                "exit_code": doctor_exit,
                "status": doctor_payload.get("status"),
                "report_path": doctor_payload.get("report_path"),
                "summary": doctor_payload.get("summary"),
                "compatibility_report": doctor_assessment,
            },
            "verify": {
                "exit_code": verify_exit,
                "status": verify_payload.get("status"),
                "report_path": verify_payload.get("report_path"),
                "summary": verify_payload.get("summary"),
            },
        }
        checks.extend(
            [
                ResultRecord(
                    "runtime_status",
                    "pass" if status_exit == 0 and status_payload.get("status") == "pass" else "fail",
                    f"runtime_manager status returned {status_payload.get('status')}",
                    {"exit_code": status_exit},
                ),
                ResultRecord(
                    "doctor",
                    doctor_check_status,
                    doctor_message,
                    {
                        "exit_code": doctor_exit,
                        **doctor_assessment,
                    },
                ),
                ResultRecord(
                    "verify",
                    "pass" if verify_exit == 0 and verify_payload.get("status") == "pass" else "fail",
                    f"verify returned {verify_payload.get('status')}",
                    {"exit_code": verify_exit},
                ),
            ]
        )

    adapter_surface = adapter_support_surface(args.adapter_url)
    openviking_surface = openviking_support_surface(args.openviking_url)
    ports = {
        8000: _port_open("127.0.0.1", 8000),
        1933: _port_open("127.0.0.1", 1933),
    }
    checks.extend(
        [
            ResultRecord(
                "adapter_health",
                "pass" if adapter_surface["health"]["ok"] and adapter_surface["error_catalog"]["ok"] else "fail",
                "Adapter health endpoints reachable"
                if adapter_surface["health"]["ok"] and adapter_surface["error_catalog"]["ok"]
                else "Adapter health endpoints failed",
                adapter_surface,
            ),
            ResultRecord(
                "openviking_health",
                "pass" if openviking_surface["health"]["ok"] else "fail",
                "OpenViking health endpoint reachable" if openviking_surface["health"]["ok"] else "OpenViking health endpoint failed",
                openviking_surface,
            ),
            ResultRecord(
                "port_8000",
                "pass" if ports[8000] else "fail",
                "Port 8000 is reachable" if ports[8000] else "Port 8000 is unavailable",
            ),
            ResultRecord(
                "port_1933",
                "pass" if ports[1933] else "fail",
                "Port 1933 is reachable" if ports[1933] else "Port 1933 is unavailable",
            ),
        ]
    )

    baseline_snapshot_dir.mkdir(parents=True, exist_ok=True)
    baseline_current_dir.mkdir(parents=True, exist_ok=True)
    last_verify_dir.mkdir(parents=True, exist_ok=True)

    copied_reports = {
        "compatibility_report": _copy_if_exists(args.artifact_root / "compatibility_report.current.json", baseline_snapshot_dir / "compatibility_report.current.json"),
        "verify_report": _copy_if_exists(args.artifact_root / "verify_report.current.json", baseline_snapshot_dir / "verify_report.current.json"),
        "runtime_manager_report": _copy_if_exists(args.artifact_root / "runtime_manager.current.json", baseline_snapshot_dir / "runtime_manager.current.json"),
    }
    _copy_if_exists(args.artifact_root / "compatibility_report.current.json", baseline_current_dir / "compatibility_report.current.json")
    _copy_if_exists(args.artifact_root / "verify_report.current.json", baseline_current_dir / "verify_report.current.json")
    _copy_if_exists(args.artifact_root / "runtime_manager.current.json", baseline_current_dir / "runtime_manager.current.json")
    _copy_if_exists(args.artifact_root / "verify_report.current.json", last_verify_dir / "verify_report.current.json")
    _copy_if_exists(args.artifact_root / "compatibility_report.current.json", last_verify_dir / "compatibility_report.current.json")

    snapshot_ok = all(value is not None for value in copied_reports.values())
    checks.append(
        ResultRecord(
            "baseline_snapshot",
            "pass" if snapshot_ok else "fail",
            "Baseline snapshot generated" if snapshot_ok else "Baseline snapshot is incomplete",
            {"snapshot_dir": str(baseline_snapshot_dir), "copied_reports": copied_reports},
        )
    )

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    success_criteria = {
        "runtime_manager_status_pass": delegated.get("status", {}).get("status") == "pass",
        "doctor_acceptable": doctor_assessment.get("is_supported") is True and doctor_assessment.get("support_level") in {"A", "B"},
        "doctor_recommended": doctor_assessment.get("is_recommended") is True,
        "verify_pass": delegated.get("verify", {}).get("status") == "pass",
        "health_endpoints_full": bool(adapter_surface["health"]["ok"] and adapter_surface["error_catalog"]["ok"] and openviking_surface["health"]["ok"]),
        "ports_available": all(ports.values()),
        "baseline_generated": snapshot_ok,
    }
    install_success = all(
        success_criteria[key]
        for key in (
            "runtime_manager_status_pass",
            "doctor_acceptable",
            "verify_pass",
            "health_endpoints_full",
            "ports_available",
            "baseline_generated",
        )
    )
    result_status = "fail" if not install_success else "warn" if counts["warn"] else "pass"
    success_manifest = {
        "schema_version": "ov-commercialization-install-success/v1",
        "run_id": run_id,
        "package_root": str(package_root),
        "status": result_status,
        "success_criteria": success_criteria,
        "doctor_assessment": doctor_assessment,
        "baseline_snapshot_dir": str(baseline_snapshot_dir),
    }
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "install.success.json").write_text(json.dumps(success_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        **report_metadata("ov-enterprise-install-validator", run_id, started_ms),
        "report_kind": "install_validator",
        "status": result_status,
        "summary": {
            "status": result_status,
            "counts": counts,
            "install_success": install_success,
        },
        "success_criteria": success_criteria,
        "doctor_assessment": doctor_assessment,
        "checks": render_records(checks),
        "delegated": delegated,
        "ports": ports,
        "health": {
            "adapter": adapter_surface,
            "openviking": openviking_surface,
        },
        "baseline_snapshot_dir": str(baseline_snapshot_dir),
        "package_root": str(package_root),
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if install_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
