"""
cloud_surface.py - Cloud Control Status and Registry Sync Surface
Phase 5: Cloud Control enhances local policy/metering/billing (optional)
"""
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

_config = None


def configure_cloud_surface(*, config_obj: Any) -> None:
    global _config
    _config = config_obj


def _attempt_registry_sync() -> dict:
    """
    Attempt to fetch remote tenant list and update cloud sync state.
    Returns the remote tenant list on success, None on failure.
    Does not raise exceptions; updates _cloud_sync_state in access.py.
    """
    from .access import update_cloud_sync_state, _fetch_remote_tenant_list

    sync_cfg = _config.registry_sync
    if not sync_cfg.enabled:
        update_cloud_sync_state(False, "disabled")
        return None

    update_cloud_sync_state(True, "syncing")

    tenants = _fetch_remote_tenant_list(
        url=sync_cfg.url,
        token=sync_cfg.token,
        timeout_seconds=sync_cfg.timeout_seconds,
    )

    if tenants is None:
        update_cloud_sync_state(True, "failed", "fetch returned None or network error")
        return None

    update_cloud_sync_state(True, "success")
    return tenants


@router.get("/cloud/status")
async def get_cloud_status():
    """
    Return current cloud control status.

    Reports:
    - cloud_enabled: whether cloud integration is configured
    - registry_sync_enabled: whether remote registry sync is enabled
    - last_sync_at: ISO timestamp of last sync attempt
    - last_sync_status: never_run | disabled | syncing | success | failed
    - last_error: error message if last_sync_status == failed
    - local_fallback_active: True when cloud is enabled but last sync failed
    - cloud_policy_updates_enabled: whether cloud policy updates are enabled
    """
    from .access import get_cloud_sync_state

    sync_state = get_cloud_sync_state()
    sync_cfg = _config.registry_sync
    cloud_cfg = _config.cloud

    local_fallback_active = (
        bool(sync_cfg.enabled)
        and sync_state.get("last_sync_status") in ("failed", "never_run")
    )

    return {
        "cloud_enabled": bool(cloud_cfg.enabled),
        "cloud_candidate_source_enabled": bool(cloud_cfg.candidate_source_enabled),
        "registry_sync_enabled": bool(sync_cfg.enabled),
        "last_sync_at": sync_state.get("last_sync_at"),
        "last_sync_status": sync_state.get("last_sync_status"),
        "last_error": sync_state.get("last_error"),
        "local_fallback_active": local_fallback_active,
        "cloud_policy_updates_enabled": bool(cloud_cfg.enabled and cloud_cfg.usage_report_enabled),
    }


@router.post("/cloud/sync")
async def trigger_cloud_sync():
    """
    Manually trigger a registry sync attempt.
    Returns the sync outcome immediately without waiting for full completion.
    """
    if not _config.registry_sync.enabled:
        raise HTTPException(
            status_code=400,
            detail="registry_sync is not enabled. Set OMNIMEMORA_REGISTRY_SYNC_ENABLED=true to use this endpoint.",
        )

    tenants = _attempt_registry_sync()
    from .access import get_cloud_sync_state

    sync_state = get_cloud_sync_state()

    return {
        "status": sync_state["last_sync_status"],
        "last_sync_at": sync_state["last_sync_at"],
        "last_error": sync_state["last_error"],
        "tenants_fetched": len(tenants) if tenants is not None else None,
    }
