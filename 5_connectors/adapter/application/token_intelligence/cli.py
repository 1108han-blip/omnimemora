"""CLI skeleton for Token Intelligence Lite."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .config import default_config_path, load_config, write_default_config
from .ledger import get_audit_event, summarize_recent_events
from .local_proxy import VERSION, check_update_metadata, serve_forever
from .receipts import build_receipt
from .reports import build_potential_savings_report


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omni-token-audit")
    parser.set_defaults(func=_cmd_help)
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="write a default local config")
    init_parser.add_argument("--config", default="", help="config path; defaults to ~/.omnimemora/token-intelligence/config.json")
    init_parser.add_argument("--force", action="store_true", help="overwrite an existing config")
    init_parser.set_defaults(func=_cmd_init)

    version_parser = subparsers.add_parser("version", help="print CLI version")
    version_parser.set_defaults(func=_cmd_version)

    proxy_parser = subparsers.add_parser("proxy", help="manage the local proxy")
    proxy_subparsers = proxy_parser.add_subparsers(dest="proxy_command")
    proxy_parser.set_defaults(func=_cmd_help)

    start_parser = proxy_subparsers.add_parser("start", help="start the local proxy in the foreground")
    start_parser.add_argument("--config", default="", help="config path")
    start_parser.set_defaults(func=_cmd_proxy_start)

    status_parser = proxy_subparsers.add_parser("status", help="probe local proxy health")
    status_parser.add_argument("--config", default="", help="config path")
    status_parser.set_defaults(func=_cmd_proxy_status)

    receipt_parser = subparsers.add_parser("receipt", help="read local audit receipts")
    receipt_subparsers = receipt_parser.add_subparsers(dest="receipt_command")
    receipt_parser.set_defaults(func=_cmd_help)

    get_parser = receipt_subparsers.add_parser("get", help="print a local audit receipt")
    get_parser.add_argument("audit_id")
    get_parser.set_defaults(func=_cmd_receipt_get)

    export_parser = receipt_subparsers.add_parser("export", help="export a local audit receipt")
    export_parser.add_argument("audit_id")
    export_parser.add_argument("--format", default="json", choices=["json"])
    export_parser.set_defaults(func=_cmd_receipt_get)

    update_parser = subparsers.add_parser("update", help="check release metadata")
    update_subparsers = update_parser.add_subparsers(dest="update_command")
    update_parser.set_defaults(func=_cmd_update_not_implemented)

    check_parser = update_subparsers.add_parser("check", help="check product-owned release metadata")
    check_parser.add_argument("--config", default="", help="config path")
    check_parser.set_defaults(func=_cmd_update_check)

    report_parser = subparsers.add_parser("report", help="read local audit reports")
    report_subparsers = report_parser.add_subparsers(dest="report_command")
    report_parser.set_defaults(func=_cmd_help)

    summary_parser = report_subparsers.add_parser("summary", help="print bounded audit summary")
    summary_parser.add_argument("--limit", default="1000", help="recent event limit, max 1000")
    summary_parser.add_argument("--db", default="", help="optional audit sqlite path")
    summary_parser.set_defaults(func=_cmd_report_summary)

    savings_parser = report_subparsers.add_parser("potential-savings", help="print potential savings report")
    savings_parser.add_argument("--limit", default="1000", help="recent event limit, max 1000")
    savings_parser.add_argument("--db", default="", help="optional audit sqlite path")
    savings_parser.set_defaults(func=_cmd_report_potential_savings)

    return parser


def _cmd_help(args: argparse.Namespace) -> int:
    _ = args
    print("Run `omni-token-audit --help` for usage.")
    return 2


def _cmd_init(args: argparse.Namespace) -> int:
    path = write_default_config(_path_arg(args.config), overwrite=bool(args.force))
    print(json.dumps({"status": "created", "config_path": str(path)}, sort_keys=True))
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    _ = args
    print(VERSION)
    return 0


def _cmd_proxy_start(args: argparse.Namespace) -> int:
    config = load_config(_path_arg(args.config))
    local_proxy_config = config.to_local_proxy_config()
    print(
        json.dumps(
            {
                "status": "starting",
                "host": local_proxy_config.host,
                "port": local_proxy_config.port,
            },
            sort_keys=True,
        )
    )
    serve_forever(local_proxy_config)
    return 0


def _cmd_proxy_status(args: argparse.Namespace) -> int:
    config = load_config(_path_arg(args.config))
    url = f"http://{config.server.host}:{config.server.port}/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = response.read()
    except urllib.error.URLError as exc:
        print(json.dumps({"status": "unreachable", "url": url, "error": str(exc)}, sort_keys=True))
        return 1
    print(body.decode("utf-8"))
    return 0


def _cmd_receipt_get(args: argparse.Namespace) -> int:
    event = get_audit_event(args.audit_id)
    if event is None:
        print(json.dumps({"error": "audit_event_not_found", "audit_id": args.audit_id}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(build_receipt(event), ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_update_not_implemented(args: argparse.Namespace) -> int:
    _ = args
    print("Run `omni-token-audit update check --help` for usage.", file=sys.stderr)
    return 2


def _cmd_update_check(args: argparse.Namespace) -> int:
    config = load_config(_path_arg(args.config))
    payload = check_update_metadata(
        config.updates.metadata_url,
        channel=config.updates.channel,
        enabled=config.updates.enabled,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_report_summary(args: argparse.Namespace) -> int:
    payload = summarize_recent_events(path=_str_arg(args.db), limit=_limit_arg(args.limit))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_report_potential_savings(args: argparse.Namespace) -> int:
    summary = summarize_recent_events(path=_str_arg(args.db), limit=_limit_arg(args.limit))
    payload = build_potential_savings_report(summary)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _path_arg(value: str) -> Optional[Path]:
    return Path(value).expanduser() if value else None


def _str_arg(value: str) -> Optional[str]:
    return str(Path(value).expanduser()) if value else None


def _limit_arg(value: str) -> int:
    try:
        return max(1, min(int(value), 1000))
    except Exception:
        return 1000


if __name__ == "__main__":
    raise SystemExit(main())
