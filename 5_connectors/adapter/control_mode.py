"""
control_mode.py - Per-Agent Control Mode Resolution
===============================================================
Loads control mode per-agent from config + capability check.
"""
from typing import Literal, Optional
from pydantic import BaseModel


ControlModeValue = Literal["observe", "guided", "force_if_possible", "off"]


class ControlMode(BaseModel):
    mode: ControlModeValue = "observe"


def get_capabilities(integration_type: str) -> dict:
    """
    Returns capability matrix for given integration type.
    Controls which control modes are supported.
    """
    CAPABILITY_REGISTRY = {
        "tool_caller": {
            "supports_guided": True,
            "supports_force_if_possible": False,
            "supports_usage_reporting": True,
        },
        "pre_llm_connector": {
            "supports_guided": True,
            "supports_force_if_possible": True,
            "supports_usage_reporting": True,
        },
        "wrapper": {
            "supports_guided": True,
            "supports_force_if_possible": True,
            "supports_usage_reporting": True,
        },
        "unknown": {
            "supports_guided": True,
            "supports_force_if_possible": False,
            "supports_usage_reporting": True,
        },
    }
    return CAPABILITY_REGISTRY.get(integration_type, CAPABILITY_REGISTRY["unknown"])


def load_control_mode(
    agent_id: str,
    integration_type: str,
    per_agent_modes: dict[str, str],
    default_mode: str = "observe",
) -> ControlMode:
    """
    Resolve control mode for an agent.

    Rules:
    1. Per-agent config takes precedence
    2. Fall back to default_mode
    3. If force_if_possible requested but capability doesn't support it, downgrade to guided

    Args:
        agent_id: unique agent identifier
        integration_type: type of integration (tool_caller / pre_llm_connector / wrapper / unknown)
        per_agent_modes: dict from config {agent_id: mode}
        default_mode: fallback mode

    Returns:
        ControlMode with resolved and capability-checked mode
    """
    # Step 1: per-agent override
    mode_str = per_agent_modes.get(agent_id, default_mode)

    # Step 2: validate it's a known mode
    valid_modes: set[str] = {"observe", "guided", "force_if_possible", "off"}
    if mode_str not in valid_modes:
        mode_str = default_mode

    # Step 3: capability downgrade for force_if_possible
    if mode_str == "force_if_possible":
        caps = get_capabilities(integration_type)
        if not caps.get("supports_force_if_possible", False):
            mode_str = "guided"

    return ControlMode(mode=mode_str)  # type: ignore