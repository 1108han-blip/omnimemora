"""Low-risk backup tool for OpenViking commercialization assets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_BACKUP_REPORT,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_MEMORY_ADAPTER_DIR,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_OPENCLAW_CONFIG_DIR,
    DEFAULT_OPENVIKING_SOURCE,
    DEFAULT_PLUGIN_DIR,
    adapter_support_surface,
    companion_artifacts,
    copy_path,
    make_run_id,
    monotonic_ms,
    report_metadata,
    write_json_report,
)


def _default_items() -> list[tuple[str, Path]]:
    return [
        ("openclaw_config", DEFAULT_OPENCLAW_CONFIG),
        ("openclaw_config_dir", DEFAULT_OPENCLAW_CONFIG_DIR),
        ("memory_adapter_dir", DEFAULT_MEMORY_ADAPTER_DIR),
        ("plugin_dir", DEFAULT_PLUGIN_DIR),
        ("commercialization_examples", DEFAULT_OPENVIKING_SOURCE / "examples" / "commercialization"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization backup")
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_BACKUP_REPORT)
    parser.add_argument("--execute", action="store_true", help="Actually create the backup snapshot")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("backup")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = args.backup_root / f"snapshot-{stamp}"
    manifest_path = snapshot_dir / "manifest.json"
    items: list[dict[str, str | bool]] = []
    support_surface = adapter_support_surface(args.adapter_url)

    if args.execute:
        snapshot_dir.mkdir(parents=True, exist_ok=False)

    for item_id, source in _default_items():
        exists = source.exists()
        target = snapshot_dir / item_id
        record = {
            "id": item_id,
            "source": str(source),
            "target": str(target),
            "exists": exists,
            "copied": False,
        }
        if args.execute and exists:
            copy_path(source, target)
            record["copied"] = True
        items.append(record)

    manifest = {
        **report_metadata("ov-enterprise-backup", run_id, started_ms),
        "status": "pass",
        "mode": "execute" if args.execute else "dry-run",
        "snapshot_dir": str(snapshot_dir),
        "adapter_url": args.adapter_url,
        "items": items,
        "support_surface": support_surface,
        "companion_artifacts": companion_artifacts(),
        "report_path": str(args.report_path),
    }
    if args.execute:
        write_json_report(manifest_path, manifest)
    write_json_report(args.report_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
