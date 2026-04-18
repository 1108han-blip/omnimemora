"""
truth_diagnostics.py - structured diagnostics helpers for Truth Bridge v2.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from .truth_models import CanonicalTruthRefs, RawTruthIntent, ResolutionDecision
from .truth_registry import CanonicalTruthRegistry, get_default_truth_registry


def build_resolution_trace(
    raw_intent: RawTruthIntent,
    canonical_refs: CanonicalTruthRefs,
    decision: Optional[ResolutionDecision] = None,
    *,
    registry: Optional[CanonicalTruthRegistry] = None,
    resolution_decision: Optional[ResolutionDecision] = None,
) -> list[dict[str, Any]]:
    decision = resolution_decision or decision
    truth_registry = registry or get_default_truth_registry()
    trace: list[dict[str, Any]] = []

    trace.append(
        {
            "step": "requested_truth",
            "provider_requested": raw_intent.provider_requested,
            "base_url_requested": raw_intent.base_url_requested,
            "model_requested": raw_intent.model_requested,
            "auth_requested": raw_intent.auth_requested,
            "wire_api_requested": raw_intent.wire_api_requested,
        }
    )

    if raw_intent.provider_requested:
        trace.append(
            {
                "step": "provider_candidate_discovered",
                "value": raw_intent.provider_requested,
                "source": raw_intent.provider_source or "unknown",
            }
        )
    if raw_intent.base_url_requested:
        trace.append(
            {
                "step": "base_url_candidate_discovered",
                "value": raw_intent.base_url_requested,
                "source": raw_intent.base_url_source or "unknown",
            }
        )
    if raw_intent.model_requested:
        trace.append(
            {
                "step": "model_candidate_discovered",
                "value": raw_intent.model_requested,
                "source": raw_intent.model_source or "unknown",
            }
        )
    if raw_intent.auth_requested:
        trace.append(
            {
                "step": "auth_candidate_discovered",
                "value": raw_intent.auth_requested,
                "source": raw_intent.auth_source or "unknown",
            }
        )

    if canonical_refs.provider_ref:
        trace.append(
            {
                "step": "provider_canonicalized",
                "provider_ref": canonical_refs.provider_ref,
            }
        )
    if canonical_refs.endpoint_ref:
        endpoint = truth_registry.get_endpoint(canonical_refs.endpoint_ref)
        trace.append(
            {
                "step": "endpoint_normalized",
                "endpoint_ref": canonical_refs.endpoint_ref,
                "base_url": endpoint.base_url if endpoint else None,
            }
        )
    if canonical_refs.model_ref:
        model = truth_registry.get_model(canonical_refs.model_ref)
        trace.append(
            {
                "step": "model_alias_normalized",
                "model_ref": canonical_refs.model_ref,
                "canonical_model_name": model.canonical_model_name if model else None,
            }
        )
    if canonical_refs.auth_ref:
        trace.append(
            {
                "step": "auth_ref_selected",
                "auth_ref": canonical_refs.auth_ref,
            }
        )
    trace.append(
        {
            "step": "canonical_ref",
            "provider_ref": canonical_refs.provider_ref,
            "endpoint_ref": canonical_refs.endpoint_ref,
            "model_ref": canonical_refs.model_ref,
            "auth_ref": canonical_refs.auth_ref,
            "canonical_wire_api": canonical_refs.canonical_wire_api,
        }
    )

    if decision is not None:
        trace.append(
            {
                "step": "resolution_applied",
                "rule": decision.resolution_rule,
                "reason": decision.resolution_reason,
                "winner_source": decision.winner_source,
                "loser_sources": list(decision.loser_sources),
            }
        )
        if decision.provider_resolved:
            trace.append(
                {
                    "step": "provider_winner_selected",
                    "provider_resolved": decision.provider_resolved,
                }
            )
        if decision.base_url_resolved:
            trace.append(
                {
                    "step": "base_url_resolved",
                    "base_url_resolved": decision.base_url_resolved,
                }
            )
        if decision.model_resolved:
            trace.append(
                {
                    "step": "model_resolved",
                    "model_resolved": decision.model_resolved,
                }
            )
        trace.append(
            {
                "step": "resolution_decision",
                "winner_source": decision.winner_source,
                "provider_resolved": decision.provider_resolved,
                "base_url_resolved": decision.base_url_resolved,
                "model_resolved": decision.model_resolved,
                "auth_resolved": decision.auth_resolved,
                "wire_api_resolved": decision.wire_api_resolved,
            }
        )
        if raw_intent.model_requested and decision.model_resolved and raw_intent.model_requested != decision.model_resolved:
            trace.append(
                {
                    "step": "model_normalized",
                    "requested": raw_intent.model_requested,
                    "resolved": decision.model_resolved,
                }
            )

    return trace


def detect_conflicts(
    raw_intent: RawTruthIntent,
    canonical_refs: CanonicalTruthRefs,
    decision: Optional[ResolutionDecision] = None,
    *,
    registry: Optional[CanonicalTruthRegistry] = None,
    resolution_decision: Optional[ResolutionDecision] = None,
) -> list[str]:
    decision = resolution_decision or decision
    truth_registry = registry or get_default_truth_registry()
    conflicts: list[str] = []

    if raw_intent.model_requested and truth_registry.find_model_by_name(raw_intent.model_requested) is None:
        conflicts.append("unknown_model_alias")
    if raw_intent.base_url_requested and truth_registry.find_endpoint_by_base_url(raw_intent.base_url_requested) is None:
        conflicts.append("unknown_endpoint_ref")

    provider_ref = (
        (decision.provider_resolved if decision and decision.provider_resolved else None)
        or canonical_refs.provider_ref
        or raw_intent.provider_requested
    )
    wire_api = (
        (decision.wire_api_resolved if decision and decision.wire_api_resolved else None)
        or canonical_refs.canonical_wire_api
        or raw_intent.wire_api_requested
    )

    if canonical_refs.model_ref and not truth_registry.is_model_compatible_with_provider(canonical_refs.model_ref, provider_ref):
        conflicts.append("model_provider_mismatch")
    if canonical_refs.auth_ref and not truth_registry.is_auth_compatible_with_provider(canonical_refs.auth_ref, provider_ref):
        conflicts.append("auth_provider_mismatch")
    if canonical_refs.endpoint_ref and not truth_registry.is_endpoint_compatible_with_provider(canonical_refs.endpoint_ref, provider_ref):
        conflicts.append("base_url_provider_mismatch")
    if wire_api and not truth_registry.is_wire_api_compatible_with_provider(wire_api, provider_ref):
        conflicts.append("wire_api_provider_mismatch")

    if raw_intent.runtime_override_present and decision and decision.winner_source not in {
        "emergency_runtime_override",
        "runtime_override",
    }:
        conflicts.append("illegal_override_attempt")

    ordered: list[str] = []
    seen: set[str] = set()
    for conflict in conflicts:
        if conflict not in seen:
            ordered.append(conflict)
            seen.add(conflict)
    return ordered


def summarize_conflict(
    conflict_types: Sequence[str],
    *,
    provider_ref: Optional[str] = None,
    raw_intent: Optional[RawTruthIntent] = None,
    canonical_refs: Optional[CanonicalTruthRefs] = None,
    resolution_decision: Optional[ResolutionDecision] = None,
) -> str:
    if not conflict_types:
        return "No truth conflicts detected."
    labels = ", ".join(conflict_types)
    if raw_intent is not None or canonical_refs is not None or resolution_decision is not None:
        resolved_provider = provider_ref
        if not resolved_provider and resolution_decision is not None:
            resolved_provider = resolution_decision.provider_resolved
        if not resolved_provider and canonical_refs is not None:
            resolved_provider = canonical_refs.provider_ref
        winner = resolution_decision.winner_source if resolution_decision is not None else "unknown"
        return (
            f"Truth conflicts detected: provider={resolved_provider or 'unknown'} "
            f"winner={winner} conflicts={labels}"
        )
    if provider_ref:
        return f"Truth conflicts detected for provider {provider_ref}: {labels}."
    return f"Truth conflicts detected: {labels}."


def build_resolution_diagnostics(
    *,
    raw_intent: RawTruthIntent,
    canonical_refs: CanonicalTruthRefs,
    resolution_decision: Optional[ResolutionDecision] = None,
    registry: Optional[CanonicalTruthRegistry] = None,
) -> dict[str, Any]:
    truth_registry = registry or get_default_truth_registry()
    conflict_types = detect_conflicts(
        raw_intent,
        canonical_refs,
        resolution_decision,
        registry=truth_registry,
    )
    trace = build_resolution_trace(
        raw_intent,
        canonical_refs,
        resolution_decision,
        registry=truth_registry,
    )
    provider_ref = (
        canonical_refs.provider_ref
        or (resolution_decision.provider_resolved if resolution_decision else None)
        or raw_intent.provider_requested
    )
    return {
        "conflict_detected": bool(conflict_types),
        "conflict_types": conflict_types,
        "conflict_summary": summarize_conflict(conflict_types, provider_ref=provider_ref),
        "resolution_trace": trace,
    }
