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
from .local_proxy import VERSION, serve_forever


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

    receipt_parser = subparsers.add_parser("receipt", help="receipt commands are reserved for TI-001D")
    receipt_subparsers = receipt_parser.add_subparsers(dest="receipt_command")
    receipt_parser.set_defaults(func=_cmd_receipt_not_implemented)

    get_parser = receipt_subparsers.add_parser("get", help="reserved")
    get_parser.add_argument("audit_id")
    get_parser.set_defaults(func=_cmd_receipt_not_implemented)

    export_parser = receipt_subparsers.add_parser("export", help="reserved")
    export_parser.add_argument("audit_id")
    export_parser.add_argument("--format", default="json", choices=["json"])
    export_parser.set_defaults(func=_cmd_receipt_not_implemented)

    update_parser = subparsers.add_parser("update", help="update commands are reserved for TI-001E")
    update_subparsers = update_parser.add_subparsers(dest="update_command")
    update_parser.set_defaults(func=_cmd_update_not_implemented)

    check_parser = update_subparsers.add_parser("check", help="reserved")
    check_parser.set_defaults(func=_cmd_update_not_implemented)

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


def _cmd_receipt_not_implemented(args: argparse.Namespace) -> int:
    _ = args
    print("receipt commands are reserved for TI-001D", file=sys.stderr)
    return 2


def _cmd_update_not_implemented(args: argparse.Namespace) -> int:
    _ = args
    print("update check is reserved for TI-001E", file=sys.stderr)
    return 2


def _path_arg(value: str) -> Optional[Path]:
    return Path(value).expanduser() if value else None


if __name__ == "__main__":
    raise SystemExit(main())
