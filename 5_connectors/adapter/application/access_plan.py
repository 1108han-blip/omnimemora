"""
access_plan.py - Identity Spine + Layered Memory Domain projection
==================================================================
Builds a request-scoped identity/access-plan contract for adapter ingress.

This module stays read-only/derivation oriented: it does not perform memory
operations itself.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


def _str_or_none(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        normalized = _str_or_none(value)
        if normalized:
            return normalized
    return None


def _header_value(headers: Mapping[str, str], *names: str) -> Optional[str]:
    for name in names:
        value = headers.get(name)
        normalized = _str_or_none(value)
        if normalized:
            return normalized
    return None


def _build_domain_ref(
    *,
    tenant_id: str,
    scope_type: str,
    scope_key: str,
    sharing_mode: str,
    bound_instance_ids: Optional[list[str]] = None,
) -> Dict[str, Any]:
    domain_id = f"{tenant_id}:{scope_type}:{scope_key}"
    payload: Dict[str, Any] = {
        "domain_id": domain_id,
        "tenant_id": tenant_id,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "sharing_mode": sharing_mode,
    }
    if bound_instance_ids:
        payload["bound_instance_ids"] = bound_instance_ids
    return payload


def extract_hints_from_request(
    *,
    request: Any = None,
    body: Optional[dict] = None,
) -> Dict[str, Any]:
    body = body if isinstance(body, dict) else {}
    headers: Mapping[str, str] = getattr(request, "headers", {}) or {}
    query: Mapping[str, str] = getattr(request, "query_params", {}) or {}

    raw_agent_id = _first_non_empty(
        _header_value(headers, "x-omnimemora-agent", "X-OmniMemora-Agent"),
        _header_value(headers, "x-agent-id", "X-Agent-Id"),
        _header_value(headers, "x-agent-family", "X-Agent-Family"),
        body.get("agent_id"),
        body.get("agent"),
        body.get("agent_family"),
    )
    family_id = _first_non_empty(
        _header_value(headers, "x-agent-family", "X-Agent-Family"),
        _header_value(headers, "x-omnimemora-agent", "X-OmniMemora-Agent"),
        body.get("agent_family"),
    )
    tenant_id = _first_non_empty(
        _header_value(headers, "x-omnimemora-tenant", "X-OmniMemora-Tenant"),
        _header_value(headers, "x-tenant-id", "X-Tenant-Id"),
        query.get("tenant"),
        body.get("tenant_id"),
        body.get("tenant"),
        "default",
    )
    session_id = _first_non_empty(
        headers.get("x-session-id"),
        query.get("session_id"),
        body.get("session_id"),
        body.get("conversation_id"),
        body.get("thread_id"),
    )
    window_id = _first_non_empty(
        headers.get("x-window-id"),
        query.get("window_id"),
        body.get("window_id"),
        body.get("session_window_id"),
        session_id,
    )
    instance_id = _first_non_empty(
        headers.get("x-instance-id"),
        body.get("instance_id"),
        body.get("client_instance_id"),
        raw_agent_id,
        family_id,
    )
    workspace_id = _first_non_empty(
        _header_value(headers, "x-omnimemora-workspace", "X-OmniMemora-Workspace"),
        _header_value(headers, "x-workspace-id", "X-Workspace-Id"),
        query.get("workspace_id"),
        body.get("workspace_id"),
    )
    user_id = _first_non_empty(
        _header_value(headers, "x-omnimemora-user", "X-OmniMemora-User"),
        _header_value(headers, "x-user-id", "X-User-Id"),
        query.get("user_id"),
        body.get("user_id"),
    )
    sharing_mode = _first_non_empty(
        _header_value(headers, "x-omnimemora-sharing-mode", "X-OmniMemora-Sharing-Mode"),
        _header_value(headers, "x-sharing-mode", "X-Sharing-Mode"),
        body.get("sharing_mode"),
        "isolated",
    )
    allow_shared_write = _truthy(
        headers.get("x-omnimemora-shared-write")
    ) or _truthy(body.get("allow_shared_write"))
    custom_shared_key = _first_non_empty(
        headers.get("x-omnimemora-custom-domain-key"),
        body.get("custom_shared_domain_key"),
    )
    shared_read_only_key = _first_non_empty(
        headers.get("x-omnimemora-readonly-domain-key"),
        body.get("shared_read_only_domain_key"),
    )
    user_shared_enabled = _truthy(
        headers.get("x-omnimemora-user-shared")
    ) or _truthy(body.get("enable_user_shared"))

    return {
        "raw_agent_id": raw_agent_id,
        "family_id": family_id,
        "tenant_id": tenant_id,
        "instance_id": instance_id,
        "session_id": session_id,
        "window_id": window_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "sharing_mode": sharing_mode,
        "allow_shared_write": allow_shared_write,
        "custom_shared_domain_key": custom_shared_key,
        "shared_read_only_domain_key": shared_read_only_key,
        "user_shared_enabled": user_shared_enabled,
    }


def build_identity_and_access_plan(
    *,
    request_id: str,
    family_id: str,
    hints: Dict[str, Any],
    sharing_policy_source: str = "default_private_first",
) -> Dict[str, Any]:
    tenant_id = _str_or_none(hints.get("tenant_id")) or "default"
    family = _str_or_none(family_id) or "unknown"
    raw_agent_id = _str_or_none(hints.get("raw_agent_id"))
    instance_id = _str_or_none(hints.get("instance_id")) or raw_agent_id or family
    session_id = _str_or_none(hints.get("session_id"))
    window_id = _str_or_none(hints.get("window_id")) or session_id
    workspace_id = _str_or_none(hints.get("workspace_id"))
    user_id = _str_or_none(hints.get("user_id"))
    sharing_mode = _str_or_none(hints.get("sharing_mode")) or "isolated"
    allow_shared_write = bool(hints.get("allow_shared_write"))
    custom_shared_key = _str_or_none(hints.get("custom_shared_domain_key"))
    shared_read_only_key = _str_or_none(hints.get("shared_read_only_domain_key"))
    user_shared_enabled = bool(hints.get("user_shared_enabled"))

    identity_spine = {
        "tenant_id": tenant_id,
        "family_id": family,
        "instance_id": instance_id,
        "window_id": window_id,
        "session_id": session_id,
        "request_id": request_id,
        "raw_agent_id": raw_agent_id,
    }

    private_scope_key = instance_id
    primary_write_domain = _build_domain_ref(
        tenant_id=tenant_id,
        scope_type="instance_private",
        scope_key=private_scope_key,
        sharing_mode="isolated",
        bound_instance_ids=[instance_id],
    )
    read_domains = [primary_write_domain]
    secondary_write_domains: list[Dict[str, Any]] = []

    if workspace_id:
        workspace_domain = _build_domain_ref(
            tenant_id=tenant_id,
            scope_type="workspace_shared",
            scope_key=workspace_id,
            sharing_mode=sharing_mode if sharing_mode in {"shared", "shared_read_only"} else "shared",
            bound_instance_ids=[instance_id],
        )
        read_domains.append(workspace_domain)
        if allow_shared_write and workspace_domain["sharing_mode"] != "shared_read_only":
            secondary_write_domains.append(workspace_domain)

    if user_shared_enabled and user_id:
        user_domain = _build_domain_ref(
            tenant_id=tenant_id,
            scope_type="user_shared",
            scope_key=user_id,
            sharing_mode="shared",
            bound_instance_ids=[instance_id],
        )
        read_domains.append(user_domain)
        if allow_shared_write:
            secondary_write_domains.append(user_domain)

    if custom_shared_key:
        custom_domain = _build_domain_ref(
            tenant_id=tenant_id,
            scope_type="custom_shared",
            scope_key=custom_shared_key,
            sharing_mode="shared",
            bound_instance_ids=[instance_id],
        )
        read_domains.append(custom_domain)
        if allow_shared_write:
            secondary_write_domains.append(custom_domain)

    if shared_read_only_key:
        read_only_domain = _build_domain_ref(
            tenant_id=tenant_id,
            scope_type="shared_read_only",
            scope_key=shared_read_only_key,
            sharing_mode="shared_read_only",
            bound_instance_ids=[instance_id],
        )
        read_domains.append(read_only_domain)

    access_plan = {
        "identity": identity_spine,
        "read_domains": read_domains,
        "primary_write_domain": primary_write_domain,
        "secondary_write_domains": secondary_write_domains,
        "allow_secondary_writes": allow_shared_write,
        "sharing_policy_source": sharing_policy_source,
    }

    return {
        "identity_spine": identity_spine,
        "access_plan": access_plan,
        "tenant_id": tenant_id,
        "family_id": family,
        "instance_id": instance_id,
        "session_id": session_id,
        "window_id": window_id,
        "raw_agent_id": raw_agent_id,
        "workspace_id": workspace_id,
        "primary_write_domain": primary_write_domain,
        "read_domains": read_domains,
        "secondary_write_domains": secondary_write_domains,
        "sharing_policy_source": sharing_policy_source,
    }
