"""Emit the current Phase 2 reserved field contract as a delivery artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ov_enterprise_common import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_PHASE2_RESERVED_FIELDS_REPORT,
    ResultRecord,
    make_run_id,
    monotonic_ms,
    path_writable,
    phase2_reserved_field_contract,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the OpenViking Phase 2 reserved field contract artifact")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_PHASE2_RESERVED_FIELDS_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("phase2-fields")
    checks: list[ResultRecord] = []

    report_ok = path_writable(args.report_path)
    artifact_root_ok = path_writable(args.artifact_root / ".probe")
    checks.extend(
        [
            ResultRecord(
                "report_path",
                "pass" if report_ok else "fail",
                "Report path is writable" if report_ok else "Report path is not writable",
                {"path": str(args.report_path)},
            ),
            ResultRecord(
                "artifact_root",
                "pass" if artifact_root_ok else "fail",
                "Artifact root is writable" if artifact_root_ok else "Artifact root is not writable",
                {"path": str(args.artifact_root)},
            ),
        ]
    )

    contract = phase2_reserved_field_contract()
    contract["generated_from"] = {
        "artifact_root": str(args.artifact_root),
        "report_path": str(args.report_path),
        "surfaces": [
            "ov_enterprise_tenant_registry.py",
            "ov_enterprise_context_kernel.py",
            "ov_enterprise_context_package_kernel.py",
            "ov_enterprise_context_snapshot_kernel.py",
            "ov_enterprise_package_assembler.py",
            "ov_enterprise_installer_scaffold.py",
            "ov_enterprise_runtime_manager.py",
            "ov_enterprise_tool_registry.py",
        ],
    }
    contract["current_surfaces"] = {
        "registry_root": {
            "fields": ["instance_id", "host_mode"],
            "notes": ["shared-runtime root fields already active in Phase 1"],
        },
        "tenant_record": {
            "fields": ["instance_id", "source_instance_id", "migration_state"],
            "notes": ["migration_state is reserved and defaults to null"],
        },
        "context_package": {
            "fields": ["source_instance_id", "target_instance", "host_mode", "migration_state"],
            "compatibility_aliases": ["target_instance_id"],
        },
        "delivery_manifest": {
            "fields": ["instance_id", "host_mode", "migration_state_enums"],
        },
        "cli_and_mcp_inputs": {
            "fields": ["target_instance"],
            "notes": ["accepted as a reserved hint, not enforced by the current control plane"],
        },
    }

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-phase2-reserved-fields", run_id, started_ms),
        "report_kind": "phase2_reserved_fields_contract",
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "canonical_field_count": len(contract.get("canonical_fields", {})),
            "compatibility_alias_count": len(contract.get("compatibility_aliases", {})),
        },
        "checks": render_records(checks),
        "contract": contract,
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
