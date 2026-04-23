# OmniMemora Controlled Beta Release v1 (2026-04-23)

## Decision

- Release mode: **closed beta / controlled beta**
- Source code: **private**
- Distribution path: `https://doloclaw.com/download`
- Artifact storage: `https://assets.doloclaw.com/omnimemora/beta/1.0.0-beta.1/`

## Package Contract

Each beta package must include:

- executable binary
- `README.txt`
- `LICENSE.txt`
- `BETA_TERMS.txt`
- `RELEASE_NOTES.txt`
- `KNOWN_ISSUES.txt`
- `VERSION.txt`

Package archives currently produced:

- `omnimemora-darwin-arm64.zip`
- `omnimemora-darwin-amd64.zip`
- `omnimemora-windows-amd64.zip`
- `SHA256SUMS.txt`

## Legal / Distribution Boundary

- Copyright retained by OmniMemora.
- `All rights reserved`.
- No source distribution.
- No redistribution.
- No commercial use.
- No reverse engineering except where non-waivable law requires otherwise.

## Download Surface

Current control-entry worker behavior:

- `/` returns control-entry status JSON
- `/download` returns human-facing beta download page
- page links point to R2-hosted artifacts under `assets.doloclaw.com`

## Feedback Loop

Initial beta feedback channel:

- support email: `support@doloclaw.com`

Required report fields:

- package version
- operating system
- `request_id`
- `error_code`
- reproduction steps
- request evidence excerpt or screenshot when available

## GitHub Strategy

- main product repository remains private
- repository is not the download surface
- no public source release is created for this beta
- future cleanup focuses on reducing history noise and space usage, not on opening source

## Validation Snapshot

- release build script updated for closed beta packaging
- R2 artifact upload completed for current beta package set
- `doloclaw.com/download` serves controlled beta HTML
- asset links and `SHA256SUMS.txt` are reachable
- support channel baseline is now aligned to `support@doloclaw.com`
- download page exposes a prefilled "Report an issue" action
- `5173` exposes a feedback action gated on real request evidence
