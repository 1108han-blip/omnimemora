"""
trace_store.py - OmniMemora Call Chain Tracing Store
====================================================
In-memory storage for request call chain traces (timing per stage).
Stores: request_id → CallChain

Usage:
    from 5_connectors.adapter.trace_store import store_trace, get_trace
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# In-memory trace storage — keyed by request_id
_trace_store: Dict[str, "CallChain"] = {}


# ------------------------------------------------------------------
# Dataclasses (mirrored from v2_compute for adapter-layer use)
# ------------------------------------------------------------------

@dataclass
class CallChainStage:
    """Single stage in a call chain with name and duration in ms."""
    name: str
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallChain:
    """Full call chain for a single request."""
    trace_id: str
    stages: List[CallChainStage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "stages": [
                {"name": s.name, "duration_ms": round(s.duration_ms, 3), "metadata": s.metadata}
                for s in self.stages
            ],
        }


# ------------------------------------------------------------------
# Store API
# ------------------------------------------------------------------

def store_trace(trace_id: str, chain: CallChain) -> None:
    """Store a call chain for a request."""
    _trace_store[trace_id] = chain


def get_trace(trace_id: str) -> Optional[CallChain]:
    """Retrieve a call chain by trace_id (request_id)."""
    return _trace_store.get(trace_id)


def get_trace_dict(trace_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a call chain as dict, or None if not found."""
    chain = get_trace(trace_id)
    return chain.to_dict() if chain else None


def list_recent_traces(limit: int = 20) -> List[Dict[str, Any]]:
    """List the most recent N traces (for live flow fallback)."""
    traces = sorted(_trace_store.values(), key=lambda c: c.trace_id, reverse=True)
    return [c.to_dict() for c in traces[:limit]]


def clear_all_traces() -> None:
    """Clear all traces. For testing only."""
    _trace_store.clear()
