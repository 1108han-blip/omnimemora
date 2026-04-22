"""Shared helpers for OpenViking commercialization tools."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOOL_VERSION = "2026.03.28"

DEFAULT_WORK_ROOT = Path(os.getenv("OPENVIKING_WORK_ROOT", r"E:\AI"))
DEFAULT_ARTIFACT_ROOT = Path(
    os.getenv(
        "OPENVIKING_ARTIFACT_ROOT",
        r"E:\AI相关\Obsidian Vault\13 OpenViking商业项目\artifacts",
    )
)
DEFAULT_OPENCLAW_CONFIG = Path(
    os.getenv(
        "OPENVIKING_OPENCLAW_CONFIG",
        str(DEFAULT_WORK_ROOT / "docker-data" / "openclaw-config" / "openclaw.json"),
    )
)
DEFAULT_PLUGIN_DIR = Path(
    os.getenv(
        "OPENVIKING_PLUGIN_DIR",
        str(DEFAULT_WORK_ROOT / "openclaw" / "extensions" / "memory-openviking"),
    )
)
DEFAULT_OPENCLAW_CONFIG_DIR = Path(
    os.getenv(
        "OPENVIKING_OPENCLAW_CONFIG_DIR",
        str(DEFAULT_WORK_ROOT / "docker-data" / "openclaw-config"),
    )
)
DEFAULT_MEMORY_ADAPTER_DIR = Path(
    os.getenv(
        "OPENVIKING_MEMORY_ADAPTER_DIR",
        str(DEFAULT_WORK_ROOT / "docker-data" / "memory-adapter"),
    )
)
DEFAULT_OPENVIKING_SOURCE = Path(
    os.getenv(
        "OPENVIKING_SOURCE_ROOT",
        str(DEFAULT_WORK_ROOT / "OpenViking-main"),
    )
)
DEFAULT_ARCHIVE_ROOT = Path(
    os.getenv(
        "OPENVIKING_ARCHIVE_ROOT",
        str(DEFAULT_WORK_ROOT / "_archive"),
    )
)
DEFAULT_BACKUP_ROOT = Path(
    os.getenv(
        "OPENVIKING_BACKUP_ROOT",
        str(DEFAULT_WORK_ROOT / "_backup" / "openviking-commercialization"),
    )
)
DEFAULT_INSTANCE_ID = os.getenv("OPENVIKING_INSTANCE_ID", "main")
DEFAULT_HOST_MODE = os.getenv("OPENVIKING_HOST_MODE", "shared-multitenant")
PHASE2_RESERVED_MIGRATION_STATES = ("migrating_in", "migrating_out")
DEFAULT_TENANT_RUNTIME_ROOT = Path(
    os.getenv(
        "OPENVIKING_TENANT_RUNTIME_ROOT",
        str(DEFAULT_ARTIFACT_ROOT / "runtime"),
    )
)
DEFAULT_TENANT_REGISTRY_PATH = DEFAULT_TENANT_RUNTIME_ROOT / "registry" / "tenant.registry.json"
DEFAULT_TENANT_POLICY_PATH = DEFAULT_TENANT_RUNTIME_ROOT / "policies" / "tenant.policy.profiles.json"
DEFAULT_ADAPTER_URL = "http://localhost:18011"
DEFAULT_OPENVIKING_URL = "http://localhost:1933"
DEFAULT_VIKING_API_KEY = os.getenv("OPENVIKING_API_KEY", os.getenv("VIKING_API_KEY", ""))
DEFAULT_VIKING_MEMORY_NAMESPACE_ROOT = os.getenv(
    "OPENVIKING_VIKING_MEMORY_NAMESPACE_ROOT",
    "viking://resources/memory-adapter",
)
DEFAULT_EXPECTED_OPENCLAW_VERSION = "2026.3.14"
DEFAULT_SUPPORTED_OPENCLAW_VERSIONS = tuple(
    version.strip()
    for version in os.getenv("OPENVIKING_SUPPORTED_OPENCLAW_VERSIONS", "2026.3.24").split(",")
    if version.strip()
)
DEFAULT_EXPECTED_PLUGIN_BASE_URL = "http://127.0.0.1:18011"
DEFAULT_EXPECTED_AGENT_ID = "supervisor"
DEFAULT_MIN_PLUGIN_TIMEOUT_MS = 30000
DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS = 45.0
DEFAULT_EXECUTE_STARTUP_WAIT_SECONDS = 30.0
DEFAULT_EXECUTE_POLL_INTERVAL_SECONDS = 3.0

DEFAULT_COMPATIBILITY_REPORT = DEFAULT_ARTIFACT_ROOT / "compatibility_report.current.json"
DEFAULT_VERIFY_REPORT = DEFAULT_ARTIFACT_ROOT / "verify_report.current.json"
DEFAULT_INSTALL_CHECK_REPORT = DEFAULT_ARTIFACT_ROOT / "install_check.current.json"
DEFAULT_INSTALL_REPORT = DEFAULT_ARTIFACT_ROOT / "install.current.json"
DEFAULT_UPGRADE_REPORT = DEFAULT_ARTIFACT_ROOT / "upgrade.current.json"
DEFAULT_BACKUP_REPORT = DEFAULT_ARTIFACT_ROOT / "backup.current.json"
DEFAULT_RESTORE_REPORT = DEFAULT_ARTIFACT_ROOT / "restore.current.json"
DEFAULT_ROLLBACK_REPORT = DEFAULT_ARTIFACT_ROOT / "rollback.current.json"
DEFAULT_UNINSTALL_REPORT = DEFAULT_ARTIFACT_ROOT / "uninstall.current.json"
DEFAULT_UNINSTALL_PLAN_REPORT = DEFAULT_ARTIFACT_ROOT / "uninstall_plan.current.json"
DEFAULT_REHEARSAL_REPORT = DEFAULT_ARTIFACT_ROOT / "rehearsal.current.json"
DEFAULT_EXECUTE_WINDOW_REPORT = DEFAULT_ARTIFACT_ROOT / "execute_window.current.json"
DEFAULT_WINDOW_PACKET_REPORT = DEFAULT_ARTIFACT_ROOT / "window_packet.current.json"
DEFAULT_WINDOW_PACKET_VERIFY_REPORT = DEFAULT_ARTIFACT_ROOT / "window_packet_verify.current.json"
DEFAULT_EXECUTE_SMOKE_REPORT = DEFAULT_ARTIFACT_ROOT / "execute_smoke.current.json"
DEFAULT_RUNTIME_MANAGER_REPORT = DEFAULT_ARTIFACT_ROOT / "runtime_manager.current.json"
DEFAULT_INSTALLER_SCAFFOLD_REPORT = DEFAULT_ARTIFACT_ROOT / "installer_scaffold.current.json"
DEFAULT_PRODUCT_SHELL_ROOT = DEFAULT_ARTIFACT_ROOT / "product-shell"
DEFAULT_PACKAGE_ASSEMBLER_REPORT = DEFAULT_ARTIFACT_ROOT / "package_assembler.current.json"
DEFAULT_INSTALL_VALIDATOR_REPORT = DEFAULT_ARTIFACT_ROOT / "install_validator.current.json"
DEFAULT_PACKAGE_ROOT = DEFAULT_ARTIFACT_ROOT / "packages"
DEFAULT_MCP_INTERFACE_VALIDATION_REPORT = DEFAULT_ARTIFACT_ROOT / "mcp_interface_validation.current.json"
DEFAULT_PUBLIC_TOOL_CATALOG_REPORT = DEFAULT_ARTIFACT_ROOT / "public_tool_catalog.current.json"
DEFAULT_TENANT_SEARCH_POSTCHECK_VALIDATION_REPORT = DEFAULT_ARTIFACT_ROOT / "tenant_search_postcheck_validation.current.json"
DEFAULT_DELIVERY_EVIDENCE_BUNDLE_REPORT = DEFAULT_ARTIFACT_ROOT / "delivery_evidence_bundle.current.json"
DEFAULT_DELIVERY_EVIDENCE_ARCHIVE_ROOT = DEFAULT_ARTIFACT_ROOT / "delivery-evidence"
DEFAULT_DELIVERY_EVIDENCE_ARCHIVE_REPORT = DEFAULT_ARTIFACT_ROOT / "delivery_evidence_archive.current.json"
DEFAULT_PHASE2_RESERVED_FIELDS_REPORT = DEFAULT_ARTIFACT_ROOT / "phase2_reserved_fields.current.json"

BASELINE_CONTAINERS = [
    "openclaw-openclaw-gateway-1",
    "supervisor",
    "strategy-brain",
    "production-brain",
    "validator-brain",
    "exploration-brain",
    "memory-adapter",
    "openviking-server",
]
CRITICAL_CONTAINERS = [
    "openclaw-openclaw-gateway-1",
    "memory-adapter",
    "openviking-server",
]
RUNTIME_SENSITIVE_DIR_NAMES = {
    "logs",
    "runtime",
    "run",
    "lock",
    "locks",
    "cache",
    "tmp",
    "temp",
    "__pycache__",
}
RESTORE_POLICY_DEFAULT: dict[str, Any] = {
    "mode": "replace_path",
    "rule": "direct_replace",
    "allow_whitelist_restore": False,
    "excluded_names": [],
    "reason": "Default direct replacement policy.",
}
RESTORE_POLICY_TABLE: dict[str, dict[str, Any]] = {
    "openclaw_config_dir": {
        "mode": "sync_contents",
        "rule": "directory_overlay_with_runtime_exclusions",
        "allow_whitelist_restore": True,
        "excluded_names": sorted(RUNTIME_SENSITIVE_DIR_NAMES),
        "reason": "Do not hard-replace runtime-sensitive config directories during execute recovery.",
    }
}
DIRECTORY_RESTORE_POLICIES = RESTORE_POLICY_TABLE


@dataclass
class ResultRecord:
    id: str
    status: str
    message: str
    details: dict[str, Any] | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def make_run_id(prefix: str) -> str:
    return f"{prefix}-{utc_now().strftime('%Y%m%dT%H%M%SZ')}"


def monotonic_ms() -> int:
    return int(time.perf_counter() * 1000)


def json_load(path: Path) -> dict[str, Any]:
    # Accept both plain UTF-8 and UTF-8 with BOM because some operator-side
    # artifact rewrites may come from PowerShell or other Windows tooling.
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl_record(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


@contextmanager
def file_lock(lock_path: Path):
    ensure_parent(lock_path)
    fd: int | None = None
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{iso_now()}\n".encode("utf-8"))
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def write_audit_event(audit_dir: Path, payload: dict[str, Any]) -> str:
    audit_path = audit_dir / f"audit-{utc_now().strftime('%Y%m%d')}.jsonl"
    append_jsonl_record(audit_path, payload)
    return str(audit_path)


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    status, body, _meta = http_json_with_meta(
        url,
        method=method,
        payload=payload,
        timeout=timeout,
        headers=headers,
    )
    return status, body


def http_json_with_meta(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any, dict[str, Any]]:
    data = None
    req = Request(url, method=method.upper())
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req.data = data
        req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(str(key), str(value))
    try:
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(text), {"headers": dict(resp.headers.items())}
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text
        return exc.code, parsed, {"headers": dict(exc.headers.items())}
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return 0, str(exc), {"headers": {}}


def extract_request_id(meta: dict[str, Any] | None) -> str | None:
    if not isinstance(meta, dict):
        return None
    headers = meta.get("headers")
    if not isinstance(headers, dict):
        return None
    normalized = {
        str(key).lower(): value
        for key, value in headers.items()
    }
    for key in ("x-request-id", "x-request-id".lower(), "x-request-id".replace("-", "")):
        value = normalized.get(key)
        if isinstance(value, str) and value:
            return value
    for key, value in normalized.items():
        if key.replace("-", "") == "xrequestid" and isinstance(value, str) and value:
            return value
    return None


def adapter_support_surface(adapter_url: str = DEFAULT_ADAPTER_URL, *, timeout: float = 5.0) -> dict[str, Any]:
    health_status, health_payload, health_meta = http_json_with_meta(f"{adapter_url.rstrip('/')}/health", timeout=timeout)
    catalog_status, catalog_payload, catalog_meta = http_json_with_meta(
        f"{adapter_url.rstrip('/')}/support/error-codes",
        timeout=timeout,
    )
    health_ok = health_status == 200 and isinstance(health_payload, dict) and health_payload.get("status") in {"healthy", "ok"}
    catalog_ok = catalog_status == 200 and isinstance(catalog_payload, dict) and isinstance(catalog_payload.get("count"), int)
    return {
        "adapter_url": adapter_url,
        "health": {
            "status_code": health_status,
            "ok": health_ok,
            "request_id": extract_request_id(health_meta),
            "payload": health_payload if isinstance(health_payload, dict) else {"response": health_payload},
        },
        "error_catalog": {
            "status_code": catalog_status,
            "ok": catalog_ok,
            "request_id": extract_request_id(catalog_meta),
            "count": catalog_payload.get("count") if isinstance(catalog_payload, dict) else None,
            "schema_version": catalog_payload.get("schema_version") if isinstance(catalog_payload, dict) else None,
        },
        "error_policy": (
            health_payload.get("error_policy")
            if isinstance(health_payload, dict) and isinstance(health_payload.get("error_policy"), dict)
            else None
        ),
    }


def openviking_support_surface(openviking_url: str = DEFAULT_OPENVIKING_URL, *, timeout: float = 5.0) -> dict[str, Any]:
    status, payload, _meta = http_json_with_meta(f"{openviking_url.rstrip('/')}/health", timeout=timeout)
    ok = status == 200 and isinstance(payload, dict) and payload.get("status") in {"healthy", "ok"}
    return {
        "openviking_url": openviking_url,
        "health": {
            "status_code": status,
            "ok": ok,
            "payload": payload if isinstance(payload, dict) else {"response": payload},
        },
    }


def docker_runtime_baseline_state(container_names: list[str] | None = None) -> dict[str, Any]:
    container_names = container_names or BASELINE_CONTAINERS
    seen = docker_names()
    running = [name for name in container_names if name in seen]
    missing = [name for name in container_names if name not in seen]
    if not running:
        state = "offline"
    elif not missing:
        state = "online"
    else:
        state = "partial"
    return {
        "state": state,
        "running": running,
        "missing": missing,
        "running_count": len(running),
        "expected_count": len(container_names),
    }


def wait_for_runtime_ready(
    *,
    adapter_url: str = DEFAULT_ADAPTER_URL,
    openviking_url: str = DEFAULT_OPENVIKING_URL,
    wait_seconds: float = DEFAULT_EXECUTE_STARTUP_WAIT_SECONDS,
    poll_interval_seconds: float = DEFAULT_EXECUTE_POLL_INTERVAL_SECONDS,
    timeout: float = 5.0,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    deadline = time.time() + max(0.0, wait_seconds)
    attempt = 0
    last_adapter: dict[str, Any] | None = None
    last_openviking: dict[str, Any] | None = None
    runtime_state: dict[str, Any] | None = None

    while True:
        attempt += 1
        runtime_state = docker_runtime_baseline_state()
        last_adapter = adapter_support_surface(adapter_url, timeout=timeout)
        last_openviking = openviking_support_surface(openviking_url, timeout=timeout)
        ready = bool(last_adapter["health"]["ok"] and last_adapter["error_catalog"]["ok"] and last_openviking["health"]["ok"])
        attempts.append(
            {
                "attempt": attempt,
                "at": iso_now(),
                "runtime_state": runtime_state["state"],
                "adapter_health_ok": last_adapter["health"]["ok"],
                "adapter_catalog_ok": last_adapter["error_catalog"]["ok"],
                "openviking_health_ok": last_openviking["health"]["ok"],
                "adapter_health_status_code": last_adapter["health"]["status_code"],
                "adapter_catalog_status_code": last_adapter["error_catalog"]["status_code"],
                "openviking_health_status_code": last_openviking["health"]["status_code"],
                "adapter_request_id": last_adapter["health"]["request_id"],
            }
        )
        if ready:
            return {
                "status": "ready",
                "ready": True,
                "attempt_count": attempt,
                "attempts": attempts,
                "runtime_state": runtime_state,
                "adapter_surface": last_adapter,
                "openviking_surface": last_openviking,
                "wait_seconds": wait_seconds,
                "poll_interval_seconds": poll_interval_seconds,
            }
        if time.time() >= deadline:
            break
        time.sleep(max(0.1, poll_interval_seconds))

    runtime_label = runtime_state["state"] if isinstance(runtime_state, dict) else "unknown"
    return {
        "status": "degraded" if runtime_label in {"offline", "partial"} else "timeout",
        "ready": False,
        "attempt_count": attempt,
        "attempts": attempts,
        "runtime_state": runtime_state,
        "adapter_surface": last_adapter,
        "openviking_surface": last_openviking,
        "wait_seconds": wait_seconds,
        "poll_interval_seconds": poll_interval_seconds,
    }


def classify_execute_reason(
    *,
    mode: str,
    status: str,
    health_window_seconds: float,
    runtime_windows: list[dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    runtime_windows = runtime_windows or []
    realized_windows = [window for window in runtime_windows if isinstance(window, dict)]
    retry_applied = any(int(window.get("attempt_count", 0)) > 1 for window in realized_windows)
    offline_seen = any(
        isinstance(window.get("runtime_state"), dict) and window["runtime_state"].get("state") in {"offline", "partial"}
        for window in realized_windows
    )
    ready_seen = any(bool(window.get("ready")) for window in realized_windows)

    if mode != "execute":
        reason_code = "DRY_RUN"
    elif status == "fail":
        reason_code = "EXECUTE_FAILED"
    elif offline_seen and not ready_seen:
        reason_code = "OFFLINE_RUNTIME_DEGRADED"
    elif retry_applied:
        reason_code = "READY_AFTER_RETRY"
    else:
        reason_code = "READY_NO_RETRY"

    return {
        "reason_code": reason_code,
        "expected_during_offline": bool(mode == "execute" and offline_seen),
        "retry_applied": retry_applied,
        "health_window_seconds": health_window_seconds,
    }


def companion_artifacts(root: Path = DEFAULT_ARTIFACT_ROOT) -> dict[str, str]:
    return {
        "compatibility_report": str(root / "compatibility_report.current.json"),
        "verify_report": str(root / "verify_report.current.json"),
        "install_check_report": str(root / "install_check.current.json"),
        "install_report": str(root / "install.current.json"),
        "upgrade_report": str(root / "upgrade.current.json"),
        "backup_report": str(root / "backup.current.json"),
        "restore_report": str(root / "restore.current.json"),
        "rollback_report": str(root / "rollback.current.json"),
        "uninstall_report": str(root / "uninstall.current.json"),
        "uninstall_plan_report": str(root / "uninstall_plan.current.json"),
        "rehearsal_report": str(root / "rehearsal.current.json"),
        "execute_window_report": str(root / "execute_window.current.json"),
        "window_packet_report": str(root / "window_packet.current.json"),
        "window_packet_verify_report": str(root / "window_packet_verify.current.json"),
        "execute_smoke_report": str(root / "execute_smoke.current.json"),
        "runtime_manager_report": str(root / "runtime_manager.current.json"),
        "installer_scaffold_report": str(root / "installer_scaffold.current.json"),
        "package_assembler_report": str(root / "package_assembler.current.json"),
        "install_validator_report": str(root / "install_validator.current.json"),
        "mcp_interface_validation_report": str(root / "mcp_interface_validation.current.json"),
        "public_tool_catalog_report": str(root / "public_tool_catalog.current.json"),
        "tenant_search_postcheck_validation_report": str(root / "tenant_search_postcheck_validation.current.json"),
        "delivery_evidence_bundle_report": str(root / "delivery_evidence_bundle.current.json"),
        "delivery_evidence_archive_report": str(root / "delivery_evidence_archive.current.json"),
        "phase2_reserved_fields_report": str(root / "phase2_reserved_fields.current.json"),
    }


def phase2_reserved_field_contract() -> dict[str, Any]:
    migration_states = list(PHASE2_RESERVED_MIGRATION_STATES)
    return {
        "schema_version": "ov-commercialization-phase2-fields/v1",
        "defaults": {
            "instance_id": DEFAULT_INSTANCE_ID,
            "host_mode": DEFAULT_HOST_MODE,
            "migration_state": None,
            "migration_state_enums": migration_states,
        },
        "canonical_fields": {
            "instance_id": {
                "type": "string",
                "status": "active",
                "scope": ["registry_root", "tenant_record", "delivery_manifest", "context_reports"],
                "description": "Current runtime instance identifier. Defaults to the shared host instance in Phase 1.",
            },
            "source_instance_id": {
                "type": "string",
                "status": "active",
                "scope": ["tenant_record", "context_snapshot_meta", "context_package"],
                "description": "Origin instance identifier preserved for future migrate-out and import flows.",
            },
            "target_instance": {
                "type": ["string", "null"],
                "status": "reserved",
                "scope": ["cli_and_mcp_inputs", "context_operations", "context_package"],
                "description": "Reserved destination instance hint. Accepted today but not acted on by the control plane.",
            },
            "host_mode": {
                "type": "string",
                "status": "active",
                "scope": ["registry_root", "delivery_manifest", "context_reports", "context_package"],
                "description": "Current hosting mode marker. Defaults to shared-multitenant during Phase 1.",
            },
            "migration_state": {
                "type": ["string", "null"],
                "status": "reserved",
                "scope": ["tenant_record", "context_package"],
                "enum": migration_states,
                "description": "Reserved explicit migration state field. Null in Phase 1 unless future migration flows set it.",
            },
        },
        "compatibility_aliases": {
            "target_instance_id": {
                "canonical_field": "target_instance",
                "status": "compatibility",
                "description": "Legacy package payload alias kept for forward-compatible readers and writers.",
            }
        },
    }


def support_trace_checkpoint(phase: str, surface: dict[str, Any]) -> dict[str, Any]:
    health = surface.get("health", {}) if isinstance(surface, dict) else {}
    catalog = surface.get("error_catalog", {}) if isinstance(surface, dict) else {}
    return {
        "phase": phase,
        "adapter_url": surface.get("adapter_url") if isinstance(surface, dict) else None,
        "health_ok": health.get("ok") if isinstance(health, dict) else None,
        "health_request_id": health.get("request_id") if isinstance(health, dict) else None,
        "catalog_ok": catalog.get("ok") if isinstance(catalog, dict) else None,
        "catalog_request_id": catalog.get("request_id") if isinstance(catalog, dict) else None,
        "error_catalog_count": catalog.get("count") if isinstance(catalog, dict) else None,
        "error_policy_schema_version": (
            surface.get("error_policy", {}).get("schema_version")
            if isinstance(surface, dict) and isinstance(surface.get("error_policy"), dict)
            else None
        ),
    }


def restore_policy_for(item_id: str, source: Path) -> dict[str, Any]:
    policy = RESTORE_POLICY_TABLE.get(item_id)
    if policy and source.is_dir():
        return policy
    return RESTORE_POLICY_DEFAULT


def apply_restore_operation(item_id: str, source: Path, destination: Path) -> dict[str, Any]:
    policy = restore_policy_for(item_id, source)
    if policy["mode"] == "sync_contents":
        return {
            "policy": policy,
            "result": sync_tree_contents(
                source,
                destination,
                exclude_names=set(policy.get("excluded_names", [])),
            ),
        }
    return {
        "policy": policy,
        "result": replace_path(source, destination),
    }


def append_execution_event(
    trace: list[dict[str, Any]],
    action: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "at": iso_now(),
        "action": action,
        "status": status,
    }
    if details:
        event["details"] = details
    trace.append(event)
    return event


def run_command(args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        return False, stderr or stdout or f"exit={proc.returncode}"
    return True, proc.stdout


def docker_names() -> set[str]:
    ok, output = run_command(["docker", "ps", "--format", "{{.Names}}"])
    if not ok:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


def docker_networks() -> set[str]:
    ok, output = run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
    if not ok:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


def resolve_plugin_config(config: dict[str, Any]) -> dict[str, Any]:
    return (
        config.get("plugins", {})
        .get("entries", {})
        .get("memory-openviking", {})
        .get("config", {})
    )


def resolve_known_agents(config: dict[str, Any]) -> list[str]:
    if not isinstance(config.get("agents"), dict):
        return []
    if not isinstance(config["agents"].get("list"), list):
        return []
    return [
        item.get("id")
        for item in config["agents"]["list"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def resolve_openclaw_version(config: dict[str, Any]) -> str | None:
    meta = config.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("lastTouchedVersion"), str):
        return meta["lastTouchedVersion"]
    return None


def resolve_agent_id(config_path: Path, fallback: str = DEFAULT_EXPECTED_AGENT_ID) -> str:
    try:
        config = json_load(config_path)
    except Exception:  # noqa: BLE001
        return fallback
    agent_id = resolve_plugin_config(config).get("agentId")
    return agent_id if isinstance(agent_id, str) and agent_id else fallback


def result_counts(records: list[ResultRecord]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for record in records:
        counts.setdefault(record.status, 0)
        counts[record.status] += 1
    counts["total"] = len(records)
    return counts


def overall_status(records: list[ResultRecord]) -> str:
    if any(record.status == "fail" for record in records):
        return "fail"
    if any(record.status == "warn" for record in records):
        return "warn"
    return "pass"


def report_metadata(tool_name: str, run_id: str, started_ms: int) -> dict[str, Any]:
    duration_ms = max(0, monotonic_ms() - started_ms)
    return {
        "schema_version": "ov-commercialization/v1",
        "tool": {
            "name": tool_name,
            "version": TOOL_VERSION,
            "python": sys.version.split()[0],
        },
        "run": {
            "id": run_id,
            "generated_at": iso_now(),
            "duration_ms": duration_ms,
            "host": socket.gethostname(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
            },
        },
    }


def path_writable(path: Path) -> bool:
    candidate = path if path.is_dir() else path.parent
    if not candidate.exists():
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
    return os_access_write(candidate)


def os_access_write(path: Path) -> bool:
    try:
        probe = path / f".ov_write_probe_{int(time.time() * 1000)}_{uuid.uuid4().hex}"
        probe.write_text("probe\n", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def classify_support_level(records: list[ResultRecord]) -> tuple[str, list[str], list[str]]:
    record_map = {record.id: record for record in records}
    failures = {record.id for record in records if record.status == "fail"}
    warnings = {record.id for record in records if record.status == "warn"}
    risks: list[str] = []
    suggestions: list[str] = []

    version_record = record_map.get("openclaw_version")
    version_reason_code = None
    if version_record and isinstance(version_record.details, dict):
        version_reason_code = version_record.details.get("reason_code")

    if "openclaw_version" in failures:
        if version_reason_code == "version_unsupported":
            risks.append("OpenClaw version is outside the supported commercialization version policy.")
            suggestions.append("Downgrade to the recommended baseline or explicitly validate and whitelist this version before delivery.")
            return "C", risks, suggestions
        risks.append("OpenClaw version could not be validated against the commercialization version policy.")
        suggestions.append("Confirm the installed OpenClaw version before treating this environment as supported.")
        return "C", risks, suggestions

    critical_chain = {
        "openclaw_config",
        "plugin_slot",
        "plugin_dir",
        "plugin_base_url",
        "agent_id",
        "agent_id_registry",
        "adapter_health",
        "openviking_health",
        "docker_primary_gateway",
        "docker_runtime_baseline",
        "docker_network",
    }
    if failures & critical_chain:
        if "adapter_health" in failures or "openviking_health" in failures:
            risks.append("Core runtime health checks failed, so the memory chain is not supportable.")
            suggestions.append("Restore Memory Adapter and OpenViking health before packaging or delivery.")
            return "D", risks, suggestions
        risks.append("Critical baseline wiring deviates from the supported OpenViking commercialization baseline.")
        suggestions.append("Repair the failed baseline checks before treating this environment as release-ready.")
        return "C", risks, suggestions

    if warnings:
        if "openclaw_version" in warnings:
            if version_reason_code == "version_drift_supported":
                risks.append("OpenClaw version differs from the frozen baseline but is in the supported compatibility list.")
                suggestions.append("Continue with this compatible version or downgrade to the recommended baseline if you need the strictest release anchor.")
            else:
                risks.append("OpenClaw version drifted away from the frozen commercialization baseline.")
                suggestions.append("Re-run doctor and verify after confirming the upgraded OpenClaw version is accepted.")
        if "plugin_timeout" in warnings:
            risks.append("Plugin timeout is below the recommended commercialization baseline.")
            suggestions.append("Keep plugin timeoutMs at or above 30000 and verify request windows at or above 45 seconds.")
        if "agent_id" in warnings or "agent_id_registry" in warnings:
            risks.append("Configured agentId is not aligned with the packaged commercialization default.")
            suggestions.append("Use supervisor as the packaged default unless a multi-agent deployment explicitly overrides it.")
        if "staging_parallel" in warnings:
            risks.append("A staging runtime is present and can pollute baseline judgments.")
            suggestions.append("Keep staging archived offline instead of running in parallel with the production baseline.")
        if "key_dirs" in warnings:
            risks.append("One or more expected commercialization directories are missing.")
            suggestions.append("Restore the missing directories or update the script arguments to the active layout.")
        if "plugin_flags" in warnings:
            risks.append("Automatic capture or recall flags differ from the validated baseline.")
            suggestions.append("Confirm whether the packaged profile should keep autoCapture and autoRecall enabled.")
        if not risks:
            risks.append("The environment is usable but differs from the frozen commercialization baseline.")
            suggestions.append("Review the warnings before using this environment as a delivery baseline.")
        return "B", risks, suggestions

    suggestions.append("Run verify after any configuration, container, or plugin package change.")
    return "A", risks, suggestions


def threshold_passed(actual: str, minimum: str) -> bool:
    order = {"A": 0, "B": 1, "C": 2, "D": 3}
    return order.get(actual, 99) <= order.get(minimum, 99)


def evaluate_openclaw_version_policy(
    detected_version: str | None,
    *,
    baseline_version: str = DEFAULT_EXPECTED_OPENCLAW_VERSION,
    supported_versions: tuple[str, ...] = DEFAULT_SUPPORTED_OPENCLAW_VERSIONS,
) -> dict[str, Any]:
    supported = tuple(dict.fromkeys(version for version in supported_versions if version))
    if not detected_version:
        return {
            "classification": "unknown",
            "is_recommended": False,
            "is_supported": False,
            "reason_code": "version_unknown",
            "message": "OpenClaw version could not be resolved",
            "action_suggestion": "resolve_version_before_continue",
            "check_status": "fail",
        }
    if detected_version == baseline_version:
        return {
            "classification": "recommended",
            "is_recommended": True,
            "is_supported": True,
            "reason_code": "version_baseline_recommended",
            "message": "Version matches the frozen baseline",
            "action_suggestion": "continue",
            "check_status": "pass",
        }
    if detected_version in supported:
        return {
            "classification": "compatible",
            "is_recommended": False,
            "is_supported": True,
            "reason_code": "version_drift_supported",
            "message": "Version differs from baseline but is in the supported list",
            "action_suggestion": "optional_downgrade_or_continue",
            "check_status": "warn",
        }
    return {
        "classification": "unsupported",
        "is_recommended": False,
        "is_supported": False,
        "reason_code": "version_unsupported",
        "message": "Version is outside the supported list",
        "action_suggestion": "downgrade_or_validate_before_install",
        "check_status": "fail",
    }


def compatibility_report_assessment(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "support_level": None,
            "classification": None,
            "is_supported": False,
            "is_recommended": False,
            "reason_code": None,
            "accepted": False,
        }
    support_level = payload.get("support_level")
    if isinstance(support_level, dict):
        support_level = support_level.get("level")
    if not isinstance(support_level, str):
        support_level = payload.get("summary", {}).get("support_level")
    classification = payload.get("classification")
    is_supported = payload.get("is_supported")
    is_recommended = payload.get("is_recommended")
    if not isinstance(is_supported, bool):
        is_supported = support_level in {"A", "B"}
    if not isinstance(is_recommended, bool):
        is_recommended = support_level == "A" or classification == "recommended"
    accepted = bool(is_supported) and support_level in {"A", "B"} and payload.get("status") in {"pass", "warn"}
    return {
        "support_level": support_level,
        "classification": classification,
        "is_supported": is_supported,
        "is_recommended": is_recommended,
        "reason_code": payload.get("reason_code"),
        "accepted": accepted,
        "message": payload.get("message"),
        "action_suggestion": payload.get("action_suggestion"),
    }


def copy_path(source: Path, destination: Path) -> dict[str, Any]:
    if source.is_dir():
        shutil.copytree(source, destination)
        return {"type": "directory", "copied": True}
    shutil.copy2(source, destination)
    return {"type": "file", "copied": True}


def render_records(records: list[ResultRecord]) -> list[dict[str, Any]]:
    return [asdict(record) for record in records]


def record_ids_by_status(records: list[ResultRecord]) -> dict[str, list[str]]:
    grouped = {"pass": [], "warn": [], "fail": [], "skip": []}
    for record in records:
        grouped.setdefault(record.status, [])
        grouped[record.status].append(record.id)
    return grouped


def sync_path(source: Path, destination: Path) -> dict[str, Any]:
    ensure_parent(destination)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return {"type": "directory", "synced": True}
    shutil.copy2(source, destination)
    return {"type": "file", "synced": True}


def replace_path(source: Path, destination: Path) -> dict[str, Any]:
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    return copy_path(source, destination)


def sync_tree_contents(
    source: Path,
    destination: Path,
    *,
    exclude_names: set[str] | None = None,
) -> dict[str, Any]:
    exclude_names = exclude_names or set()
    destination.mkdir(parents=True, exist_ok=True)

    for child in destination.iterdir():
        if child.name in exclude_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    for child in source.iterdir():
        if child.name in exclude_names:
            continue
        copy_path(child, destination / child.name)

    return {
        "type": "directory",
        "synced_contents": True,
        "excluded": sorted(exclude_names),
    }


def move_path(source: Path, destination: Path) -> dict[str, Any]:
    ensure_parent(destination)
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.move(str(source), str(destination))
    return {"moved": True}


def load_backup_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / "manifest.json"
    return json_load(manifest_path)


def plugin_entry_from_baseline(
    *,
    base_url: str = DEFAULT_EXPECTED_PLUGIN_BASE_URL,
    timeout_ms: int = DEFAULT_MIN_PLUGIN_TIMEOUT_MS,
    auto_recall: bool = True,
    auto_capture: bool = True,
    agent_id: str = DEFAULT_EXPECTED_AGENT_ID,
) -> dict[str, Any]:
    return {
        "config": {
            "baseUrl": base_url,
            "timeoutMs": timeout_ms,
            "autoRecall": auto_recall,
            "autoCapture": auto_capture,
            "agentId": agent_id,
        }
    }


def merge_plugin_baseline_config(config: dict[str, Any], desired_entry: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    plugins = config.setdefault("plugins", {})
    if plugins.get("enabled") is not True:
        changes.append({"path": "plugins.enabled", "before": plugins.get("enabled"), "after": True})
        plugins["enabled"] = True

    allow = plugins.setdefault("allow", [])
    if "memory-openviking" not in allow:
        allow.append("memory-openviking")
        changes.append({"path": "plugins.allow", "before": "missing", "after": "memory-openviking added"})

    slots = plugins.setdefault("slots", {})
    if slots.get("memory") != "memory-openviking":
        changes.append({"path": "plugins.slots.memory", "before": slots.get("memory"), "after": "memory-openviking"})
        slots["memory"] = "memory-openviking"

    entries = plugins.setdefault("entries", {})
    current_entry = entries.get("memory-openviking", {})
    if current_entry != desired_entry:
        changes.append({"path": "plugins.entries.memory-openviking", "before": current_entry, "after": desired_entry})
        entries["memory-openviking"] = desired_entry

    return changes
