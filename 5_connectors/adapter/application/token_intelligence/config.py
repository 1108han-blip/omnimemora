"""Config loading for the Token Intelligence local proxy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .local_proxy import LocalProxyConfig

DEFAULT_CONFIG_ENV = "OMNIMEMORA_TOKEN_INTELLIGENCE_CONFIG"
DEFAULT_API_KEY_ENV = "OMNI_AUDIT_UPSTREAM_API_KEY"
DEFAULT_OPENAI_API_KEY_ENV = "OMNI_AUDIT_OPENAI_UPSTREAM_API_KEY"
DEFAULT_ANTHROPIC_API_KEY_ENV = "OMNI_AUDIT_ANTHROPIC_UPSTREAM_API_KEY"
DEFAULT_METADATA_URL = "https://doloclaw.com/releases/token-intelligence/latest.json"


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 18081


@dataclass(frozen=True)
class UpstreamConfig:
    base_url: str = "https://example-relay.invalid/v1"
    api_key_env: str = DEFAULT_API_KEY_ENV
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class ProtocolUpstreamsConfig:
    openai: UpstreamConfig = field(
        default_factory=lambda: UpstreamConfig(
            base_url="https://example-openai-relay.invalid/v1",
            api_key_env=DEFAULT_OPENAI_API_KEY_ENV,
        )
    )
    anthropic: UpstreamConfig = field(
        default_factory=lambda: UpstreamConfig(
            base_url="https://example-anthropic-relay.invalid",
            api_key_env=DEFAULT_ANTHROPIC_API_KEY_ENV,
        )
    )


@dataclass(frozen=True)
class PrivacyConfig:
    content_mode: str = "metadata_only"
    store_raw_prompt: bool = False
    store_raw_response: bool = False


@dataclass(frozen=True)
class AuditConfig:
    enabled: bool = True
    fail_open: bool = True


@dataclass(frozen=True)
class UpdatesConfig:
    enabled: bool = True
    metadata_url: str = DEFAULT_METADATA_URL
    channel: str = "beta"


@dataclass(frozen=True)
class TokenIntelligenceConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    upstream: UpstreamConfig = field(default_factory=UpstreamConfig)
    upstreams: ProtocolUpstreamsConfig = field(default_factory=ProtocolUpstreamsConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    updates: UpdatesConfig = field(default_factory=UpdatesConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
            },
            "upstream": {
                "base_url": self.upstream.base_url,
                "api_key_env": self.upstream.api_key_env,
                "timeout_seconds": self.upstream.timeout_seconds,
            },
            "upstreams": {
                "openai": {
                    "base_url": self.upstreams.openai.base_url,
                    "api_key_env": self.upstreams.openai.api_key_env,
                    "timeout_seconds": self.upstreams.openai.timeout_seconds,
                },
                "anthropic": {
                    "base_url": self.upstreams.anthropic.base_url,
                    "api_key_env": self.upstreams.anthropic.api_key_env,
                    "timeout_seconds": self.upstreams.anthropic.timeout_seconds,
                },
            },
            "privacy": {
                "content_mode": self.privacy.content_mode,
                "store_raw_prompt": self.privacy.store_raw_prompt,
                "store_raw_response": self.privacy.store_raw_response,
            },
            "audit": {
                "enabled": self.audit.enabled,
                "fail_open": self.audit.fail_open,
            },
            "updates": {
                "enabled": self.updates.enabled,
                "metadata_url": self.updates.metadata_url,
                "channel": self.updates.channel,
            },
        }

    def resolved_upstream_api_key(self) -> str:
        return os.getenv(self.upstream.api_key_env, "").strip()

    def resolved_openai_upstream_api_key(self) -> str:
        return os.getenv(self.upstreams.openai.api_key_env, "").strip()

    def resolved_anthropic_upstream_api_key(self) -> str:
        return os.getenv(self.upstreams.anthropic.api_key_env, "").strip()

    def to_local_proxy_config(self) -> LocalProxyConfig:
        validate_config(self)
        return LocalProxyConfig(
            host=self.server.host,
            port=self.server.port,
            upstream_base_url=self.upstream.base_url,
            upstream_api_key=self.resolved_upstream_api_key(),
            upstream_timeout_seconds=self.upstream.timeout_seconds,
            openai_upstream_base_url=self.upstreams.openai.base_url,
            openai_upstream_api_key=self.resolved_openai_upstream_api_key(),
            openai_upstream_timeout_seconds=self.upstreams.openai.timeout_seconds,
            anthropic_upstream_base_url=self.upstreams.anthropic.base_url,
            anthropic_upstream_api_key=self.resolved_anthropic_upstream_api_key(),
            anthropic_upstream_timeout_seconds=self.upstreams.anthropic.timeout_seconds,
            audit_enabled=self.audit.enabled,
            audit_fail_open=self.audit.fail_open,
            update_check_enabled=self.updates.enabled,
            update_metadata_url=self.updates.metadata_url,
            update_channel=self.updates.channel,
        )


def default_config_path() -> Path:
    explicit = os.getenv(DEFAULT_CONFIG_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".omnimemora" / "token-intelligence" / "config.json"


def default_config() -> TokenIntelligenceConfig:
    return TokenIntelligenceConfig()


def load_config(path: Optional[str | Path] = None) -> TokenIntelligenceConfig:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config root must be an object")
    config = _config_from_dict(payload)
    validate_config(config)
    return config


def write_default_config(path: Optional[str | Path] = None, *, overwrite: bool = False) -> Path:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if config_path.exists() and not overwrite:
        raise FileExistsError(str(config_path))
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_json(default_config().to_dict()) + "\n", encoding="utf-8")
    return config_path


def validate_config(config: TokenIntelligenceConfig) -> None:
    if config.server.host != "127.0.0.1":
        raise ValueError("server.host must be 127.0.0.1 for TI-001")
    if config.server.port <= 0 or config.server.port > 65535:
        raise ValueError("server.port must be between 1 and 65535")
    if not config.upstream.base_url.strip():
        raise ValueError("upstream.base_url is required")
    if not config.upstream.api_key_env.strip():
        raise ValueError("upstream.api_key_env is required")
    if config.upstream.timeout_seconds <= 0:
        raise ValueError("upstream.timeout_seconds must be positive")
    _validate_upstream_config("upstreams.openai", config.upstreams.openai)
    _validate_upstream_config("upstreams.anthropic", config.upstreams.anthropic)
    if config.privacy.content_mode != "metadata_only":
        raise ValueError("TI-001 only supports privacy.content_mode=metadata_only")
    if config.privacy.store_raw_prompt or config.privacy.store_raw_response:
        raise ValueError("TI-001 must not store raw prompt or response by default")
    if not config.updates.metadata_url.strip():
        raise ValueError("updates.metadata_url is required")


def _config_from_dict(payload: dict[str, Any]) -> TokenIntelligenceConfig:
    server = _as_dict(payload.get("server"))
    upstream = _as_dict(payload.get("upstream"))
    upstreams = _as_dict(payload.get("upstreams"))
    privacy = _as_dict(payload.get("privacy"))
    audit = _as_dict(payload.get("audit"))
    updates = _as_dict(payload.get("updates"))
    legacy_upstream = UpstreamConfig(
        base_url=str(upstream.get("base_url", "https://example-relay.invalid/v1")),
        api_key_env=str(upstream.get("api_key_env", DEFAULT_API_KEY_ENV)),
        timeout_seconds=_float(upstream.get("timeout_seconds", 120.0)),
    )
    openai_upstream = _protocol_upstream_config(
        _as_dict(upstreams.get("openai")),
        fallback=legacy_upstream,
    )
    anthropic_upstream = _protocol_upstream_config(
        _as_dict(upstreams.get("anthropic")),
        fallback=legacy_upstream,
    )
    return TokenIntelligenceConfig(
        server=ServerConfig(
            host=str(server.get("host", "127.0.0.1")),
            port=_int(server.get("port", 18081)),
        ),
        upstream=legacy_upstream,
        upstreams=ProtocolUpstreamsConfig(openai=openai_upstream, anthropic=anthropic_upstream),
        privacy=PrivacyConfig(
            content_mode=str(privacy.get("content_mode", "metadata_only")),
            store_raw_prompt=bool(privacy.get("store_raw_prompt", False)),
            store_raw_response=bool(privacy.get("store_raw_response", False)),
        ),
        audit=AuditConfig(
            enabled=bool(audit.get("enabled", True)),
            fail_open=bool(audit.get("fail_open", True)),
        ),
        updates=UpdatesConfig(
            enabled=bool(updates.get("enabled", True)),
            metadata_url=str(updates.get("metadata_url", DEFAULT_METADATA_URL)),
            channel=str(updates.get("channel", "beta")),
        ),
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _protocol_upstream_config(payload: dict[str, Any], *, fallback: UpstreamConfig) -> UpstreamConfig:
    if not payload:
        return fallback
    return UpstreamConfig(
        base_url=str(payload.get("base_url", fallback.base_url)),
        api_key_env=str(payload.get("api_key_env", fallback.api_key_env)),
        timeout_seconds=_float(payload.get("timeout_seconds", fallback.timeout_seconds)),
    )


def _validate_upstream_config(name: str, upstream: UpstreamConfig) -> None:
    if not upstream.base_url.strip():
        raise ValueError(f"{name}.base_url is required")
    if not upstream.api_key_env.strip():
        raise ValueError(f"{name}.api_key_env is required")
    if upstream.timeout_seconds <= 0:
        raise ValueError(f"{name}.timeout_seconds must be positive")


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
