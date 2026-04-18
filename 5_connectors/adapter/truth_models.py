"""
Single-definition truth model dataclasses for Truth Bridge v2 foundation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .truth_arbitration import DEFAULT_SOURCE_PRIORITY_CHAIN as ARBITRATION_SOURCE_PRIORITY_CHAIN


DEFAULT_SOURCE_PRIORITY_CHAIN: tuple[str, ...] = tuple(ARBITRATION_SOURCE_PRIORITY_CHAIN)


@dataclass(frozen=True)
class ProviderDefinition:
    provider_ref: str
    provider_canonical_name: str
    supported_wire_apis: tuple[str, ...] = field(default_factory=tuple)
    default_endpoint_ref: Optional[str] = None
    auth_modes_supported: tuple[str, ...] = field(default_factory=tuple)
    compile_supported: bool = False
    fallback_supported: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EndpointDefinition:
    endpoint_ref: str
    base_url: str
    provider_ref: str
    wire_apis_supported: tuple[str, ...] = field(default_factory=tuple)
    environment_scope: Optional[str] = None
    is_default: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelDefinition:
    model_ref: str
    canonical_model_name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    provider_ref: str = ""
    wire_model_name: Optional[str] = None
    routing_tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthDefinition:
    auth_ref: str
    auth_type: str
    provider_ref: str
    injection_mode: str
    source_kind: str
    redaction_strategy: str = "mask_all"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


ProviderRecord = ProviderDefinition
EndpointRecord = EndpointDefinition
ModelRecord = ModelDefinition
AuthRecord = AuthDefinition
ProviderTruth = ProviderDefinition
EndpointTruth = EndpointDefinition
ModelTruth = ModelDefinition
AuthTruth = AuthDefinition


@dataclass(frozen=True)
class RawTruthIntent:
    agent_id: str
    request_path: str
    wire_api_requested: Optional[str] = None
    provider_requested: Optional[str] = None
    base_url_requested: Optional[str] = None
    model_requested: Optional[str] = None
    auth_requested: Optional[str] = None
    fallback_requested: Optional[bool] = None
    provider_source: Optional[str] = None
    base_url_source: Optional[str] = None
    model_source: Optional[str] = None
    auth_source: Optional[str] = None
    fallback_source: Optional[str] = None
    runtime_override_present: bool = False
    policy_profile: Optional[str] = None
    compile_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalTruthRefs:
    provider_ref: Optional[str] = None
    endpoint_ref: Optional[str] = None
    model_ref: Optional[str] = None
    auth_ref: Optional[str] = None
    fallback_policy_ref: Optional[str] = None
    canonical_wire_api: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolutionDecision:
    provider_resolved: Optional[str] = None
    base_url_resolved: Optional[str] = None
    model_resolved: Optional[str] = None
    auth_resolved: Optional[str] = None
    wire_api_resolved: Optional[str] = None
    fallback_used: bool = False
    resolution_rule: Optional[str] = None
    resolution_reason: Optional[str] = None
    winner_source: Optional[str] = None
    loser_sources: list[str] = field(default_factory=list)
    conflict_detected: bool = False
    conflict_types: list[str] = field(default_factory=list)
    source_priority_chain: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_PRIORITY_CHAIN))
    resolved_fields: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedTruthContract:
    request_id: str
    agent_id: str
    policy_profile: Optional[str] = None
    model_requested: Optional[str] = None
    provider_requested: Optional[str] = None
    base_url_requested: Optional[str] = None
    provider_ref: Optional[str] = None
    endpoint_ref: Optional[str] = None
    model_ref: Optional[str] = None
    auth_ref: Optional[str] = None
    fallback_policy_ref: Optional[str] = None
    provider_resolved: Optional[str] = None
    base_url_resolved: Optional[str] = None
    model_resolved: Optional[str] = None
    auth_source: Optional[str] = None
    auth_resolved: Optional[str] = None
    wire_api_resolved: Optional[str] = None
    fallback_used: bool = False
    compile_enabled: bool = False
    resolution_rule: Optional[str] = None
    resolution_reason: Optional[str] = None
    conflict_detected: bool = False
    conflict_types: list[str] = field(default_factory=list)
    source_priority_chain: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_PRIORITY_CHAIN))
    resolution_trace: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaterializedAuth:
    auth_ref: Optional[str] = None
    auth_type: Optional[str] = None
    injection_mode: Optional[str] = None
    source_kind: Optional[str] = None
    provider_ref: Optional[str] = None
    header_name: Optional[str] = None
    header_value: Optional[str] = None
    header_value_redacted: Optional[str] = None
    auth_present: bool = False
    materialization_status: str = "not_requested"
    materialization_error: Optional[str] = None
    materialization_trace: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
