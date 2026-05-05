#!/usr/bin/env python3
"""Upload closed-beta artifacts to R2 and deploy the control-entry download page."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import boto3
from boto3.exceptions import S3UploadFailedError
import requests


ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "066fdd55ca132844a1a136e3f90ae0aa")
BUCKET = os.getenv("OMNIMEMORA_RELEASE_BUCKET", "doloclaw-assets-v2")
WORKER_NAME = os.getenv("OMNIMEMORA_CONTROL_ENTRY_WORKER", "omnimemora-control-entry")
SUPPORT_EMAIL = os.getenv("OMNIMEMORA_BETA_SUPPORT_EMAIL", "support@doloclaw.com")
API_BASE = "https://api.cloudflare.com/client/v4"
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
ROOT = Path(__file__).resolve().parents[2]
WORKER_TEMPLATE = ROOT.parents[1] / "6_console" / "control-entry" / "worker.js"


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        try:
            value = (
                subprocess.run(
                    ["launchctl", "getenv", name],
                    check=False,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            )
        except Exception:
            value = ""
    if not value:
        raise SystemExit(f"missing required env: {name}")
    return value


def cf_headers() -> dict[str, str]:
    return {
        "X-Auth-Email": require_env("CLOUDFLARE_AUTH_EMAIL"),
        "X-Auth-Key": require_env("CLOUDFLARE_GLOBAL_API_KEY"),
        "Content-Type": "application/json",
    }


def cf_request(method: str, path: str, **kwargs):
    response = requests.request(method, f"{API_BASE}{path}", headers=cf_headers(), timeout=30, **kwargs)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", False):
        raise RuntimeError(f"cloudflare api failed: {payload}")
    return payload["result"]


def create_r2_upload_token() -> tuple[str, str]:
    body = {
        "name": "omnimemora-beta-r2-upload",
        "policies": [
            {
                "effect": "allow",
                "resources": {
                    f"com.cloudflare.edge.r2.bucket.{ACCOUNT_ID}_default_{BUCKET}": "*"
                },
                "permission_groups": [
                    {"id": "6a018a9f2fc74eb6b293b0c548f38b39"},
                    {"id": "2efd5506f9c8494dacb1fa10a3e7d5b6"},
                ],
            }
        ],
    }
    result = cf_request("POST", "/user/tokens", data=json.dumps(body))
    return result["id"], result["value"]


def delete_token(token_id: str) -> None:
    try:
        cf_request("DELETE", f"/user/tokens/{token_id}")
    except Exception as exc:  # pragma: no cover - cleanup best effort
        print(f"warning: failed to delete temporary token {token_id}: {exc}", file=sys.stderr)


def upload_artifacts(package_version: str, token_id: str, token_value: str) -> None:
    secret = hashlib.sha256(token_value.encode()).hexdigest()
    client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=token_id,
        aws_secret_access_key=secret,
        region_name="auto",
    )

    release_dir = ROOT / "release" / package_version
    if not release_dir.exists():
        raise SystemExit(f"release directory missing: {release_dir}")

    upload_names = [
        f"OmniMemora-Desktop-{package_version}-darwin-arm64.dmg",
        "omnimemora-darwin-amd64.zip",
        "omnimemora-darwin-arm64.zip",
        "omnimemora-windows-amd64.zip",
        "SHA256SUMS.txt",
        "RELEASE_INDEX.txt",
        f"{package_version}.json",
        "latest.json",
    ]
    time.sleep(2)
    for name in upload_names:
        source = release_dir / name
        key = f"omnimemora/beta/{package_version}/{name}"
        extra = {"ContentType": "application/octet-stream"}
        if name.endswith(".txt"):
            extra = {"ContentType": "text/plain; charset=utf-8"}
        if name.endswith(".json"):
            extra = {"ContentType": "application/json; charset=utf-8"}
        last_exc = None
        for attempt in range(3):
            try:
                client.upload_file(str(source), BUCKET, key, ExtraArgs=extra)
                last_exc = None
                break
            except S3UploadFailedError as exc:
                last_exc = exc
                if "Unauthorized" not in str(exc) or attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        print(f"uploaded: {key}")


def deploy_worker(package_version: str) -> None:
    template = WORKER_TEMPLATE.read_text()
    script = (
        template.replace("__PACKAGE_VERSION__", package_version)
        .replace("__SUPPORT_EMAIL__", SUPPORT_EMAIL)
    )

    files = {
        "metadata": (None, json.dumps({"body_part": "script", "compatibility_date": "2026-04-23"}), "application/json"),
        "script": ("worker.js", script, "application/javascript"),
    }
    response = requests.put(
        f"{API_BASE}/accounts/{ACCOUNT_ID}/workers/scripts/{WORKER_NAME}",
        headers={
            "X-Auth-Email": require_env("CLOUDFLARE_AUTH_EMAIL"),
            "X-Auth-Key": require_env("CLOUDFLARE_GLOBAL_API_KEY"),
        },
        files=files,
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", False):
        raise RuntimeError(f"worker deploy failed: {payload}")
    print(f"deployed worker: {WORKER_NAME}")


def main() -> None:
    package_version = sys.argv[1] if len(sys.argv) > 1 else "1.0.0-beta.6"
    token_id, token_value = create_r2_upload_token()
    try:
        upload_artifacts(package_version, token_id, token_value)
        deploy_worker(package_version)
    finally:
        delete_token(token_id)


if __name__ == "__main__":
    main()
