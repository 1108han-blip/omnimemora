# OmniMemora Controlled Beta

Package version: {{PACKAGE_VERSION}}

## What this package is

This is a closed beta build of OmniMemora.

- Local-first product
- 5173 = user control surface
- 18011 = product ingress
- 8765 = internal memory plane

This package is for controlled user testing only. It is not an open-source release and not a public production installer.

## Quick Start

1. Extract the archive.
2. Run `./omnimemora start` on macOS or `omnimemora.exe start` on Windows.
3. Open the dashboard if it does not open automatically.
4. Verify:
   - `http://127.0.0.1:5173`
   - `http://127.0.0.1:18011/health`
   - `http://127.0.0.1:8765/health`

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
- No commercial use is permitted.
- No redistribution is permitted.
- Automatic update is not included.

## Download base

{{DOWNLOAD_BASE_URL}}
