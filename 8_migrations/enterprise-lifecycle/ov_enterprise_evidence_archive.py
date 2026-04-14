"""Archive the current delivery evidence bundle into a versioned snapshot directory."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_DELIVERY_EVIDENCE_ARCHIVE_REPORT,
    DEFAULT_DELIVERY_EVIDENCE_ARCHIVE_ROOT,
    DEFAULT_DELIVERY_EVIDENCE_BUNDLE_REPORT,
    ResultRecord,
    json_load,
    make_run_id,
    monotonic_ms,
    path_writable,
    render_records,
    report_metadata,
    result_counts,
    write_json_report,
)


def _bucket_for_path(path: Path) -> str:
    normalized = str(path).lower()
    if "\\artifacts\\" in normalized or normalized.endswith("\\artifacts"):
        return "formal-artifacts"
    if "tenant-phase1-smoke" in normalized:
        return "runtime-smoke"
    if "tenant-phase1-execute-verify-v4" in normalized:
        return "runtime-execute"
    return "external"


def _copy_artifact(source: Path, archive_dir: Path) -> dict[str, Any]:
    bucket = _bucket_for_path(source)
    target_dir = archive_dir / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        stem = source.stem
        suffix = source.suffix
        counter = 1
        while target.exists():
            target = target_dir / f"{stem}-{counter}{suffix}"
            counter += 1
    shutil.copy2(source, target)
    return {
        "source_path": str(source),
        "archived_path": str(target),
        "bucket": bucket,
        "size_bytes": target.stat().st_size,
    }


def _collect_source_paths(bundle_payload: dict[str, Any], bundle_path: Path) -> list[Path]:
    ordered: list[str] = [str(bundle_path)]
    artifacts = bundle_payload.get("artifacts")
    if isinstance(artifacts, dict):
        ordered.extend(str(value) for value in artifacts.values() if isinstance(value, str))
    checks = bundle_payload.get("checks")
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict):
                continue
            for value in item.get("artifacts", []):
                if isinstance(value, str):
                    ordered.append(value)
    seen: set[str] = set()
    paths: list[Path] = []
    for raw in ordered:
        if raw in seen:
            continue
        seen.add(raw)
        paths.append(Path(raw))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive the current OpenViking delivery evidence bundle")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--bundle-path", type=Path, default=DEFAULT_DELIVERY_EVIDENCE_BUNDLE_REPORT)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_DELIVERY_EVIDENCE_ARCHIVE_ROOT)
    parser.add_argument("--label")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_DELIVERY_EVIDENCE_ARCHIVE_REPORT)
    parser.add_argument("--execute", action="store_true", help="Actually copy the evidence artifacts into a versioned archive directory")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("evidence-archive")
    checks: list[ResultRecord] = []

    report_ok = path_writable(args.report_path)
    archive_root_ok = path_writable(args.archive_root / ".probe")
    bundle_exists = args.bundle_path.exists()

    checks.extend(
        [
            ResultRecord(
                "report_path",
                "pass" if report_ok else "fail",
                "Report path is writable" if report_ok else "Report path is not writable",
                {"path": str(args.report_path)},
            ),
            ResultRecord(
                "archive_root",
                "pass" if archive_root_ok else "fail",
                "Archive root is writable" if archive_root_ok else "Archive root is not writable",
                {"path": str(args.archive_root)},
            ),
            ResultRecord(
                "bundle_path",
                "pass" if bundle_exists else "fail",
                "Delivery evidence bundle exists" if bundle_exists else "Delivery evidence bundle is missing",
                {"path": str(args.bundle_path)},
            ),
        ]
    )

    if bundle_exists:
        bundle_payload = json_load(args.bundle_path)
        source_paths = _collect_source_paths(bundle_payload, args.bundle_path)
    else:
        bundle_payload = {}
        source_paths = []

    existing_sources = [path for path in source_paths if path.exists()]
    missing_sources = [path for path in source_paths if not path.exists()]
    checks.append(
        ResultRecord(
            "bundle_sources",
            "pass" if not missing_sources else "warn",
            "All bundle source artifacts are present" if not missing_sources else "Some bundle source artifacts are missing",
            {
                "present_count": len(existing_sources),
                "missing_count": len(missing_sources),
                "missing_paths": [str(path) for path in missing_sources],
            },
        )
    )

    stamp = run_id.split("-", 2)[-1]
    archive_name = f"evidence-{stamp}"
    if args.label:
        archive_name = f"{archive_name}-{args.label}"
    archive_dir = args.archive_root / archive_name

    archived_files: list[dict[str, Any]] = []
    manifest_path = archive_dir / "archive.manifest.json"
    if args.execute and not any(record.status == "fail" for record in checks):
        archive_dir.mkdir(parents=True, exist_ok=False)
        for source in existing_sources:
            archived_files.append(_copy_artifact(source, archive_dir))
        manifest = {
            "schema_version": "1.0",
            "report_kind": "delivery_evidence_archive_manifest",
            "archive_name": archive_name,
            "bundle_path": str(args.bundle_path),
            "source_artifact_count": len(existing_sources),
            "archived_files": archived_files,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checks.append(
            ResultRecord(
                "archive_execute",
                "pass",
                "Delivery evidence archive created",
                {"archive_dir": str(archive_dir), "file_count": len(archived_files), "manifest_path": str(manifest_path)},
            )
        )
    elif args.execute:
        checks.append(ResultRecord("archive_execute", "blocked", "Evidence archive blocked by precheck failure"))
    else:
        checks.append(
            ResultRecord(
                "archive_execute",
                "skip",
                "Dry-run only; no evidence archive created",
                {"archive_dir": str(archive_dir), "planned_file_count": len(existing_sources)},
            )
        )

    counts = result_counts(checks)
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        **report_metadata("ov-enterprise-evidence-archive", run_id, started_ms),
        "report_kind": "delivery_evidence_archive",
        "status": status,
        "mode": "execute" if args.execute else "dry-run",
        "summary": {
            "status": status,
            "counts": counts,
            "archive_name": archive_name,
            "planned_file_count": len(existing_sources),
            "missing_file_count": len(missing_sources),
        },
        "inputs": {
            "artifact_root": str(args.artifact_root),
            "bundle_path": str(args.bundle_path),
            "archive_root": str(args.archive_root),
            "label": args.label,
        },
        "checks": render_records(checks),
        "archive": {
            "archive_dir": str(archive_dir),
            "manifest_path": str(manifest_path),
            "archived_files": archived_files,
        },
        "bundle_artifacts": {
            "existing_sources": [str(path) for path in existing_sources],
            "missing_sources": [str(path) for path in missing_sources],
        },
        "report_path": str(args.report_path),
    }
    write_json_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
