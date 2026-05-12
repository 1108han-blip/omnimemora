# OmniMemora Desktop Beta17 Structured Compile v2 Release Closeout

Date: 2026-05-13

## Scope

- Release version: `1.0.0-beta.17`.
- Product line: controlled beta local-first desktop product.
- Included product work:
  - SC-015 through SC-019 structured compile v2 running value gate and promotion closeout.
  - OpenClaw Anthropic-compatible structured tool-result compression validation after local product install.
  - desktop version alignment across Tauri config, package metadata, release scripts, GUI fallback status, local installed app, and cloud download surfaces.

## Repository Reality

- Version defaults updated to `1.0.0-beta.17` in release scripts and desktop shell metadata.
- Release version commit: `d64be85`.
- Structured compile closeout commits before release:
  - `629b6bf` - golden fixture corpus, typed compressor v2, per-label offline evaluation.
  - `dcfe773` - SC-019 promotion gate closeout record.
- No external compression library, model download, model inference, or network compressor was added.
- No new product daemon, scheduler, watcher, or background compression worker was added.

## Build Evidence

- `npm --prefix 6_console/desktop-shell run build`: passed.
- `npm --prefix 6_console/demo-dashboard run build`: passed.
- `cargo test --manifest-path 6_console/desktop-shell/src-tauri/Cargo.toml`: passed, 1 test.
- Structured compile adapter regression: `22 passed`.
- `OMNIMEMORA_ALLOW_UNSIGNED_BETA_DESKTOP=1 npm --prefix 6_console/desktop-shell run tauri:build`: produced beta17 `.app`, DMG, and updater tarball; returned non-zero only because `TAURI_SIGNING_PRIVATE_KEY` is not present for signed updater manifest generation.
- `OMNIMEMORA_ALLOW_UNSIGNED_BETA_DESKTOP=1 bash 4_core/local-runtime/scripts/release/build_release.sh 1.0.0-beta.17`: passed.
- `shasum -a 256 -c 4_core/local-runtime/release/1.0.0-beta.17/SHA256SUMS.txt`: passed for all release artifacts.
- `hdiutil imageinfo 4_core/local-runtime/release/1.0.0-beta.17/OmniMemora-Desktop-1.0.0-beta.17-darwin-arm64.dmg`: passed.

## Running Reality

- Local desktop app installed at `/Applications/OmniMemora Desktop.app`.
- Local desktop version: `1.0.0-beta.17`.
- Local component manifest: `~/.omnimemora/app/current/manifest.json` version `1.0.0-beta.17`.
- Runtime path remains `~/.omnimemora/app/current/bin/omnimemora serve`.
- Adapter path remains `~/.omnimemora/app/current/tools/_run_adapter.py`.
- `http://127.0.0.1:8765/health`: HTTP 200, `status=ok`.
- `http://127.0.0.1:18011/health`: HTTP 200, `status=healthy`.
- `http://127.0.0.1:18011/metrics/core_capabilities?tenant=all`: HTTP 200, `metric_contract_version=real_input_v1`.
- `http://127.0.0.1:18011/metrics/summary?tenant=all`: HTTP 200, degraded by design with `summary_unavailable_no_historical_scan`.
- Spotlight app discovery was cleaned back to one bundle id result: `/Applications/OmniMemora Desktop.app`.

## Structured Compile Running Validation

- Direct OpenClaw product request after beta17 local install:
  - path: `/llm/v1/messages`
  - agent: `openclaw`
  - trace: `beta17-release-verify`
  - request_id: `f02b48ef70e5`
  - upstream response id: `0652d6895b7a97e5736e11c74f4fb036`
  - upstream status: `200`
  - compile_status: `structured_compile_success`
  - compile_path: `structured_context_compile`
  - compile_reason: `deterministic_extract_search_result`
  - original_token_estimate: `2186`
  - compiled_token_estimate: `592`
  - compression_ratio: `0.7291857273559013`
  - selected_memory_count: `0`
- `/compile/status?window_minutes=10` after validation:
  - `openclaw.proxied_requests`: `4`
  - `openclaw.structured_compile_success`: `4`
  - `openclaw.structured_compile.success_share`: `1.0`
  - `openclaw.compile_token_savings.saved_token_estimate`: `6682`
  - `openclaw.compile_token_savings.savings_ratio`: `0.738`

## Cloud Reality

- First publish attempt uploaded R2 artifacts but failed during Worker deploy with transient Cloudflare API SSL EOF.
- Second publish attempt succeeded:
  - command: `uvx --with boto3 --with requests python 4_core/local-runtime/scripts/release/publish_beta_release.py 1.0.0-beta.17`
  - uploaded beta17 DMG, updater tarball, component zips, `SHA256SUMS.txt`, `RELEASE_INDEX.txt`, `1.0.0-beta.17.json`, and `latest.json`.
  - deployed Worker: `omnimemora-control-entry`.
- `https://doloclaw.com/releases/latest.json`: version `1.0.0-beta.17`.
- `https://doloclaw.com/releases/1.0.0-beta.17.json`: version `1.0.0-beta.17`.
- `https://doloclaw.com/download`: displays `1.0.0-beta.17`.
- `https://doloclaw.com/download/file/darwin-arm64`: redirects to the beta17 DMG path.
- Remote DMG SHA256 verified as `d640851d847de699bb1bfbd9734a3c071d69a953c8c459a0f47ad4428eb3ef5f`, matching local release artifact, remote `latest.json`, and remote `SHA256SUMS.txt`.

## Boundaries

- `5173` was not started as a current product dependency.
- Cloud policy remains candidate-only; no cloud policy auto-promotion was introduced.
- User-facing memory data was not deleted or migrated.
- The app remains unsigned controlled beta distribution. The current updater surface is beta one-click download, SHA verify, and open DMG fallback; the signed Tauri updater manifest is not published without `TAURI_SIGNING_PRIVATE_KEY`.
