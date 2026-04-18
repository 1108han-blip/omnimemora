"""
truth_bridge.py - Unified request truth resolution metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from .truth_arbitration import arbitrate_truth
from .truth_contract import build_resolved_contract, validate_contract
from .truth_diagnostics import build_resolution_diagnostics
from .truth_models import RawTruthIntent
from .truth_registry import DEFAULT_SOURCE_PRIORITY_CHAIN, DEFAULT_TRUTH_REGISTRY


DEFAULT_PRIORITY = " > ".join(DEFAULT_SOURCE_PRIORITY_CHAIN)


@dataclass
class TruthResolution:
    agent_id: str
    route: str
    wire_api_resolved: str
    provider_resolved: str
    base_url_resolved: str
    base_url_source: str
    model_requested: str
    model_resolved: str
    model_resolution_source: str
    auth_source: str
    auth_present: bool
    fallback_used: bool = False
    fallback_reason: str = ""
    override_fields: list[str] = field(default_factory=list)
    truth_priority: str = DEFAULT_PRIORITY

    def as_event_fields(self) -> dict[str, Any]:
        return {
            "truth_priority": self.truth_priority,
            "wire_api_resolved": self.wire_api_resolved,
            "provider_resolved": self.provider_resolved,
            "base_url_resolved": self.base_url_resolved,
            "base_url_source": self.base_url_source,
            "model_requested": self.model_requested,
            "model_resolved": self.model_resolved,
            "model_resolution_source": self.model_resolution_source,
            "auth_source": self.auth_source,
            "auth_present": self.auth_present,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "override_applied": bool(self.override_fields),
            "override_fields": list(self.override_fields),
        }


def infer_provider_name(base_url: str, default_provider: str = "openai_compatible") -> str:
    normalized = (base_url or "").strip().lower()
    if not normalized:
        return default_provider
    if "chatgpt.com/backend-api/codex" in normalized:
        return "openai_codex_oauth"
    if "api.minimaxi.com/anthropic" in normalized:
        return "minimax_anthropic_compatible"
    if "api.anthropic.com" in normalized:
        return "anthropic"
    if "api.openai.com" in normalized:
        return "openai"
    if "localhost" in normalized or "127.0.0.1" in normalized:
        return default_provider
    return default_provider


def classify_model_resolution(
    *,
    requested_model: str,
    resolved_model: str,
    default_model: str,
    mapped_models: Optional[Iterable[str]] = None,
    family_prefix: Optional[str] = None,
    family_default_reason: str = "product_family_default",
) -> str:
    requested = (requested_model or "").strip()
    resolved = (resolved_model or "").strip()
    default = (default_model or "").strip()
    mapped = set(mapped_models or [])

    if requested and requested in mapped and requested != resolved:
        return "product_model_map"
    if requested and family_prefix and requested.startswith(family_prefix) and resolved == default:
        return family_default_reason
    if requested and resolved == requested:
        return "agent_passthrough"
    if not requested and resolved == default:
        return "product_default"
    if requested != resolved:
        return "product_normalized"
    return "product_default"


def auth_source_from_values(
    *,
    explicit_authorization: bool = False,
    agent_truth_source: Optional[str] = None,
    product_api_key_present: bool = False,
) -> str:
    if explicit_authorization:
        return "runtime_override_authorization_header"
    if agent_truth_source:
        return agent_truth_source
    if product_api_key_present:
        return "product_upstream_api_key"
    return "none"


def _filter_truth_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "", [])
    }


def _raw_intent_payload(raw_intent: RawTruthIntent) -> dict[str, Any]:
    payload = raw_intent.as_dict()
    payload["compile_enabled"] = raw_intent.compile_enabled
    return payload


def product_auth_ref_for_provider(provider_name: Optional[str]) -> Optional[str]:
    normalized = (provider_name or "").strip().lower()
    if not normalized:
        return None
    if normalized == "anthropic":
        return "product_anthropic_api_key"
    if normalized == "minimax_anthropic_compatible":
        return "product_minimax_api_key"
    if normalized in {"openai_compatible", "openai", "openai_codex_oauth"}:
        return "product_openai_api_key"
    return None


def codex_auth_ref_for_source(
    agent_truth_source: Optional[str],
    *,
    explicit_authorization: bool = False,
) -> Optional[str]:
    if explicit_authorization:
        return None
    normalized = (agent_truth_source or "").strip().lower()
    if normalized == "codex_auth_json_chatgpt_access_token":
        return "codex_chatgpt_access_token"
    if normalized == "codex_auth_json_openai_api_key":
        return "product_openai_api_key"
    return None


def auth_ref_from_values(
    *,
    explicit_authorization: bool = False,
    agent_truth_source: Optional[str] = None,
    provider_resolved: Optional[str] = None,
    product_api_key_present: bool = False,
) -> Optional[str]:
    if explicit_authorization:
        return "runtime_authorization_header"
    source = (agent_truth_source or "").strip().lower()
    if source == "codex_auth_json_chatgpt_access_token":
        return "codex_chatgpt_access_token"
    if source == "codex_auth_json_openai_api_key":
        return "product_openai_api_key"
    if product_api_key_present:
        provider = (provider_resolved or "").strip().lower()
        if provider == "anthropic":
            return "product_anthropic_api_key"
        if provider == "minimax_anthropic_compatible":
            return "product_minimax_api_key"
        return "product_openai_api_key"
    return None


def resolve_truth_contract(
    *,
    request_id: str,
    agent_id: str,
    route: str,
    requested_model: str,
    wire_api_requested: str,
    provider_requested: Optional[str] = None,
    base_url_requested: Optional[str] = None,
    auth_requested: Optional[str] = None,
    fallback_requested: Optional[bool] = None,
    provider_source: Optional[str] = None,
    base_url_source: Optional[str] = None,
    model_source: Optional[str] = None,
    auth_source: Optional[str] = None,
    fallback_source: Optional[str] = None,
    policy_profile: str = "default",
    candidates_by_source: Optional[dict[str, dict[str, Any]]] = None,
    compile_enabled: bool = True,
) -> tuple[Any, dict[str, Any]]:
    raw_intent = RawTruthIntent(
        agent_id=agent_id,
        request_path=route,
        wire_api_requested=wire_api_requested,
        provider_requested=provider_requested,
        base_url_requested=base_url_requested,
        model_requested=requested_model,
        auth_requested=auth_requested,
        fallback_requested=fallback_requested,
        provider_source=provider_source,
        base_url_source=base_url_source,
        model_source=model_source,
        auth_source=auth_source,
        fallback_source=fallback_source,
        runtime_override_present=bool(
            provider_source == "runtime_override"
            or base_url_source == "runtime_override"
            or auth_source == "runtime_override_authorization_header"
        ),
        policy_profile=policy_profile,
        compile_enabled=compile_enabled,
    )

    registry_lookup = DEFAULT_TRUTH_REGISTRY.canonicalize_refs(
        provider_requested=provider_requested,
        base_url_requested=base_url_requested,
        model_requested=requested_model,
        auth_requested=auth_requested,
        fallback_policy_requested=fallback_requested,
        canonical_wire_api=wire_api_requested,
    )
    canonical_refs = registry_lookup.refs

    resolved_sources = {
        "agent_payload_explicit": _filter_truth_payload(
            {
                "provider": provider_requested,
                "base_url": base_url_requested,
                "model": requested_model,
                "auth": auth_requested,
                "wire_api": wire_api_requested,
                "fallback": fallback_requested,
            }
        )
    }
    if candidates_by_source:
        for source_name, payload in candidates_by_source.items():
            if isinstance(payload, dict):
                resolved_sources[source_name] = _filter_truth_payload(payload)

    if canonical_refs.provider_ref:
        provider_record = DEFAULT_TRUTH_REGISTRY.get_provider(canonical_refs.provider_ref)
        default_endpoint = DEFAULT_TRUTH_REGISTRY.default_endpoint_for_provider(canonical_refs.provider_ref)
        resolved_sources.setdefault(
            "provider_default",
            _filter_truth_payload(
                {
                    "provider": canonical_refs.provider_ref,
                    "base_url": default_endpoint.base_url if default_endpoint else None,
                    "wire_api": canonical_refs.canonical_wire_api,
                    "fallback": provider_record.fallback_supported if provider_record else False,
                }
            ),
        )

    decision = arbitrate_truth(
        resolved_sources,
        priority_chain=DEFAULT_SOURCE_PRIORITY_CHAIN,
    )
    contract = build_resolved_contract(
        raw_intent=_raw_intent_payload(raw_intent),
        canonical_refs=canonical_refs.as_dict(),
        resolution_decision=decision,
        request_id=request_id,
    )
    contract_conflicts = validate_contract(contract)
    diagnostics = build_resolution_diagnostics(
        raw_intent=raw_intent,
        canonical_refs=canonical_refs,
        resolution_decision=decision,
        registry=DEFAULT_TRUTH_REGISTRY,
    )

    base_url_resolution = getattr(decision, "resolved_fields", {}).get("base_url")
    model_resolution = getattr(decision, "resolved_fields", {}).get("model")
    truth_meta = {
        "truth_priority": " > ".join(DEFAULT_SOURCE_PRIORITY_CHAIN),
        "provider_requested": provider_requested,
        "provider_resolved": contract.provider_resolved,
        "provider_ref": contract.provider_ref,
        "base_url_requested": base_url_requested,
        "base_url_resolved": contract.base_url_resolved,
        "base_url_source": (
            base_url_resolution.winner_source
            if base_url_resolution is not None
            else (base_url_source or provider_source or "product_upstream_config")
        ),
        "endpoint_ref": contract.endpoint_ref,
        "model_requested": requested_model,
        "model_resolved": contract.model_resolved,
        "model_ref": contract.model_ref,
        "model_resolution_source": (
            model_resolution.winner_source
            if model_resolution is not None
            else (model_source or "agent_payload_explicit")
        ),
        "auth_requested": auth_requested,
        "auth_resolved": contract.auth_resolved,
        "auth_source": contract.auth_source,
        "auth_ref": contract.auth_ref,
        "auth_present": bool(auth_requested or contract.auth_ref or contract.auth_source),
        "wire_api_resolved": contract.wire_api_resolved,
        "fallback_used": contract.fallback_used,
        "fallback_reason": "conflict_detected" if contract_conflicts else "",
        "override_applied": bool(
            provider_source == "runtime_override"
            or base_url_source == "runtime_override"
            or auth_source == "runtime_override_authorization_header"
        ),
        "override_fields": [
            field_name
            for field_name, source_name in (
                ("provider", provider_source),
                ("base_url", base_url_source),
                ("authorization", auth_source),
                ("model", model_source),
            )
            if source_name in {"runtime_override", "runtime_override_authorization_header"}
        ],
        "policy_profile": contract.policy_profile,
        "resolution_rule": contract.resolution_rule,
        "resolution_reason": contract.resolution_reason,
        "conflict_detected": bool(contract_conflicts or diagnostics["conflict_detected"]),
        "conflict_types": list(dict.fromkeys(list(contract_conflicts) + diagnostics["conflict_types"])),
        "source_priority_chain": list(contract.source_priority_chain),
        "resolution_trace": diagnostics["resolution_trace"],
        "compile_enabled": compile_enabled,
    }
    return contract, truth_meta
