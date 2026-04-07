# OmniMemora Tool Interface Specification

**Version:** 1.0
**Status:** Public

This document describes the public tool interface exposed by OmniMemora for AI agents.

---

## Tool Definitions

### `memory_write`

Store a new memory item in the agent's long-term memory.

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| `agent` | string | Yes | Agent identifier (e.g. `"claude"`, `"codex"`) |
| `type` | string | Yes | Memory category (e.g. `"general"`, `"decision"`, `"preference"`) |
| `content` | string | Yes | The memory content to store |
| `tags` | string[] | No | Optional tags |
| `memory_type` | string | No | Explicit memory type override |
| `timestamp` | integer | No | Unix timestamp (seconds); defaults to now |

**Response:**

```json
{
  "status": "stored",
  "memory_id": "viking://resources/...",
  "memory_type": "long_term",
  "memory_level": 2,
  "score": 85,
  "memory_expire_at": 1750000000
}
```

---

### `memory_search`

Search the agent's memory store.

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| `query` | string | Yes | Natural language search query |
| `agent` | string | No | Filter by agent namespace |
| `memory_type` | string | No | Filter by memory type |
| `memory_level` | string | No | Filter by level (L1/L2/L3) |
| `limit` | integer | No | Max results (default: 10) |
| `scoreThreshold` | float | No | Minimum relevance (0-1) |
| `include_expired` | boolean | No | Include expired memories |

**Response:**

```json
{
  "memories": [
    {
      "uri": "viking://...",
      "content": "Full memory text...",
      "abstract": "Short summary...",
      "score": 0.92,
      "category": "decision",
      "level": 2
    }
  ],
  "total": 5
}
```

---

### `memory_read`

Read a specific memory by URI, or perform a content search.

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| `uri` | string | No | Memory URI (required if no query) |
| `query` | string | No | Search query (required if no URI) |
| `agent` | string | No | Agent namespace |
| `memory_type` | string | No | Filter by memory type |
| `memory_level` | string | No | Filter by level |
| `limit` | integer | No | Max results (default: 10) |
| `include_expired` | boolean | No | Include expired memories |

---

### `memory_delete`

Delete a specific memory by URI.

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| `uri` | string | Yes | The memory URI to delete |

---

### `memory_snapshot`

Generate an auto-summary of recent memories for agent startup context.

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| `agent` | string | Yes | Agent identifier |
| `limit` | integer | No | Max source memories (default: 200) |

---

## HTTP API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/memory/write` | Write a memory |
| `POST` | `/memory/search` | Search memories |
| `POST` | `/memory/read` | Read a specific memory |
| `POST` | `/memory/delete` | Delete a memory |
| `POST` | `/memory/snapshot` | Generate startup snapshot |
| `GET` | `/memory/types` | Memory type configuration |
| `GET` | `/memory/dedup/stats` | Deduplication statistics |
| `GET` | `/memory/rate_limit/stats` | Rate limit status |
| `GET` | `/support/error-codes` | Error code catalog |

---

## Authentication Headers

| Header | Description |
|--------|-------------|
| `X-OmniMemora-Key` | OmniMemora API key |
| `X-OpenViking-Account` | Tenant identifier |
| `X-OpenViking-User` | User identifier |
| `X-Request-ID` | Request correlation ID (returned in all responses) |

---

## Error Response Format

All errors follow the OmniMemora Support Schema:

```json
{
  "schema_version": "ov-support/v1",
  "status": "error",
  "message": "Human-readable error message",
  "detail": "Detailed error description",
  "error_code": "ADAPTER_SEARCH_FAILED",
  "request_id": "req-abc123",
  "support": {
    "category": "dependency",
    "severity": "medium",
    "retryable": true,
    "operation": "search_memory",
    "suggested_action": "Check OpenViking search state."
  }
}
```

---

## Memory Levels

| Level | Name | TTL | Description |
|-------|------|-----|-------------|
| L0 | Discard | - | Do not store |
| L1 | Short-term | 7 days | Ephemeral working context |
| L2 | Experience | 30 days | Learned experiences |
| L3 | Core | Permanent | Core facts and decisions |

---

## Status Codes

| Status | Description |
|--------|-------------|
| `stored` | Memory successfully stored |
| `skipped` | Memory filtered out (not stored) |
| `duplicate` | Duplicate content detected |
| `rate_limited` | Request rate exceeded |
| `error` | Processing error occurred |
