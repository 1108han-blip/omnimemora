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

from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional


# =============================================================================
# Classification Rules
# =============================================================================

# Known internal query patterns
_INTERNAL_QUERIES = {
    "session bootstrap context handshake",
}

_INTERNAL_QUERY_PREFIXES = (
    "sender (untrusted metadata):",
    "system (untrusted):",
)

_INTERNAL_QUERY_MARKERS = (
    "openclaw-control-ui",
    "exec completed (",
)

_OPERATOR_VERIFICATION_MARKERS = (
    "ui链路验收",
    "openclaw_final_check",
    "openclaw_after_fix",
    "openclaw_real_path_ok",
    "openclaw_route_used",
    "openclaw_chat_check_ok",
    "reply with ok",
    "reply with ok-2",
    "dashboard live meter check",
    "port-18011 live meter check",
    "5173 ui refresh verification",
    "dashboard verification test",
    "stability heartbeat iteration",
)

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
    normalized_query = extract_user_visible_query(query)

    # Rule 1: Known internal query patterns
    if query in _INTERNAL_QUERIES or normalized_query in _INTERNAL_QUERIES:
        return "internal"

    query_lower = query.lower()
    normalized_query_lower = normalized_query.lower()

    # Rule 1b: Untrusted control-surface metadata should not count as a real request
    if any(query_lower.startswith(prefix) for prefix in _INTERNAL_QUERY_PREFIXES):
        if any(marker in query_lower for marker in _INTERNAL_QUERY_MARKERS):
            if not normalized_query:
                return "internal"

    # Rule 2: Internal agent + bootstrap in query
    agent_lower = agent.lower()
    if agent_lower in _INTERNAL_AGENTS and "bootstrap" in normalized_query_lower:
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


def is_operator_verification_query(query: str) -> bool:
    """Return True when query matches known operator-only verification traffic."""
    query_lower = extract_user_visible_query(query).strip().lower()
    if not query_lower:
        return False
    return any(marker in query_lower for marker in _OPERATOR_VERIFICATION_MARKERS)


def is_operator_verification_request(meter: Any) -> bool:
    query = getattr(meter, "query", "") or ""
    return is_operator_verification_query(query)


def is_task_request(meter: Any) -> bool:
    """
    User-visible task request for overview/live flow.

    This is intentionally broader than "real":
    any request with user-visible prompt content counts as a task request,
    even if it originated from a validation run.
    """
    return bool(extract_user_visible_query(getattr(meter, "query", "") or ""))


def is_default_overview_request(meter: Any) -> bool:
    """Default overview shows task data, not a narrower 'real' subset."""
    return is_task_request(meter)


def collapse_retry_bursts(meters: Iterable[Any], window_seconds: int = 90) -> List[Any]:
    """
    Collapse retry bursts from the same user action into one representative meter.

    OpenClaw may retry identical prompts several times within a short window when
    the upstream provider overloads or the gateway reconnects. For user-facing
    overview surfaces we keep the latest attempt in each short burst.
    """
    ordered = sorted(list(meters), key=_meter_timestamp)
    collapsed: List[Any] = []
    latest_by_fingerprint: dict[tuple[str, str], tuple[int, float]] = {}

    for meter in ordered:
        ts = _meter_timestamp(meter)
        fingerprint = _request_fingerprint(meter)
        prev = latest_by_fingerprint.get(fingerprint)
        if prev and (ts - prev[1]) <= window_seconds:
            collapsed[prev[0]] = meter
            latest_by_fingerprint[fingerprint] = (prev[0], ts)
            continue

        collapsed.append(meter)
        latest_by_fingerprint[fingerprint] = (len(collapsed) - 1, ts)

    return collapsed


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


def _meter_timestamp(meter: Any) -> float:
    raw = getattr(meter, "timestamp", "") or ""
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except Exception:
        return 0.0


def _request_fingerprint(meter: Any) -> tuple[str, str]:
    agent = (getattr(meter, "agent", "") or "").strip().lower()
    query = " ".join(extract_user_visible_query(getattr(meter, "query", "") or "").strip().lower().split())
    return agent, query


def extract_user_visible_query(query: str) -> str:
    """
    Strip known OpenClaw metadata envelopes and return the actual user-visible prompt.

    If the payload is metadata-only, returns an empty string.
    """
    raw = (query or "").strip()
    if not raw:
        return ""

    lower = raw.lower()
    if not any(lower.startswith(prefix) for prefix in _INTERNAL_QUERY_PREFIXES):
        return raw

    if "```" not in raw:
        return ""

    first_fence = raw.find("```")
    second_fence = raw.find("```", first_fence + 3)
    if second_fence == -1:
        return ""

    remainder = raw[second_fence + 3 :].strip()
    return remainder
