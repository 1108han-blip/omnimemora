# OmniMemora - Local Memory Plane for AI Agents

Version 1.0.0

## What is OmniMemora?

OmniMemora is a local memory plane that helps AI agents (Codex, Claude Code, etc.) save tokens by intelligently compressing context from previous conversations.

## Quick Start

1. Extract the archive
2. Run: `./omnimemora start` (or `omnimemora.exe start` on Windows)
3. Browser opens automatically to the dashboard
4. See your token savings immediately!

## Commands

```bash
omnimemora start       # Start the runtime
omnimemora status      # Show runtime status
omnimemora stop        # Stop the runtime
omnimemora dashboard   # Open dashboard in browser
omnimemora connect codex   # Show Codex integration guide
omnimemora connect claude  # Show Claude Code integration guide
omnimemora version     # Show version
```

## Connect to Your Agent

### Codex
```bash
omnimemora connect codex
```

### Claude Code
```bash
omnimemora connect claude
```

## How It Works

OmniMemora intercepts memory retrieval requests and applies intelligent context compression:

1. Your agent makes a memory query
2. OmniMemora finds relevant memories
3. Context is assembled using optimal strategy
4. Token count is reduced while preserving relevance
5. You save tokens on every query!

## System Requirements

- macOS 10.14+ or Windows 10+
- No external dependencies (fully self-contained)
- Default port: 8765 (automatically selects next available if occupied)

## Data Location

All data is stored locally in:
- macOS/Linux: `~/.omnimemora/`
- Windows: `%USERPROFILE%\.omnimemora\`

## Documentation

For full documentation, visit:
https://github.com/omnimemora/omnimemora

## Support

Report issues at:
https://github.com/omnimemora/omnimemora/issues
