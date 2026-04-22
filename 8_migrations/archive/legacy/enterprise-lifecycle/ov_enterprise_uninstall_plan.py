"""Generate a reversible uninstall plan for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ov_enterprise_common import (
    BASELINE_CONTAINERS,
    DEFAULT_ADAPTER_URL,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_PLUGIN_DIR,
    DEFAULT_UNINSTALL_PLAN_REPORT,
    adapter_support_surface,
    companion_artifacts,
    docker_names,
    make_run_id,
    monotonic_ms,
    report_metadata,
    write_json_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization uninstall-plan")
    parser.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_UNINSTALL_PLAN_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("uninstall-plan")
    running_containers = docker_names()
    affected_containers = [name for name in BASELINE_CONTAINERS if name in running_containers]
    support_surface = adapter_support_surface(args.adapter_url)

    report = {
        **report_metadata("ov-enterprise-uninstall-plan", run_id, started_ms),
        "status": "pass",
        "summary": {
            "containers_seen": affected_containers,
            "plugin_dir_exists": args.plugin_dir.exists(),
            "archive_root_exists": args.archive_root.exists(),
        },
        "support_surface": support_surface,
        "companion_artifacts": companion_artifacts(),
        "plan": [
            {
                "step": 1,
                "title": "Create a backup",
                "required": True,
                "details": "Run ov_enterprise_backup.py --execute and retain the snapshot path before any uninstall action.",
            },
            {
                "step": 2,
                "title": "Stop OpenViking-related containers",
                "required": True,
                "details": affected_containers,
            },
            {
                "step": 3,
                "title": "Disable or remove the memory-openviking plugin entry",
                "required": True,
                "details": str(args.plugin_dir),
            },
            {
                "step": 4,
                "title": "Archive runtime data instead of hard-deleting it",
                "required": True,
                "details": str(args.archive_root),
            },
            {
                "step": 5,
                "title": "Run doctor and verify after rollback or reinstall",
                "required": True,
                "details": "Use the formalized tools to confirm the environment returns to a supported state.",
            },
        ],
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
