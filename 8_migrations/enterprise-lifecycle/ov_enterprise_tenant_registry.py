"""Tenant registry helpers for commercialization tooling."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    DEFAULT_HOST_MODE,
    DEFAULT_INSTANCE_ID,
    PHASE2_RESERVED_MIGRATION_STATES,
    DEFAULT_TENANT_REGISTRY_PATH,
    iso_now,
    json_load,
    write_json_file,
)


DEFAULT_RESOURCES = {
    "memory_quota_mb": 1024,
    "snapshot_quota": 50,
    "artifact_quota_mb": 1024,
    "max_concurrent_executes": 1,
}

DEFAULT_RETENTION = {
    "short_term_days": 30,
    "artifact_days": 90,
    "backup_days": 180,
}

VALID_TENANT_STATUSES = {
    "active",
    "degraded",
    "suspended",
    "archived",
    *PHASE2_RESERVED_MIGRATION_STATES,
}

VALID_TENANT_MODES = {
    "shared",
    "dedicated",
    *PHASE2_RESERVED_MIGRATION_STATES,
    "suspended",
}


def default_registry(*, instance_id: str = DEFAULT_INSTANCE_ID) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "instance_id": instance_id,
        "host_mode": DEFAULT_HOST_MODE,
        "current_tenant": None,
        "tenants": {},
    }


def load_tenant_registry(registry_path: Path | None = None) -> dict[str, Any]:
    resolved = registry_path or DEFAULT_TENANT_REGISTRY_PATH
    if not resolved.exists():
        return default_registry()
    data = json_load(resolved)
    if not isinstance(data, dict):
        raise ValueError("tenant registry must be a JSON object")
    data.setdefault("schema_version", "1.0")
    data.setdefault("instance_id", DEFAULT_INSTANCE_ID)
    data.setdefault("host_mode", DEFAULT_HOST_MODE)
    data.setdefault("current_tenant", None)
    data.setdefault("tenants", {})
    if not isinstance(data["tenants"], dict):
        raise ValueError("tenant registry tenants must be an object")
    return data


def save_tenant_registry(registry_path: Path, data: dict[str, Any]) -> None:
    write_json_file(registry_path, data)


def ensure_tenant_registry(registry_path: Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = registry_path or DEFAULT_TENANT_REGISTRY_PATH
    if path.exists():
        return path, load_tenant_registry(path)
    payload = default_registry()
    save_tenant_registry(path, payload)
    return path, payload


def list_tenants(registry: dict[str, Any]) -> list[dict[str, Any]]:
    tenants = registry.get("tenants", {})
    if not isinstance(tenants, dict):
        return []
    return [deepcopy(item) for item in tenants.values() if isinstance(item, dict)]


def get_tenant(registry: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    tenants = registry.get("tenants", {})
    if not isinstance(tenants, dict) or tenant_id not in tenants or not isinstance(tenants[tenant_id], dict):
        raise KeyError(f"tenant '{tenant_id}' not found")
    return deepcopy(tenants[tenant_id])


def validate_tenant_record(tenant: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("tenant_id", "display_name", "namespace", "tenant_mode", "policy_profile", "status", "created_at"):
        value = tenant.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{key} is required")
    if tenant.get("status") not in VALID_TENANT_STATUSES:
        errors.append("status is invalid")
    if tenant.get("tenant_mode") not in VALID_TENANT_MODES:
        errors.append("tenant_mode is invalid")
    migration_state = tenant.get("migration_state")
    if migration_state is not None and migration_state not in PHASE2_RESERVED_MIGRATION_STATES:
        errors.append("migration_state is invalid")
    openclaw = tenant.get("openclaw")
    if not isinstance(openclaw, dict):
        errors.append("openclaw section is required")
    else:
        for key in ("config_path", "workspace_root"):
            value = openclaw.get(key)
            if not isinstance(value, str) or not value:
                errors.append(f"openclaw.{key} is required")
    return errors


def create_tenant_record(
    *,
    tenant_id: str,
    display_name: str | None = None,
    namespace: str | None = None,
    policy_profile: str = "default",
    tenant_mode: str = "shared",
    status: str = "active",
    config_path: str,
    workspace_root: str,
    openclaw_version: str | None = None,
    instance_id: str = DEFAULT_INSTANCE_ID,
    source_instance_id: str | None = None,
    migration_state: str | None = None,
    resources: dict[str, Any] | None = None,
    retention: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "tenant_id": tenant_id,
        "display_name": display_name or tenant_id,
        "namespace": namespace or tenant_id,
        "tenant_mode": tenant_mode,
        "policy_profile": policy_profile,
        "status": status,
        "created_at": iso_now(),
        "updated_at": iso_now(),
        "instance_id": instance_id,
        "source_instance_id": source_instance_id or instance_id,
        "migration_state": migration_state,
        "openclaw": {
            "version": openclaw_version,
            "config_path": config_path,
            "workspace_root": workspace_root,
        },
        "resources": {
            **DEFAULT_RESOURCES,
            **(resources or {}),
        },
        "retention": {
            **DEFAULT_RETENTION,
            **(retention or {}),
        },
    }
    errors = validate_tenant_record(record)
    if errors:
        raise ValueError("; ".join(errors))
    return record


def upsert_tenant(registry: dict[str, Any], tenant: dict[str, Any]) -> dict[str, Any]:
    errors = validate_tenant_record(tenant)
    if errors:
        raise ValueError("; ".join(errors))
    registry.setdefault("tenants", {})
    registry["tenants"][tenant["tenant_id"]] = deepcopy(tenant)
    registry["tenants"][tenant["tenant_id"]]["updated_at"] = iso_now()
    if not registry.get("current_tenant"):
        registry["current_tenant"] = tenant["tenant_id"]
    return registry


def update_tenant_status(registry: dict[str, Any], tenant_id: str, status: str) -> dict[str, Any]:
    if status not in VALID_TENANT_STATUSES:
        raise ValueError(f"unsupported tenant status '{status}'")
    tenant = get_tenant(registry, tenant_id)
    tenant["status"] = status
    tenant["updated_at"] = iso_now()
    return upsert_tenant(registry, tenant)


def update_tenant_policy_profile(registry: dict[str, Any], tenant_id: str, policy_profile: str) -> dict[str, Any]:
    tenant = get_tenant(registry, tenant_id)
    tenant["policy_profile"] = policy_profile
    tenant["updated_at"] = iso_now()
    return upsert_tenant(registry, tenant)


def set_current_tenant(registry: dict[str, Any], tenant_id: str | None) -> dict[str, Any]:
    if tenant_id is not None:
        get_tenant(registry, tenant_id)
    registry["current_tenant"] = tenant_id
    return registry


def assert_tenant_operation_allowed(tenant: dict[str, Any], operation: str) -> None:
    status = tenant.get("status")
    if status in {"archived"}:
        raise ValueError(f"tenant '{tenant.get('tenant_id')}' is archived and cannot run {operation}")
    if operation in {"restore", "rollback", "import"} and status in {"suspended", "migrating_out"}:
        raise ValueError(f"tenant '{tenant.get('tenant_id')}' status '{status}' blocks {operation}")
