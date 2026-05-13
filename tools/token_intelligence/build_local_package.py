#!/usr/bin/env python3
"""Build a lightweight Token Intelligence local beta package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "5_connectors" / "adapter" / "application" / "token_intelligence"
WORKER_TEMPLATE = REPO_ROOT / "6_console" / "control-entry" / "worker.js"
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "omnimemora-token-intelligence-build"
DEFAULT_VERSION = "0.1.0-beta.2"
DEFAULT_CHANNEL = "beta"
PRODUCT = "omnimemora-token-intelligence"
DEFAULT_CLOUDFLARE_ACCOUNT_ID = "066fdd55ca132844a1a136e3f90ae0aa"
DEFAULT_RELEASE_BUCKET = "doloclaw-assets-v2"
DEFAULT_CONTROL_ENTRY_WORKER = "omnimemora-control-entry"


def main() -> int:
    args = _parser().parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    version = str(args.version)
    package_name = f"omni-token-audit-{version}-local"
    stage_dir = output_dir / package_name
    zip_path = output_dir / f"{package_name}.zip"
    checksum_path = output_dir / "SHA256SUMS.txt"
    metadata_path = output_dir / "latest.local.json"
    release_dir = output_dir / "release" / "omnimemora" / "token-intelligence" / version

    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    if release_dir.exists():
        shutil.rmtree(release_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True)

    _copy_module(stage_dir / "token_intelligence")
    _write_launcher(stage_dir / "omni-token-audit")
    _write_text(stage_dir / "VERSION.txt", _version_text(version, args.channel))
    _write_text(stage_dir / "README.txt", _readme_text(version))

    if zip_path.exists():
        zip_path.unlink()
    _zip_dir(stage_dir, zip_path)
    digest = _sha256(zip_path)
    metadata = _metadata(version, args.channel, zip_path.name, digest)
    _write_text(checksum_path, f"{digest}  {zip_path.name}\n")
    _write_json(metadata_path, metadata)
    _write_release_layout(release_dir, zip_path, digest, metadata, version)

    payload = {
        "zip": str(zip_path),
        "sha256": digest,
        "metadata": str(metadata_path),
        "release_dir": str(release_dir),
    }
    if args.dry_run_publish_plan:
        payload["publish_plan"] = _dry_run_publish_plan(release_dir, version)
    if args.preflight_release_gate:
        publish_plan = payload.get("publish_plan") or _dry_run_publish_plan(release_dir, version)
        payload["publish_plan"] = publish_plan
        payload["preflight"] = _preflight_release_gate(version, publish_plan)

    print(json.dumps(payload, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_local_package.py")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument(
        "--dry-run-publish-plan",
        action="store_true",
        help="print the future R2/Worker publication plan without uploading or deploying",
    )
    parser.add_argument(
        "--preflight-release-gate",
        action="store_true",
        help="print local cloud-publication readiness checks without uploading or deploying",
    )
    return parser


def _copy_module(destination: Path) -> None:
    if not MODULE_DIR.exists():
        raise FileNotFoundError(str(MODULE_DIR))
    shutil.copytree(
        MODULE_DIR,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )


def _write_launcher(path: Path) -> None:
    _write_text(
        path,
        "#!/usr/bin/env python3\n"
        "from token_intelligence.cli import main\n"
        "raise SystemExit(main())\n",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _version_text(version: str, channel: str) -> str:
    return f"PRODUCT={PRODUCT}\nVERSION={version}\nCHANNEL={channel}\n"


def _readme_text(version: str) -> str:
    return f"""DoloToken {version}

OmniMemora Token Intelligence Lite internal package.
This is an unsigned controlled-beta local proxy package.
Source code is not included in this package.

What it does:
  - runs a localhost OpenAI-compatible audit proxy
  - forwards requests to your configured upstream provider or relay
  - records token-flow receipts without storing raw prompts by default
  - labels reported token usage separately from local estimates
  - summarizes local receipts, top requests, and potential token savings

Current version boundary:
  - audits LLM requests only when they pass through this local proxy
  - treats provider-reported or relay-reported usage as the highest-confidence count
  - uses local estimates only when upstream usage is missing or for comparison
  - does not present local estimates as provider billing truth
  - reports usage differences neutrally as normal, warning, unexplained, estimated-only, or not-applicable

Quickstart:
  ./omni-token-audit init
  # Edit ~/.omnimemora/token-intelligence/config.json:
  #   upstream.base_url = your upstream /v1 endpoint
  #   upstream.api_key_env = the environment variable that contains your API key
  export OMNI_AUDIT_UPSTREAM_API_KEY="your-upstream-key"
  ./omni-token-audit doctor
  ./omni-token-audit proxy start

Point a compatible client at:
  OPENAI_BASE_URL=http://127.0.0.1:18081/v1
  OPENAI_API_KEY can be any placeholder accepted by your client

Optional attach helper:
  ./omni-token-audit attach openclaw --with-launcher
  ./omni-token-audit detach openclaw

Reports:
  ./omni-token-audit report summary
  ./omni-token-audit report top-requests
  ./omni-token-audit report potential-savings

Updates:
  ./omni-token-audit update check

Verify downloads with SHA256SUMS.txt before replacing this package.

During unsigned macOS beta distribution, Privacy & Security / Gatekeeper manual approval may be required.
No silent install or self-replacement is performed by this package candidate.
"""


def _metadata(version: str, channel: str, zip_name: str, digest: str) -> dict[str, object]:
    return {
        "product": PRODUCT,
        "channel": channel,
        "version": version,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "minimum_supported_version": version,
        "force_update": False,
        "platforms": {
            "darwin-arm64": {
                "download_url": f"https://doloclaw.com/download/file/token-intelligence/{zip_name}",
                "sha256": digest,
                "unsigned_beta": True,
                "gatekeeper_note": "Manual Privacy & Security approval may be required during beta.",
            }
        },
    }


def _write_release_layout(
    release_dir: Path,
    zip_path: Path,
    digest: str,
    metadata: dict[str, object],
    version: str,
) -> None:
    release_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, release_dir / zip_path.name)
    _write_text(release_dir / "SHA256SUMS.txt", f"{digest}  {zip_path.name}\n")
    _write_json(release_dir / "latest.json", metadata)
    _write_json(release_dir / f"{version}.json", metadata)


def _dry_run_publish_plan(release_dir: Path, version: str) -> dict[str, object]:
    upload_files = []
    for path in sorted(release_dir.iterdir()):
        if not path.is_file():
            continue
        upload_files.append(
            {
                "path": str(path),
                "r2_key": f"omnimemora/token-intelligence/{version}/{path.name}",
                "content_type": _content_type(path.name),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "dry_run": True,
        "mutates_cloud": False,
        "product": PRODUCT,
        "version": version,
        "release_dir": str(release_dir),
        "r2_bucket_env": "OMNIMEMORA_RELEASE_BUCKET",
        "r2_prefix": f"omnimemora/token-intelligence/{version}/",
        "worker_name_env": "OMNIMEMORA_CONTROL_ENTRY_WORKER",
        "worker_expected_token_intelligence_version": version,
        "worker_routes": {
            "download": f"/download/file/token-intelligence/omni-token-audit-{version}-local.zip",
            "latest_manifest": "/releases/token-intelligence/latest.json",
            "version_manifest": f"/releases/token-intelligence/{version}.json",
        },
        "upload_files": upload_files,
    }


def _preflight_release_gate(version: str, publish_plan: dict[str, object]) -> dict[str, object]:
    worker_version = _worker_token_intelligence_version()
    credential_env = [
        "CLOUDFLARE_AUTH_EMAIL",
        "CLOUDFLARE_GLOBAL_API_KEY",
    ]
    credential_presence = {name: _env_present(name) for name in credential_env}
    target_config = {
        "CLOUDFLARE_ACCOUNT_ID": _target_config("CLOUDFLARE_ACCOUNT_ID", DEFAULT_CLOUDFLARE_ACCOUNT_ID),
        "OMNIMEMORA_RELEASE_BUCKET": _target_config("OMNIMEMORA_RELEASE_BUCKET", DEFAULT_RELEASE_BUCKET),
        "OMNIMEMORA_CONTROL_ENTRY_WORKER": _target_config(
            "OMNIMEMORA_CONTROL_ENTRY_WORKER",
            DEFAULT_CONTROL_ENTRY_WORKER,
        ),
    }
    upload_files = publish_plan.get("upload_files")
    upload_count = len(upload_files) if isinstance(upload_files, list) else 0
    required_files_present = upload_count == 4
    worker_version_matches = worker_version == version
    credentials_ready = all(credential_presence.values())
    target_config_ready = all(item["value_present"] for item in target_config.values())
    return {
        "dry_run": True,
        "mutates_cloud": False,
        "version": version,
        "worker_template": str(WORKER_TEMPLATE),
        "worker_token_intelligence_version": worker_version,
        "worker_version_matches": worker_version_matches,
        "credential_env": credential_presence,
        "credentials_ready": credentials_ready,
        "target_config": target_config,
        "target_config_ready": target_config_ready,
        "upload_file_count": upload_count,
        "required_files_present": required_files_present,
        "live_route_check_included": False,
        "ready_for_manual_publish": bool(
            worker_version_matches and credentials_ready and target_config_ready and required_files_present
        ),
        "next_manual_checks": [
            "Confirm live token-intelligence routes are still expected before upload.",
            "Upload the files listed in publish_plan only after operator approval.",
            "Deploy the Worker only after R2 object availability is verified.",
        ],
    }


def _worker_token_intelligence_version() -> str:
    try:
        raw = WORKER_TEMPLATE.read_text(encoding="utf-8")
    except Exception:
        return ""
    match = re.search(r'TOKEN_INTELLIGENCE_VERSION\s*=\s*"([^"]+)"', raw)
    return match.group(1) if match else ""


def _env_present(name: str) -> bool:
    return bool(_env_value(name))


def _env_value(name: str) -> str:
    if os.getenv(name, "").strip():
        return os.getenv(name, "").strip()
    try:
        value = subprocess.run(
            ["launchctl", "getenv", name],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        value = ""
    return value.strip()


def _target_config(name: str, default: str) -> dict[str, object]:
    value = _env_value(name)
    source = "env" if value else "default"
    resolved = value or default
    return {
        "source": source,
        "value": resolved,
        "value_present": bool(resolved),
    }


def _content_type(name: str) -> str:
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    if name.endswith(".txt"):
        return "text/plain; charset=utf-8"
    if name.endswith(".zip"):
        return "application/zip"
    return "application/octet-stream"


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                arcname = str(path.relative_to(source_dir.parent))
                info = zipfile.ZipInfo.from_file(path, arcname=arcname)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
                archive.writestr(info, path.read_bytes())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
