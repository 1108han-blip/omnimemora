# OmniMemora Desktop Beta Execution Baseline (2026-05-01)

## Scope

Execution line: `Desktop Beta Packaging + Three-Layer Update Foundation v1`.

Branch: `codex/desktop-update-foundation-v1`.

Target version: `1.0.0-beta.2`.

## Reality Split

Repository reality:

- Tauri desktop shell foundation exists under `6_console/desktop-shell`.
- macOS arm64 Tauri build has produced a DMG locally.
- Release manifest foundation exists in `4_core/local-runtime/scripts/release/build_release.sh`.
- Cloudflare Worker foundation includes tracked download paths and release manifest routes.

Running reality on the operator machine:

- `127.0.0.1:8765` may be healthy from an existing runtime process.
- `127.0.0.1:18011` may be healthy from an existing adapter process.
- `127.0.0.1:5173` may be healthy from an existing dev UI process.
- Those running processes are not proof that the desktop App can manage services until desktop-owned PID/state validation passes.

Candidate reality:

- The desktop shell currently has command contracts for service management and updates.
- Cloud policy remains candidate-only and must not auto-promote over local active policy.

## Boundaries

In scope:

- Desktop service management.
- Local component directory layout.
- Manifest-based local component update and rollback foundation.
- Desktop GUI status, update, and feedback surfaces.
- Local release validation for `1.0.0-beta.2`.

Out of scope for this execution line unless reopened explicitly:

- Railway changes.
- Silent telemetry.
- Ticket backend.
- Desktop shell self-update.
- Automatic cloud policy promotion.
- Cloud publish before local installer and service management pass.
