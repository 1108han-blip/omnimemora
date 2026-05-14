# Doctor Quality Layer Pilot

Status: Phase C observe-only pilot.

This pilot adds manual quality doctor checks for OmniMemora and DoloToken. It does not fix code, mutate services, install dependencies, deploy, upload release artifacts, or add CI failure gates.

## Commands

Run static OmniDoctor and TokenDoctor checks:

```bash
make doctor
```

Run the same checks as JSON:

```bash
make doctor-json
```

Run static checks plus ReactDoctor through `npx` for the React/Vite frontend packages:

```bash
make doctor-react
```

`doctor-react` is intentionally explicit because it may need network/package-manager access for `npx -y react-doctor@0.1.6`. The baseline `make doctor` command stays local and standard-library only.

The default ReactDoctor package is pinned by `tools/doctor_quality.py` as `react-doctor@0.1.6`. Override with `REACT_DOCTOR_PACKAGE=<package>` only when deliberately testing a newer release.

## Scope

OmniDoctor checks current product boundary invariants:

- `18011` remains product ingress after explicit opt-in.
- `5173` remains legacy/dev surface, not product ingress.
- `8765` remains internal memory plane.
- agent detection must not auto-attach or auto-enable routing.
- `/metrics/core_capabilities` remains the MVP real-input savings truth surface.

TokenDoctor checks DoloToken / Token Intelligence invariants:

- version constants stay aligned across package builder, proxy, MCP companion, and Worker.
- usage source and confidence labels remain explicit.
- local estimates are not presented as provider billing truth.
- default posture remains metadata-only and avoids raw prompt storage.
- release metadata stays on the product-owned DoloToken route.
- cloud publish plans remain explicit and non-mutating by default.

ReactDoctor checks are limited to:

- `6_console/desktop-shell`
- `6_console/demo-dashboard`

## Gate Policy

Current mode is observe-only:

- findings are for review
- no automatic fixes
- no CI blocking
- no production read-path change

Future CI gates should start as warnings. Blocking gates should be limited to high-confidence product-boundary, token-truth, or release-safety violations.

## Phase E Warning Workflow

`.github/workflows/doctor-quality.yml` runs the product-local doctor as a report-only GitHub Actions workflow.

Current workflow posture:

- runs on relevant pull requests, pushes to `master` or `main`, and manual dispatch
- produces `doctor-quality.json` as a workflow artifact
- produces `doctor-quality-react.json` as a separate ReactDoctor workflow artifact
- writes a compact summary to the GitHub Actions step summary
- runs `make doctor`, Python compilation, and the focused doctor unit test
- runs ReactDoctor in a separate report-only job pinned to `react-doctor@0.1.6`
- uses `continue-on-error` so findings remain visible without becoming a merge-blocking gate
- does not vendor ReactDoctor source code or add it to `package.json`

Promoting any finding to a hard CI failure requires a separate gate decision after the observe-only noise is understood.
