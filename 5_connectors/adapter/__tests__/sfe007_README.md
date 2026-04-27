# SFE-007: Memory Feedback Loop Verification

## Goal

Prove that OmniMemora's memory feedback loop exists:

```
response returns through product
→ product writes internal work memory
→ next related request retrieves it
```

## Architecture

```
Agent CLI (Claude Code / OpenClaw)
    │
    │  POST /llm/chat or /llm/anthropic
    ▼
OmniMemora Adapter (18011)
    │
    ├─ compile: fetch memories from backend (8765)
    ├─ inject memories into prompt
    │
    │  upstream call
    ▼
Model (Claude / GPT)
    │
    │  response returns
    ▼
OmniMemora Adapter
    │  ← HERE: what happens? AUTO-WRITE or NOT?
    ▼
Return to agent
```

**Critical finding from code review**: The proxy path has **no automatic memory write**.
After the upstream response, OmniMemora only calls `_record_event()` + returns the response.
Memory write must be triggered explicitly by the agent (via MCP `memory.write` or CLI).

## Three sub-paths

### Path A: Direct API round-trip ✅ testable
```
POST /memory/write  → write memory with unique marker
POST /memory/search → search for the marker
VERIFY: written memory appears in search results
```

### Path B: Compile retrieval round-trip ⚠️ requires running service
```
Write a memory item via POST /memory/write
Call run_gateway_compile() with a related query
VERIFY: the compiled payload's packed_context contains the written content
```

### Path C: Agent end-to-end loop ❌ manual verification
```
Agent sends request → gets response → agent writes memory (via MCP/CLI)
Agent sends follow-up request
VERIFY: compile retrieves the memory from first response
```

Path C is **not automated** — it depends on agent behavior.
It is verified by checking MCP call logs or agent session traces.

## Gate Criteria

| Path | Gate |
|------|------|
| Path A | Write succeeds + search finds the marker |
| Path B | Write succeeds + compile retrieves memory + content found in packed_context |
| Path C | Manual verification |

**SFE-007 passes**: Path A AND Path B both pass.

## Running

```bash
# Prerequisites
# Start adapter: python tools/_run_adapter.py &
# Start memory backend on 8765 (if using remote backend)

# Run all
python -m pytest __tests__/test_sfe007_memory_roundtrip.py -v

# Path A only (no adapter needed for Path A if using direct HTTP)
OMNIMEMORA_ADAPTER_URL=http://127.0.0.1:18011 \
    python -m pytest __tests__/test_sfe007_memory_roundtrip.py -v -k "path_a"

# Path B only
OMNIMEMORA_ADAPTER_URL=http://127.0.0.1:18011 \
    python -m pytest __tests__/test_sfe007_memory_roundtrip.py -v -k "path_b"
```

## If Path B fails

The compile path is not retrieving memories written in the same session.

Likely causes:
1. Memory backend not accessible → check 8765 connectivity
2. Memory write succeeded but search not finding it → check backend indexing
3. Compile not calling the right search scope → check runtime_bridge.fetch_memory_candidates

If Path A passes but Path B fails: the API write→search works, but the compile path has a separate issue.
