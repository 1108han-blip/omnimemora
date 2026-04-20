import hashlib
import json
import os
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

# In-memory cloud sync state — reset on restart (not persistent)
# Used by GET /cloud/status to report last sync outcome
_cloud_sync_state = {
    "enabled": False,
    "last_sync_at": None,
    "last_sync_status": "never_run",
    "last_error": None,
}


def update_cloud_sync_state(enabled: bool, status: str, error: Optional[str] = None) -> None:
    import datetime
    _cloud_sync_state["enabled"] = enabled
    _cloud_sync_state["last_sync_status"] = status
    _cloud_sync_state["last_error"] = error
    if status == "success":
        _cloud_sync_state["last_sync_at"] = datetime.datetime.utcnow().isoformat() + "Z"


def get_cloud_sync_state() -> dict:
    return dict(_cloud_sync_state)


def normalize(value: Optional[str], max_length: int = 256) -> str:
    return (value or "").strip()[:max_length]


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_api_key(request: Request) -> str:
    explicit = normalize(request.headers.get("X-OmniMemora-Key"))
    if explicit:
        return explicit

    authorization = normalize(request.headers.get("Authorization"))
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return ""


def _fetch_remote_tenant_list(
    url: str,
    token: str,
    timeout_seconds: float,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch tenant list from a protected remote endpoint.

    Returns a list of tenant-entry dicts on success, or None if the fetch
    fails for any reason (network error, non-2xx response, parse error).
    Does not raise exceptions.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            if resp.status != 200:
                return None
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        # Network error, timeout, bad JSON — fail silently so caller can fall back.
        return None

    # Normalize the remote payload into the expected list-of-tenant-entry shape.
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        tenants = payload.get("tenants", [])
        return tenants if isinstance(tenants, list) else []
    return None


def sync_registry(
    registry_path: str,
    remote_url: str,
    remote_token: str,
    remote_timeout: float,
) -> None:
    """
    Attempt to fetch the tenant registry from a protected remote endpoint and
    atomically cache it to the local registry path.

    If the remote fetch succeeds the local registry file is replaced with the
    remote data (normalized into the ``{"tenants": [...]}`` schema).  If the
    fetch fails the local file is left untouched and the function returns
    silently, preserving existing local behaviour.
    """
    remote_tenants = _fetch_remote_tenant_list(remote_url, remote_token, remote_timeout)
    if remote_tenants is None:
        # Remote unavailable — caller should fall back to existing local data.
        return

    atomic_write_registry(registry_path, remote_tenants)


def load_registry(registry_path: str) -> list[Dict[str, Any]]:
    path = Path(registry_path)
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        tenants = payload.get("tenants", [])
        return tenants if isinstance(tenants, list) else []
    return []


def get_tenant_registry_entry(registry_path: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    normalized_tenant = normalize(tenant_id, 120)
    if not normalized_tenant:
        return None

    registry = load_registry(registry_path)
    return next(
        (
            item
            for item in registry
            if normalize(str(item.get("tenant_id", "")), 120) == normalized_tenant
        ),
        None,
    )


@dataclass
class AccessResolution:
    tenant_id: str
    user_id: str
    plan: str
    status: str
    token_id: Optional[str]
    auth_mode: str
    key_present: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_query_access(
    request: Request,
    requested_tenant: str,
    requested_user: str,
    registry_path: str,
    require_key: bool = False,
    registry_sync: Optional[Dict[str, Any]] = None,
) -> AccessResolution:
    """
    Resolve access for a /memory/query request.

    When ``registry_sync`` is provided as a dict with ``enabled=True``, a non-empty
    ``url``, and a non-empty ``token``, ``sync_registry`` is called first to refresh
    the local registry cache from the remote tenant endpoint.  If the remote fetch
    fails the function falls back silently to the existing local JSON behaviour.
    """
    supplied_key = extract_api_key(request)
    normalized_tenant = normalize(requested_tenant, 120)
    normalized_user = normalize(requested_user, 120) or "api-user"

    if supplied_key:
        # Attempt remote registry sync before matching if sync is enabled and configured.
        if registry_sync and registry_sync.get("enabled"):
            sync_url = registry_sync.get("url", "")
            sync_token = registry_sync.get("token", "")
            sync_timeout = float(registry_sync.get("timeout_seconds", 10.0))
            if sync_url and sync_token:
                sync_registry(
                    registry_path=registry_path,
                    remote_url=sync_url,
                    remote_token=sync_token,
                    remote_timeout=sync_timeout,
                )

        registry = load_registry(registry_path)
        supplied_hash = hash_api_key(supplied_key)
        matched = next(
            (
                item
                for item in registry
                if normalize(str(item.get("api_key_hash", "")), 128).lower() == supplied_hash
            ),
            None,
        )

        if not matched:
            raise HTTPException(status_code=401, detail="Invalid OmniMemora API key.")

        tenant_id = normalize(str(matched.get("tenant_id", "")), 120)
        status = normalize(str(matched.get("status", "disabled")), 40).lower() or "disabled"
        if not tenant_id:
            raise HTTPException(status_code=500, detail="Tenant registry entry is missing tenant_id.")
        if status != "active":
            raise HTTPException(status_code=403, detail="Tenant is disabled.")
        if normalized_tenant and normalized_tenant != tenant_id:
            raise HTTPException(status_code=403, detail="Tenant does not match the supplied API key.")

        header_user = normalize(request.headers.get("X-OmniMemora-User"), 120)
        default_user = normalize(str(matched.get("default_user", "")), 120)

        return AccessResolution(
            tenant_id=tenant_id,
            user_id=header_user or normalized_user or default_user or "api-user",
            plan=normalize(str(matched.get("plan", "starter")), 80) or "starter",
            status=status,
            token_id=normalize(str(matched.get("token_id", "")), 120) or None,
            auth_mode="omnimemora_key",
            key_present=True,
        )

    if require_key:
        raise HTTPException(status_code=401, detail="An OmniMemora API key is required for this endpoint.")

    return AccessResolution(
        tenant_id=normalized_tenant,
        user_id=normalized_user,
        plan="internal",
        status="active",
        token_id=None,
        auth_mode="legacy_body",
        key_present=False,
    )


def atomic_write_registry(registry_path: str, tenants: list[Dict[str, Any]]) -> None:
    """
    Atomically write the tenant registry to disk using a write-to-temp-then-rename pattern.

    The caller passes the desired list of tenant entries (already serializable dicts).
    A temporary file in the same directory as the target is used so rename is atomic
    on the same filesystem.  On success the final file contains a JSON object with
    a top-level "tenants" key matching the existing registry schema.
    """
    target = Path(registry_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory so rename is atomic (same FS)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix="registry_",
        dir=str(target.parent.resolve()),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"tenants": tenants}, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, str(target))
    except Exception:
        # Clean up temp file if anything goes wrong
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
