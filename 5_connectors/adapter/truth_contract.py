"""
truth_contract.py - resolved truth contract builder and minimal auth materialization.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, Optional

from .truth_arbitration import ResolutionDecision
from .truth_models import CanonicalTruthRefs, MaterializedAuth, RawTruthIntent, ResolvedTruthContract
from .truth_registry import CanonicalTruthRegistry, DEFAULT_TRUTH_REGISTRY, get_default_truth_registry


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_mapping(value: Mapping[str, Any] | RawTruthIntent | CanonicalTruthRefs) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Expected mapping or dataclass, got {type(value)!r}")


def build_resolution_trace(
    *,
    raw_intent: Mapping[str, Any] | RawTruthIntent,
    canonical_refs: Mapping[str, Any] | CanonicalTruthRefs,
    resolution_decision: ResolutionDecision,
) -> list[dict[str, Any]]:
    raw_intent_map = _as_mapping(raw_intent)
    canonical_refs_map = _as_mapping(canonical_refs)
    trace: list[dict[str, Any]] = []

    for field_name, field_resolution in getattr(resolution_decision, "resolved_fields", {}).items():
        winner_source = getattr(field_resolution, "winner_source", None)
        if not winner_source:
            continue
        trace.append(
            {
                "step": "candidate_selected",
                "field": field_name,
                "winner_source": winner_source,
                "value": getattr(field_resolution, "value", None),
                "reason": getattr(field_resolution, "resolution_reason", None),
            }
        )

    for ref_name in ("provider_ref", "endpoint_ref", "model_ref", "auth_ref", "fallback_policy_ref"):
        ref_value = _normalize_text(canonical_refs_map.get(ref_name))
        if ref_value:
            trace.append({"step": "canonical_ref_attached", "field": ref_name, "value": ref_value})

    if resolution_decision.conflict_detected:
        trace.append(
            {
                "step": "conflict_detected",
                "conflict_types": list(resolution_decision.conflict_types),
            }
        )

    raw_model = _normalize_text(raw_intent_map.get("model_requested"))
    resolved_model = _normalize_text(resolution_decision.model_resolved)
    if raw_model and resolved_model and raw_model != resolved_model:
        trace.append(
            {
                "step": "model_normalized",
                "requested": raw_model,
                "resolved": resolved_model,
            }
        )

    return trace


def build_resolved_contract(
    raw_intent: Mapping[str, Any] | RawTruthIntent,
    canonical_refs: Mapping[str, Any] | CanonicalTruthRefs,
    resolution_decision: ResolutionDecision,
    request_id: str,
) -> ResolvedTruthContract:
    raw_intent_map = _as_mapping(raw_intent)
    canonical_refs_map = _as_mapping(canonical_refs)

    return ResolvedTruthContract(
        request_id=request_id,
        agent_id=_normalize_text(raw_intent_map.get("agent_id")) or "unknown",
        policy_profile=_normalize_text(raw_intent_map.get("policy_profile")),
        model_requested=_normalize_text(raw_intent_map.get("model_requested")),
        provider_requested=_normalize_text(raw_intent_map.get("provider_requested")),
        base_url_requested=_normalize_text(raw_intent_map.get("base_url_requested")),
        provider_ref=_normalize_text(canonical_refs_map.get("provider_ref")),
        endpoint_ref=_normalize_text(canonical_refs_map.get("endpoint_ref")),
        model_ref=_normalize_text(canonical_refs_map.get("model_ref")),
        auth_ref=_normalize_text(canonical_refs_map.get("auth_ref")),
        fallback_policy_ref=_normalize_text(canonical_refs_map.get("fallback_policy_ref")),
        provider_resolved=_normalize_text(resolution_decision.provider_resolved),
        base_url_resolved=_normalize_text(resolution_decision.base_url_resolved),
        model_resolved=_normalize_text(resolution_decision.model_resolved),
        auth_source=_normalize_text(raw_intent_map.get("auth_source")),
        auth_resolved=_normalize_text(resolution_decision.auth_resolved),
        wire_api_resolved=_normalize_text(
            canonical_refs_map.get("canonical_wire_api") or resolution_decision.wire_api_resolved
        ),
        fallback_used=bool(resolution_decision.fallback_used),
        compile_enabled=bool(raw_intent_map.get("compile_enabled", False)),
        resolution_rule=resolution_decision.resolution_rule,
        resolution_reason=resolution_decision.resolution_reason,
        conflict_detected=bool(resolution_decision.conflict_detected),
        conflict_types=list(resolution_decision.conflict_types),
        source_priority_chain=list(resolution_decision.source_priority_chain),
        resolution_trace=build_resolution_trace(
            raw_intent=raw_intent_map,
            canonical_refs=canonical_refs_map,
            resolution_decision=resolution_decision,
        ),
    )


def validate_contract(contract: ResolvedTruthContract) -> list[str]:
    conflicts = list(contract.conflict_types)

    provider = _normalize_text(contract.provider_resolved)
    base_url = _normalize_text(contract.base_url_resolved)
    model = _normalize_text(contract.model_resolved)
    auth = _normalize_text(contract.auth_resolved or contract.auth_ref or contract.auth_source)
    wire_api = _normalize_text(contract.wire_api_resolved)

    if provider and base_url:
        normalized_provider = provider.lower()
        normalized_base_url = base_url.lower()
        if "anthropic" in normalized_provider and "openai" in normalized_base_url:
            conflicts.append("base_url_provider_mismatch")
        if "openai" in normalized_provider and "anthropic" in normalized_base_url:
            conflicts.append("base_url_provider_mismatch")

    if provider and model:
        normalized_provider = provider.lower()
        normalized_model = model.lower()
        if normalized_model.startswith("claude") and "anthropic" not in normalized_provider:
            conflicts.append("model_provider_mismatch")
        if normalized_model.startswith(("gpt", "o1", "o3")) and "openai" not in normalized_provider:
            conflicts.append("model_provider_mismatch")

    if provider and auth:
        normalized_provider = provider.lower()
        normalized_auth = auth.lower()
        if "anthropic" in normalized_auth and "anthropic" not in normalized_provider:
            conflicts.append("auth_provider_mismatch")
        if "openai" in normalized_auth and "openai" not in normalized_provider:
            conflicts.append("auth_provider_mismatch")

    if provider and wire_api:
        normalized_provider = provider.lower()
        normalized_wire_api = wire_api.lower()
        if normalized_wire_api == "anthropic_messages" and "anthropic" not in normalized_provider:
            conflicts.append("wire_api_provider_mismatch")
        if normalized_wire_api in {"responses", "chat_completions"} and "openai" not in normalized_provider:
            conflicts.append("wire_api_provider_mismatch")

    return list(dict.fromkeys(conflicts))


def _resolve_header_name(injection_mode: str | None) -> str | None:
    normalized = _normalize_text(injection_mode)
    if normalized == "authorization_bearer":
        return "Authorization"
    if normalized == "x_api_key_header":
        return "x-api-key"
    return None


def _coerce_header_value(injection_mode: str | None, secret_value: str | None) -> str | None:
    secret = _normalize_text(secret_value)
    if not secret:
        return None
    normalized_mode = _normalize_text(injection_mode)
    if normalized_mode == "authorization_bearer":
        if secret.lower().startswith("bearer "):
            return secret
        return f"Bearer {secret}"
    if normalized_mode == "x_api_key_header" and secret.lower().startswith("bearer "):
        stripped = secret[7:].strip()
        return stripped or None
    return secret


def _redact_secret(value: str | None, strategy: str | None = "mask_all") -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    normalized_strategy = _normalize_text(strategy) or "mask_all"
    if normalized_strategy == "token_tail":
        tail = text[-4:] if len(text) > 4 else text
        return f"***{tail}"
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}...{text[-4:]}"


def materialize_auth_headers(
    contract: ResolvedTruthContract,
    *,
    auth_value: Any = None,
    credential_value: Optional[str] = None,
    registry: Optional[CanonicalTruthRegistry] = None,
) -> MaterializedAuth:
    truth_registry = registry or get_default_truth_registry()
    raw_value = credential_value if credential_value is not None else auth_value
    auth_ref = _normalize_text(contract.auth_ref or contract.auth_resolved)
    provider_ref = _normalize_text(contract.provider_resolved or contract.provider_ref)
    auth_definition = truth_registry.get_auth(auth_ref)

    trace: list[dict[str, Any]] = [
        {
            "step": "materialization_requested",
            "provider_ref": provider_ref,
            "auth_ref": auth_ref,
            "wire_api_resolved": _normalize_text(contract.wire_api_resolved),
        }
    ]

    if auth_definition is None:
        trace.append({"step": "materialization_failed", "reason": "missing_auth_ref"})
        return MaterializedAuth(
            auth_ref=auth_ref,
            provider_ref=provider_ref,
            auth_present=False,
            materialization_status="missing_auth_ref",
            materialization_error="No canonical auth_ref available for resolved contract.",
            materialization_trace=trace,
        )

    header_name = _resolve_header_name(auth_definition.injection_mode)
    header_value = _coerce_header_value(auth_definition.injection_mode, raw_value)
    trace.append(
        {
            "step": "auth_definition_selected",
            "auth_ref": auth_definition.auth_ref,
            "auth_type": auth_definition.auth_type,
            "injection_mode": auth_definition.injection_mode,
            "source_kind": auth_definition.source_kind,
            "header_name": header_name,
        }
    )

    if not header_name:
        trace.append({"step": "materialization_failed", "reason": "unsupported_injection_mode"})
        return MaterializedAuth(
            auth_ref=auth_definition.auth_ref,
            auth_type=auth_definition.auth_type,
            injection_mode=auth_definition.injection_mode,
            source_kind=auth_definition.source_kind,
            provider_ref=provider_ref or auth_definition.provider_ref,
            auth_present=False,
            materialization_status="unsupported_injection_mode",
            materialization_error=f"Unsupported injection mode: {auth_definition.injection_mode}",
            materialization_trace=trace,
        )

    if not header_value:
        trace.append(
            {
                "step": "materialization_failed",
                "reason": "missing_auth_value",
                "header_name": header_name,
            }
        )
        return MaterializedAuth(
            auth_ref=auth_definition.auth_ref,
            auth_type=auth_definition.auth_type,
            injection_mode=auth_definition.injection_mode,
            source_kind=auth_definition.source_kind,
            provider_ref=provider_ref or auth_definition.provider_ref,
            header_name=header_name,
            auth_present=False,
            materialization_status="missing_auth_value",
            materialization_error=f"Missing auth value for {auth_definition.auth_ref}",
            materialization_trace=trace,
        )

    redacted = _redact_secret(header_value, auth_definition.redaction_strategy)
    trace.append(
        {
            "step": "header_materialized",
            "header_name": header_name,
            "header_value_redacted": redacted,
        }
    )
    return MaterializedAuth(
        auth_ref=auth_definition.auth_ref,
        auth_type=auth_definition.auth_type,
        injection_mode=auth_definition.injection_mode,
        source_kind=auth_definition.source_kind,
        provider_ref=provider_ref or auth_definition.provider_ref,
        header_name=header_name,
        header_value=header_value,
        header_value_redacted=redacted,
        auth_present=True,
        materialization_status="materialized",
        materialization_trace=trace,
    )
