# OmniMemora Memory Plugin

OpenClaw memory plugin through OmniMemora Gateway (`:18011`).

## Architecture

```text
OpenClaw
  -> omnimemora-memory plugin
  -> OmniMemora Gateway (:18011)
  -> OmniMemora Runtime (:8765, internal)
```

## Features

- Auto-Recall before prompt build
- Auto-Capture after conversation completion
- Tools: `memory_recall`, `memory_store`, `memory_forget`
- Gateway-side filtering/routing/rate-limit governance

## Install

1. Place plugin in `extensions/omnimemora-memory/`
2. Restart OpenClaw gateway

## Configure

```bash
openclaw config set plugins.enabled true --json
openclaw config set plugins.slots.memory omnimemora-memory
openclaw config set plugins.entries.omnimemora-memory.config.baseUrl "http://127.0.0.1:18011"
openclaw config set plugins.entries.omnimemora-memory.config.agentId "supervisor"
openclaw config set plugins.entries.omnimemora-memory.config.autoCapture true
openclaw config set plugins.entries.omnimemora-memory.config.autoRecall true
```

## Gateway API Used

- `POST /memory/write`
- `POST /memory/search`
- `POST /memory/read`
- `POST /memory/delete`
- `POST /memory/snapshot`
- `GET /health`

## Verify

```bash
docker logs openclaw-openclaw-gateway-1 | grep omnimemora-memory
curl http://localhost:18011/health
```

## Troubleshooting

If health check fails, verify:

1. OmniMemora gateway process is running
2. `baseUrl` points to reachable `18011`
3. OpenClaw gateway restarted after config change
