# OmniMemora Local Runtime

The Go runtime is the internal memory plane behind the gateway. It is not a second product entry.

## Role

| Surface | Role | Status |
|--------|------|--------|
| `:8765` | Runtime HTTP API | Internal only |
| `:18011` | Gateway | External product entry |

Use the runtime for storage, retrieval, and runtime-local health only. External agents should integrate through the gateway at `:18011`.

## Current Boundary

- owns local memory persistence
- serves runtime health and storage/search/query/delete operations
- does not define product entry behavior
- does not own KPI truth
- does not decide bypass policy
- does not decide agent routing policy
- does not auto-attach detected agents by default

Canonical references:

- [CANONICAL_FACTS.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/CANONICAL_FACTS.md)
- [9_adr/ADR-0003-interface-access-paths.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0003-interface-access-paths.md)
- [README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/README.md)

## Exposed Runtime HTTP Contract

| Method | Path | Notes |
|------|------|-------|
| `GET` | `/health` | Runtime health |
| `GET` | `/metrics` | Runtime-local metrics |
| `GET` | `/agents/control` | Internal agent install state for UI control |
| `POST` | `/agents/control/install` | Internal low-frequency attach/install action |
| `POST` | `/agents/control/uninstall` | Internal low-frequency detach/uninstall with backup restore |
| `POST` | `/agents/control/rescan` | Recompute detectable parent-level agents for UI |
| `POST` | `/memory/write` | Write memory |
| `POST` | `/memory/query` | Query memory |
| `POST` | `/memory/search` | Search memory |
| `POST` | `/memory/delete` | Delete memory |
| `POST` | `/connector/register` | Internal connector registration |
| `GET` | `/connector/list` | Internal connector listing |

Not part of the current runtime HTTP contract:

- `/memory/read`
- direct external-agent product access
- KPI/dashboard source of truth
- high-frequency routing decisions

## Runtime-to-Gateway Relationship

```text
Gateway (:18011)
  -> adapter bridge
  -> runtime (:8765)
  -> local store
```

The adapter bridge contract is versioned by tests. If request or response shapes change, contract tests must be updated first.

## Key Source Areas

| Path | Responsibility |
|------|----------------|
| `api/` | HTTP routes and middleware |
| `app/` | Core runtime service layer |
| `scope/` | Scope enforcement |
| `store/` | Store abstraction and SQLite implementation |
| `metering/` | Runtime-local metering |
| `tests/` | Runtime contract and behavior tests |

## Start

```bash
cd 4_core/local-runtime
go mod download
go build -o omnimemora-runtime .
./omnimemora-runtime
```

Default runtime state lives under `~/.omnimemora/runtime/` unless overridden by config.

## Verify

```bash
go test ./tests/... -v
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/metrics
```

## Non-Goals

- not a public gateway
- not a direct agent SDK
- not the KPI truth surface
- not the place to reintroduce bypass or product-entry decisions
- not the place to restore auto-attach as a default startup behavior

## Agent Control Notes

- Runtime attach/detach is the low-frequency install layer only.
- Attach must create a backup before changing an agent config.
- Uninstall/detach must restore the backup, not merely delete OmniMemora fragments.
- Runtime control is parent-card oriented; temporary subagents remain runtime-visible for metrics but are not independent control objects.
