"""Data models for Token Intelligence Lite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


USAGE_SOURCES = {
    "provider_reported",
    "relay_reported",
    "local_estimated",
    "post_fetch_reported",
    "manual_price_inferred",
}

CONFIDENCE_CLASSES = {
    "official_usage",
    "reconciled_usage",
    "provider_tokenizer",
    "compatible_estimate",
    "tokenizer_estimate",
    "rough_estimate",
}


@dataclass(frozen=True)
class NormalizedUsage:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    image_tokens: Optional[int] = None
    audio_tokens: Optional[int] = None
    tool_tokens: Optional[int] = None
    source: str = "local_estimated"
    confidence: str = "rough_estimate"
    raw_usage_present: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "cached_input_tokens": self.cached_input_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "reasoning_tokens": self.reasoning_tokens,
                "image_tokens": self.image_tokens,
                "audio_tokens": self.audio_tokens,
                "tool_tokens": self.tool_tokens,
                "source": self.source,
                "confidence": self.confidence,
                "raw_usage_present": self.raw_usage_present,
            }
        )


@dataclass(frozen=True)
class NormalizedCost:
    total_cost_usd: Optional[float] = None
    source: str = "manual_price_inferred"
    confidence: str = "rough_estimate"
    pricing_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "total_cost_usd": self.total_cost_usd,
                "source": self.source,
                "confidence": self.confidence,
                "pricing_version": self.pricing_version,
            }
        )


@dataclass(frozen=True)
class AuditEvent:
    audit_id: str
    request_id: str
    request_hash: str
    response_hash: str
    upstream_base_url_hash: str
    provider: str
    model_requested: str
    model_reported: str
    usage: NormalizedUsage
    cost: NormalizedCost = field(default_factory=NormalizedCost)
    latency_ms: Optional[int] = None
    status_code: Optional[int] = None
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "audit_id": self.audit_id,
                "request_id": self.request_id,
                "request_hash": self.request_hash,
                "response_hash": self.response_hash,
                "upstream_base_url_hash": self.upstream_base_url_hash,
                "provider": self.provider,
                "model_requested": self.model_requested,
                "model_reported": self.model_reported,
                "usage": self.usage.to_dict(),
                "cost": self.cost.to_dict(),
                "latency_ms": self.latency_ms,
                "status_code": self.status_code,
                "created_at": self.created_at,
                "metadata": self.metadata,
            }
        )


def _drop_none(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
