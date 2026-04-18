"""
truth_arbitration.py
====================

Centralized precedence-based truth arbitration for provider/base_url/model/auth/
wire_api/fallback resolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


DEFAULT_SOURCE_PRIORITY_CHAIN = [
    "emergency_runtime_override",
    "runtime_override",
    "product_policy_binding",
    "agent_truth_bridge",
    "agent_payload_explicit",
    "local_default_profile",
    "provider_default",
]

DEFAULT_RESOLUTION_RULE = "precedence_first_non_empty"

SUPPORTED_TRUTH_FIELDS = (
    "provider",
    "base_url",
    "model",
    "auth",
    "wire_api",
    "fallback",
)


@dataclass(frozen=True)
class TruthCandidate:
    field_name: str
    value: Any
    source: str
    detail: str | None = None
    priority: int | None = None

    def normalized_priority(self, priority_chain: list[str]) -> int:
        if self.priority is not None:
            return self.priority
        try:
            return priority_chain.index(self.source)
        except ValueError:
            return len(priority_chain) + 100


@dataclass(frozen=True)
class FieldResolution:
    field_name: str
    value: Any
    winner_source: str | None
    loser_sources: list[str] = field(default_factory=list)
    resolution_rule: str = DEFAULT_RESOLUTION_RULE
    resolution_reason: str = ""
    conflict_detected: bool = False
    conflict_types: list[str] = field(default_factory=list)
    candidates: list[TruthCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class ResolutionDecision:
    provider_resolved: str | None
    base_url_resolved: str | None
    model_resolved: str | None
    auth_resolved: str | None
    wire_api_resolved: str | None
    fallback_used: bool
    resolution_rule: str
    resolution_reason: str
    winner_source: str | None
    loser_sources: list[str] = field(default_factory=list)
    conflict_detected: bool = False
    conflict_types: list[str] = field(default_factory=list)
    source_priority_chain: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_PRIORITY_CHAIN))
    resolved_fields: dict[str, FieldResolution] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_resolved": self.provider_resolved,
            "base_url_resolved": self.base_url_resolved,
            "model_resolved": self.model_resolved,
            "auth_resolved": self.auth_resolved,
            "wire_api_resolved": self.wire_api_resolved,
            "fallback_used": self.fallback_used,
            "resolution_rule": self.resolution_rule,
            "resolution_reason": self.resolution_reason,
            "winner_source": self.winner_source,
            "loser_sources": list(self.loser_sources),
            "conflict_detected": self.conflict_detected,
            "conflict_types": list(self.conflict_types),
            "source_priority_chain": list(self.source_priority_chain),
        }


@dataclass(frozen=True)
class ArbitrationInput:
    candidates_by_source: Mapping[str, Mapping[str, Any]]
    priority_chain: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_PRIORITY_CHAIN))

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates_by_source": dict(self.candidates_by_source),
            "priority_chain": list(self.priority_chain),
        }


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _normalize_field_value(field_name: str, value: Any) -> Any:
    if field_name == "fallback":
        return _normalize_bool(value)
    return _normalize_text(value)


def _make_candidate(field_name: str, raw_value: Any, source: str) -> TruthCandidate | None:
    normalized = _normalize_field_value(field_name, raw_value)
    if normalized is None:
        return None
    return TruthCandidate(field_name=field_name, value=normalized, source=source)


def collect_truth_candidates(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> dict[str, list[TruthCandidate]]:
    priority_list = list(priority_chain or DEFAULT_SOURCE_PRIORITY_CHAIN)
    collected: dict[str, list[TruthCandidate]] = {field_name: [] for field_name in SUPPORTED_TRUTH_FIELDS}

    for source_name, payload in candidates_by_source.items():
        if not isinstance(payload, Mapping):
            continue
        for field_name in SUPPORTED_TRUTH_FIELDS:
            candidate = _make_candidate(field_name, payload.get(field_name), source_name)
            if candidate is not None:
                collected[field_name].append(candidate)

    for field_name, candidates in collected.items():
        candidates.sort(key=lambda item: item.normalized_priority(priority_list))
        collected[field_name] = candidates
    return collected


def _detect_field_conflicts(field_name: str, candidates: list[TruthCandidate]) -> list[str]:
    if len(candidates) <= 1:
        return []

    unique_values = {candidate.value for candidate in candidates}
    if len(unique_values) <= 1:
        return []

    if field_name == "base_url":
        return ["base_url_conflict"]
    if field_name == "provider":
        return ["provider_conflict"]
    if field_name == "model":
        return ["model_conflict"]
    if field_name == "auth":
        return ["auth_conflict"]
    if field_name == "wire_api":
        return ["wire_api_conflict"]
    if field_name == "fallback":
        return ["fallback_policy_conflict"]
    return [f"{field_name}_conflict"]


def resolve_field(
    field_name: str,
    candidates: Iterable[TruthCandidate],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    priority_list = list(priority_chain or DEFAULT_SOURCE_PRIORITY_CHAIN)
    ordered = sorted(
        list(candidates),
        key=lambda item: item.normalized_priority(priority_list),
    )
    if not ordered:
        return FieldResolution(
            field_name=field_name,
            value=None,
            winner_source=None,
            resolution_reason=f"no_candidate_for_{field_name}",
            candidates=[],
        )

    winner = ordered[0]
    losers = [candidate.source for candidate in ordered[1:]]
    conflict_types = _detect_field_conflicts(field_name, ordered)
    return FieldResolution(
        field_name=field_name,
        value=winner.value,
        winner_source=winner.source,
        loser_sources=losers,
        resolution_reason=(
            f"{winner.source} selected by precedence for {field_name}"
            if losers
            else f"{winner.source} supplied {field_name}"
        ),
        conflict_detected=bool(conflict_types),
        conflict_types=conflict_types,
        candidates=ordered,
    )


def _resolve_from_sources(
    field_name: str,
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    collected = collect_truth_candidates(candidates_by_source, priority_chain=priority_chain)
    return resolve_field(
        field_name,
        collected.get(field_name, []),
        priority_chain=priority_chain,
    )


def resolve_provider(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    return _resolve_from_sources("provider", candidates_by_source, priority_chain=priority_chain)


def resolve_base_url(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    return _resolve_from_sources("base_url", candidates_by_source, priority_chain=priority_chain)


def resolve_model(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    return _resolve_from_sources("model", candidates_by_source, priority_chain=priority_chain)


def resolve_auth(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    return _resolve_from_sources("auth", candidates_by_source, priority_chain=priority_chain)


def resolve_wire_api(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    return _resolve_from_sources("wire_api", candidates_by_source, priority_chain=priority_chain)


def resolve_fallback(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> FieldResolution:
    return _resolve_from_sources("fallback", candidates_by_source, priority_chain=priority_chain)


def _infer_cross_field_conflicts(resolved_fields: Mapping[str, FieldResolution]) -> list[str]:
    conflict_types: list[str] = []

    provider_value = _normalize_text(resolved_fields.get("provider", FieldResolution("provider", None, None)).value)
    base_url_value = _normalize_text(resolved_fields.get("base_url", FieldResolution("base_url", None, None)).value)
    model_value = _normalize_text(resolved_fields.get("model", FieldResolution("model", None, None)).value)
    auth_value = _normalize_text(resolved_fields.get("auth", FieldResolution("auth", None, None)).value)
    wire_api_value = _normalize_text(resolved_fields.get("wire_api", FieldResolution("wire_api", None, None)).value)

    if provider_value and base_url_value:
        normalized_provider = provider_value.lower()
        normalized_base = base_url_value.lower()
        if "anthropic" in normalized_provider and "openai" in normalized_base:
            conflict_types.append("base_url_provider_mismatch")
        if "openai" in normalized_provider and "anthropic" in normalized_base:
            conflict_types.append("base_url_provider_mismatch")

    if provider_value and model_value:
        normalized_provider = provider_value.lower()
        normalized_model = model_value.lower()
        if normalized_model.startswith("claude") and "anthropic" not in normalized_provider:
            conflict_types.append("model_provider_mismatch")
        if normalized_model.startswith(("gpt", "o1", "o3")) and "openai" not in normalized_provider:
            conflict_types.append("model_provider_mismatch")

    if provider_value and auth_value:
        normalized_provider = provider_value.lower()
        normalized_auth = auth_value.lower()
        if "anthropic" in normalized_auth and "anthropic" not in normalized_provider:
            conflict_types.append("auth_provider_mismatch")
        if "openai" in normalized_auth and "openai" not in normalized_provider:
            conflict_types.append("auth_provider_mismatch")

    if provider_value and wire_api_value:
        normalized_provider = provider_value.lower()
        normalized_wire = wire_api_value.lower()
        if normalized_wire == "anthropic_messages" and "anthropic" not in normalized_provider:
            conflict_types.append("wire_api_provider_mismatch")
        if normalized_wire in {"responses", "chat_completions"} and "openai" not in normalized_provider:
            conflict_types.append("wire_api_provider_mismatch")

    return conflict_types


def arbitrate_truth(
    candidates_by_source: Mapping[str, Mapping[str, Any]],
    *,
    priority_chain: Iterable[str] | None = None,
) -> ResolutionDecision:
    priority_list = list(priority_chain or DEFAULT_SOURCE_PRIORITY_CHAIN)
    candidates = collect_truth_candidates(candidates_by_source, priority_chain=priority_list)

    resolved_fields = {
        field_name: resolve_field(field_name, field_candidates, priority_chain=priority_list)
        for field_name, field_candidates in candidates.items()
    }

    all_conflicts: list[str] = []
    all_losers: list[str] = []
    winner_sources: list[str] = []

    for field_resolution in resolved_fields.values():
        all_conflicts.extend(field_resolution.conflict_types)
        all_losers.extend(field_resolution.loser_sources)
        if field_resolution.winner_source:
            winner_sources.append(field_resolution.winner_source)

    all_conflicts.extend(_infer_cross_field_conflicts(resolved_fields))
    deduped_conflicts = list(dict.fromkeys(all_conflicts))
    deduped_losers = list(dict.fromkeys(all_losers))

    if winner_sources:
        winner_source = min(
            winner_sources,
            key=lambda source: priority_list.index(source) if source in priority_list else len(priority_list) + 100,
        )
    else:
        winner_source = None

    provider_resolved = _normalize_text(resolved_fields["provider"].value)
    base_url_resolved = _normalize_text(resolved_fields["base_url"].value)
    model_resolved = _normalize_text(resolved_fields["model"].value)
    auth_resolved = _normalize_text(resolved_fields["auth"].value)
    wire_api_resolved = _normalize_text(resolved_fields["wire_api"].value)
    fallback_used = bool(resolved_fields["fallback"].value) if resolved_fields["fallback"].value is not None else False

    resolution_reason = (
        f"{winner_source} won precedence arbitration"
        if winner_source
        else "no truth candidates resolved"
    )

    return ResolutionDecision(
        provider_resolved=provider_resolved,
        base_url_resolved=base_url_resolved,
        model_resolved=model_resolved,
        auth_resolved=auth_resolved,
        wire_api_resolved=wire_api_resolved,
        fallback_used=fallback_used,
        resolution_rule=DEFAULT_RESOLUTION_RULE,
        resolution_reason=resolution_reason,
        winner_source=winner_source,
        loser_sources=deduped_losers,
        conflict_detected=bool(deduped_conflicts),
        conflict_types=deduped_conflicts,
        source_priority_chain=priority_list,
        resolved_fields=resolved_fields,
    )
