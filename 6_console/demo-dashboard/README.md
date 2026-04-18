# OmniMemora Demo Dashboard

This dashboard is a demo/operator UI layer. It inspects gateway-backed state through `:18011`, but it is not the product truth source by itself.

## Run

```bash
npm install
npm run dev
```

Default UI port is `5173`. API calls are proxied to `http://localhost:18011`.

Interpretation rule:

- `5173` is the current user control entry
- `18011` remains the only product data entry once product routing is enabled
- this demo dashboard does not license direct product validation against runtime `:8765`

## Header Metrics Semantics

- `active(5m)`: count of agents returned by `/agents/live?window_minutes=5`
- `active(24h)`: count of agents returned by `/agents/live?window_minutes=1440`
- `history`: count of `usage.by_agent` from `/usage/token-savings`

These are intentionally different metrics:

- `active(*)` is windowed real-time activity.
- `history` is cumulative historical participation.

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
