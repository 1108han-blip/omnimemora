"""Profile-only agent attach helpers for Token Intelligence Lite."""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import default_config_path, load_config
from .local_proxy import VERSION

ATTACH_DIR_ENV = "OMNIMEMORA_TOKEN_INTELLIGENCE_ATTACH_DIR"


def build_doctor_report(config_path: Path) -> tuple[int, dict[str, Any]]:
    payload: dict[str, Any] = {
        "schema_version": "token-intelligence-doctor-v1",
        "version": VERSION,
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
    }
    try:
        config = load_config(config_path)
    except Exception as exc:
        payload.update({"status": "error", "config_valid": False, "config_error": str(exc)})
        return 1, payload
    proxy_base_url = proxy_base_url_for_config(config)
    payload.update(
        {
            "status": "ok",
            "config_valid": True,
            "proxy_base_url": proxy_base_url,
            "mcp_url": f"http://{config.server.host}:{config.server.port}/mcp",
            "upstream_base_url": config.upstream.base_url,
            "upstream_api_key_env": config.upstream.api_key_env,
            "upstream_api_key_present": bool(config.resolved_upstream_api_key()),
            "attach_dir": str(attach_dir()),
            "supported_targets": ["openclaw", "claude-code", "generic"],
            "proxy_health": probe_proxy_health(proxy_base_url),
        }
    )
    return 0, payload


def attach_profile(target_value: str, config_path: Path | None, *, dry_run: bool = False) -> dict[str, Any]:
    config = load_config(config_path or default_config_path())
    target = normalize_target(target_value)
    profile = build_attach_profile(target, config)
    if dry_run:
        return profile
    path = attach_profile_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    profile["profile_path"] = str(path)
    profile["status"] = "profile_written"
    return profile


def detach_profile(target_value: str) -> dict[str, Any]:
    target = normalize_target(target_value)
    path = attach_profile_path(target)
    existed = path.exists()
    if existed:
        path.unlink()
    return {
        "schema_version": "token-intelligence-agent-detach-v1",
        "target": target,
        "status": "detached" if existed else "not_attached",
        "profile_path": str(path),
        "agent_config_mutated": False,
    }


def proxy_base_url_for_config(config: Any) -> str:
    return f"http://{config.server.host}:{config.server.port}/v1"


def probe_proxy_health(proxy_base_url: str) -> dict[str, Any]:
    health_url = proxy_base_url.rsplit("/", 1)[0] + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=2) as response:
            body = json.loads(response.read())
        return {"reachable": True, "status": body.get("status"), "url": health_url}
    except Exception as exc:
        return {"reachable": False, "url": health_url, "error": str(exc)}


def normalize_target(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "claude": "claude-code",
        "claude-code-cli": "claude-code",
        "claude-code": "claude-code",
        "openclaw": "openclaw",
        "generic": "generic",
        "openai": "generic",
        "openai-compatible": "generic",
    }
    if normalized not in aliases:
        raise ValueError(f"unsupported attach target: {value}")
    return aliases[normalized]


def build_attach_profile(target: str, config: Any) -> dict[str, Any]:
    proxy_base_url = proxy_base_url_for_config(config)
    agent_id = "claude_code" if target == "claude-code" else target
    return {
        "schema_version": "token-intelligence-agent-attach-v1",
        "status": "dry_run",
        "target": target,
        "agent_id": agent_id,
        "mode": "local_proxy_profile",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "proxy_base_url": proxy_base_url,
        "mcp_url": f"http://{config.server.host}:{config.server.port}/mcp",
        "upstream_base_url": config.upstream.base_url,
        "upstream_api_key_env": config.upstream.api_key_env,
        "client_headers": {"x-omni-agent-id": agent_id},
        "client_env": {
            "OPENAI_BASE_URL": proxy_base_url,
            "OPENAI_API_KEY": f"${config.upstream.api_key_env}",
        },
        "agent_config_mutated": False,
        "apply_status": "profile_only",
        "next_steps": [
            "Start the local proxy with `omni-token-audit proxy start`.",
            "Configure the agent base_url to proxy_base_url if it supports OpenAI-compatible custom endpoints.",
            "Use `omni-token-audit doctor` to check local readiness.",
        ],
        "rollback_command": f"omni-token-audit detach {target}",
    }


def attach_dir() -> Path:
    explicit = os.getenv(ATTACH_DIR_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".omnimemora" / "token-intelligence" / "agents"


def attach_profile_path(target: str) -> Path:
    return attach_dir() / f"{target}.json"
