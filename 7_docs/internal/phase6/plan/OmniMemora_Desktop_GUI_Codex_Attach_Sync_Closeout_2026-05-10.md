# OmniMemora Desktop GUI + Codex Managed Attach Sync Closeout (2026-05-10)

## Status

Closed for current documentation sync.

This record aligns the current product docs with the 2026-05-10 implementation and running-reality work:

- Desktop GUI is the current user control/display surface.
- `5173` is legacy/browser dev-only and is not required by the desktop GUI.
- Desktop service controls manage local OmniMemora services only: `8765` runtime and `18011` adapter.
- Codex attach uses an OmniMemora-managed profile/launcher path and must not rewrite the official `~/.codex/config.toml`.

## Current Product Boundary

| Surface | Current role |
|---------|--------------|
| OmniMemora Desktop app | User control/display surface |
| `18011` | Product ingress after explicit user opt-in |
| `8765` | Internal memory plane/runtime |
| `5173` | Legacy/browser dev surface only |

## Codex Attach Contract

- `接入 OmniMemora` for Codex prepares a managed profile/launcher under OmniMemora-controlled app assets.
- The official Codex config at `~/.codex/config.toml` is not rewritten by the current default attach path.
- Legacy Codex provider rewrites remain cleanup/restoration-only compatibility behavior.
- Route disable must not delete the managed attach assets required for later repair/relaunch.

## Desktop GUI Contract

- `启动服务`, `重启服务`, and `停止服务` do not start or require `5173`.
- Settings/service status should show only current local services: runtime `8765` and adapter `18011`.
- If live-flow refresh fails or times out, the GUI must show the failure instead of silently rendering empty data.
- Live flow groups recent requests by real agent instance, keeps up to 10 rows per instance, and keeps instance sections collapsible.
- Decision tags must preserve the current product labels: `精炼` and `记忆`; generic fallback labels such as `回退` are not current product copy.
- Savings UI uses the real-input savings concept and displays cost with two decimal places.

## Running Evidence Captured

- `8765/health` returned healthy runtime status.
- `18011/health` returned healthy adapter status and confirmed `18011` as external agent entry with `8765` internal-only.
- `lsof -nP -iTCP:5173 -sTCP:LISTEN` returned no listener after the legacy dashboard LaunchAgent was disabled.
- `/metrics/core_capabilities` returned `metric_contract_version=real_input_v1`, `observed_request_count=34`, and `saved_tokens=947744`.
- `/metrics/summary` returned quickly with `degraded=true` / `summary_unavailable_no_historical_scan`, which is expected for the shrink-first no-historical-scan path and must not be used as a claim of full historical summary availability.

## Promotion / Install Evidence

- Adapter promotion was run for the savings/live-flow backend path before the final desktop-only cleanup.
- The packaged desktop app was rebuilt and installed to `/Applications/OmniMemora Desktop.app`.
- The installed desktop app hash recorded during validation was `0dbb26bb5fd3c6bce9b03b338adc7ab73ab68452fe40a29033424015cc29fad6`.
- GUI validation showed service count `2/2`, no `5173` service card, and live data rendering from `18011`.

## Not Claimed

- This record does not claim the legacy `6_console/demo-dashboard` source is deleted.
- This record does not rewrite old historical phase evidence that mentioned `5173` as the then-current browser dashboard.
- This record does not claim app-level automatic update management is production-complete.
- This record does not claim cloud policy candidates replaced local active policy.

## Shrink-First Check

- File count: documentation file count increased by one for this closeout record.
- Resident background logic: decreased or stayed lower in running reality because legacy `5173` launchd service is disabled and desktop service controls no longer manage the legacy dashboard.
- Runtime validation scope: `/health` for `8765` and `18011` returned successfully; `/metrics/core_capabilities` returned current real-input savings data; `/metrics/summary` returned quickly in degraded no-historical-scan mode.
- Log retention: no change; this documentation sync does not alter retention behavior.
