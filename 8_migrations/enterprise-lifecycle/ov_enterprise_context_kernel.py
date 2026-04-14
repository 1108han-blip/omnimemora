"""Context-first registry operations used by CLI and MCP wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ov_enterprise_common import DEFAULT_HOST_MODE, DEFAULT_INSTANCE_ID, DEFAULT_TENANT_POLICY_PATH, DEFAULT_TENANT_REGISTRY_PATH, DEFAULT_TENANT_RUNTIME_ROOT
from ov_enterprise_tenant_paths import ensure_tenant_dirs
from ov_enterprise_tenant_policy import ensure_policy_profiles
from ov_enterprise_tenant_registry import (
    create_tenant_record,
    ensure_tenant_registry,
    get_tenant,
    list_tenants,
    save_tenant_registry,
    set_current_tenant,
    update_tenant_policy_profile,
    update_tenant_status,
)


def resolve_context_id(arguments: dict[str, Any]) -> str:
    for key in ("context_id", "tenant_id", "tenant"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("context_id is required")


def resolve_runtime_paths(arguments: dict[str, Any]) -> tuple[Path, Path, Path]:
    instance_root = Path(arguments.get("instance_root") or DEFAULT_TENANT_RUNTIME_ROOT)
    registry_path = Path(arguments.get("registry_path") or DEFAULT_TENANT_REGISTRY_PATH)
    policy_path = Path(arguments.get("policy_path") or DEFAULT_TENANT_POLICY_PATH)
    return instance_root, registry_path, policy_path


def default_context_paths(context_id: str) -> tuple[str, str]:
    safe_context = context_id.strip()
    state_root = Path.home() / f".openclaw-{safe_context}"
    return str(state_root / "openclaw.json"), str(state_root / "workspace")


def _context_response(
    action: str,
    *,
    registry_path: Path,
    registry: dict[str, Any],
    context: dict[str, Any] | None = None,
    contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    context_id = (context or {}).get("tenant_id")
    return {
        "status": "pass",
        "action": action,
        "context_id": context_id,
        "tenant_id": context_id,
        "instance_id": registry.get("instance_id"),
        "host_mode": registry.get("host_mode"),
        "registry_path": str(registry_path),
        "context": context,
        "contexts": contexts,
        "summary": {
            "action": action,
            "context_id": context_id,
            "context_count": len(contexts or []),
        },
    }


def list_contexts(arguments: dict[str, Any]) -> dict[str, Any]:
    _, registry_path, policy_path = resolve_runtime_paths(arguments)
    registry_path, registry = ensure_tenant_registry(registry_path)
    ensure_policy_profiles(policy_path)
    contexts = list_tenants(registry)
    return _context_response("context_list", registry_path=registry_path, registry=registry, contexts=contexts)


def show_context(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    _, registry_path, _policy_path = resolve_runtime_paths(arguments)
    registry_path, registry = ensure_tenant_registry(registry_path)
    context = get_tenant(registry, context_id)
    set_current_tenant(registry, context_id)
    save_tenant_registry(registry_path, registry)
    return _context_response("context_show", registry_path=registry_path, registry=registry, context=context)


def create_context(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    instance_root, registry_path, policy_path = resolve_runtime_paths(arguments)
    registry_path, registry = ensure_tenant_registry(registry_path)
    ensure_policy_profiles(policy_path)
    ensure_tenant_dirs(instance_root, context_id)
    config_path, workspace_root = (
        arguments.get("config_path") or default_context_paths(context_id)[0],
        arguments.get("workspace_root") or default_context_paths(context_id)[1],
    )
    context = create_tenant_record(
        tenant_id=context_id,
        display_name=arguments.get("display_name"),
        namespace=arguments.get("namespace"),
        policy_profile=arguments.get("policy_profile") or "default",
        config_path=config_path,
        workspace_root=workspace_root,
        instance_id=registry.get("instance_id", DEFAULT_INSTANCE_ID),
        source_instance_id=registry.get("instance_id", DEFAULT_INSTANCE_ID),
    )
    registry.setdefault("host_mode", DEFAULT_HOST_MODE)
    registry.setdefault("instance_id", DEFAULT_INSTANCE_ID)
    registry["tenants"][context_id] = context
    set_current_tenant(registry, context_id)
    save_tenant_registry(registry_path, registry)
    return _context_response("context_create", registry_path=registry_path, registry=registry, context=context)


def update_context(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    _, registry_path, _policy_path = resolve_runtime_paths(arguments)
    registry_path, registry = ensure_tenant_registry(registry_path)
    policy_profile = arguments.get("policy_profile")
    if not isinstance(policy_profile, str) or not policy_profile.strip():
        raise ValueError("policy_profile is required")
    update_tenant_policy_profile(registry, context_id, policy_profile)
    save_tenant_registry(registry_path, registry)
    context = get_tenant(registry, context_id)
    return _context_response("context_update", registry_path=registry_path, registry=registry, context=context)


def suspend_context(arguments: dict[str, Any]) -> dict[str, Any]:
    return _set_context_status(arguments, "suspended", "context_suspend")


def resume_context(arguments: dict[str, Any]) -> dict[str, Any]:
    return _set_context_status(arguments, "active", "context_resume")


def status_context(arguments: dict[str, Any]) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    _, registry_path, _policy_path = resolve_runtime_paths(arguments)
    registry_path, registry = ensure_tenant_registry(registry_path)
    context = get_tenant(registry, context_id)
    return _context_response("context_status", registry_path=registry_path, registry=registry, context=context)


def _set_context_status(arguments: dict[str, Any], status: str, action: str) -> dict[str, Any]:
    context_id = resolve_context_id(arguments)
    _, registry_path, _policy_path = resolve_runtime_paths(arguments)
    registry_path, registry = ensure_tenant_registry(registry_path)
    update_tenant_status(registry, context_id, status)
    save_tenant_registry(registry_path, registry)
    context = get_tenant(registry, context_id)
    return _context_response(action, registry_path=registry_path, registry=registry, context=context)
