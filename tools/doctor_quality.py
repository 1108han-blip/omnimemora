#!/usr/bin/env python3
"""Observe-only quality doctor for OmniMemora and DoloToken."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_PACKAGES = [
    REPO_ROOT / "6_console" / "desktop-shell",
    REPO_ROOT / "6_console" / "demo-dashboard",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run observe-only OmniMemora/DoloToken doctor checks.")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument("--react-doctor", action="store_true", help="also run ReactDoctor through npx")
    parser.add_argument("--react-timeout", type=int, default=120, help="seconds per ReactDoctor package")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when static doctor errors are present; default is observe-only",
    )
    args = parser.parse_args(argv)

    checks: list[dict[str, Any]] = []
    checks.extend(run_omni_doctor())
    checks.extend(run_token_doctor())
    react_results = run_react_doctor(args.react_timeout) if args.react_doctor else []

    report = {
        "schema_version": "omnimemora-doctor-quality-v1",
        "mode": "observe_only",
        "repo": str(REPO_ROOT),
        "summary": summarize(checks, react_results),
        "checks": checks,
        "react_doctor": react_results,
        "next_gate": "Review findings before any CI fail gate or automatic fix.",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text_report(report)

    if args.strict and report["summary"]["static_errors"] > 0:
        return 1
    return 0


def run_omni_doctor() -> list[dict[str, Any]]:
    readme = read_text("README.md")
    agents = read_text("AGENTS.md")
    makefile = read_text("Makefile")
    structured_compile = read_text("7_docs/internal/structured_compile/README.md")

    return [
        contains_check(
            "omni.18011_product_ingress",
            readme,
            ["18011", "only product data entry"],
            "README states 18011 is the only product data entry when routing is enabled.",
        ),
        contains_check(
            "omni.5173_legacy_dev",
            readme,
            ["5173", "legacy"],
            "README states 5173 is legacy/dev, not required by current desktop GUI.",
        ),
        contains_check(
            "omni.8765_internal_memory_plane",
            readme + "\n" + agents,
            ["8765", "internal"],
            "Current docs keep 8765 as an internal memory plane.",
        ),
        contains_check(
            "omni.no_auto_attach",
            readme + "\n" + agents,
            ["Agent detection", "must not auto-attach", "auto-enable routing"],
            "Current docs preserve the no hidden auto-attach rule.",
        ),
        contains_check(
            "omni.metrics_core_capabilities_truth",
            readme,
            ["/metrics/core_capabilities", "real_input_v1"],
            "README names the MVP real-input savings truth surface.",
        ),
        contains_check(
            "omni.health_checks_cover_ingress_and_runtime",
            makefile,
            ["18011/health", "8765/health"],
            "Makefile health target checks both product ingress and internal runtime.",
            severity="warning",
        ),
        active_5173_conflict_check(readme + "\n" + agents + "\n" + structured_compile),
    ]


def run_token_doctor() -> list[dict[str, Any]]:
    docs = read_text("7_docs/internal/token_intelligence/README.md")
    models = read_text("5_connectors/adapter/application/token_intelligence/models.py")
    config = read_text("5_connectors/adapter/application/token_intelligence/config.py")
    local_proxy = read_text("5_connectors/adapter/application/token_intelligence/local_proxy.py")
    mcp_companion = read_text("5_connectors/adapter/application/token_intelligence/mcp_companion.py")
    package_builder = read_text("tools/token_intelligence/build_local_package.py")
    worker = read_text("6_console/control-entry/worker.js")

    versions = {
        "package_builder": match_value(package_builder, r'DEFAULT_VERSION\s*=\s*"([^"]+)"'),
        "local_proxy": match_value(local_proxy, r'VERSION\s*=\s*"([^"]+)"'),
        "mcp_companion": match_value(mcp_companion, r'"version":\s*"([^"]+)"'),
        "worker": match_value(worker, r'TOKEN_INTELLIGENCE_VERSION\s*=\s*"([^"]+)"'),
    }
    version_values = {value for value in versions.values() if value}

    return [
        value_check(
            "token.version_alignment",
            len(version_values) == 1 and len(versions) == sum(1 for value in versions.values() if value),
            "DoloToken package, local proxy, MCP companion, and Worker versions are aligned.",
            metadata={"versions": versions},
        ),
        contains_check(
            "token.usage_source_labels",
            models,
            ["provider_reported", "relay_reported", "local_estimated"],
            "Token usage source labels distinguish provider, relay, and local estimates.",
        ),
        contains_check(
            "token.confidence_labels",
            models,
            ["official_usage", "compatible_estimate", "rough_estimate"],
            "Token confidence labels include official and estimated classes.",
        ),
        contains_check(
            "token.local_estimate_not_billing_truth",
            docs,
            ["Local estimates must not be presented as provider billing truth"],
            "Docs preserve the local-estimate versus provider-billing boundary.",
        ),
        contains_check(
            "token.metadata_only_default",
            docs + "\n" + package_builder,
            ["metadata-only", "no raw prompt"],
            "DoloToken default posture stays metadata-only and avoids raw prompt storage.",
        ),
        value_check(
            "token.update_metadata_url_alignment",
            extract_url(config) == extract_url(local_proxy) == "https://doloclaw.com/releases/token-intelligence/latest.json",
            "Config and proxy use the product-owned DoloToken release metadata URL.",
            metadata={"config_url": extract_url(config), "local_proxy_url": extract_url(local_proxy)},
        ),
        contains_check(
            "token.public_brand_worker",
            worker,
            ["DoloToken CLI", "View DoloToken release manifest"],
            "Public Worker copy uses the DoloToken brand on download surfaces.",
        ),
        contains_check(
            "token.no_silent_cloud_publish",
            package_builder,
            ["mutates_cloud", "False", "Deploy the Worker only after R2 object availability is verified"],
            "Package builder keeps cloud publish plans explicit and non-mutating by default.",
        ),
    ]


def run_react_doctor(timeout_seconds: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    npx_path = shutil.which("npx")
    if not npx_path:
        return [
            {
                "tool": "react-doctor",
                "status": "skipped",
                "severity": "warning",
                "message": "npx not found; ReactDoctor was not run.",
            }
        ]

    for package_dir in FRONTEND_PACKAGES:
        package_json = package_dir / "package.json"
        if not package_json.exists():
            results.append(
                {
                    "tool": "react-doctor",
                    "path": str(package_dir.relative_to(REPO_ROOT)),
                    "status": "skipped",
                    "severity": "warning",
                    "message": "package.json not found.",
                }
            )
            continue
        command = [
            npx_path,
            "-y",
            "react-doctor@latest",
            str(package_dir),
            "--json",
            "--offline",
            "--full",
            "--fail-on",
            "none",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            results.append(
                {
                    "tool": "react-doctor",
                    "path": str(package_dir.relative_to(REPO_ROOT)),
                    "status": "timeout",
                    "severity": "warning",
                    "timeout_seconds": timeout_seconds,
                    "message": str(exc),
                }
            )
            continue
        payload = parse_json_stdout(completed.stdout)
        results.append(
            {
                "tool": "react-doctor",
                "path": str(package_dir.relative_to(REPO_ROOT)),
                "status": "completed" if completed.returncode == 0 else "nonzero_exit",
                "severity": "warning" if completed.returncode else "info",
                "exit_code": completed.returncode,
                "version": payload.get("version") if isinstance(payload, dict) else None,
                "score": extract_score(payload),
                "diagnostic_count": extract_diagnostic_count(payload),
                "stdout_json_ok": payload is not None,
                "stderr_tail": tail(completed.stderr),
            }
        )
    return results


def summarize(checks: list[dict[str, Any]], react_results: list[dict[str, Any]]) -> dict[str, Any]:
    static_errors = sum(1 for check in checks if check["status"] == "fail" and check["severity"] == "error")
    static_warnings = sum(1 for check in checks if check["status"] == "fail" and check["severity"] == "warning")
    react_completed = sum(1 for result in react_results if result.get("status") == "completed")
    return {
        "static_total": len(checks),
        "static_passed": sum(1 for check in checks if check["status"] == "pass"),
        "static_errors": static_errors,
        "static_warnings": static_warnings,
        "react_doctor_requested": bool(react_results),
        "react_doctor_completed": react_completed,
        "overall_status": "needs_review" if static_errors or static_warnings else "ok",
    }


def contains_check(
    check_id: str,
    haystack: str,
    needles: list[str],
    message: str,
    *,
    severity: str = "error",
) -> dict[str, Any]:
    missing = [needle for needle in needles if needle not in haystack]
    return {
        "id": check_id,
        "status": "pass" if not missing else "fail",
        "severity": severity,
        "message": message,
        "missing": missing,
    }


def value_check(
    check_id: str,
    passed: bool,
    message: str,
    *,
    severity: str = "error",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "message": message,
        "metadata": metadata or {},
    }


def active_5173_conflict_check(text: str) -> dict[str, Any]:
    conflict_pattern = re.compile(r"(only product|product data|唯一产品入口|必须|must|required)", re.I)
    matches = []
    for line in text.splitlines():
        if "5173" not in line or not conflict_pattern.search(line):
            continue
        lowered = line.lower()
        if "not required" in lowered or "must not" in lowered or "不得" in line:
            continue
        matches.append(line.strip())
    return {
        "id": "omni.no_active_5173_ingress_claim",
        "status": "pass" if not matches else "fail",
        "severity": "error",
        "message": "Active current docs must not describe 5173 as product ingress or required dependency.",
        "matches": matches[:5],
    }


def read_text(relative_path: str) -> str:
    path = REPO_ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def match_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if not match:
        return ""
    return match.group(1) if match.groups() else match.group(0)


def extract_url(text: str) -> str:
    return match_value(text, r'https://doloclaw\.com/releases/token-intelligence/latest\.json')


def parse_json_stdout(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except Exception:
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stdout[start : end + 1])
            except Exception:
                return None
        return None


def extract_score(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    score = payload.get("score")
    if isinstance(score, dict):
        return score.get("score")
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary.get("score")
    return score


def extract_diagnostic_count(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, list):
        return len(diagnostics)
    summary = payload.get("summary")
    if isinstance(summary, dict):
        total = summary.get("total") or summary.get("diagnostics") or summary.get("totalDiagnosticCount")
        return total
    return None


def tail(text: str, limit: int = 1000) -> str:
    return text[-limit:] if len(text) > limit else text


def print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("OmniMemora Doctor Quality Layer")
    print(f"mode: {report['mode']}")
    print(
        "static: "
        f"{summary['static_passed']}/{summary['static_total']} passed, "
        f"errors={summary['static_errors']}, warnings={summary['static_warnings']}"
    )
    for check in report["checks"]:
        mark = "ok" if check["status"] == "pass" else check["severity"]
        print(f"- [{mark}] {check['id']}: {check['message']}")
        if check.get("missing"):
            print(f"  missing: {', '.join(check['missing'])}")
        if check.get("matches"):
            print(f"  matches: {check['matches']}")
    if report["react_doctor"]:
        print("react-doctor:")
        for result in report["react_doctor"]:
            print(
                f"- [{result.get('status')}] {result.get('path', '')} "
                f"score={result.get('score')} diagnostics={result.get('diagnostic_count')}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
