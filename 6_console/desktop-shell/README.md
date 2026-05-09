# OmniMemora Desktop Shell

Tauri-based desktop shell for `1.0.0-beta.11`.

This shell provides the local desktop control entry for service status, explicit service actions, local component updates, rollback, agent connection, and feedback.

## Current behavior

- Frontend renders the user-facing desktop control entry.
- Tauri command `get_desktop_status` checks local TCP reachability for:
  - runtime: `127.0.0.1:8765`
  - adapter: `127.0.0.1:18011`
  - UI: `127.0.0.1:5173`
- Start/stop/restart, manifest update, signed Tauri desktop updater, rollback, and agent connect/disconnect commands call the local desktop host.
- Feedback uses `support@doloclaw.com` with version and service state prefilled.
- macOS controlled beta builds use free ad-hoc app signing plus Tauri updater signing. They are not Apple Developer ID notarized, so first launch may require manual approval in System Settings.

## Validation

```bash
npm ci
npm run build
```

Tauri installer validation requires Rust/Cargo:

```bash
npm run tauri:build
```

On macOS arm64, `npm run tauri:build` produces:

```text
src-tauri/target/release/bundle/dmg/OmniMemora Desktop_1.0.0-beta.11_aarch64.dmg
src-tauri/target/release/bundle/macos/OmniMemora Desktop.app.tar.gz
src-tauri/target/release/bundle/macos/OmniMemora Desktop.app.tar.gz.sig
```
