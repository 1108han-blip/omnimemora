# OmniMemora Runtime
Version 1.0.0

## What this binary is

This binary is the local runtime behind OmniMemora.

- Product-facing data entry: `http://127.0.0.1:18011`
- User control entry: `:5173` / future GUI
- Runtime port: `:8765` by default

`8765` is an internal memory plane. It is not a second product entry.

## What this binary does

- stores local memory
- serves runtime-local health and internal HTTP contract
- executes low-frequency install / uninstall actions for agent configs
- supports gateway compile / search / query through internal calls

## Runtime surface families (:8765)

- memory plane: /memory/*
- control/integration carrier: /agents/control/* and /gateway/decision/*
- runtime/operator/internal: /health, /metrics, /dashboard, /internal/metrics, /mcp*, /sse

All of these are internal runtime surfaces. Product-facing data entry remains :18011.

## What this binary does not do

- does not replace the gateway at `:18011`
- does not define product routing policy
- does not define KPI truth
- does not auto-enable routing
- does not make product-entry decisions for users

## Commands

```bash
omnimemora start            # Start runtime and expose detected agents to the UI
omnimemora start --attach   # Explicitly attach detected agents
omnimemora attach <agent>   # Attach one agent
omnimemora detach <agent>   # Detach one agent
omnimemora status           # Show runtime-local status
omnimemora stop             # Stop runtime
omnimemora dashboard        # Open runtime dashboard (operator/internal view)
```

## Operator Notes

- The runtime dashboard is an internal/operator surface.
- Product-facing validation should bind to the gateway at `:18011`.
- Runtime health checks and contract checks may use `:8765` for internal verification only.

## Ports

- Runtime default port: `8765`
- Runtime may fall back to `8766 / 8767 / 8775` if occupied
- Gateway product port: `18011`

## Data Location

All data is stored locally:

- Windows: `%USERPROFILE%\\.omnimemora\\`
- macOS/Linux: `~/.omnimemora/`

## Internal Checks

- Runtime health: `http://127.0.0.1:8765/health`
- Product entry health: `http://127.0.0.1:18011/health`

Use the runtime health endpoint only for internal/operator checks.
