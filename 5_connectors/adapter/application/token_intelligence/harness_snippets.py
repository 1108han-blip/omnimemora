"""Copy-paste harness snippets for Token Intelligence Lite."""

from __future__ import annotations

from typing import Any

from .agent_attach import proxy_base_url_for_config

SUPPORTED_SNIPPETS = {
    "generic-env",
    "openai-sdk-js",
    "openai-sdk-python",
    "litellm",
    "openclaw",
}


def build_harness_snippet(kind: str, config: Any) -> dict[str, Any]:
    normalized = _normalize_kind(kind)
    proxy_base_url = proxy_base_url_for_config(config)
    api_key_ref = f"${config.upstream.api_key_env}"
    return {
        "schema_version": "token-intelligence-harness-snippet-v1",
        "kind": normalized,
        "proxy_base_url": proxy_base_url,
        "upstream_api_key_env": config.upstream.api_key_env,
        "mutates_files": False,
        "stores_api_key_value": False,
        "content": _snippet_content(normalized, proxy_base_url, api_key_ref, config.upstream.api_key_env),
    }


def supported_snippets() -> list[str]:
    return sorted(SUPPORTED_SNIPPETS)


def _normalize_kind(kind: str) -> str:
    normalized = kind.strip().lower().replace("_", "-")
    aliases = {
        "env": "generic-env",
        "generic": "generic-env",
        "generic-env": "generic-env",
        "node": "openai-sdk-js",
        "javascript": "openai-sdk-js",
        "openai-js": "openai-sdk-js",
        "openai-sdk-js": "openai-sdk-js",
        "python": "openai-sdk-python",
        "openai-python": "openai-sdk-python",
        "openai-sdk-python": "openai-sdk-python",
        "litellm": "litellm",
        "openclaw": "openclaw",
    }
    if normalized not in aliases:
        raise ValueError(f"unsupported snippet kind: {kind}")
    return aliases[normalized]


def _snippet_content(kind: str, proxy_base_url: str, api_key_ref: str, api_key_env: str) -> str:
    if kind == "generic-env":
        return "\n".join(
            [
                f"export OPENAI_BASE_URL={_shell_quote(proxy_base_url)}",
                f"export OPENAI_API_KEY={_shell_quote(api_key_ref)}",
                "export OMNI_TOKEN_AUDIT_AGENT_ID='generic'",
            ]
        )
    if kind == "openai-sdk-js":
        return "\n".join(
            [
                "import OpenAI from 'openai';",
                "",
                "const client = new OpenAI({",
                f"  baseURL: '{proxy_base_url}',",
                f"  apiKey: process.env.{api_key_env},",
                "});",
            ]
        )
    if kind == "openai-sdk-python":
        return "\n".join(
            [
                "import os",
                "from openai import OpenAI",
                "",
                "client = OpenAI(",
                f"    base_url='{proxy_base_url}',",
                f"    api_key=os.environ['{api_key_env}'],",
                ")",
            ]
        )
    if kind == "litellm":
        return "\n".join(
            [
                f"export OPENAI_API_BASE={_shell_quote(proxy_base_url)}",
                f"export OPENAI_API_KEY={_shell_quote(api_key_ref)}",
                "# Then use an OpenAI-compatible model through LiteLLM.",
            ]
        )
    if kind == "openclaw":
        return "\n".join(
            [
                "# Prefer the managed launcher when OpenClaw reads OpenAI-compatible env vars:",
                "omni-token-audit attach openclaw --with-launcher",
                "~/.omnimemora/token-intelligence/agents/openclaw-launch.sh openclaw <args...>",
                "",
                "# Manual equivalent:",
                f"export OPENAI_BASE_URL={_shell_quote(proxy_base_url)}",
                f"export OPENAI_API_KEY={_shell_quote(api_key_ref)}",
            ]
        )
    raise ValueError(f"unsupported snippet kind: {kind}")


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
