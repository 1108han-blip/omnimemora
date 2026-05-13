"""Audit receipt helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import AuditEvent


def stable_hash(value: Any) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        serialized = str(value)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_receipt(event: AuditEvent) -> dict[str, Any]:
    return {
        "audit_id": event.audit_id,
        "request_id": event.request_id,
        "request_hash": event.request_hash,
        "response_hash": event.response_hash,
        "upstream_base_url_hash": event.upstream_base_url_hash,
        "provider": event.provider,
        "model_requested": event.model_requested,
        "model_reported": event.model_reported,
        "usage": event.usage.to_dict(),
        "cost": event.cost.to_dict(),
        "latency_ms": event.latency_ms,
        "status_code": event.status_code,
        "created_at": event.created_at,
        "blocks": event.blocks,
    }
