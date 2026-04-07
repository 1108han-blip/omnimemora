# Integration Guide — Claude Code + OmniMemora MCP

This guide shows how to connect OmniMemora to Claude Code via the reference MCP server.

## Prerequisites

- Claude Code installed
- OmniMemora API key (from your OmniMemora dashboard)
- Python 3.11+

## Setup

### 1. Add MCP Server to Claude Code

Run the following command in Claude Code:

```
/claude mcp add omnimemora python /FULL/PATH/TO/ov_enterprise_mcp_server.py
```

Or add it manually to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "omnimemora": {
      "command": "python",
      "args": ["-m", "omnimemora.mcp_server"],
      "env": {
        "OMNIMEMORA_API_KEY": "omni-your-key-here",
        "OMNIMEMORA_ADAPTER_URL": "https://api.doloclaw.com"
      }
    }
  }
}
```

### 2. Set Environment Variables

```bash
export OMNIMEMORA_API_KEY="omni-your-key-here"
export OMNIMEMORA_ADAPTER_URL="https://api.doloclaw.com"
```

### 3. Verify Connection

```
/claude mcp list
# You should see "omnimemora" listed as an active MCP server
```

## Using OmniMemora Tools in Claude Code

After setup, you can use these tools in any Claude Code session:

```
Use memory_write to remember that the user prefers concise responses.
Use memory_search to find what project we were working on last week.
Use memory_snapshot to get an overview of the user's context before starting.
```

## Troubleshooting

**MCP server not starting:**
- Verify Python path: `python --version` should be 3.11+
- Check that `OMNIMEMORA_API_KEY` is set correctly
- Try running the MCP server directly: `python ov_enterprise_mcp_server.py`

**"Connection refused" errors:**
- Verify `api.doloclaw.com` is accessible: `curl https://api.doloclaw.com/health`
- Check your API key is valid in the OmniMemora dashboard
