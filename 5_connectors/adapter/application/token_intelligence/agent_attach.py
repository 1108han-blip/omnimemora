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
            "proxy_anthropic_base_url": proxy_anthropic_base_url_for_config(config),
            "mcp_url": f"http://{config.server.host}:{config.server.port}/mcp",
            "upstream_base_url": config.upstream.base_url,
            "upstream_api_key_env": config.upstream.api_key_env,
            "upstream_api_key_present": bool(config.resolved_upstream_api_key()),
            "upstreams": {
                "openai": {
                    "base_url": config.upstreams.openai.base_url,
                    "api_key_env": config.upstreams.openai.api_key_env,
                    "api_key_present": bool(config.resolved_openai_upstream_api_key()),
                },
                "anthropic": {
                    "base_url": config.upstreams.anthropic.base_url,
                    "api_key_env": config.upstreams.anthropic.api_key_env,
                    "api_key_present": bool(config.resolved_anthropic_upstream_api_key()),
                },
            },
            "attach_dir": str(attach_dir()),
            "supported_targets": ["openclaw", "claude-code", "generic"],
            "proxy_health": probe_proxy_health(proxy_base_url),
        }
    )
    return 0, payload


def attach_profile(
    target_value: str,
    config_path: Path | None,
    *,
    dry_run: bool = False,
    with_launcher: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path or default_config_path())
    target = normalize_target(target_value)
    profile = build_attach_profile(target, config)
    if dry_run:
        if with_launcher:
            profile["launcher"] = launch_artifact_paths(target)
        return profile
    path = attach_profile_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    if with_launcher:
        profile["launcher"] = write_launch_artifacts(target, profile)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    profile["profile_path"] = str(path)
    profile["status"] = "profile_written"
    return profile


def detach_profile(target_value: str) -> dict[str, Any]:
    target = normalize_target(target_value)
    path = attach_profile_path(target)
    launcher = launch_artifact_paths(target)
    existed = path.exists()
    if existed:
        path.unlink()
    removed_launcher = _unlink_if_exists(Path(launcher["script_path"]))
    removed_env = _unlink_if_exists(Path(launcher["env_path"]))
    return {
        "schema_version": "token-intelligence-agent-detach-v1",
        "target": target,
        "status": "detached" if existed else "not_attached",
        "profile_path": str(path),
        "removed_launcher": removed_launcher,
        "removed_env": removed_env,
        "agent_config_mutated": False,
    }


def proxy_base_url_for_config(config: Any) -> str:
    return f"http://{config.server.host}:{config.server.port}/v1"


def proxy_anthropic_base_url_for_config(config: Any) -> str:
    return f"http://{config.server.host}:{config.server.port}"


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
    proxy_anthropic_base_url = proxy_anthropic_base_url_for_config(config)
    agent_id = "claude_code" if target == "claude-code" else target
    return {
        "schema_version": "token-intelligence-agent-attach-v1",
        "status": "dry_run",
        "target": target,
        "agent_id": agent_id,
        "mode": "local_proxy_profile",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "proxy_base_url": proxy_base_url,
        "proxy_anthropic_base_url": proxy_anthropic_base_url,
        "mcp_url": f"http://{config.server.host}:{config.server.port}/mcp",
        "upstream_base_url": config.upstream.base_url,
        "upstream_api_key_env": config.upstream.api_key_env,
        "upstreams": {
            "openai": {
                "base_url": config.upstreams.openai.base_url,
                "api_key_env": config.upstreams.openai.api_key_env,
            },
            "anthropic": {
                "base_url": config.upstreams.anthropic.base_url,
                "api_key_env": config.upstreams.anthropic.api_key_env,
            },
        },
        "client_headers": {"x-omni-agent-id": agent_id},
        "client_env": {
            "OPENAI_BASE_URL": proxy_base_url,
            "OPENAI_API_KEY": f"${config.upstreams.openai.api_key_env}",
            "ANTHROPIC_BASE_URL": proxy_anthropic_base_url,
            "ANTHROPIC_AUTH_TOKEN": f"${config.upstreams.anthropic.api_key_env}",
            "OMNI_TOKEN_AUDIT_AGENT_ID": agent_id,
            "OMNI_TOKEN_AUDIT_MCP_URL": f"http://{config.server.host}:{config.server.port}/mcp",
        },
        "agent_config_mutated": False,
        "apply_status": "profile_only",
        "next_steps": [
            "Start the local proxy with `omni-token-audit proxy start`.",
            "Configure OpenAI-compatible clients to proxy_base_url.",
            "Configure Anthropic-compatible clients to proxy_anthropic_base_url.",
            "Use `omni-token-audit doctor` to check local readiness.",
        ],
        "rollback_command": f"omni-token-audit detach {target}",
    }


def write_launch_artifacts(target: str, profile: dict[str, Any]) -> dict[str, Any]:
    paths = launch_artifact_paths(target)
    env_path = Path(paths["env_path"])
    script_path = Path(paths["script_path"])
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(_env_text(profile), encoding="utf-8")
    script_path.write_text(_launcher_text(target, env_path.name), encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | 0o755)
    return {
        **paths,
        "mode": "managed_env_launcher",
        "agent_config_mutated": False,
        "usage": f"{script_path} <agent command> [args...]",
    }


def launch_artifact_paths(target: str) -> dict[str, str]:
    directory = attach_dir()
    return {
        "env_path": str(directory / f"{target}.env"),
        "script_path": str(directory / f"{target}-launch.sh"),
    }


def attach_dir() -> Path:
    explicit = os.getenv(ATTACH_DIR_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".omnimemora" / "token-intelligence" / "agents"


def attach_profile_path(target: str) -> Path:
    return attach_dir() / f"{target}.json"


def _env_text(profile: dict[str, Any]) -> str:
    client_env = profile.get("client_env") if isinstance(profile.get("client_env"), dict) else {}
    lines = [
        "# Generated by omni-token-audit attach --with-launcher.",
        "# This file references the upstream API key environment variable; it does not store the key value.",
    ]
    for key in [
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "OMNI_TOKEN_AUDIT_AGENT_ID",
        "OMNI_TOKEN_AUDIT_MCP_URL",
    ]:
        value = str(client_env.get(key) or "")
        if not value:
            continue
        lines.append(f"export {key}={_shell_quote(value)}")
    return "\n".join(lines) + "\n"


def _launcher_text(target: str, env_name: str) -> str:
    return (
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        'SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        f'. "$SCRIPT_DIR/{env_name}"\n'
        'if [ "$#" -eq 0 ]; then\n'
        f'  echo "Token Audit launcher for {target}. Pass the agent command to run." >&2\n'
        '  echo "Example: $0 <agent-command> [args...]" >&2\n'
        "  exit 2\n"
        "fi\n"
        'exec "$@"\n'
    )


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _unlink_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True
