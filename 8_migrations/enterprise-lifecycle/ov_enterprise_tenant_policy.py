"""Tenant policy helpers for commercialization tooling."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ov_enterprise_common import DEFAULT_TENANT_POLICY_PATH, json_load, write_json_file


DEFAULT_POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "allow_full_replace": False,
        "excluded_runtime_dirs": ["logs", "runtime", "lock", "cache", "tmp"],
        "retry_on_refused": True,
        "degraded_window_seconds": 15,
        "require_pre_snapshot": True,
        "require_verify_after_restore": False,
    },
    "strict": {
        "allow_full_replace": False,
        "excluded_runtime_dirs": ["logs", "runtime", "lock", "cache", "tmp"],
        "retry_on_refused": True,
        "degraded_window_seconds": 8,
        "require_pre_snapshot": True,
        "require_verify_after_restore": True,
    },
}


def load_policy_profiles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    resolved = path or DEFAULT_TENANT_POLICY_PATH
    if not resolved.exists():
        return deepcopy(DEFAULT_POLICY_PROFILES)
    payload = json_load(resolved)
    if not isinstance(payload, dict):
        raise ValueError("tenant policy profiles must be a JSON object")
    merged = deepcopy(DEFAULT_POLICY_PROFILES)
    for profile, values in payload.items():
        if isinstance(values, dict):
            merged[profile] = {**merged.get(profile, {}), **values}
    return merged


def ensure_policy_profiles(path: Path | None = None) -> tuple[Path, dict[str, dict[str, Any]]]:
    resolved = path or DEFAULT_TENANT_POLICY_PATH
    profiles = load_policy_profiles(resolved) if resolved.exists() else deepcopy(DEFAULT_POLICY_PROFILES)
    if not resolved.exists():
        write_json_file(resolved, profiles)
    return resolved, profiles


def resolve_tenant_policy(
    instance_default: dict[str, Any] | None,
    policy_profiles: dict[str, dict[str, Any]],
    tenant: dict[str, Any],
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile_name = tenant.get("policy_profile", "default")
    policy = {}
    policy.update(instance_default or {})
    policy.update(policy_profiles.get("default", {}))
    policy.update(policy_profiles.get(profile_name, {}))
    policy.update(cli_overrides or {})
    policy["profile_name"] = profile_name
    policy["tenant_id"] = tenant.get("tenant_id")
    return policy
