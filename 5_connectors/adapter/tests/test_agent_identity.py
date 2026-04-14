"""
Tests for agent_identity.py — ADR-0005 Canonical Agent ID
==============================================================
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_identity import (
    resolve_agent_identity,
    resolve_canonical_agent_id,
    _safe_str,
    _safe_optional_str,
    _safe_integration,
    AgentIdentity,
    AGENT_ID_MAPPING,
)


class MockRequest:
    def __init__(self, headers=None, query_params=None, state_body=None):
        self._headers = headers or {}
        self._query = query_params or {}
        self._state_body = state_body or {}
        # Expose _body_cache so resolve_agent_identity can find it
        self.state = self
        self.state._body_cache = self._state_body

    @property
    def headers(self):
        return self._headers

    @property
    def query_params(self):
        return MockQueryParams(self._query)

    def json(self):
        return self._state_body


class MockQueryParams:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


# =============================================================================
# AGENT ID MAPPING
# =============================================================================
class TestAgentIdMapping:
    def test_known_mapping_claude_code(self):
        assert resolve_canonical_agent_id("claude-code-cli") == "claude_code"
        assert resolve_canonical_agent_id("claude-code") == "claude_code"

    def test_known_mapping_openclaw(self):
        assert resolve_canonical_agent_id("openclaw-agent") == "openclaw"
        assert resolve_canonical_agent_id("openclaw") == "openclaw"

    def test_known_mapping_codex(self):
        assert resolve_canonical_agent_id("codex-cli") == "codex_cli"

    def test_unknown_raw_passthrough(self):
        """ADR-0005: unmapped raw values are still treated as canonical."""
        assert resolve_canonical_agent_id("my-custom-agent") == "my-custom-agent"

    def test_none_or_unknown_returns_unknown(self):
        assert resolve_canonical_agent_id(None) == "unknown"
        assert resolve_canonical_agent_id("unknown") == "unknown"
        assert resolve_canonical_agent_id("") == "unknown"


# =============================================================================
# SAFE STR HELPERS
# =============================================================================
class TestSafeStr:
    def test_normal_string(self):
        assert _safe_str("openclaw-agent") == "openclaw-agent"

    def test_empty_string(self):
        assert _safe_str("") == "unknown"

    def test_none(self):
        assert _safe_str(None) == "unknown"

    def test_whitespace(self):
        assert _safe_str("   ") == "unknown"


class TestSafeOptionalStr:
    def test_normal_string(self):
        assert _safe_optional_str("openclaw-agent") == "openclaw-agent"

    def test_empty_string(self):
        assert _safe_optional_str("") is None

    def test_none(self):
        assert _safe_optional_str(None) is None

    def test_whitespace(self):
        assert _safe_optional_str("   ") is None


class TestSafeIntegration:
    def test_valid_tool_caller(self):
        assert _safe_integration("tool_caller") == "tool_caller"

    def test_valid_pre_llm_connector(self):
        assert _safe_integration("pre_llm_connector") == "pre_llm_connector"

    def test_valid_wrapper(self):
        assert _safe_integration("wrapper") == "wrapper"

    def test_invalid_defaults_to_unknown(self):
        assert _safe_integration("invalid") == "unknown"
        assert _safe_integration(None) == "unknown"
        assert _safe_integration("") == "unknown"


# =============================================================================
# IDENTITY RESOLUTION
# =============================================================================
class TestResolveAgentIdentity:
    def test_header_priority(self):
        """Headers take highest priority."""
        req = MockRequest(
            headers={
                "x-agent-id": "claude-code-cli",
                "x-session-id": "session-from-header",
                "x-workspace-id": "ws-from-header",
                "x-user-id": "user-from-header",
                "x-integration-type": "tool_caller",
            },
            query_params={"agent_id": "agent-from-query"},
        )
        identity = resolve_agent_identity(req)
        # canonical maps raw "claude-code-cli" → "claude_code"
        assert identity.canonical_agent_id == "claude_code"
        assert identity.raw_agent_id == "claude-code-cli"
        assert identity.session_id == "session-from-header"
        assert identity.workspace_id == "ws-from-header"
        assert identity.user_id == "user-from-header"
        assert identity.source == "header"
        assert identity.integration_type == "tool_caller"

    def test_query_fallback_when_header_unknown(self):
        """Query params used when header value is missing."""
        req = MockRequest(
            headers={"x-agent-id": ""},
            query_params={"agent_id": "openclaw-agent", "session_id": "session-from-query"},
        )
        identity = resolve_agent_identity(req)
        assert identity.canonical_agent_id == "openclaw"
        assert identity.raw_agent_id == "openclaw-agent"
        assert identity.session_id == "session-from-query"
        assert identity.source == "query"

    def test_body_fallback(self):
        """Body used when header+query give nothing."""
        req = MockRequest(
            headers={},
            query_params={},
            state_body={"agent_id": "codex-cli", "session_id": "sess-body"},
        )
        identity = resolve_agent_identity(req)
        assert identity.canonical_agent_id == "codex_cli"
        assert identity.raw_agent_id == "codex-cli"
        assert identity.session_id == "sess-body"
        assert identity.source == "body"

    def test_body_agent_fallback_when_agent_id_missing(self):
        """Body `agent` should also map to canonical agent id."""
        req = MockRequest(
            headers={},
            query_params={},
            state_body={"agent": "claude-code", "session_id": "sess-body-agent"},
        )
        identity = resolve_agent_identity(req)
        assert identity.raw_agent_id == "claude-code"
        assert identity.canonical_agent_id == "claude_code"
        assert identity.session_id == "sess-body-agent"
        assert identity.source == "body"

    def test_body_session_fallback_conversation_and_thread(self):
        """conversation_id / thread_id should be accepted as session fallback."""
        req_conv = MockRequest(
            headers={},
            query_params={},
            state_body={"agent": "codex", "conversation_id": "conv-123"},
        )
        identity_conv = resolve_agent_identity(req_conv)
        assert identity_conv.session_id == "conv-123"

        req_thread = MockRequest(
            headers={},
            query_params={},
            state_body={"agent": "codex", "thread_id": "thread-456"},
        )
        identity_thread = resolve_agent_identity(req_thread)
        assert identity_thread.session_id == "thread-456"

    def test_missing_fields_default_to_none_not_unknown(self):
        """ADR-0005: missing optional fields return None, not 'unknown' strings."""
        req = MockRequest(headers={}, query_params={})
        identity = resolve_agent_identity(req)
        assert identity.canonical_agent_id == "unknown"
        assert identity.raw_agent_id is None
        assert identity.agent_family is None
        assert identity.session_id is None
        assert identity.workspace_id is None
        assert identity.user_id is None
        assert identity.source in ("header", "query")

    def test_integration_type_normalization(self):
        """Invalid integration types become 'unknown'."""
        req = MockRequest(
            headers={"x-integration-type": "totally_invalid_type"}
        )
        identity = resolve_agent_identity(req)
        assert identity.integration_type == "unknown"

    def test_agent_family_preserved(self):
        """agent_family is preserved if provided."""
        req = MockRequest(
            headers={"x-agent-family": "claude-code", "x-agent-id": "claude-code-cli"}
        )
        identity = resolve_agent_identity(req)
        assert identity.agent_family == "claude-code"
        assert identity.canonical_agent_id == "claude_code"

    def test_raw_agent_id_captured(self):
        """ADR-0005: raw_agent_id is always preserved separately from canonical."""
        req = MockRequest(
            headers={"x-agent-id": "claude-code-cli"}
        )
        identity = resolve_agent_identity(req)
        assert identity.raw_agent_id == "claude-code-cli"
        assert identity.canonical_agent_id == "claude_code"  # mapped

    def test_unmapped_raw_becomes_canonical(self):
        """Raw values not in mapping table are still treated as canonical."""
        req = MockRequest(
            headers={"x-agent-id": "my-custom-agent-v2"}
        )
        identity = resolve_agent_identity(req)
        assert identity.raw_agent_id == "my-custom-agent-v2"
        assert identity.canonical_agent_id == "my-custom-agent-v2"


# =============================================================================
# AGENT IDENTITY MODEL DEFAULTS
# =============================================================================
class TestAgentIdentityModel:
    def test_defaults(self):
        """Minimal identity has correct defaults."""
        identity = AgentIdentity()
        assert identity.canonical_agent_id == "unknown"
        assert identity.raw_agent_id is None
        assert identity.agent_family is None
        assert identity.integration_type == "unknown"
        assert identity.session_id is None
        assert identity.workspace_id is None
        assert identity.user_id is None
        assert identity.source == "default"

    def test_full_construction(self):
        """Full AgentIdentity construction works."""
        identity = AgentIdentity(
            canonical_agent_id="claude_code",
            raw_agent_id="claude-code-cli-session-7",
            agent_family="claude_code",
            integration_type="tool_caller",
            session_id="sess_123",
            workspace_id="ws_abc",
            user_id="user_x",
            source="header",
        )
        assert identity.canonical_agent_id == "claude_code"
        assert identity.raw_agent_id == "claude-code-cli-session-7"
        assert identity.session_id == "sess_123"
