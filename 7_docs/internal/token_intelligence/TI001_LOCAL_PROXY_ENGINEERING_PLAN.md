# TI-001 Local Proxy Engineering Plan

Date: 2026-05-13

## Purpose

TI-001 turns Token Intelligence Lite from a repo-only core into a usable local audit entrypoint.

The first engineering goal is not a general gateway. It is a proprietary local CLI/local-proxy download that lets a user point an OpenAI-compatible client at OmniMemora, forward the request to the user's configured upstream, and receive an audit receipt without storing raw prompt content by default.

## Current Baseline

Repo reality:

- Token Intelligence core exists under `5_connectors/adapter/application/token_intelligence/`.
- Core coverage includes usage normalization, source/confidence labels, metadata-only SQLite ledger, compact receipt generation, and raw-content avoidance tests.
- It is not wired into `llm_proxy.py`, `18011`, the desktop GUI, or cloud release packaging.

Running reality:

- Current product ingress remains `http://127.0.0.1:18011`.
- TI-001 local proxy is a candidate entrypoint until explicitly promoted.
- TI-001 must not be used as evidence that `18011` behavior changed.

## Product Shape

Initial user flow:

```text
AI client / relay user
        ↓
http://127.0.0.1:<token-audit-port>/v1/chat/completions
        ↓
OmniMemora Token Intelligence local proxy
        ↓
configured upstream_base_url
```

Default candidate port:

```text
127.0.0.1:18081
```

Reason:

- avoid contaminating current `18011` product ingress;
- allow side-by-side local validation;
- allow later promotion into desktop/`18011` only after pass-through and audit semantics are stable.

## Non-Goals

TI-001 must not:

- replace `18011`;
- modify `llm_proxy.py` in the first implementation batch;
- alter request payload semantics;
- rewrite model names;
- add cloud-hosted audit storage;
- require a browser extension;
- store raw prompt, full tool output, or full provider response by default;
- support Anthropic-native or streaming before non-streaming receipt semantics pass;
- become user profiling or hidden behavior telemetry.

## CLI Contract

Candidate binary name:

```text
omni-token-audit
```

Required commands:

```text
omni-token-audit init
omni-token-audit proxy start
omni-token-audit proxy stop
omni-token-audit proxy status
omni-token-audit receipt get <audit_id>
omni-token-audit receipt export <audit_id> --format json
omni-token-audit update check
omni-token-audit version
```

Optional later commands:

```text
omni-token-audit config set upstream.base_url <url>
omni-token-audit config set upstream.api_key_env <ENV_NAME>
omni-token-audit report today
```

The first implementation may expose the proxy as a Python module or existing adapter subcommand before building a standalone binary, but the command contract above is the product target.

## Local Files

Default paths:

```text
~/.omnimemora/token-intelligence/config.json
~/.omnimemora/adapter/token_intelligence/audit.sqlite3
~/.omnimemora/token-intelligence/logs/
```

Retention:

- logs: at most 7 days by default;
- audit events: configurable, default bounded retention before normal release;
- raw content: off by default and not part of TI-001.

The existing core ledger default path remains valid for TI-001. A later migration may move all Token Intelligence files under one directory, but the migration must be explicit and tested.

## Config Schema

Minimum config:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 18081
  },
  "upstream": {
    "base_url": "https://example-relay.invalid/v1",
    "api_key_env": "OMNI_AUDIT_UPSTREAM_API_KEY",
    "timeout_seconds": 120
  },
  "privacy": {
    "content_mode": "metadata_only",
    "store_raw_prompt": false,
    "store_raw_response": false
  },
  "audit": {
    "enabled": true,
    "fail_open": true
  },
  "updates": {
    "enabled": true,
    "metadata_url": "https://doloclaw.com/releases/token-intelligence/latest.json",
    "channel": "beta"
  }
}
```

Rules:

- store API key by environment-variable reference, not raw key, in the default config;
- invalid config must fail before opening the port;
- audit persistence failure must not block upstream forwarding when `fail_open=true`;
- `content_mode=full_content` is out of TI-001 scope.

## HTTP Routes

MVP routes:

```text
GET  /health
GET  /version
POST /v1/chat/completions
GET  /audit/events/<audit_id>
GET  /audit/events/<audit_id>/receipt
GET  /audit/summary
GET  /updates/check
```

Route semantics:

- `/v1/chat/completions` forwards to `<upstream.base_url>/chat/completions`.
- Non-streaming only in TI-001.
- Response body and status should match upstream unless the local proxy itself fails before upstream is called.
- Audit receipt creation happens after upstream response parsing and must not mutate the user-visible response.
- `/audit/*` must never return raw prompt or raw full response in default mode.

## Header And Payload Semantics

Forward:

- `Authorization` rebuilt from configured upstream key;
- content type;
- provider-compatible request body.

Do not forward by default:

- local proxy internal headers;
- OmniMemora internal routing headers;
- user secrets unrelated to upstream auth.

Do not alter:

- `messages`;
- `tools`;
- `tool_choice`;
- `model`;
- `temperature`;
- provider-specific payload fields.

If later model mapping is needed, it must be a separate explicit feature, not TI-001 pass-through behavior.

## Audit Semantics

For every completed upstream request, create one audit event with:

- `audit_id`;
- local request id;
- request hash;
- response hash;
- upstream base URL hash;
- provider/relay label;
- requested model;
- reported model if known;
- normalized usage;
- normalized or inferred cost when available;
- latency;
- status code;
- compact sanitized metadata.

Usage source order:

1. provider or relay reported `usage`;
2. post-fetch usage if available later;
3. local estimate;
4. rough estimate only when clearly labeled.

TI-001 may start with provider/relay usage plus local estimate fallback. Cost inference can be stored as empty until pricing table exists.

## Update Metadata Contract

Token Intelligence local proxy can use product-owned release metadata.

Candidate URL:

```text
https://doloclaw.com/releases/token-intelligence/latest.json
```

Minimum JSON:

```json
{
  "product": "omnimemora-token-intelligence",
  "channel": "beta",
  "version": "0.1.0-beta.1",
  "published_at": "2026-05-13T00:00:00Z",
  "platforms": {
    "darwin-arm64": {
      "download_url": "https://doloclaw.com/download/file/token-intelligence/darwin-arm64",
      "sha256": "",
      "unsigned_beta": true,
      "gatekeeper_note": "Manual Privacy & Security approval may be required during beta."
    }
  },
  "minimum_supported_version": "0.1.0-beta.1",
  "force_update": false,
  "update_notice": "",
  "security_notice": ""
}
```

Rules:

- online update check is allowed;
- update notices and minimum-version warnings are allowed;
- auto-download may be added later only with checksum verification;
- signed silent updater language is forbidden until signing/notarization exists;
- unsigned macOS beta must clearly mention Privacy & Security / Gatekeeper manual approval.

## Test Matrix

Repo tests:

- config load success and invalid config failure;
- fake upstream success with `usage`;
- fake upstream success without `usage`;
- fake upstream error status pass-through;
- fake upstream slow response within timeout;
- upstream timeout returns a local proxy error with no false audit success;
- audit DB write success;
- audit DB write failure with `fail_open=true` still returns upstream response;
- receipt does not include raw prompt or raw response;
- metadata sanitizer drops prompt/content/messages/tool-output-like keys;
- local estimate is labeled `local_estimated`;
- reported usage is labeled `provider_reported` or `relay_reported`;
- `/health` works without upstream call;
- `/updates/check` parses local fixture metadata.

Running validation:

- start local proxy on `127.0.0.1:18081`;
- call `/health`;
- send one fake or safe upstream `POST /v1/chat/completions`;
- verify response pass-through;
- fetch receipt;
- verify `18011/health` remains unchanged when current product is also running;
- verify no raw prompt in the default audit row.

## Implementation Batches

### TI-001-Prep - Plan Lock

Status: this document.

Exit:

- plan committed;
- worktree clean;
- no running behavior changed.

### TI-001A - Local Proxy Skeleton

Status: repo implementation completed on 2026-05-13; running promotion not started.

Scope:

- create the smallest local HTTP proxy surface;
- add `/health`, `/version`, and non-streaming `POST /v1/chat/completions`;
- use fake upstream tests.

Forbidden:

- no `llm_proxy.py` modification;
- no desktop GUI modification;
- no cloud deploy.

Exit:

- fake upstream response is returned unchanged;
- error status pass-through is tested;
- worktree stays under threshold.

### TI-001B - Config And Secret Reference

Status: repo implementation completed on 2026-05-13; CLI packaging and running promotion not started.

Scope:

- config file load;
- API key env reference;
- startup validation;
- CLI command skeleton if not already present.

Exit:

- no raw API key written to config by default;
- invalid config blocks port open.

### TI-001C - Audit Ledger Integration

Status: repo implementation completed on 2026-05-13; receipt API and running promotion not started.

Scope:

- call existing Token Intelligence core after upstream response;
- record metadata-only audit event suitable for later receipt retrieval;
- fail open when audit persistence fails.

Exit:

- raw prompt/response absence tested;
- audit failure does not block successful upstream response.
- successful audit returns `x-omni-token-audit-id`.

### TI-001D - Receipt And Summary API

Scope:

- add receipt read/export;
- add compact local summary endpoint;
- avoid historical hot-path scans.

Exit:

- receipt returns source/confidence labels;
- summary uses indexed ledger queries or bounded windows.

### TI-001E - Update Check

Scope:

- parse product-owned release metadata;
- report current/latest/minimum version;
- surface unsigned beta Gatekeeper note.

Exit:

- local fixture tests pass;
- no automatic install side effect.

### TI-001F - Packaging Candidate

Scope:

- package CLI/local proxy for local beta test;
- publish or stage checksum-verifiable artifact only after repo tests pass.

Exit:

- install/run instructions exist;
- update metadata fixture exists;
- Gatekeeper wording is visible.

## Promotion Rule

TI-001 must not be promoted into current `18011` running reality until:

- fake-upstream tests pass;
- local proxy pass-through running validation passes;
- audit persistence is proven fail-open;
- raw prompt absence is verified;
- the operator explicitly approves a running promotion or desktop integration batch.

## Stop Conditions

Stop implementation if:

- a change requires broad ingress rewrites;
- the audit path delays upstream response materially;
- raw prompt storage appears in default mode;
- file count or worktree threshold exceeds governance limits;
- implementation begins to add browser extension, cloud SaaS storage, or profiling features.

## First Code Entry Point Recommendation

Start with an isolated module and tests, not `llm_proxy.py`.

Candidate code layout:

```text
5_connectors/adapter/application/token_intelligence/
  config.py
  local_proxy.py
  update_check.py
  ...

5_connectors/adapter/tests/test_token_intelligence_local_proxy.py
5_connectors/adapter/tests/test_token_intelligence_update_check.py
```

This keeps single-file growth controlled and allows later reuse by desktop or `18011` integration without committing the current product ingress to TI-001 too early.
