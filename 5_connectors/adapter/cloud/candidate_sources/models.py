"""Models for cloud recommendation candidate sources."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CandidatePointer(BaseModel):
    candidate_id: str
    policy_version: str
    snapshot_id: str
    snapshot_store: str = "railway"
    fetched_at: Optional[str] = None
    meta: dict[str, Any] = {}


class CandidateSnapshot(BaseModel):
    snapshot_id: str
    policy: dict[str, Any]
    policy_version: Optional[str] = None
    source: str = "railway_snapshot"
    meta: dict[str, Any] = {}
