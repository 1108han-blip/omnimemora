"""
path_registry.py - Request path classification registry

Phase 0/1 foundation:
- central place to classify primary vs legacy vs direct paths
- supports later shadow/traffic-shift work without changing routing yet
"""
from __future__ import annotations

from typing import Dict, Optional


_PATH_REGISTRY: Dict[str, Dict[str, object]] = {
    "/v1/responses": {
        "path_class": "primary",
        "path_family": "responses",
        "runtime_mode": "main",
        "notes": "Current primary Codex-compatible product path",
    },
    "/v1/codex/responses": {
        "path_class": "legacy",
        "path_family": "responses",
        "runtime_mode": "legacy_alias",
        "notes": "Compatibility alias for responses path",
    },
    "/v1/chat/completions": {
        "path_class": "legacy",
        "path_family": "chat_completions",
        "runtime_mode": "legacy_direct",
        "notes": "OpenAI-compatible compatibility path",
    },
    "/llm/chat": {
        "path_class": "legacy",
        "path_family": "chat_completions",
        "runtime_mode": "legacy_direct",
        "notes": "Gateway chat alias for OpenClaw compatibility",
    },
    "/llm/chat/completions": {
        "path_class": "legacy",
        "path_family": "chat_completions",
        "runtime_mode": "legacy_direct",
        "notes": "Gateway chat completions alias",
    },
    "/llm/v1/chat/completions": {
        "path_class": "legacy",
        "path_family": "chat_completions",
        "runtime_mode": "legacy_direct",
        "notes": "Gateway v1 chat completions alias",
    },
    "/llm/api/chat": {
        "path_class": "legacy",
        "path_family": "chat_completions",
        "runtime_mode": "legacy_direct",
        "notes": "OpenClaw historical chat ingress",
    },
    "/llm/anthropic": {
        "path_class": "legacy",
        "path_family": "anthropic_messages",
        "runtime_mode": "legacy_direct",
        "notes": "Anthropic legacy alias",
    },
    "/llm/v1/messages": {
        "path_class": "legacy",
        "path_family": "anthropic_messages",
        "runtime_mode": "legacy_direct",
        "notes": "Anthropic gateway alias",
    },
    "/v1/messages": {
        "path_class": "legacy",
        "path_family": "anthropic_messages",
        "runtime_mode": "legacy_direct",
        "notes": "Anthropic public compatibility path",
    },
    "/mcp": {
        "path_class": "legacy",
        "path_family": "mcp",
        "runtime_mode": "compatibility",
        "notes": "MCP compatibility surface",
    },
}


def classify_path(path: Optional[str]) -> Dict[str, object]:
    normalized = (path or "").strip() or "unknown"
    entry = dict(_PATH_REGISTRY.get(normalized, {}))
    if not entry:
        entry = {
            "path_class": "unknown",
            "path_family": "unknown",
            "runtime_mode": "unknown",
            "notes": "Unregistered path",
        }
    entry["path"] = normalized
    return entry


def is_primary_path(path: Optional[str]) -> bool:
    return classify_path(path).get("path_class") == "primary"


def get_registry_snapshot() -> Dict[str, Dict[str, object]]:
    return {path: dict(meta) for path, meta in _PATH_REGISTRY.items()}
