"""
truth_registry.py - canonical registries for Truth Bridge v2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .truth_models import (
    AuthDefinition,
    CanonicalTruthRefs,
    DEFAULT_SOURCE_PRIORITY_CHAIN as MODEL_SOURCE_PRIORITY_CHAIN,
    EndpointDefinition,
    ModelDefinition,
    ProviderDefinition,
    RawTruthIntent,
)


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


PROVIDER_ALIASES: dict[str, str] = {
    "openai": "openai_compatible",
    "openai_compatible": "openai_compatible",
    "openai_codex_oauth": "openai_codex_oauth",
    "openai-codex": "openai_codex_oauth",
    "anthropic": "anthropic",
    "minimax_anthropic_compatible": "minimax_anthropic_compatible",
}

ENDPOINT_ALIASES: dict[str, str] = {
    "openai_local_default": "local_ollama_openai_v1",
    "local_ollama_openai_v1": "local_ollama_openai_v1",
    "openai_codex_chatgpt": "chatgpt_codex_backend",
    "chatgpt_codex_backend": "chatgpt_codex_backend",
    "chatgpt_codex_primary": "chatgpt_codex_backend",
    "anthropic_default": "anthropic_api_messages",
    "anthropic_api_messages": "anthropic_api_messages",
    "anthropic_primary": "anthropic_api_messages",
    "minimax_anthropic_api": "minimax_anthropic_api",
}

LEGACY_ENDPOINT_REFS: dict[str, str] = {
    "local_ollama_openai_v1": "openai_local_default",
    "chatgpt_codex_backend": "openai_codex_chatgpt",
    "anthropic_api_messages": "anthropic_default",
    "minimax_anthropic_api": "minimax_anthropic_api",
}

MODEL_REF_ALIASES: dict[str, str] = {
    "gemma4_26b": "local_gemma4_26b",
    "local_gemma4_26b": "local_gemma4_26b",
    "codex_gpt54": "codex_gpt54",
    "claude_sonnet_45": "claude_sonnet_45",
    "minimax_m27": "minimax_m27",
}

AUTH_ALIASES: dict[str, str] = {
    "runtime_authorization_header": "runtime_override_authorization_header",
    "codex_auth_json_chatgpt_access_token": "codex_chatgpt_access_token",
    "codex_chatgpt_access_token": "codex_chatgpt_access_token",
    "openai_codex_oauth_primary": "openai_codex_oauth_primary",
    "omnimemora_openai_api_key": "openai_api_key_env",
    "openai_api_key_env": "openai_api_key_env",
    "product_openai_api_key": "product_openai_api_key",
    "anthropic_api_key_env": "anthropic_api_key_env",
    "product_anthropic_api_key": "product_anthropic_api_key",
    "minimax_api_key_env": "minimax_api_key_env",
    "product_minimax_api_key": "product_minimax_api_key",
    "runtime_override_authorization_header": "runtime_override_authorization_header",
}


def _canonical_provider_ref(provider_ref: Optional[str]) -> Optional[str]:
    normalized = _normalize(provider_ref)
    if not normalized:
        return None
    return PROVIDER_ALIASES.get(normalized, normalized)


def _canonical_endpoint_ref(endpoint_ref: Optional[str]) -> Optional[str]:
    normalized = _normalize(endpoint_ref)
    if not normalized:
        return None
    return ENDPOINT_ALIASES.get(normalized, normalized)


def _canonical_model_ref(model_ref: Optional[str]) -> Optional[str]:
    normalized = _normalize(model_ref)
    if not normalized:
        return None
    return MODEL_REF_ALIASES.get(normalized, normalized)


def _canonical_auth_ref(auth_ref: Optional[str]) -> Optional[str]:
    normalized = _normalize(auth_ref)
    if not normalized:
        return None
    return AUTH_ALIASES.get(normalized, normalized)


def _infer_provider_from_base_url(
    base_url: Optional[str],
    default_provider: Optional[str] = "openai_compatible",
) -> Optional[str]:
    normalized = _normalize(base_url)
    if not normalized:
        return _canonical_provider_ref(default_provider)
    if "chatgpt.com/backend-api/codex" in normalized:
        return "openai_codex_oauth"
    if "api.minimaxi.com/anthropic" in normalized:
        return "minimax_anthropic_compatible"
    if "api.anthropic.com" in normalized:
        return "anthropic"
    if "api.openai.com" in normalized:
        return "openai_compatible"
    if "127.0.0.1" in normalized or "localhost" in normalized:
        return _canonical_provider_ref(default_provider)
    return _canonical_provider_ref(default_provider)


DEFAULT_SOURCE_PRIORITY_CHAIN: tuple[str, ...] = tuple(MODEL_SOURCE_PRIORITY_CHAIN)


DEFAULT_PROVIDERS: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        provider_ref="openai_compatible",
        provider_canonical_name="OpenAI Compatible",
        supported_wire_apis=("chat_completions", "responses"),
        default_endpoint_ref="local_ollama_openai_v1",
        auth_modes_supported=("authorization_bearer", "api_key_placeholder", "none"),
        compile_supported=True,
        fallback_supported=True,
    ),
    ProviderDefinition(
        provider_ref="openai_codex_oauth",
        provider_canonical_name="OpenAI Codex OAuth",
        supported_wire_apis=("responses",),
        default_endpoint_ref="chatgpt_codex_backend",
        auth_modes_supported=("authorization_bearer",),
        compile_supported=True,
        fallback_supported=False,
    ),
    ProviderDefinition(
        provider_ref="anthropic",
        provider_canonical_name="Anthropic",
        supported_wire_apis=("anthropic_messages",),
        default_endpoint_ref="anthropic_api_messages",
        auth_modes_supported=("x_api_key_header",),
        compile_supported=True,
        fallback_supported=True,
    ),
    ProviderDefinition(
        provider_ref="minimax_anthropic_compatible",
        provider_canonical_name="MiniMax Anthropic Compatible",
        supported_wire_apis=("anthropic_messages",),
        default_endpoint_ref="minimax_anthropic_api",
        auth_modes_supported=("x_api_key_header", "authorization_bearer"),
        compile_supported=True,
        fallback_supported=True,
    ),
)


DEFAULT_ENDPOINTS: tuple[EndpointDefinition, ...] = (
    EndpointDefinition(
        endpoint_ref="local_ollama_openai_v1",
        base_url="http://127.0.0.1:11434/v1",
        provider_ref="openai_compatible",
        wire_apis_supported=("chat_completions", "responses"),
        environment_scope="local",
        is_default=True,
    ),
    EndpointDefinition(
        endpoint_ref="chatgpt_codex_backend",
        base_url="https://chatgpt.com/backend-api/codex",
        provider_ref="openai_codex_oauth",
        wire_apis_supported=("responses",),
        environment_scope="user_session",
        is_default=True,
    ),
    EndpointDefinition(
        endpoint_ref="anthropic_api_messages",
        base_url="https://api.anthropic.com",
        provider_ref="anthropic",
        wire_apis_supported=("anthropic_messages",),
        environment_scope="remote",
        is_default=True,
    ),
    EndpointDefinition(
        endpoint_ref="minimax_anthropic_api",
        base_url="https://api.minimaxi.com/anthropic",
        provider_ref="minimax_anthropic_compatible",
        wire_apis_supported=("anthropic_messages",),
        environment_scope="remote",
        is_default=True,
    ),
)


DEFAULT_MODELS: tuple[ModelDefinition, ...] = (
    ModelDefinition(
        model_ref="codex_gpt54",
        canonical_model_name="gpt-5.4",
        aliases=("gpt-5.4", "openai-codex/gpt-5.4"),
        provider_ref="openai_codex_oauth",
        wire_model_name="gpt-5.4",
        routing_tags=("codex", "responses"),
    ),
    ModelDefinition(
        model_ref="local_gemma4_26b",
        canonical_model_name="gemma4:26b",
        aliases=("gemma4:26b", "gemma4", "gemma4_26b", "omnimemora/gemma4:26b"),
        provider_ref="openai_compatible",
        wire_model_name="gemma4:26b",
        routing_tags=("local", "ollama"),
    ),
    ModelDefinition(
        model_ref="claude_sonnet_45",
        canonical_model_name="claude-sonnet-4-5",
        aliases=("claude-sonnet-4-5", "claude-sonnet-4-20250514", "claude-sonnet-4-6"),
        provider_ref="anthropic",
        wire_model_name="claude-sonnet-4-20250514",
        routing_tags=("anthropic",),
    ),
    ModelDefinition(
        model_ref="minimax_m27",
        canonical_model_name="MiniMax-M2.7",
        aliases=("MiniMax-M2.7", "claude-opus-4-5"),
        provider_ref="minimax_anthropic_compatible",
        wire_model_name="MiniMax-M2.7",
        routing_tags=("minimax", "anthropic-compatible"),
    ),
)


DEFAULT_AUTHS: tuple[AuthDefinition, ...] = (
    AuthDefinition(
        auth_ref="openai_api_key_env",
        auth_type="api_key",
        provider_ref="openai_compatible",
        injection_mode="authorization_bearer",
        source_kind="product_env",
        redaction_strategy="mask_all",
    ),
    AuthDefinition(
        auth_ref="product_openai_api_key",
        auth_type="api_key",
        provider_ref="openai_compatible",
        injection_mode="authorization_bearer",
        source_kind="product_env",
        redaction_strategy="mask_all",
    ),
    AuthDefinition(
        auth_ref="codex_chatgpt_access_token",
        auth_type="oauth_access_token",
        provider_ref="openai_codex_oauth",
        injection_mode="authorization_bearer",
        source_kind="agent_auth_store",
        redaction_strategy="token_tail",
    ),
    AuthDefinition(
        auth_ref="openai_codex_oauth_primary",
        auth_type="oauth_access_token",
        provider_ref="openai_codex_oauth",
        injection_mode="authorization_bearer",
        source_kind="agent_auth_store",
        redaction_strategy="token_tail",
    ),
    AuthDefinition(
        auth_ref="anthropic_api_key_env",
        auth_type="api_key",
        provider_ref="anthropic",
        injection_mode="x_api_key_header",
        source_kind="product_env",
        redaction_strategy="mask_all",
    ),
    AuthDefinition(
        auth_ref="product_anthropic_api_key",
        auth_type="api_key",
        provider_ref="anthropic",
        injection_mode="x_api_key_header",
        source_kind="product_env",
        redaction_strategy="mask_all",
    ),
    AuthDefinition(
        auth_ref="minimax_api_key_env",
        auth_type="api_key",
        provider_ref="minimax_anthropic_compatible",
        injection_mode="x_api_key_header",
        source_kind="product_env",
        redaction_strategy="mask_all",
    ),
    AuthDefinition(
        auth_ref="product_minimax_api_key",
        auth_type="api_key",
        provider_ref="minimax_anthropic_compatible",
        injection_mode="x_api_key_header",
        source_kind="product_env",
        redaction_strategy="mask_all",
    ),
    AuthDefinition(
        auth_ref="runtime_override_authorization_header",
        auth_type="authorization_bearer",
        provider_ref="*",
        injection_mode="authorization_bearer",
        source_kind="runtime_override",
        redaction_strategy="mask_all",
    ),
)


@dataclass(frozen=True)
class CanonicalizationLookup:
    refs: CanonicalTruthRefs
    provider: Optional[ProviderDefinition] = None
    endpoint: Optional[EndpointDefinition] = None
    model: Optional[ModelDefinition] = None
    auth: Optional[AuthDefinition] = None


@dataclass(frozen=True)
class CanonicalTruthRegistry:
    providers: tuple[ProviderDefinition, ...] = DEFAULT_PROVIDERS
    endpoints: tuple[EndpointDefinition, ...] = DEFAULT_ENDPOINTS
    models: tuple[ModelDefinition, ...] = DEFAULT_MODELS
    auths: tuple[AuthDefinition, ...] = DEFAULT_AUTHS
    source_priority_chain: tuple[str, ...] = DEFAULT_SOURCE_PRIORITY_CHAIN

    def get_provider(self, provider_ref: Optional[str]) -> Optional[ProviderDefinition]:
        wanted = _canonical_provider_ref(provider_ref)
        if not wanted:
            return None
        for provider in self.providers:
            if _normalize(provider.provider_ref) == wanted:
                return provider
        return None

    def get_endpoint(self, endpoint_ref: Optional[str]) -> Optional[EndpointDefinition]:
        wanted = _canonical_endpoint_ref(endpoint_ref)
        if not wanted:
            return None
        for endpoint in self.endpoints:
            if _normalize(endpoint.endpoint_ref) == wanted:
                return endpoint
        return None

    def get_model(self, model_ref_or_name: Optional[str]) -> Optional[ModelDefinition]:
        wanted = _canonical_model_ref(model_ref_or_name)
        if wanted:
            for model in self.models:
                if _normalize(model.model_ref) == wanted:
                    return model
        return self.find_model_by_name(model_ref_or_name)

    def get_auth(self, auth_ref: Optional[str]) -> Optional[AuthDefinition]:
        wanted = _canonical_auth_ref(auth_ref)
        if not wanted:
            return None
        for auth in self.auths:
            if _normalize(auth.auth_ref) == wanted:
                return auth
        return None

    def find_endpoint_by_base_url(self, base_url: Optional[str]) -> Optional[EndpointDefinition]:
        wanted = _normalize(base_url).rstrip("/")
        if not wanted:
            return None
        for endpoint in self.endpoints:
            if _normalize(endpoint.base_url).rstrip("/") == wanted:
                return endpoint
        return None

    def find_model_by_name(self, model_name: Optional[str]) -> Optional[ModelDefinition]:
        wanted = _normalize(model_name)
        if not wanted:
            return None
        for model in self.models:
            if _normalize(model.canonical_model_name) == wanted:
                return model
            if _normalize(model.model_ref) == _canonical_model_ref(wanted):
                return model
            if any(_normalize(alias) == wanted for alias in model.aliases):
                return model
        return None

    def find_model(self, model_name: Optional[str]) -> Optional[ModelDefinition]:
        return self.find_model_by_name(model_name)

    def default_endpoint_for_provider(self, provider_ref: Optional[str]) -> Optional[EndpointDefinition]:
        provider = self.get_provider(provider_ref)
        if not provider or not provider.default_endpoint_ref:
            return None
        return self.get_endpoint(provider.default_endpoint_ref)

    def get_default_endpoint_for_provider(self, provider_ref: Optional[str]) -> Optional[EndpointDefinition]:
        return self.default_endpoint_for_provider(provider_ref)

    def default_auth_for_provider(self, provider_ref: Optional[str]) -> Optional[AuthDefinition]:
        provider = _canonical_provider_ref(provider_ref)
        if not provider:
            return None
        preferred = {
            "openai_compatible": ("openai_api_key_env", "product_openai_api_key"),
            "openai_codex_oauth": ("codex_chatgpt_access_token", "openai_codex_oauth_primary"),
            "anthropic": ("anthropic_api_key_env", "product_anthropic_api_key"),
            "minimax_anthropic_compatible": ("minimax_api_key_env", "product_minimax_api_key"),
        }.get(provider, ())
        for auth_ref in preferred:
            auth = self.get_auth(auth_ref)
            if auth:
                return auth
        return None

    def resolve_provider_ref(
        self,
        *,
        provider_requested: Optional[str] = None,
        endpoint_ref: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        default_provider: Optional[str] = None,
    ) -> Optional[str]:
        provider = self.get_provider(provider_requested)
        if provider:
            return provider.provider_ref

        endpoint = self.get_endpoint(endpoint_ref) or self.find_endpoint_by_base_url(base_url)
        if endpoint:
            return endpoint.provider_ref

        model = self.find_model_by_name(model_name)
        if model:
            return model.provider_ref

        inferred = _infer_provider_from_base_url(base_url, default_provider or "openai_compatible")
        if self.get_provider(inferred):
            return inferred
        return _canonical_provider_ref(default_provider)

    def supports_wire_api(self, provider_ref: Optional[str], wire_api: Optional[str]) -> bool:
        provider = self.get_provider(provider_ref)
        if not provider or not wire_api:
            return False
        return _normalize(wire_api) in {_normalize(item) for item in provider.supported_wire_apis}

    def auth_matches_provider(self, auth_ref: Optional[str], provider_ref: Optional[str]) -> bool:
        auth = self.get_auth(auth_ref)
        provider = self.get_provider(provider_ref)
        if not auth or not provider:
            return False
        if auth.provider_ref == "*":
            return True
        return _normalize(auth.provider_ref) == _normalize(provider.provider_ref)

    def is_model_compatible_with_provider(self, model_ref: Optional[str], provider_ref: Optional[str]) -> bool:
        model = self.get_model(model_ref)
        provider = self.get_provider(provider_ref)
        if not model or not provider:
            return True
        return _normalize(model.provider_ref) == _normalize(provider.provider_ref)

    def is_auth_compatible_with_provider(self, auth_ref: Optional[str], provider_ref: Optional[str]) -> bool:
        return self.auth_matches_provider(auth_ref, provider_ref)

    def is_endpoint_compatible_with_provider(self, endpoint_ref: Optional[str], provider_ref: Optional[str]) -> bool:
        endpoint = self.get_endpoint(endpoint_ref)
        provider = self.get_provider(provider_ref)
        if not endpoint or not provider:
            return True
        return _normalize(endpoint.provider_ref) == _normalize(provider.provider_ref)

    def is_wire_api_compatible_with_provider(self, wire_api: Optional[str], provider_ref: Optional[str]) -> bool:
        if not wire_api or not provider_ref:
            return True
        return self.supports_wire_api(provider_ref, wire_api)

    def canonicalize(self, raw_intent: RawTruthIntent) -> CanonicalTruthRefs:
        return self.canonicalize_refs(
            provider_requested=raw_intent.provider_requested,
            base_url_requested=raw_intent.base_url_requested,
            model_requested=raw_intent.model_requested,
            auth_requested=raw_intent.auth_requested,
            fallback_policy_requested=raw_intent.fallback_requested,
            canonical_wire_api=raw_intent.wire_api_requested,
        ).refs

    def canonicalize_refs(
        self,
        *,
        provider_requested: Optional[str] = None,
        base_url_requested: Optional[str] = None,
        model_requested: Optional[str] = None,
        auth_requested: Optional[str] = None,
        fallback_policy_requested: Optional[bool] = None,
        canonical_wire_api: Optional[str] = None,
    ) -> CanonicalizationLookup:
        endpoint = self.find_endpoint_by_base_url(base_url_requested)
        model = self.find_model_by_name(model_requested)
        auth = self.get_auth(auth_requested)
        provider_ref = self.resolve_provider_ref(
            provider_requested=provider_requested,
            endpoint_ref=endpoint.endpoint_ref if endpoint else None,
            base_url=base_url_requested,
            model_name=model_requested,
            default_provider="openai_compatible",
        )
        provider = self.get_provider(provider_ref)

        if provider is None and endpoint:
            provider = self.get_provider(endpoint.provider_ref)
            provider_ref = endpoint.provider_ref
        if provider is None and model:
            provider = self.get_provider(model.provider_ref)
            provider_ref = model.provider_ref
        if provider is None and auth and auth.provider_ref != "*":
            provider = self.get_provider(auth.provider_ref)
            provider_ref = auth.provider_ref

        if endpoint is None and provider:
            endpoint = self.default_endpoint_for_provider(provider.provider_ref)
        if auth is None and provider:
            auth = self.default_auth_for_provider(provider.provider_ref)

        refs = CanonicalTruthRefs(
            provider_ref=provider.provider_ref if provider else provider_ref,
            endpoint_ref=endpoint.endpoint_ref if endpoint else None,
            model_ref=model.model_ref if model else None,
            auth_ref=auth.auth_ref if auth else None,
            fallback_policy_ref=(
                "fallback_enabled"
                if fallback_policy_requested is True
                else "fallback_disabled"
                if fallback_policy_requested is False
                else None
            ),
            canonical_wire_api=canonical_wire_api
            or (provider.supported_wire_apis[0] if provider and provider.supported_wire_apis else None),
        )
        return CanonicalizationLookup(
            refs=refs,
            provider=provider,
            endpoint=endpoint,
            model=model,
            auth=auth,
        )

    # Legacy compatibility helpers used by older tests and callers.
    def canonicalize_model(self, model_name: Optional[str]) -> Optional[str]:
        model = self.find_model_by_name(model_name)
        return model.model_ref if model else None

    def canonicalize_auth(
        self,
        auth_name: Optional[str],
        *,
        provider_ref: Optional[str] = None,
    ) -> Optional[str]:
        auth = self.get_auth(auth_name)
        if auth:
            return auth.auth_ref
        if _canonical_auth_ref(auth_name) == "runtime_override_authorization_header":
            return "runtime_override_authorization_header"
        default_auth = self.default_auth_for_provider(provider_ref)
        return default_auth.auth_ref if default_auth else None

    def model_matches_provider(self, model_ref: Optional[str], provider_ref: Optional[str]) -> bool:
        return self.is_model_compatible_with_provider(model_ref, provider_ref)

    def endpoint_matches_provider(self, endpoint_ref: Optional[str], provider_ref: Optional[str]) -> bool:
        return self.is_endpoint_compatible_with_provider(endpoint_ref, provider_ref)

    def provider_supports_wire_api(self, provider_ref: Optional[str], wire_api: Optional[str]) -> bool:
        return self.supports_wire_api(provider_ref, wire_api)

    def resolve_canonical_refs(
        self,
        *,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        auth: Optional[str] = None,
        canonical_wire_api: Optional[str] = None,
    ) -> CanonicalTruthRefs:
        lookup = self.canonicalize_refs(
            provider_requested=provider,
            base_url_requested=base_url,
            model_requested=model,
            auth_requested=auth,
            canonical_wire_api=canonical_wire_api,
        )
        refs = lookup.refs
        return CanonicalTruthRefs(
            provider_ref=refs.provider_ref,
            endpoint_ref=LEGACY_ENDPOINT_REFS.get(refs.endpoint_ref or "", refs.endpoint_ref),
            model_ref=refs.model_ref,
            auth_ref=refs.auth_ref,
            fallback_policy_ref=refs.fallback_policy_ref,
            canonical_wire_api=refs.canonical_wire_api,
        )


TruthRegistry = CanonicalTruthRegistry
DEFAULT_TRUTH_REGISTRY = CanonicalTruthRegistry()


def get_default_truth_registry() -> CanonicalTruthRegistry:
    return DEFAULT_TRUTH_REGISTRY


def create_default_truth_registry() -> CanonicalTruthRegistry:
    return CanonicalTruthRegistry()
