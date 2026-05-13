#!/usr/bin/env python3
"""Build a lightweight Token Intelligence local beta package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "5_connectors" / "adapter" / "application" / "token_intelligence"
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "omnimemora-token-intelligence-build"
DEFAULT_VERSION = "0.1.0-dev"
DEFAULT_CHANNEL = "beta"
PRODUCT = "omnimemora-token-intelligence"


def main() -> int:
    args = _parser().parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    version = str(args.version)
    package_name = f"omni-token-audit-{version}-local"
    stage_dir = output_dir / package_name
    zip_path = output_dir / f"{package_name}.zip"
    checksum_path = output_dir / "SHA256SUMS.txt"
    metadata_path = output_dir / "latest.local.json"

    if stage_dir.exists():
        shutil.rmtree(stage_dir)
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
    _write_text(checksum_path, f"{digest}  {zip_path.name}\n")
    _write_json(metadata_path, _metadata(version, args.channel, zip_path.name, digest))

    print(json.dumps({"zip": str(zip_path), "sha256": digest, "metadata": str(metadata_path)}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_local_package.py")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
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
    return f"""OmniMemora Token Intelligence Lite {version}

This is an unsigned controlled-beta local proxy package.

Run:
  ./omni-token-audit init
  ./omni-token-audit proxy start --config ~/.omnimemora/token-intelligence/config.json

During unsigned macOS beta distribution, Privacy & Security / Gatekeeper manual approval may be required.
No automatic install or self-update is performed by this package candidate.
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


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir.parent))


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
