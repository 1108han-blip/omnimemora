# OmniMemora - Local Memory Plane for AI Agents
Version 1.0.0 (Phase 3.6)

## What is OmniMemora Runtime?

This binary is the Local Memory Plane backend (internal service).
Product-facing interfaces are unified at Python Adapter `:18011`.

## Quick Start (安装即生效)

1. Extract the archive
2. Double-click `omnimemora.exe` or run: `omnimemora start`
3. Done! Dashboard opens automatically
4. OmniMemora auto-detects your AI tools and connects them

## New in v1.0.0

- Auto-detect AI tools (Codex, Claude Code, Cursor, OpenClaw)
- Auto-attach on first run
- Memory verification ensures everything works
- Status card shows Runtime, Memory, and Savings status

## Commands

```bash
omnimemora start              # Start + auto-detect + auto-attach
omnimemora start --skip-attach   # Start without auto-attaching
omnimemora attach <agent>    # Attach agent (codex/claude/cursor/openclaw/all)
omnimemora detach <agent>    # Detach agent
omnimemora status            # Show status and savings
omnimemora stop              # Stop runtime
omnimemora dashboard         # Open dashboard
```

## Auto-Detection

OmniMemora automatically detects these AI tools:
- Codex (OpenAI)
- Claude Code (Anthropic)
- Cursor
- OpenClaw

When multiple agents are detected, a quick-select UI lets you choose which to connect.

## How It Works

1. Your agent makes a memory query
2. OmniMemora finds relevant memories
3. Context is compressed using intelligent strategy
4. Token count is reduced while preserving relevance
5. You save tokens on every query!

## System Requirements

- Windows 10+ or macOS 10.14+
- Fully self-contained (no dependencies)
- Default backend port: 8765 (auto-fallback to 8766/8767/8775 if occupied)

## Data Location

All data stored locally:
- Windows: `%USERPROFILE%\.omnimemora\`
- macOS/Linux: `~/.omnimemora/`

## Dashboard

The dashboard shows:
- Total tokens saved
- Today's / Week's / Month's savings
- Daily trend chart
- Connection status

Internal runtime dashboard: http://127.0.0.1:8765/dashboard
Product entry health: http://127.0.0.1:18011/health

## Support

Report issues: https://github.com/omnimemora/omnimemora/issues
