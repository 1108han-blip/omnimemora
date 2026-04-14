from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime


class PolicyWeights(BaseModel):
    relevance: float = 1.0
    recency: float = 1.0
    scope: float = 1.0


class PolicyCompression(BaseModel):
    enabled: bool = True
    mode: str = "balanced"


class PolicySelection(BaseModel):
    max_memories: int = 6


class Policy(BaseModel):
    version: str = "local-default-v1"
    weights: PolicyWeights = PolicyWeights()
    compression: PolicyCompression = PolicyCompression()
    selection: PolicySelection = PolicySelection()


class FeatureFlags(BaseModel):
    optimization_enabled: bool = True
    live_feedback_enabled: bool = True
    aggressive_mode: bool = False


class UsageReport(BaseModel):
    request_id: str
    tenant: Optional[str] = None
    saved_tokens: int = 0
    savings_ratio: float = 0.0
    request_count: int = 1
    timestamp: str = ""
