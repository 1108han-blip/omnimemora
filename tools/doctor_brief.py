#!/usr/bin/env python3
"""Print a human-readable Doctor Quality brief."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import doctor_quality


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a readable Doctor Quality brief.")
    parser.add_argument("--react-json", help="reuse an existing doctor_quality JSON report with ReactDoctor results")
    parser.add_argument("--react-timeout", type=int, default=180, help="seconds per ReactDoctor package when scanning")
    args = parser.parse_args(argv)

    static_checks = doctor_quality.run_omni_doctor() + doctor_quality.run_token_doctor()
    react_report = load_react_report(args.react_json, args.react_timeout)
    print(render_brief(static_checks, react_report))
    return 0


def load_react_report(path: str | None, timeout_seconds: int) -> dict[str, Any]:
    if path:
        report_path = Path(path)
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))

    output = subprocess.check_output(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "doctor_quality.py"),
            "--json",
            "--react-doctor",
            "--react-timeout",
            str(timeout_seconds),
        ],
        cwd=REPO_ROOT,
        text=True,
    )
    return json.loads(output)


def render_brief(static_checks: list[dict[str, Any]], react_report: dict[str, Any]) -> str:
    lines: list[str] = []
    static_failures = [item for item in static_checks if item.get("status") != "pass"]
    react_results = react_report.get("react_doctor", [])

    lines.append("# Doctor Quality Brief")
    lines.append("")
    if static_failures:
        lines.append("结论：产品边界或 token 可信规则有未通过项，先处理这些。")
    else:
        lines.append("结论：产品边界和 token 可信规则通过；ReactDoctor 只有 warning，适合分批治理。")
    lines.append("")

    lines.append("## 先看这里")
    lines.append("")
    if static_failures:
        for item in static_failures:
            lines.append(f"- {item.get('id')}: {item.get('message')}")
    else:
        lines.append("- OmniDoctor / TokenDoctor: 通过。")
    for result in react_results:
        lines.append(
            "- {path}: score {score}, diagnostics {diagnostics}, status {status}".format(
                path=result.get("path", "unknown"),
                score=result.get("score", "unknown"),
                diagnostics=result.get("diagnostic_count", "unknown"),
                status=result.get("status", "unknown"),
            )
        )
    lines.append("")

    grouped = group_findings(react_results)
    render_group(lines, "## 优先修", grouped["fix_first"])
    render_group(lines, "## 接着修", grouped["next"])
    render_group(lines, "## 先确认再清理", grouped["confirm_before_cleanup"])
    render_group(lines, "## 可以延后", grouped["later"])

    lines.append("## 使用建议")
    lines.append("")
    lines.append("- 不需要看 JSON。先按“优先修”处理，再跑 `make doctor-brief`。")
    lines.append("- Dead code 不要直接删，先确认是不是未来保留接口。")
    lines.append("- 当前仍是 report-only；不要因为单次 warning 直接升级 hard gate。")
    return "\n".join(lines)


def group_findings(react_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {
        "fix_first": [],
        "next": [],
        "confirm_before_cleanup": [],
        "later": [],
    }
    for result in react_results:
        path = result.get("path", "")
        summary = result.get("diagnostic_summary") or {}
        for finding in summary.get("priority_findings", []):
            if not isinstance(finding, dict):
                continue
            item = dict(finding)
            item["package_path"] = path
            priority = item.get("priority")
            grouped.setdefault(str(priority), grouped["later"]).append(item)
    return grouped


def render_group(lines: list[str], title: str, items: list[dict[str, Any]]) -> None:
    lines.append(title)
    lines.append("")
    if not items:
        lines.append("- 暂无。")
        lines.append("")
        return
    for item in items[:12]:
        location = format_location(item)
        lines.append(f"- {location}: {item.get('message')}")
    if len(items) > 12:
        lines.append(f"- 还有 {len(items) - 12} 项同类 warning，先不用一次性处理完。")
    lines.append("")


def format_location(item: dict[str, Any]) -> str:
    package = item.get("package_path") or "unknown-package"
    file_path = item.get("file") or "unknown-file"
    line = item.get("line")
    if line in (None, 0, "0"):
        return f"{package}/{file_path}"
    return f"{package}/{file_path}:{line}"


if __name__ == "__main__":
    raise SystemExit(main())
