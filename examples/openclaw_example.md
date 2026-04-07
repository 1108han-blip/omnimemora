# Integration Guide — OpenClaw + OmniMemora

OpenClaw plugins can use OmniMemora via the REST API or MCP server.

## REST API Integration

Add OmniMemora as a backend in your OpenClaw plugin configuration:

```json
{
  "omnimemora": {
    "api_url": "https://api.doloclaw.com",
    "api_key_env": "OMNIMEMORA_API_KEY",
    "tenant_header": "X-OpenViking-Account",
    "user_header": "X-OpenViking-User"
  }
}
```

## OpenClaw Tool Definitions

The OmniMemora tools follow the OpenClaw tool contract:

```typescript
// Tool definition for OpenClaw plugin registry
const TOOLS = [
  {
    name: "memory_write",
    description: "Store important information in long-term memory",
    inputSchema: {
      type: "object",
      properties: {
        agent: { type: "string" },
        type: { type: "string" },
        content: { type: "string" },
        tags: { type: "array", items: { type: "string" } },
      },
      required: ["agent", "type", "content"],
    },
  },
  {
    name: "memory_search",
    description: "Search the agent's memory store",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        agent: { type: "string" },
        memory_type: { type: "string" },
        limit: { type: "integer", default: 10 },
      },
      required: ["query"],
    },
  },
];
```

## Response Compatibility

OmniMemora responses are compatible with OpenClaw's expected schema:

```typescript
interface MemoryResponse {
  status: "stored" | "skipped" | "duplicate" | "rate_limited" | "error";
  memory_id?: string;
  uri?: string;
  memory_type?: string;
  memory_level?: number;
  score?: number;
  request_id?: string;
}
```

## Environment Variables

Configure your OpenClaw plugin with:

```bash
OMNIMEMORA_API_KEY=omni-your-key-here
OMNIMEMORA_TENANT=your-tenant-id
OMNIMEMORA_USER=your-user-id
```
