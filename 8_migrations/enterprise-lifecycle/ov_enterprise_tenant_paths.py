"""Tenant-aware path helpers for commercialization tooling."""

from __future__ import annotations

from pathlib import Path

from ov_enterprise_common import (
    DEFAULT_INSTANCE_ID,
    DEFAULT_TENANT_POLICY_PATH,
    DEFAULT_TENANT_REGISTRY_PATH,
    DEFAULT_TENANT_RUNTIME_ROOT,
)


CURRENT_REPORT_FILENAMES = {
    "doctor": "doctor.current.json",
    "verify": "verify.current.json",
    "backup": "backup.current.json",
    "restore": "restore.current.json",
    "rollback": "rollback.current.json",
    "export": "export.current.json",
    "import": "import.current.json",
    "status": "status.current.json",
}


def resolve_instance_root(instance_root: Path | None = None) -> Path:
    return (instance_root or DEFAULT_TENANT_RUNTIME_ROOT).resolve()


def resolve_registry_dir(instance_root: Path | None = None) -> Path:
    return resolve_instance_root(instance_root) / "registry"


def resolve_policy_dir(instance_root: Path | None = None) -> Path:
    return resolve_instance_root(instance_root) / "policies"


def resolve_tenant_registry_path(instance_root: Path | None = None) -> Path:
    if instance_root is None:
        return DEFAULT_TENANT_REGISTRY_PATH
    return resolve_registry_dir(instance_root) / "tenant.registry.json"


def resolve_tenant_policy_path(instance_root: Path | None = None) -> Path:
    if instance_root is None:
        return DEFAULT_TENANT_POLICY_PATH
    return resolve_policy_dir(instance_root) / "tenant.policy.profiles.json"


def resolve_instance_artifacts_dir(instance_root: Path | None = None) -> Path:
    return resolve_instance_root(instance_root) / "artifacts" / "instance"


def resolve_tenants_artifacts_dir(instance_root: Path | None = None) -> Path:
    return resolve_instance_root(instance_root) / "artifacts" / "tenants"


def resolve_tenant_root(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_instance_root(instance_root) / "tenants" / tenant_id


def resolve_tenant_artifacts_dir(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_tenants_artifacts_dir(instance_root) / tenant_id


def resolve_tenant_audit_dir(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_tenant_artifacts_dir(instance_root, tenant_id) / "audit"


def resolve_tenant_exports_dir(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_tenant_artifacts_dir(instance_root, tenant_id) / "exports"


def resolve_tenant_reports_dir(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_tenant_artifacts_dir(instance_root, tenant_id)


def resolve_tenant_current_report_path(instance_root: Path | None, tenant_id: str, report_kind: str) -> Path:
    filename = CURRENT_REPORT_FILENAMES.get(report_kind, f"{report_kind}.current.json")
    return resolve_tenant_reports_dir(instance_root, tenant_id) / filename


def resolve_backups_dir(instance_root: Path | None = None) -> Path:
    return resolve_instance_root(instance_root) / "backups"


def resolve_tenants_backups_dir(instance_root: Path | None = None) -> Path:
    return resolve_backups_dir(instance_root) / "tenants"


def resolve_tenant_backups_dir(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_tenants_backups_dir(instance_root) / tenant_id


def resolve_tenant_snapshot_dir(instance_root: Path | None, tenant_id: str, snapshot_id: str) -> Path:
    return resolve_tenant_backups_dir(instance_root, tenant_id) / snapshot_id


def resolve_tenant_locks_dir(instance_root: Path | None, tenant_id: str) -> Path:
    return resolve_tenant_root(instance_root, tenant_id) / "locks"


def resolve_tenant_lock_path(instance_root: Path | None, tenant_id: str, operation: str) -> Path:
    return resolve_tenant_locks_dir(instance_root, tenant_id) / f"{operation}.lock"


def ensure_runtime_layout(instance_root: Path | None = None) -> dict[str, str]:
    root = resolve_instance_root(instance_root)
    registry_dir = resolve_registry_dir(root)
    policy_dir = resolve_policy_dir(root)
    instance_artifacts_dir = resolve_instance_artifacts_dir(root)
    tenants_artifacts_dir = resolve_tenants_artifacts_dir(root)
    tenants_backups_dir = resolve_tenants_backups_dir(root)
    for path in (root, registry_dir, policy_dir, instance_artifacts_dir, tenants_artifacts_dir, tenants_backups_dir):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "instance_root": str(root),
        "registry_dir": str(registry_dir),
        "policy_dir": str(policy_dir),
        "instance_artifacts_dir": str(instance_artifacts_dir),
        "tenants_artifacts_dir": str(tenants_artifacts_dir),
        "tenants_backups_dir": str(tenants_backups_dir),
    }


def ensure_tenant_dirs(instance_root: Path | None, tenant_id: str) -> dict[str, str]:
    ensure_runtime_layout(instance_root)
    dirs = {
        "tenant_root": resolve_tenant_root(instance_root, tenant_id),
        "artifacts_dir": resolve_tenant_artifacts_dir(instance_root, tenant_id),
        "audit_dir": resolve_tenant_audit_dir(instance_root, tenant_id),
        "exports_dir": resolve_tenant_exports_dir(instance_root, tenant_id),
        "backups_dir": resolve_tenant_backups_dir(instance_root, tenant_id),
        "locks_dir": resolve_tenant_locks_dir(instance_root, tenant_id),
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return {key: str(value) for key, value in dirs.items()}


def instance_context_payload(instance_root: Path | None = None) -> dict[str, str]:
    root = resolve_instance_root(instance_root)
    return {
        "instance_id": DEFAULT_INSTANCE_ID,
        "instance_root": str(root),
        "tenant_registry_path": str(resolve_tenant_registry_path(root)),
        "tenant_policy_path": str(resolve_tenant_policy_path(root)),
    }
