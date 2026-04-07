# OmniMemora — Open Memory Adapter Interface

> **This repository contains the public integration surface, API/interface specs, and reference MCP server for OmniMemora.**
> It does **not** include private production adapter logic or proprietary memory orchestration internals.

---

## What is OmniMemora?

OmniMemora is a token-saving memory layer for AI agents. It provides:

- **Standardized memory tool interface** (write, search, read, delete, snapshot)
- **Token savings metering** — measure how many tokens your agent saves by using long-term memory vs. re-sending context
- **Multi-tenant access control** via API key authentication
- **Reference MCP server** for Claude Code, Codex, and OpenClaw integration

## Repository Structure

```
omnimemora-core/
├── README.md
├── LICENSE
├── TOOL_INTERFACE.md
├── INTEGRATION_GUIDE.md
├── COMPLIANCE.md
├── openapi.yaml
├── schemas/
│   ├── memory_write.request.json
│   ├── memory_write.response.json
│   ├── memory_search.request.json
│   ├── memory_search.response.json
│   └── health.response.json
├── examples/
│   ├── claude_code_mcp_example.md
│   ├── codex_api_example.md
│   └── openclaw_example.md
├── mcp/
│   └── ov_enterprise_mcp_server.py
└── mock/
    └── mock_adapter.py
```

## Quick Start

```bash
# 1. Install the reference MCP server
pip install -e .

# 2. Configure in Claude Code
# Add to your MCP settings (Claude Code → Settings → MCP):
# {
#   "mcpServers": {
#     "omnimemora": {
#       "command": "python",
#       "args": ["-m", "ov_enterprise_mcp_server"]
#     }
#   }
# }

# 3. Set your API key
export OMNIMEMORA_API_KEY="omni-your-key-here"
```

## Public API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/memory/write` | Store a memory |
| `POST` | `/memory/search` | Search memories |
| `POST` | `/memory/read` | Read memory by URI or query |
| `POST` | `/memory/delete` | Delete memory by URI |
| `POST` | `/memory/snapshot` | Generate MEMORY.md startup summary |
| `GET` | `/memory/types` | Memory type and level configuration |

See `openapi.yaml` for the full OpenAPI 3.1 specification.

## Authentication

All API requests require:

| Header | Description |
|--------|-------------|
| `X-OmniMemora-Key` | Your OmniMemora API key |
| `X-OpenViking-Account` | Tenant ID (required for multi-tenant access) |
| `X-OpenViking-User` | User ID (required for multi-tenant access) |

## What is NOT in This Repository

The following are **proprietary** and kept in the private `omnimemora-adapter-prod` repository:

- Normalizer, filter, router, and dedup algorithms
- Tenant registry and quota enforcement logic
- Token savings meter persistence layer
- Railway deployment configuration
- Cloudflare integration secrets

## License

See [LICENSE](./LICENSE). Core interface specs are MIT. Implementation details are proprietary.
