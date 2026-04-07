"""
Mock OmniMemora Adapter for local development and testing.

This module provides a mock HTTP server that implements the OmniMemora
public API surface, useful for:
- Local development without a real adapter deployment
- Unit testing of agents that consume the OmniMemora API
- Demo and showcase environments

It uses in-memory storage and does not connect to OpenViking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="OmniMemora Mock Adapter", version="1.0.0")

# In-memory storage for mock
_memories: list[dict[str, Any]] = []


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "viking_url": "mock://localhost",
        "viking_connected": True,
        "namespace_root": "mock://resources",
        "mock": True,
    }


@app.post("/memory/write")
async def write_memory(request: Request):
    body = await request.json()
    agent = body.get("agent", "unknown")
    content = body.get("content", "")
    memory_type = body.get("type", "general")

    memory_id = f"mock://memory/{uuid.uuid4().hex[:8]}"
    memory = {
        "uri": memory_id,
        "agent": agent,
        "content": content,
        "category": memory_type,
        "level": 2,
        "score": 80,
        "created_at": datetime.now().isoformat(),
    }
    _memories.append(memory)

    return {
        "status": "stored",
        "memory_id": memory_id,
        "uri": memory_id,
        "memory_type": memory_type,
        "memory_level": 2,
        "score": 80,
        "memory_expire_at": -1,
        "request_id": f"mock-{uuid.uuid4().hex[:8]}",
    }


@app.post("/memory/search")
async def search_memory(request: Request):
    body = await request.json()
    query = body.get("query", "").lower()
    limit = body.get("limit", 10)

    results = []
    for mem in reversed(_memories):
        if query in mem.get("content", "").lower():
            results.append(
                {
                    "uri": mem["uri"],
                    "content": mem["content"],
                    "abstract": mem["content"][:240],
                    "score": 0.9,
                    "category": mem["category"],
                    "level": mem["level"],
                    "metadata": {},
                }
            )
        if len(results) >= limit:
            break

    return {"memories": results, "total": len(results)}


@app.post("/memory/read")
async def read_memory(request: Request):
    body = await request.json()
    uri = body.get("uri")
    if uri:
        for mem in _memories:
            if mem["uri"] == uri:
                return {"content": mem["content"]}
        raise HTTPException(status_code=404, detail="Memory not found")
    query = body.get("query", "")
    return await search_memory(request)


@app.post("/memory/delete")
async def delete_memory(request: Request):
    body = await request.json()
    uri = body.get("uri")
    for i, mem in enumerate(_memories):
        if mem["uri"] == uri:
            _memories.pop(i)
            return {"success": True, "uri": uri}
    return {"success": False, "uri": uri, "reason": "not_found"}


@app.post("/memory/snapshot")
async def memory_snapshot(request: Request):
    body = await request.json()
    agent = body.get("agent", "unknown")
    return {
        "agent": agent,
        "generatedAt": datetime.now().isoformat(),
        "sourceCount": len(_memories),
        "markdown": f"## 启动必读摘要\n\nMock snapshot with {len(_memories)} memories.\n",
        "sections": {"identity": 0, "projects": 0, "preferences": 0, "decisions": 0, "facts": len(_memories)},
        "request_id": f"mock-{uuid.uuid4().hex[:8]}",
    }


@app.get("/memory/types")
async def memory_types():
    return {
        "memory_types": ["long_term", "short_term"],
        "memory_levels": {
            "L0": "Discard",
            "L1": "Short-term (7 days)",
            "L2": "Experience (30 days)",
            "L3": "Core (permanent)",
        },
        "ttl_config": {"L1": "7 days", "L2": "30 days", "L3": "permanent"},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
