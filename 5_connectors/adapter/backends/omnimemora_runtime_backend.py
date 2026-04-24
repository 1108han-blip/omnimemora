# omnimemora_runtime_backend.py
"""OmniMemora Runtime Backend Adapter (internal 8765 plane)

This adapter implements the internal MemoryBackend bridge to OmniMemora Runtime.
It is an adapter-internal transport layer, not a second product entry surface.

ADR-0006: All internal traffic uses internal_transport for loopback resolution
and proxy-free HTTP client creation.
"""

import httpx
import os
from datetime import datetime
from typing import Optional, Dict, Any

from .base import (
    MemoryBackend,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryWriteRequest,
    MemoryRecord,
    BackendHealth,
)
from .factory import register_backend
from .. import internal_transport as _it


@register_backend("omnimemora_runtime")
class OmniMemoraRuntimeBackend(MemoryBackend):
    """OmniMemora Runtime Backend Adapter for the internal runtime plane

    ADR-0006: base_url is resolved through internal_transport.resolve_internal_base_url
    to find the best reachable loopback address at runtime.
    """

    backend_type = "omnimemora_runtime"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
    ):
        default_url = os.getenv("MEMORY_BACKEND_URL", "http://127.0.0.1:8765")
        configured_url = base_url or default_url

        # ADR-0006 §3.2: Resolve to a reachable loopback address
        # Use sync path during init (no event loop available yet)
        try:
            resolved_url, _ = _it.resolve_internal_base_url_sync(
                "omnimemora_runtime", configured_url
            )
        except Exception:
            # Fallback: use configured URL as-is if resolution fails
            resolved_url = configured_url

        self.base_url = resolved_url.rstrip("/")
        self.api_key = api_key
        # ADR-0006 §2.3: Internal traffic uses trust_env=False
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds),
            trust_env=False,
        )

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _runtime_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an internal runtime-plane request."""
        url = f"{self.base_url}{path}"
        response = await self._client.request(
            method=method,
            url=url,
            headers=self._headers(),
            **kwargs
        )
        response.raise_for_status()
        return response.json()

    async def search(self, request: MemorySearchRequest, **kwargs) -> MemorySearchResult:
        """Search via POST /memory/search"""
        body = {
            "keyword": request.query,
            "query": request.query,
            "limit": request.limit,
        }
        if isinstance(request.access_plan, dict) and request.access_plan:
            body["access_plan"] = request.access_plan
        result = await self._runtime_request("POST", "/memory/search", json=body)
        enforcement = result.get("enforcement_trace") if isinstance(result.get("enforcement_trace"), dict) else None
        if enforcement is None and isinstance(result.get("actual_enforcement"), dict):
            enforcement = result.get("actual_enforcement")

        memories = []
        for item in result.get("results", []):
            memories.append(MemoryRecord(
                memory_id=item.get("memory_id", ""),
                content=item.get("content", ""),
                scope=request.scope,
                scope_ref=request.scope_ref,
                metadata={},
                created_at=item.get("created_at"),
                score=item.get("score"),
                enforcement_trace=enforcement,
            ))
        return MemorySearchResult(
            memories=memories,
            total=result.get("total", len(memories)),
            query=request.query,
            enforcement_trace=enforcement,
        )

    async def write(self, request: MemoryWriteRequest, **kwargs) -> MemoryRecord:
        """Write via POST /memory/write"""
        body = {
            "content": request.content,
            "scope": request.scope,
            "scope_ref": request.scope_ref,
            "metadata": request.metadata,
            "overwrite": request.overwrite,
        }
        if isinstance(request.access_plan, dict) and request.access_plan:
            body["access_plan"] = request.access_plan
        result = await self._runtime_request("POST", "/memory/write", json=body)
        enforcement = result.get("enforcement_trace") if isinstance(result.get("enforcement_trace"), dict) else None
        if enforcement is None and isinstance(result.get("actual_enforcement"), dict):
            enforcement = result.get("actual_enforcement")

        return MemoryRecord(
            memory_id=result.get("memory_id", ""),
            content=request.content,
            scope=request.scope,
            scope_ref=request.scope_ref,
            metadata=request.metadata,
            created_at=result.get("created_at"),
            enforcement_trace=enforcement,
        )

    async def read(self, memory_id: str) -> Optional[MemoryRecord]:
        """Read via GET /memory/read/{memory_id}"""
        try:
            result = await self._runtime_request("GET", f"/memory/read/{memory_id}")
            return MemoryRecord(
                memory_id=result.get("id", memory_id),
                content=result.get("content", ""),
                scope=result.get("scope", "unknown"),
                scope_ref=result.get("scope_ref", "unknown"),
                metadata=result.get("metadata", {}),
                created_at=result.get("created_at"),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete(self, memory_id: str) -> bool:
        """Delete via DELETE /memory/delete/{memory_id}"""
        try:
            await self._runtime_request("DELETE", f"/memory/delete/{memory_id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    async def health(self) -> BackendHealth:
        """Check via GET /health"""
        try:
            response = await self._client.get(
                f"{self.base_url}/health",
                headers=self._headers(),
                timeout=httpx.Timeout(5.0, connect=2.0)
            )
            healthy = response.status_code == 200
        except Exception as e:
            return BackendHealth(
                healthy=False,
                backend_type=self.backend_type,
                details={"error": str(e)}
            )

        return BackendHealth(healthy=healthy, backend_type=self.backend_type)

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()
