"""
agent_identity.py - Unified Agent/Session/Workspace Identity Resolution
=======================================================================
Per ADR-0005: adapter 只做映射，不做定义。

Runtime defines canonical_agent_id (治理字段，用于 memory scope / record 归属).
Adapter resolves raw input, maps to canonical, and supplements with session/integration metadata.

Priorities: Header > Query > Body > fallback(unknown)
"""
from pydantic import BaseModel
from typing import Literal, Optional
from fastapi import Request


IntegrationType = Literal["tool_caller", "pre_llm_connector", "wrapper", "unknown"]

# ADR-0005: 标准映射表 — raw_agent_id → canonical_agent_id
AGENT_ID_MAPPING: dict[str, str] = {
    "claude-code-cli": "claude_code",
    "claude-code": "claude_code",
    "openclaw-agent": "openclaw",
    "openclaw": "openclaw",
    "codex-cli": "codex_cli",
    "codex": "codex_cli",
}


class AgentIdentity(BaseModel):
    """
    ADR-0005: Adapter 内部标准结构。

    - canonical_agent_id: runtime 认可的 agent 唯一标识（治理字段）
    - raw_agent_id: 外部接入传入的原始值（不可信，仅用于日志/tracking）
    - 其余字段: session/integration 维度的补充 metadata
    """
    # ===== 核心字段 =====
    canonical_agent_id: str = "unknown"

    # ===== 输入来源 =====
    raw_agent_id: Optional[str] = None

    # ===== 分类信息 =====
    agent_family: Optional[str] = None
    integration_type: IntegrationType = "unknown"

    # ===== 会话维度 =====
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None

    # ===== 来源标记 =====
    source: Literal["header", "query", "body", "inferred", "default"] = "default"


def _safe_str(value: Optional[str]) -> str:
    """Normalize empty/None to 'unknown'."""
    if not value or value.strip() == "":
        return "unknown"
    return value.strip()


def _safe_optional_str(value: Optional[str]) -> Optional[str]:
    """Return None for empty/None, else stripped string."""
    if not value or value.strip() == "":
        return None
    return value.strip()


def _safe_integration(value: Optional[str]) -> IntegrationType:
    """Normalize to valid IntegrationType."""
    valid = {"tool_caller", "pre_llm_connector", "wrapper"}
    if value in valid:
        return value  # type: ignore
    return "unknown"


def resolve_canonical_agent_id(raw_agent_id: Optional[str]) -> str:
    """
    ADR-0005 Rule 1 & 2:
    将外部 raw_agent_id 映射为 runtime 的 canonical_agent_id。

    优先级:
    1. 映射表匹配
    2. agent_family 推断
    3. fallback = "unknown"
    """
    if not raw_agent_id or raw_agent_id == "unknown":
        return "unknown"

    # 1. 映射表
    if raw_agent_id in AGENT_ID_MAPPING:
        return AGENT_ID_MAPPING[raw_agent_id]

    # 2. 直接返回（未经映射的原始值也算 canonical）
    #    ADR-0005: adapter 不重新定义，只能映射
    return raw_agent_id


def resolve_agent_identity(request: Request) -> AgentIdentity:
    """
    ADR-0005: 解析 request 身份，按优先级从 Header > Query > Body 提取。

    1. 提取 raw_agent_id（外部原始值）
    2. 映射为 canonical_agent_id（runtime 对齐）
    3. 补充 session / workspace / integration metadata
    """
    # 1. Try Header
    raw_agent_id = _safe_optional_str(request.headers.get("x-agent-id"))
    agent_family = _safe_optional_str(request.headers.get("x-agent-family"))
    session_id = _safe_optional_str(request.headers.get("x-session-id"))
    workspace_id = _safe_optional_str(request.headers.get("x-workspace-id"))
    user_id = _safe_optional_str(request.headers.get("x-user-id"))
    integration_type = _safe_integration(request.headers.get("x-integration-type"))
    source: str = "header"

    # 2. Try Query params (only if header gave nothing)
    if raw_agent_id is None:
        raw_agent_id = _safe_optional_str(request.query_params.get("agent_id"))
        source = "query"
    if session_id is None:
        session_id = _safe_optional_str(request.query_params.get("session_id"))
    if workspace_id is None:
        workspace_id = _safe_optional_str(request.query_params.get("workspace_id"))
    if integration_type == "unknown":
        integration_type = _safe_integration(request.query_params.get("integration_type"))

    # 3. Try Body JSON (only if still unknown)
    body_data = {}
    try:
        body_data = request.state._body_cache if hasattr(request.state, "_body_cache") else {}
    except Exception:
        pass

    if raw_agent_id is None and "agent_id" in body_data:
        raw_agent_id = _safe_optional_str(body_data.get("agent_id"))
        source = "body"
    if raw_agent_id is None and "agent" in body_data:
        raw_agent_id = _safe_optional_str(body_data.get("agent"))
        source = "body"
    if session_id is None and "session_id" in body_data:
        session_id = _safe_optional_str(body_data.get("session_id"))
    if session_id is None and "conversation_id" in body_data:
        session_id = _safe_optional_str(body_data.get("conversation_id"))
    if session_id is None and "thread_id" in body_data:
        session_id = _safe_optional_str(body_data.get("thread_id"))
    if workspace_id is None and "workspace_id" in body_data:
        workspace_id = _safe_optional_str(body_data.get("workspace_id"))
    if user_id is None and "user_id" in body_data:
        user_id = _safe_optional_str(body_data.get("user_id"))
    if integration_type == "unknown" and "integration_type" in body_data:
        integration_type = _safe_integration(body_data.get("integration_type"))

    # 4. Map to canonical
    canonical_agent_id = resolve_canonical_agent_id(raw_agent_id)

    return AgentIdentity(
        canonical_agent_id=canonical_agent_id,
        raw_agent_id=raw_agent_id,
        agent_family=agent_family,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        integration_type=integration_type,
        source=source,
    )


def agent_identity_to_log_fields(identity: AgentIdentity) -> dict:
    """Convert AgentIdentity to flat dict for logging (per ADR-0005 logging spec)."""
    return {
        "canonical_agent_id": identity.canonical_agent_id,
        "raw_agent_id": identity.raw_agent_id,
        "agent_family": identity.agent_family,
        "session_id": identity.session_id,
        "integration_type": identity.integration_type,
        "identity_source": identity.source,
    }
