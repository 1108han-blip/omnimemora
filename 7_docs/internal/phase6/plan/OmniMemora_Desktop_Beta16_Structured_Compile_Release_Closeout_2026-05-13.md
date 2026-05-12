# OmniMemora Desktop Beta16 Structured Compile Release Closeout

Date: 2026-05-13

## Scope

- Release version: `1.0.0-beta.16`.
- Product line: controlled beta local-first desktop product.
- Included product work:
  - structured, protocol-preserving compile path from the current compile mainline.
  - OpenClaw latency and streaming adapter fixes already promoted before release.
  - desktop version alignment across Tauri config, package metadata, release scripts, GUI fallback status, and local installed app.
  - desktop startup repair so installed `~/.omnimemora/app/current` components take precedence over legacy `~/.omnimemora/service/current` LaunchAgent paths.

## Repository Reality

- Version defaults updated to `1.0.0-beta.16` in:
  - `4_core/local-runtime/scripts/release/build_release.sh`
  - `4_core/local-runtime/scripts/release/publish_beta_release.py`
  - `6_console/desktop-shell/package.json`
  - `6_console/desktop-shell/src-tauri/tauri.conf.json`
  - `6_console/desktop-shell/src-tauri/Cargo.toml`
  - desktop GUI fallback status and README text.
- No new product service, daemon, or background workflow was added.
- File count increased by one documentation record only.
- Resident runtime logic stayed flat; existing LaunchAgent paths are aligned to the installed component path instead of introducing another startup layer.

## Build Evidence

- `npm --prefix 6_console/desktop-shell run build`: passed.
- `cargo test --manifest-path 6_console/desktop-shell/src-tauri/Cargo.toml`: passed, 1 test.
- `OMNIMEMORA_ALLOW_UNSIGNED_BETA_DESKTOP=1 npm --prefix 6_console/desktop-shell run tauri:build`: produced `.app`, `.dmg`, and updater archive; returned non-zero only because `TAURI_SIGNING_PRIVATE_KEY` is not present for signed updater archive generation.
- `OMNIMEMORA_ALLOW_UNSIGNED_BETA_DESKTOP=1 bash 4_core/local-runtime/scripts/release/build_release.sh 1.0.0-beta.16`: passed.
- `shasum -a 256 -c 4_core/local-runtime/release/1.0.0-beta.16/SHA256SUMS.txt`: passed for all release artifacts.
- `hdiutil imageinfo 4_core/local-runtime/release/1.0.0-beta.16/OmniMemora-Desktop-1.0.0-beta.16-darwin-arm64.dmg`: passed.

## Running Reality

- Local desktop app installed at `/Applications/OmniMemora Desktop.app`.
- Local desktop version: `1.0.0-beta.16`.
- Local component manifest: `~/.omnimemora/app/current/manifest.json` version `1.0.0-beta.16`.
- Runtime process path: `~/.omnimemora/app/current/bin/omnimemora serve`.
- Adapter process path: `~/.omnimemora/app/current/tools/_run_adapter.py`.
- `http://127.0.0.1:8765/health`: `status=ok`.
- `http://127.0.0.1:18011/health`: `status=healthy`.
- `http://127.0.0.1:18011/metrics/summary`: returned successfully.
- `http://127.0.0.1:18011/metrics/core_capabilities`: returned `metric_contract_version=real_input_v1`.

## Cloud Reality

- Published with `uvx --with boto3 --with requests python 4_core/local-runtime/scripts/release/publish_beta_release.py 1.0.0-beta.16`.
- Uploaded artifacts:
  - `OmniMemora-Desktop-1.0.0-beta.16-darwin-arm64.dmg`
  - `OmniMemora-Desktop-1.0.0-beta.16-darwin-aarch64.app.tar.gz`
  - `omnimemora-darwin-arm64.zip`
  - `omnimemora-darwin-amd64.zip`
  - `omnimemora-windows-amd64.zip`
  - `SHA256SUMS.txt`
  - `RELEASE_INDEX.txt`
  - `1.0.0-beta.16.json`
  - `latest.json`
- Deployed Worker: `omnimemora-control-entry`.
- `https://doloclaw.com/releases/latest.json`: version `1.0.0-beta.16`.
- `https://doloclaw.com/download/file/darwin-arm64`: redirects to the beta16 DMG path.
- Remote DMG SHA256 verified as `69c5ee15e3673ea7561fd0507fbd5787e84f37b4044cf1f14b8347f73b149fa6`, matching remote `SHA256SUMS.txt` and `latest.json`.

## Beta14 Supersession

`1.0.0-beta.14` and `1.0.0-beta.15` were built and briefly published during validation, then superseded by `1.0.0-beta.16`.

Reason: beta14 and beta15 R2 object paths were overwritten during final desktop startup repair validation. To avoid any `latest.json` SHA mismatch for users due to Cloudflare edge caching, the final release moved to the new immutable beta16 path instead of reusing earlier beta paths.

## Boundaries

- `5173` was not started as a current product dependency.
- Cloud policy remains candidate-only; no cloud policy auto-promotion was introduced.
- User-facing memory data was not deleted or migrated.
- The app remains unsigned controlled beta distribution; macOS Privacy & Security manual allowance may still be required.
