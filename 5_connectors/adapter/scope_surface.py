"""
scope_surface.py - Scope Capabilities API
Exposes supported scopes, sharing modes, and registered custom scopes.
"""
from typing import Any
from fastapi import APIRouter, HTTPException

router = APIRouter()

_config = None
_scope_registry_path = None


def configure_scope_surface(*, config_obj: Any, scope_registry_path: str) -> None:
    global _config, _scope_registry_path
    _config = config_obj
    _scope_registry_path = scope_registry_path


def _load_scope_registry() -> dict:
    """Load custom scope registry from disk."""
    import json
    path = _scope_registry_path or ""
    if not path or not __import__("os").path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


@router.get("/scope/capabilities")
async def get_scope_capabilities():
    """
    Returns the active scope/sharing contract at the product layer.

    - supported_scopes: all scope types currently enforced
    - supported_sharing_modes: all sharing modes currently enforced
    - default_scope: config default
    - default_sharing_mode: config default
    - custom_scopes: registered custom scope definitions
    """
    import os

    supported_scopes = ["agent", "workspace", "user", "custom"]
    supported_sharing_modes = ["isolated", "shared", "shared_read_only"]

    default_scope = getattr(_config, "scope", None)
    default_scope_name = getattr(default_scope, "default", "workspace") if default_scope else "workspace"
    default_sharing = getattr(default_scope, "default_sharing_mode", "isolated") if default_scope else "isolated"

    # Load custom scopes from registry
    custom_scopes = []
    registry_path = _scope_registry_path or ""
    if registry_path and os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                import json
                data = json.load(f) or {}
                custom_scopes = data.get("custom_scopes", [])
        except Exception:
            pass

    return {
        "supported_scopes": supported_scopes,
        "supported_sharing_modes": supported_sharing_modes,
        "default_scope": default_scope_name,
        "default_sharing_mode": default_sharing,
        "custom_scopes": custom_scopes,
    }