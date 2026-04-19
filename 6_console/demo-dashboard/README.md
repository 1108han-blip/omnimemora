# OmniMemora 5173 Control Entry

This UI is the current user control entry. It consumes control and diagnostic state from `:18011`, but it does not redefine product truth by itself.

## Run

```bash
npm install
npm run dev
```

Default UI port is `5173`. API calls are proxied to `http://localhost:18011`.

To bind the UI to a candidate adapter instance, override the proxy target:

```bash
OMNIMEMORA_UI_API_TARGET=http://127.0.0.1:18025 npm run dev
```

Interpretation rule:

- `5173` is the current user control entry
- `18011` remains the only product data entry once product routing is enabled
- runtime `:8765` remains internal only and is not a user control truth source

## Current Control Contract

The `agents` page is the formal control surface for:

- `install / uninstall` = attach layer
- `enable / disable` = routing layer
- `system_status` = current gateway/capability state

The UI must not treat historical observation widgets as a substitute for these control semantics.

## Header Metrics Semantics

- `active(5m)`: count of agents from `/agents/control` where `active=true` and `last_seen_at` within 5 minutes
- `active(24h)`: count of agents from `/agents/control` where `active=true` and `last_seen_at` within 24 hours
- `history`: count of unique agents in `usage.by_agent` from `/usage/token-savings`

Activity truth is unified with the Agent control card surface via `AgentControlCard.active` field.

## Family Name Canonicalization

Internal agent identifiers are normalized to canonical family names for user display:

| Internal ID | Canonical Family |
|-------------|------------------|
| `openclaw`, `openclaw-agent`, `openclaw-bundle-mcp` | OpenClaw |
| `claude_code`, `claude-code` | Claude Code |
| `codex`, `codex_cli` | Codex |

## Internal Event Filtering

The Live Request Flow filters internal handshake events (`session bootstrap context handshake`) to show only user-facing requests.

## Header Status Light

- Green (`active`): `active(5m) > 0`
- Yellow (`idle`): `active(5m) == 0` and `active(24h) > 0`
- Gray (`no-active`): `active(24h) == 0`
- Red (`error`): any required API request failed during refresh

## Operator Debug Endpoint

Use `/debug/runtime_fingerprint` on port `18011` to verify runtime identity:

- process `pid`
- `hostname`
- `started_at`
- backend and events-path config
- current `live_counts` (5m/24h)

This helps confirm UI and agents are connected to the same adapter instance.

It is an operator/debug aid, not a replacement for the current product boundary documents.
