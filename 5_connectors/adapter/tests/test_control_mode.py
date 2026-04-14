"""
Tests for control_mode.py
===============================================================
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_mode import load_control_mode, get_capabilities, ControlMode


class TestGetCapabilities:
    def test_tool_caller_capabilities(self):
        caps = get_capabilities("tool_caller")
        assert caps["supports_guided"] is True
        assert caps["supports_force_if_possible"] is False
        assert caps["supports_usage_reporting"] is True

    def test_pre_llm_connector_capabilities(self):
        caps = get_capabilities("pre_llm_connector")
        assert caps["supports_guided"] is True
        assert caps["supports_force_if_possible"] is True

    def test_wrapper_capabilities(self):
        caps = get_capabilities("wrapper")
        assert caps["supports_guided"] is True
        assert caps["supports_force_if_possible"] is True

    def test_unknown_defaults(self):
        caps = get_capabilities("unknown")
        assert caps["supports_guided"] is True
        assert caps["supports_force_if_possible"] is False

    def test_invalid_type_defaults_to_unknown(self):
        caps = get_capabilities("totally_invalid")
        assert caps == get_capabilities("unknown")


class TestLoadControlMode:
    def test_per_agent_override_takes_precedence(self):
        """Per-agent config has highest priority."""
        per_agent = {"claude-code": "guided", "openclaw": "force_if_possible"}
        mode = load_control_mode("claude-code", "tool_caller", per_agent, default_mode="observe")
        assert mode.mode == "guided"

    def test_default_when_no_per_agent_config(self):
        """Falls back to default_mode when no per-agent override."""
        mode = load_control_mode("unknown-agent", "tool_caller", per_agent_modes={}, default_mode="observe")
        assert mode.mode == "observe"

    def test_invalid_mode_defaults_to_default(self):
        """Invalid mode string falls back to default."""
        per_agent = {"my-agent": "not_a_real_mode"}
        mode = load_control_mode("my-agent", "tool_caller", per_agent, default_mode="guided")
        assert mode.mode == "guided"

    def test_force_if_possible_downgrades_for_tool_caller(self):
        """
        force_if_possible requires capability support.
        tool_caller does NOT support it → should downgrade to guided.
        """
        per_agent = {"some-agent": "force_if_possible"}
        mode = load_control_mode("some-agent", "tool_caller", per_agent, default_mode="observe")
        assert mode.mode == "guided"

    def test_force_if_possible_allowed_for_pre_llm_connector(self):
        """pre_llm_connector supports force_if_possible."""
        per_agent = {"my-agent": "force_if_possible"}
        mode = load_control_mode("my-agent", "pre_llm_connector", per_agent, default_mode="observe")
        assert mode.mode == "force_if_possible"

    def test_force_if_possible_allowed_for_wrapper(self):
        """wrapper supports force_if_possible."""
        per_agent = {"my-agent": "force_if_possible"}
        mode = load_control_mode("my-agent", "wrapper", per_agent, default_mode="observe")
        assert mode.mode == "force_if_possible"

    def test_off_mode_is_preserved(self):
        """off mode should be preserved regardless of capability."""
        per_agent = {"my-agent": "off"}
        mode = load_control_mode("my-agent", "tool_caller", per_agent, default_mode="guided")
        assert mode.mode == "off"

    def test_observe_mode_preserved(self):
        """observe mode is always allowed."""
        per_agent = {"my-agent": "observe"}
        mode = load_control_mode("my-agent", "unknown", per_agent, default_mode="guided")
        assert mode.mode == "observe"

    def test_guided_mode_preserved(self):
        """guided mode is always allowed."""
        per_agent = {"my-agent": "guided"}
        mode = load_control_mode("my-agent", "unknown", per_agent, default_mode="off")
        assert mode.mode == "guided"