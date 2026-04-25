"""Read-only lifecycle health and manual refresh APIs for Data Lifecycle Plane."""

from __future__ import annotations

import importlib

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["data-lifecycle"])

_health = importlib.import_module("5_connectors.adapter.data_lifecycle.health")
_policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
_maintenance_manager_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.maintenance_manager")
_snapshot_cache = importlib.import_module("5_connectors.adapter.application.control_snapshot_cache")


@router.get("/data-lifecycle/status")
async def get_data_lifecycle_status():
    policy = _policy_mod.load_policy()
    return _health.build_health_payload(policy=policy)


@router.post("/data-lifecycle/maintenance/refresh")
async def post_data_lifecycle_manual_refresh():
    policy = _policy_mod.load_policy()
    manager = _maintenance_manager_mod.MaintenanceManager(policy=policy)
    record = manager.run_once("manual_refresh")
    if str(record.get("status") or "").lower() == "success":
        _snapshot_cache.invalidate_agents_control_snapshot()
        return {"schema_version": "dlp-manual-refresh-v1", "record": record}
    raise HTTPException(
        status_code=503,
        detail={
            "schema_version": "dlp-manual-refresh-v1",
            "message": "manual refresh failed",
            "record": record,
        },
    )
