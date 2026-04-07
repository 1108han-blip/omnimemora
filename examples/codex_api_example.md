# Integration Guide — Codex API + OmniMemora

This guide shows how to use OmniMemora's REST API directly from Codex.

## Prerequisites

- OpenAI Codex API access
- OmniMemora API key

## Authentication

Include your API key in all requests:

```bash
curl -X POST https://api.doloclaw.com/memory/write \
  -H "X-OmniMemora-Key: omni-your-key-here" \
  -H "X-OpenViking-Account: your-tenant-id" \
  -H "X-OpenViking-User: your-user-id" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "codex",
    "type": "general",
    "content": "Remember that the user is building a React app with TypeScript."
  }'
```

## Python Example

```python
import httpx
import os

API_KEY = os.environ["OMNIMEMORA_API_KEY"]
BASE_URL = "https://api.doloclaw.com"
HEADERS = {
    "X-OmniMemora-Key": API_KEY,
    "X-OpenViking-Account": "your-tenant",
    "X-OpenViking-User": "your-user",
    "Content-Type": "application/json",
}

def write_memory(agent: str, memory_type: str, content: str):
    resp = httpx.post(
        f"{BASE_URL}/memory/write",
        headers=HEADERS,
        json={"agent": agent, "type": memory_type, "content": content},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()

def search_memories(query: str, limit: int = 5):
    resp = httpx.post(
        f"{BASE_URL}/memory/search",
        headers=HEADERS,
        json={"query": query, "limit": limit},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()

# Example: remember a decision
write_memory(
    agent="codex",
    memory_type="decision",
    content="User decided to use PostgreSQL instead of SQLite for the main database.",
)

# Example: search for relevant context
results = search_memories("What database is the user using?")
for mem in results["memories"]:
    print(f"- [{mem['category']}] {mem['abstract']}")
```

## Token Savings

Use the V2 query endpoint to get token savings estimates:

```python
def query_memories(tenant: str, user: str, agent: str, query: str):
    resp = httpx.post(
        f"{BASE_URL}/memory/query",
        headers=HEADERS,
        json={
            "tenant": tenant,
            "user": user,
            "agent": agent,
            "query": query,
            "options": {"max_local_cards": 4, "enable_packing": True},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()

result = query_memories("my-tenant", "my-user", "codex", "What was decided about the database?")
print(f"Tokens injected: {result['memory_tokens_injected']}")
print(f"Tokens saved: {result['tokens_saved_estimate']}")
print(f"Savings ratio: {result['savings_ratio']:.1%}")
```
