# OmniMemora Desktop Shell

Tauri-based desktop shell foundation for `1.0.0-beta.2`.

This batch defines the desktop GUI, service status model, update-layer model, and Tauri command contract. It does not yet implement real service mutation or build distributable installers.

## Current behavior

- Frontend renders the user-facing desktop control entry.
- Tauri command `get_desktop_status` checks local TCP reachability for:
  - runtime: `127.0.0.1:8765`
  - adapter: `127.0.0.1:18011`
  - UI: `127.0.0.1:5173`
- Start/stop/restart/update/rollback commands are contract placeholders and return a clear foundation-only message.
- Feedback uses `support@doloclaw.com` with version and service state prefilled.

## Validation

```bash
npm ci
npm run build
```

Tauri installer validation requires Rust/Cargo:

```bash
npm run tauri:build
```

If `cargo` is missing, Tauri build fails before compiling Rust. That is an environment prerequisite, not a desktop-shell source validation pass.
