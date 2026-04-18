from typing import Dict

from fastapi import Request

QUOTA_ROUTE_KEYWORDS = (
    "account",
    "usage",
    "limit",
    "billing",
    "subscription",
    "entitlement",
    "quota",
    "credit",
    "remaining",
)

PROXY_INGRESS_PATHS = {
    "/llm/chat",
    "/llm/chat/completions",
    "/llm/v1/chat/completions",
    "/llm/api/chat",
    "/llm/anthropic",
    "/llm/v1/messages",
    "/v1/messages",
    "/v1/responses",
    "/v1/codex/responses",
    "/v1/chat/completions",
}


def is_quota_related_path(path: str) -> bool:
    lowered = (path or "").lower()
    if lowered in PROXY_INGRESS_PATHS:
        return True
    return any(token in lowered for token in QUOTA_ROUTE_KEYWORDS)


def quota_marker(request: Request) -> Dict[str, str]:
    marker = getattr(request.state, "quota_audit", None)
    if isinstance(marker, dict):
        return {
            "upstream_url": str(marker.get("upstream_url") or ""),
            "action": str(marker.get("action") or "").strip(),
        }
    return {"upstream_url": "", "action": ""}


def classify_quota_observation(
    request: Request,
    path: str,
    status_code: int,
    content_length: str,
) -> str:
    marker = quota_marker(request)
    if marker["action"]:
        return marker["action"]
    if path in PROXY_INGRESS_PATHS:
        return "intercepted"
    if status_code in {404, 405}:
        return "intercepted"
    if str(content_length).strip() in {"0", ""} and status_code in {200, 204}:
        return "empty"
    return "bypassed"


def upstream_url_for_observation(request: Request, path: str) -> str:
    marker = quota_marker(request)
    if marker["upstream_url"]:
        return marker["upstream_url"]
    normalized = (path or "").strip()
    if normalized in {"/v1/responses", "/v1/codex/responses"}:
        return "unknown(codex_responses_chain)"
    return ""
