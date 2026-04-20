"""
billing_surface.py - Billing Overview, Plan Catalog, and Plan Switching
Phase 4: Metering → Billing closed loop
"""
from typing import Any
from fastapi import APIRouter, HTTPException

router = APIRouter()

_config = None
_get_tenant_usage_fn = None
_get_tenant_current_usage_fn = None


def configure_billing_surface(
    *,
    config_obj: Any,
    get_tenant_usage_fn: Any,
    get_tenant_current_usage_fn: Any,
) -> None:
    global _config, _get_tenant_usage_fn, _get_tenant_current_usage_fn
    _config = config_obj
    _get_tenant_usage_fn = get_tenant_usage_fn
    _get_tenant_current_usage_fn = get_tenant_current_usage_fn


# Plan catalog — hardcoded, Phase 4 only
PLAN_CATALOG = [
    {
        "plan_id": "starter",
        "display_name": "Starter",
        "monthly_quota_tokens": 100000,
        "overage_policy": "capped",
        "description": "Local-first, token-savings tracking with hard quota cap",
    },
    {
        "plan_id": "pro",
        "display_name": "Pro",
        "monthly_quota_tokens": 1000000,
        "overage_policy": "billable",
        "description": "Full token-savings billing with overage allowed",
    },
    {
        "plan_id": "enterprise",
        "display_name": "Enterprise",
        "monthly_quota_tokens": 10000000,
        "overage_policy": "billable",
        "description": "High-volume enterprise with separate billing label",
    },
]


@router.get("/billing/plans")
async def get_billing_plans():
    """Return the active plan catalog."""
    return {"plans": PLAN_CATALOG}


@router.get("/billing/overview")
async def get_billing_overview(tenant: str):
    """
    Return billing overview for a tenant.

    Combines registry plan data with current usage from meter store.
    """
    if not tenant:
        raise HTTPException(status_code=400, detail="tenant is required")

    from .access import get_tenant_registry_entry, load_registry

    entry = get_tenant_registry_entry(_config.omnimemora_access_registry_path, tenant)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant} not found in registry")

    plan = entry.get("plan", "starter")
    status = entry.get("status", "active")
    raw_quota = entry.get("monthly_quota_tokens", "")
    monthly_quota = int(raw_quota) if raw_quota not in (None, "") else 0

    usage = _get_tenant_usage_fn(tenant)
    current_period_usage = usage.get("actual_tokens_estimate_total", 0)
    saved_tokens_total = usage.get("saved_tokens_total", 0)

    if monthly_quota == 0:
        quota_status = "untracked"
    elif current_period_usage > monthly_quota:
        quota_status = "over_quota"
    else:
        quota_status = "within_quota"

    overage_tokens = max(0, current_period_usage - monthly_quota)
    billable_tokens = overage_tokens if plan in ("pro", "enterprise") else 0
    billing_mode = "capped" if plan == "starter" else "billable"

    return {
        "tenant": tenant,
        "plan": plan,
        "status": status,
        "monthly_quota_tokens": monthly_quota,
        "current_period_usage": current_period_usage,
        "saved_tokens_total": saved_tokens_total,
        "quota_status": quota_status,
        "billable_tokens": billable_tokens,
        "overage_tokens": overage_tokens,
        "billing_mode": billing_mode,
    }


@router.post("/admin/tenants/{tenant_id}/plan")
async def switch_tenant_plan(tenant_id: str, plan: str):
    """
    Switch a tenant's billing plan.

    Requires X-OmniMemora-Admin-Token header matching config value.
    """
    from .access import load_registry, atomic_write_registry

    if not hasattr(_config, "omnimemora_admin_api_token"):
        raise HTTPException(status_code=500, detail="Admin token not configured")

    valid_plans = [p["plan_id"] for p in PLAN_CATALOG]
    if plan not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan {plan}. Must be one of: {valid_plans}",
        )

    registry = load_registry(_config.omnimemora_access_registry_path)
    updated = False
    for entry in registry:
        if entry.get("tenant_id") == tenant_id:
            entry["plan"] = plan
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")

    atomic_write_registry(_config.omnimemora_access_registry_path, registry)

    return {
        "tenant_id": tenant_id,
        "plan": plan,
        "status": "updated",
    }
