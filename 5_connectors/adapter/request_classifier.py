"""
request_classifier.py - Unified Request Classification for OmniMemora
========================================================================
Provides a single source of truth for classifying requests as:
  - real: user-facing work requests
  - internal: bootstrap, handshake, transport-level events

Used by:
  - metrics_service (四卡, trend, recent_requests)
  - agent_control_api._build_traffic_truth()
  - any other adapter-level request classification

Public Interface
----------------
classify_request(agent: str, query: str, extra: dict | None = None) -> str
  Returns "real" or "internal"

is_real_request(meter) -> bool
  Convenience for meter objects (has .agent and .query attributes)
"""

from typing import Any, Optional


# =============================================================================
# Classification Rules
# =============================================================================

# Known internal query patterns
_INTERNAL_QUERIES = {
    "session bootstrap context handshake",
}

# Known internal agents
_INTERNAL_AGENTS = {
    "openclaw-bundle-mcp",
    "openclaw_bundle_mcp",
}


def classify_request(agent: str, query: str, extra: Optional[dict] = None) -> str:
    """
    Classify a request as 'real' or 'internal'.

    Rules (in priority order):
    1. If query matches known internal pattern -> internal
    2. If agent is known internal agent AND query contains 'bootstrap' -> internal
    3. If extra flags indicate internal (e.g., transport-level event) -> internal
    4. Otherwise -> real

    Args:
        agent: Agent identifier string
        query: Query text string
        extra: Optional dict with additional classification hints (e.g., {"transport_event": True})

    Returns:
        "real" or "internal"
    """
    query = query or ""
    agent = agent or ""

    # Rule 1: Known internal query patterns
    if query in _INTERNAL_QUERIES:
        return "internal"

    # Rule 2: Internal agent + bootstrap in query
    agent_lower = agent.lower()
    if agent_lower in _INTERNAL_AGENTS and "bootstrap" in query.lower():
        return "internal"

    # Rule 3: Extra flags
    if extra:
        # Transport-level events are always internal
        if extra.get("transport_event"):
            return "internal"
        # MCP handshake events
        if extra.get("mcp_handshake"):
            return "internal"

    # Rule 4: Default
    return "real"


def is_real_request(meter: Any) -> bool:
    """
    Convenience function for meter objects.

    Args:
        meter: Any object with .agent and .query attributes

    Returns:
        True if this is a real request, False if internal
    """
    agent = getattr(meter, "agent", "") or ""
    query = getattr(meter, "query", "") or ""
    return classify_request(agent, query) == "real"


def is_tiny_ping(meter: Any, threshold: int = 50) -> bool:
    """
    Detect tiny/basic ping requests that don't represent meaningful work.

    Args:
        meter: Meter object with baseline_tokens_estimate or similar
        threshold: Token count below which a request is considered a ping (default 50)

    Returns:
        True if the request appears to be a ping (no meaningful context)
    """
    baseline = getattr(meter, "baseline_tokens_estimate", 0)
    # Handle both int and float
    try:
        baseline = int(baseline)
    except (ValueError, TypeError):
        return True  # Can't determine, assume ping

    return baseline < threshold