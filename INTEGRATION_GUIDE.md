# OmniMemora Integration Guide

## Overview

OmniMemora provides two integration paths for AI agents:

1. **MCP Server** — Use OmniMemora tools directly in Claude Code via the MCP protocol
2. **REST API** — Call OmniMemora directly via HTTP from any agent or application

## Quick Start

### 1. Get an API Key

Sign up at https://doloclaw.com to receive your OmniMemora API key.

### 2. Choose Your Integration

#### Option A: MCP Server (Recommended for Claude Code)

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "omnimemora": {
      "command": "python",
      "args": ["/path/to/ov_enterprise_mcp_server.py"],
      "env": {
        "OMNIMEMORA_API_KEY": "omni-your-key-here",
        "OMNIMEMORA_ADAPTER_URL": "https://api.doloclaw.com"
      }
    }
  }
}
```

#### Option B: REST API (Recommended for Codex and OpenClaw)

```python
import httpx

resp = httpx.post(
    "https://api.doloclaw.com/memory/write",
    headers={
        "X-OmniMemora-Key": "omni-your-key-here",
        "X-OpenViking-Account": "your-tenant",
        "X-OpenViking-User": "your-user",
        "Content-Type": "application/json",
    },
    json={
        "agent": "codex",
        "type": "general",
        "content": "Remember that the user prefers short, actionable responses.",
    },
)
```

### 3. Verify Setup

```
curl https://api.doloclaw.com/health
```

You should receive a `200 OK` with `status: healthy`.

## Agent-Specific Guides

- [Claude Code + MCP](./examples/claude_code_mcp_example.md)
- [Codex + REST API](./examples/codex_api_example.md)
- [OpenClaw + REST API](./examples/openclaw_example.md)

## Core Concepts

### Memory Levels

| Level | Name | TTL | Use Case |
|-------|------|-----|----------|
| L1 | Short-term | 7 days | Working context, current task state |
| L2 | Experience | 30 days | Learned patterns, recurring insights |
| L3 | Core | Permanent | Key facts, user identity, important decisions |

### Token Savings

OmniMemora tracks token savings by injecting relevant memories from long-term storage instead of re-sending context. Use the `/memory/query` endpoint (V2) to get token savings reports:

```json
{
  "memory_tokens_injected": 842,
  "tokens_saved_estimate": 3158,
  "savings_ratio": 0.79
}
```

### Memory Types

| Type | Description |
|------|-------------|
| `general` | General facts and information |
| `decision` | Important decisions made |
| `preference` | User preferences and habits |
| `identity` | User identity and relationship facts |
| `project` | Project-specific knowledge |
| `failure` | Error experiences and failure patterns |

## Error Handling

All errors return a structured response with `error_code` and `support` metadata. See `COMPLIANCE.md` for the full error catalog.

## Rate Limits

| Plan | Requests/Minute |
|------|----------------|
| Starter | 100 |
| Pro | 500 |
| Enterprise | Custom |

## Support

- Docs: https://doloclaw.com/docs
- Support: support@doloclaw.com
