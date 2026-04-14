# OmniMemora Memory Adapter (ARCHIVED - Legacy)

> **⚠️ ARCHIVED**: This is the legacy Python-based Adapter (port 8000) developed before the Go Runtime architecture.
> It has been superseded by the OmniMemora Go Runtime (port 8765).
> The current product uses native binary deployment, not Docker.
>
> **Current product**: See `../local-runtime/README.txt`

## Original README (preserved for reference)

Cloud-hosted FastAPI service that provides the OmniMemora memory-as-a-service API:
- `/memory/write` — store agent memories with normalization, deduplication, and routing
- `/memory/query` — V2 unified query with Token Savings Meter
- `/internal/trial-query` — internal endpoint for Cloudflare Pages proxy (protected)
- `/usage/token-savings` — aggregated token savings per tenant
- `/health` — health check

## Quick Start

### Local Development

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your values

# 4. Run
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker build -t omnimemora-adapter .
docker run -p 8000:8000 --env-file .env omnimemora-adapter
```

### Railway Deployment

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and init
railway login
railway init

# Set environment variables in Railway dashboard, then:
railway up --detach
railway domain  # shows public URL
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VIKING_URL` | Yes | `http://host.docker.internal:1933` | OpenViking server URL |
| `VIKING_API_KEY` | Yes | — | OpenViking API key |
| `OMNIMEMORA_INTERNAL_API_TOKEN` | Yes | — | Shared token for Cloudflare → adapter internal calls |
| `OMNIMEMORA_ADMIN_API_TOKEN` | Yes | — | Admin token for management endpoints |
| `OMNIMEMORA_REGISTRY_SYNC_ENABLED` | No | `false` | Sync tenants from Cloudflare D1 |
| `OMNIMEMORA_REGISTRY_SYNC_URL` | No | — | Cloudflare tenant sync endpoint |
| `OMNIMEMORA_REGISTRY_SYNC_TOKEN` | No | — | Cloudflare sync token |
| `OMNIMEMORA_TRIAL_DAYS` | No | `14` | Default trial duration |
| `OMNIMEMORA_TRIAL_QUOTA_TOKENS` | No | `500000` | Default trial token quota |

See `.env.example` for the full list.

## API Overview

```
POST /memory/write     — Store a memory (agent, type, content)
POST /memory/search    — Search memories (query, agent, limit)
POST /memory/query     — V2 unified query with token savings meter
GET  /usage/token-savings?tenant={id}  — Token savings stats
GET  /health           — Service health check
POST /internal/trial-query  — Internal: Cloudflare trial query proxy
```

## Architecture

```
Client (Claude Code / Codex / OpenClaw)
  └─→ Cloudflare Pages (doloclaw.com/api/*)
        ├─ D1: validate API key
        └─ → /internal/trial-query → OmniMemora Adapter
                                          └─→ OpenViking (viking://)
```

## License

Apache 2.0
