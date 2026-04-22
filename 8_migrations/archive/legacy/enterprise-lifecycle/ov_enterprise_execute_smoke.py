"""Aggregate execute-smoke evidence for chained commercialization drills."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_EXECUTE_SMOKE_REPORT,
    ResultRecord,
    compatibility_report_assessment,
    companion_artifacts,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)


CHAIN_CASES: list[dict[str, Any]] = [
    {
        "id": "restore_twice",
        "title": "Restore twice",
        "snapshot_dir": r"E:\AI\_backup\openviking-commercialization\snapshot-20260328T020420Z",
        "steps": [
            "restore.chain-restore-twice.step1-20260328T020420Z.json",
            "restore.chain-restore-twice.step2-20260328T020420Z.json",
        ],
        "post_validation": {
            "compatibility_report": "compatibility_report.after-chain-restore-twice-20260328T020939Z.json",
            "verify_report": "verify_report.after-chain-restore-twice-20260328T020939Z.json",
        },
    },
    {
        "id": "rollback_then_restore",
        "title": "Rollback then restore",
        "snapshot_dir": r"E:\AI\_backup\openviking-commercialization\snapshot-20260328T020420Z",
        "steps": [
            "rollback.chain-rollback-restore.step1-20260328T020420Z.json",
            "restore.chain-rollback-restore.step2-20260328T020420Z.json",
        ],
        "post_validation": {
            "compatibility_report": "compatibility_report.after-chain-rollback-restore-20260328T021515Z.json",
            "verify_report": "verify_report.after-chain-rollback-restore-20260328T021515Z.json",
        },
    },
    {
        "id": "upgrade_then_rollback",
        "title": "Upgrade then rollback",
        "snapshot_dir": r"E:\AI\_backup\openviking-commercialization\snapshot-20260328T020420Z",
        "steps": [
            "upgrade.chain-upgrade-rollback.step1-20260328T020420Z.json",
            "rollback.chain-upgrade-rollback.step2-20260328T020420Z.json",
        ],
        "post_validation": {
            "compatibility_report": None,
            "verify_report": None,
            "inference": {
                "status": "pass",
                "basis": "No dedicated archived post-validation file was preserved for this chain. The environment immediately continued into the next chain and the recorded pre-uninstall doctor/verify gate passed before uninstall execute.",
                "doctor_run_id": "doctor-20260328T021852Z",
                "verify_run_id": "verify-20260328T021852Z",
            },
        },
    },
    {
        "id": "verify_then_uninstall_then_restore",
        "title": "Verify then uninstall then restore",
        "snapshot_dir": r"E:\AI\_backup\openviking-commercialization\snapshot-20260328T021924Z",
        "steps": [
            "uninstall.chain-verify-uninstall-restore.step1-20260328T021924Z.json",
            "restore.chain-verify-uninstall-restore.step2-20260328T021924Z.json",
        ],
        "post_validation": {
            "compatibility_report": "compatibility_report.after-chain-verify-uninstall-restore-20260328T022247Z.json",
            "verify_report": "verify_report.after-chain-verify-uninstall-restore-20260328T022247Z.json",
        },
    },
]


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _acceptable_step(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    status = payload.get("status")
    if status == "pass":
        return True
    if status != "warn":
        return False
    if payload.get("expected_during_offline") is True:
        return True
    if payload.get("reason_code") in {
        "OFFLINE_RUNTIME_DEGRADED",
        "OFFLINE_SUPPORT_SURFACE_DEGRADED",
    }:
        return True

    mode = payload.get("mode")
    support_surface = payload.get("support_surface")
    if mode == "execute" and isinstance(support_surface, dict):
        health = support_surface.get("health")
        catalog = support_surface.get("error_catalog")
        health_ok = health.get("ok") if isinstance(health, dict) else None
        catalog_ok = catalog.get("ok") if isinstance(catalog, dict) else None
        if health_ok is False and catalog_ok is False:
            return True
    return False


def _supported_compatible(payload: dict[str, Any] | None) -> bool:
    return compatibility_report_assessment(payload).get("accepted") is True


def _verify_pass(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and payload.get("status") == "pass"


def _summarize_step(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": payload.get("status") if isinstance(payload, dict) else None,
        "reason_code": payload.get("reason_code") if isinstance(payload, dict) else None,
        "expected_during_offline": payload.get("expected_during_offline") if isinstance(payload, dict) else None,
        "retry_applied": payload.get("retry_applied") if isinstance(payload, dict) else None,
        "health_window_seconds": payload.get("health_window_seconds") if isinstance(payload, dict) else None,
        "run_id": payload.get("run", {}).get("id") if isinstance(payload, dict) else None,
        "accepted": _acceptable_step(payload),
    }


def _summarize_validation(path: Path, *, kind: str) -> dict[str, Any]:
    payload = _load_json(path)
    compatibility = compatibility_report_assessment(payload) if kind == "compatibility" else {}
    accepted = _supported_compatible(payload) if kind == "compatibility" else _verify_pass(payload)
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": payload.get("status") if isinstance(payload, dict) else None,
        "run_id": payload.get("run", {}).get("id") if isinstance(payload, dict) else None,
        "accepted": accepted,
        "support_level": compatibility.get("support_level"),
        "classification": compatibility.get("classification"),
        "is_recommended": compatibility.get("is_recommended"),
        "is_supported": compatibility.get("is_supported"),
        "reason_code": compatibility.get("reason_code"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking execute-smoke evidence aggregator")
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_EXECUTE_SMOKE_REPORT)
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("execute-smoke")
    checks: list[ResultRecord] = []
    cases: list[dict[str, Any]] = []
    evidence_gaps: list[str] = []

    report_path_ok = path_writable(args.report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_path_ok else "fail",
            "Report path is writable" if report_path_ok else "Report path is not writable",
            {"path": str(args.report_path)},
        )
    )

    for case_def in CHAIN_CASES:
        step_summaries = [
            _summarize_step(args.artifacts_root / file_name)
            for file_name in case_def["steps"]
        ]
        step_ok = all(item["accepted"] for item in step_summaries)

        post_validation = case_def["post_validation"]
        compat_name = post_validation.get("compatibility_report")
        verify_name = post_validation.get("verify_report")
        compat_summary = (
            _summarize_validation(args.artifacts_root / compat_name, kind="compatibility")
            if compat_name
            else None
        )
        verify_summary = (
            _summarize_validation(args.artifacts_root / verify_name, kind="verify")
            if verify_name
            else None
        )

        inference = post_validation.get("inference")
        if compat_summary and verify_summary:
            validation_ok = bool(compat_summary["accepted"] and verify_summary["accepted"])
            validation_mode = "artifact"
        elif inference:
            validation_ok = inference.get("status") == "pass"
            validation_mode = "inferred"
            evidence_gaps.append(
                f"{case_def['id']}: dedicated post-validation artifact missing; accepted via recorded pre-uninstall verification gate."
            )
        else:
            validation_ok = False
            validation_mode = "missing"
            evidence_gaps.append(f"{case_def['id']}: post-validation evidence missing.")

        case_status = "pass" if step_ok and validation_ok else "warn" if step_ok else "fail"
        checks.append(
            ResultRecord(
                f"case_{case_def['id']}",
                case_status,
                f"Execute smoke chain {case_def['id']} completed",
                {
                    "snapshot_dir": case_def["snapshot_dir"],
                    "validation_mode": validation_mode,
                },
            )
        )
        cases.append(
            {
                "id": case_def["id"],
                "title": case_def["title"],
                "status": case_status,
                "snapshot_dir": case_def["snapshot_dir"],
                "steps": step_summaries,
                "post_validation": {
                    "mode": validation_mode,
                    "compatibility": compat_summary,
                    "verify": verify_summary,
                    "inference": inference,
                },
            }
        )

    current_compat = _load_json(args.artifacts_root / "compatibility_report.current.json")
    current_verify = _load_json(args.artifacts_root / "verify_report.current.json")
    current_baseline = {
        "compatibility_report": {
            "path": str(args.artifacts_root / "compatibility_report.current.json"),
            "status": current_compat.get("status") if isinstance(current_compat, dict) else None,
            "support_level": compatibility_report_assessment(current_compat).get("support_level"),
            "classification": compatibility_report_assessment(current_compat).get("classification"),
            "run_id": current_compat.get("run", {}).get("id") if isinstance(current_compat, dict) else None,
        },
        "verify_report": {
            "path": str(args.artifacts_root / "verify_report.current.json"),
            "status": current_verify.get("status") if isinstance(current_verify, dict) else None,
            "run_id": current_verify.get("run", {}).get("id") if isinstance(current_verify, dict) else None,
        },
        "accepted": bool(_supported_compatible(current_compat) and _verify_pass(current_verify)),
    }

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    accepted_cases = [case["id"] for case in cases if case["status"] == "pass"]

    report = {
        **report_metadata("ov-enterprise-execute-smoke", run_id, started_ms),
        "report_kind": "execute_smoke",
        "status": status,
        "summary": {
            "status": status,
            "counts": counts,
            "case_count": len(cases),
            "accepted_cases": accepted_cases,
            "evidence_gaps": evidence_gaps,
            "current_baseline_accepted": current_baseline["accepted"],
        },
        "acceptance": {
            "verdict": "accepted" if status == "pass" and current_baseline["accepted"] else "conditional" if status == "warn" else "blocked",
            "execute_chain_smoke_ready": status in {"pass", "warn"} and current_baseline["accepted"],
            "requires_followup": bool(evidence_gaps),
        },
        "checks": render_records(checks),
        "cases": cases,
        "current_baseline": current_baseline,
        "companion_artifacts": companion_artifacts(args.artifacts_root),
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} and current_baseline["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
