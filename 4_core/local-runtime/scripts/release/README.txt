# OmniMemora Controlled Beta

Package version: {{PACKAGE_VERSION}}

## What this package is

This is a closed beta build of OmniMemora.

- Local-first product
- 5173 = user control surface
- 18011 = product ingress
- 8765 = internal memory plane

This package is for controlled user testing only. It is not an open-source release and not a public production release.

## Quick Start

1. Download the installer for your platform from the OmniMemora download page.
2. On macOS controlled beta builds, approve first launch in System Settings if Gatekeeper blocks the app.
3. Open OmniMemora from the desktop app.
4. Use the app status screen for startup, repair, updates, and feedback.

## Update policy

All OmniMemora products downloaded to a user's local machine must include app-level automatic update management before they are released as a normal downloadable app.

Required update behavior:

- detect a newer product version.
- notify the user inside the app.
- download the update through the official release manifest.
- verify checksums/signatures before install.
- install signed desktop app updates through the app updater with clear user consent.
- recover or roll back if the update fails.
- keep local user memory and product data intact.

## Main commands

```bash
omnimemora start
omnimemora status
omnimemora stop
omnimemora dashboard
omnimemora connect-codex
omnimemora connect-claude
```

## Feedback

When reporting problems, include:

- package version
- operating system
- request_id
- error_code
- steps to reproduce
- request evidence excerpt or screenshot when available

Support contact: {{SUPPORT_EMAIL}}

## Known limits

- This is a controlled beta package.
- macOS builds are ad-hoc signed and updater-signed, but not Apple Developer ID notarized.
- No commercial use is permitted.
- No redistribution is permitted.
- Desktop-shell replacement must use the signed app updater for normal downloadable app releases.
- Local component updates are manifest-based and require user confirmation.
- Cloud policy candidates require explicit user confirmation before activation.

## Download base

{{DOWNLOAD_BASE_URL}}

## Release manifest

https://doloclaw.com/releases/latest.json
