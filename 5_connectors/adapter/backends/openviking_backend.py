# openviking_backend.py
"""OpenViking Backend Adapter (1933)

This adapter implements the MemoryBackend interface for OpenViking.
All OpenViking-specific protocol details (viking://, /api/v1/) stay here.

ADR-0006: Internal traffic uses trust_env=False client for proxy bypass.
"""

import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import quote
from pathlib import PurePosixPath

from .base import (
    MemoryBackend,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryWriteRequest,
    MemoryRecord,
    BackendHealth,
)
from .factory import register_backend
from .. import config


@register_backend("openviking")
class OpenVikingBackend(MemoryBackend):
    """OpenViking Backend Adapter for 1933

    This backend is a LEGACY / COMPATIBILITY backend.
    It exists to provide full CRUD support for environments that require it.
    For new deployments, use 'omnimemora_runtime' (default query-path backend).
    """

    backend_type = "openviking"
    is_compatibility_backend = True

    def __init__(
        self,
        base_url: str = "http://host.docker.internal:1933",
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
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

    # ========================================================================
    # OpenViking-specific URI utilities (private)
    # ========================================================================

    def _normalize_viking_uri(self, uri: str) -> str:
        normalized = (uri or "").strip()
        if normalized == "viking://":
            return normalized
        return normalized.rstrip("/")

    def _split_viking_uri(self, uri: str) -> List[str]:
        normalized = self._normalize_viking_uri(uri)
        if not normalized.startswith("viking://"):
            return []
        suffix = normalized[len("viking://"):]
        return [segment for segment in suffix.split("/") if segment]

    def _join_viking_uri(self, segments: List[str]) -> str:
        if not segments:
            return "viking://"
        return "viking://" + "/".join(segments)

    def _sanitize_path_segment(self, value: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in (value or "").strip())
        safe = safe.strip("-_")
        return safe or "unknown"

    def _build_memory_root_prefix(self) -> str:
        return self._normalize_viking_uri(config.viking_memory_namespace_root)

    def _build_agent_memory_prefix(self, agent: str) -> str:
        agent_segment = self._sanitize_path_segment(agent)
        return f"{self._build_memory_root_prefix()}/{agent_segment}"

    def _build_memory_type_prefix(self, agent: str, memory_type: str) -> str:
        prefix = self._build_agent_memory_prefix(agent)
        type_segment = self._sanitize_path_segment(memory_type or "general")
        return f"{prefix}/{type_segment}"

    def _scope_to_uri(self, scope: str, scope_ref: str) -> str:
        """Convert scope model to OpenViking viking:// URI"""
        if scope == "agent":
            return f"viking://resources/memory-adapter/{scope_ref}/short_term"
        elif scope == "workspace":
            return f"viking://resources/memory-adapter/{scope_ref}"
        elif scope == "tenant":
            return f"viking://resources/memory-adapter/{scope_ref}"
        return "viking://resources/memory-adapter"

    # ========================================================================
    # OpenViking-specific namespace helpers (private)
    # ========================================================================

    async def _list_directory_entries(self, uri: str) -> List[Dict[str, Any]]:
        """List directory entries via GET /api/v1/fs/ls"""
        encoded_uri = quote(uri, safe="")
        try:
            response = await self._client.request(
                "GET",
                f"{self.base_url}/api/v1/fs/ls?uri={encoded_uri}",
                headers=self._headers(),
                timeout=httpx.Timeout(config.viking_snapshot_timeout_seconds, connect=config.viking_connect_timeout_seconds),
            )
            if response.is_success:
                payload = response.json()
                result = payload.get("result", [])
                if isinstance(result, list):
                    return [item for item in result if isinstance(item, dict)]
            return []
        except Exception:
            return []

    async def _mkdir_uri(self, uri: str) -> bool:
        """Create directory via POST /api/v1/fs/mkdir"""
        try:
            response = await self._client.request(
                "POST",
                f"{self.base_url}/api/v1/fs/mkdir",
                headers=self._headers(),
                json={"uri": uri},
                timeout=httpx.Timeout(config.viking_resolve_timeout_seconds, connect=config.viking_connect_timeout_seconds),
            )
            return response.is_success
        except Exception:
            return False

    async def _namespace_exists(self, uri: str) -> bool:
        """Check if namespace exists"""
        normalized = self._normalize_viking_uri(uri)
        segments = self._split_viking_uri(normalized)
        if not segments:
            return False
        if normalized == "viking://resources":
            return True

        current_parent = "viking://resources"
        for index in range(2, len(segments) + 1):
            current_uri = self._join_viking_uri(segments[:index])
            entries = await self._list_directory_entries(current_parent)
            if not any(
                self._normalize_viking_uri(str(item.get("uri", ""))) == current_uri
                for item in entries
            ):
                return False
            current_parent = current_uri
        return True

    async def _resolve_leaf_uri(
        self,
        root_uri: str,
    ) -> str:
        """Resolve leaf file URI from resource root via GET /api/v1/fs/tree"""
        if root_uri.startswith(self._build_memory_root_prefix()) and not await self._namespace_exists(root_uri):
            return root_uri
        encoded_uri = quote(root_uri, safe="")
        try:
            response = await self._client.request(
                "GET",
                f"{self.base_url}/api/v1/fs/tree?uri={encoded_uri}",
                headers=self._headers(),
                timeout=httpx.Timeout(config.viking_resolve_timeout_seconds, connect=config.viking_connect_timeout_seconds),
            )
            if not response.is_success:
                return root_uri
            payload = response.json()
            result = payload.get("result", [])
            if not isinstance(result, list):
                return root_uri
            leaf_candidates = [
                item.get("uri")
                for item in result
                if isinstance(item, dict) and not item.get("isDir") and item.get("uri")
            ]
            for uri in leaf_candidates:
                if not self._is_derived_resource_uri(uri):
                    return uri
            return root_uri
        except Exception:
            return root_uri

    async def _collect_memory_leaf_uris(
        self,
        root_uri: str,
        max_files: int = 200,
    ) -> List[str]:
        """Traverse tree to collect leaf file URIs"""
        collected: List[str] = []
        seen_dirs = set()
        stack = [root_uri]

        while stack and len(collected) < max_files:
            current = stack.pop()
            if current in seen_dirs:
                continue
            seen_dirs.add(current)

            for item in await self._list_directory_entries(current):
                uri = item.get("uri")
                if not isinstance(uri, str) or not uri:
                    continue
                name = PurePosixPath(uri).name
                if item.get("isDir"):
                    if not name.startswith("."):
                        stack.append(uri)
                    continue
                if self._is_derived_resource_uri(uri):
                    continue
                if name.startswith("upload_") and uri not in collected:
                    collected.append(uri)
                    if len(collected) >= max_files:
                        break

        return collected

    def _is_derived_resource_uri(self, uri: str) -> bool:
        """Check if URI is a derived resource"""
        if not uri:
            return True
        name = PurePosixPath(uri).name
        return name.startswith(".") or name in ("result", "result.json", "metadata.json")

    async def _read_clean_resource_content(self, uri: str) -> Optional[str]:
        """Read and extract content via GET /api/v1/content/read"""
        encoded_uri = quote(uri, safe="")
        try:
            response = await self._client.request(
                "GET",
                f"{self.base_url}/api/v1/content/read?uri={encoded_uri}",
                headers=self._headers(),
                timeout=httpx.Timeout(config.viking_read_timeout_seconds, connect=config.viking_connect_timeout_seconds),
            )
            if not response.is_success:
                return None
            result = response.json()
            # Extract content from OpenViking response
            content = result.get("content") or result.get("text") or ""
            return content
        except Exception:
            return None

    # ========================================================================
    # MemoryBackend interface implementation
    # ========================================================================

    async def _viking_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make request to OpenViking - OpenViking protocol only"""
        url = f"{self.base_url}{path}"
        response = await self._client.request(
            method=method,
            url=url,
            headers=self._headers(),
            **kwargs
        )
        response.raise_for_status()
        return response.json()

    async def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        """Search via POST /api/v1/search/find"""
        body = {
            "query": request.query,
            "limit": request.limit,
            "target_uri": self._scope_to_uri(request.scope, request.scope_ref),
            "score_threshold": request.score_threshold,
        }
        result = await self._viking_request("POST", "/api/v1/search/find", json=body)

        memories = []
        for item in result.get("memories", []):
            memories.append(MemoryRecord(
                memory_id=item.get("uri", ""),
                content=self._extract_content(item),
                scope=request.scope,
                scope_ref=request.scope_ref,
                metadata=item.get("metadata", {}),
                created_at=item.get("created_at"),
                score=item.get("score"),
            ))
        return MemorySearchResult(
            memories=memories,
            total=len(memories),
            query=request.query,
        )

    def _extract_content(self, item: Dict[str, Any]) -> str:
        """Extract content from OpenViking memory item"""
        if "content" in item:
            return item["content"]
        if "text" in item:
            return item["text"]
        return str(item.get("data", ""))

    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        """Write via temp_upload + resources commit (two-phase)"""
        target_uri = self._scope_to_uri(request.scope, request.scope_ref)

        # Phase 1: temp_upload
        upload_body = {
            "content": request.content,
            "metadata": request.metadata,
            "target_uri": target_uri,
        }
        upload_result = await self._viking_request(
            "POST", "/api/v1/resources/temp_upload", json=upload_body
        )

        # Phase 2: commit resource
        commit_body = {
            "resources": [upload_result.get("resource_id")],
            "target_uri": target_uri,
        }
        await self._viking_request("POST", "/api/v1/resources", json=commit_body)

        # Resolve leaf URI for the returned memory_id
        resource_id = upload_result.get("resource_id", "")
        resolved_uri = await self._resolve_leaf_uri(target_uri)

        return MemoryRecord(
            memory_id=resolved_uri,
            content=request.content,
            scope=request.scope,
            scope_ref=request.scope_ref,
            metadata=request.metadata,
            created_at=datetime.utcnow(),
        )

    async def read(self, memory_id: str) -> Optional[MemoryRecord]:
        """Read via GET /api/v1/content/read"""
        encoded_uri = memory_id.replace(":", "%3A").replace("/", "%2F")
        result = await self._viking_request(
            "GET", f"/api/v1/content/read?uri={encoded_uri}"
        )
        if not result:
            return None
        return MemoryRecord(
            memory_id=memory_id,
            content=result.get("content", ""),
            scope="unknown",
            scope_ref="unknown",
            metadata=result.get("metadata", {}),
            created_at=result.get("created_at"),
        )

    async def delete(self, memory_id: str) -> bool:
        """Delete via DELETE /api/v1/fs"""
        encoded_uri = memory_id.replace(":", "%3A").replace("/", "%2F")
        try:
            await self._viking_request("DELETE", f"/api/v1/fs?uri={encoded_uri}")
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

    # ========================================================================
    # Namespace and fallback operations
    # ========================================================================

    async def prepare_namespace(self, scope: str, scope_ref: str) -> bool:
        """Prepare namespace tree for write operation.

        Creates the OpenViking namespace hierarchy if it doesn't exist.
        """
        uri = self._scope_to_uri(scope, scope_ref)
        normalized = self._normalize_viking_uri(uri)
        segments = self._split_viking_uri(normalized)
        if len(segments) < 2:
            return False

        current_parent = "viking://resources"
        for index in range(2, len(segments) + 1):
            current_uri = self._join_viking_uri(segments[:index])
            entries = await self._list_directory_entries(current_parent)
            if any(
                self._normalize_viking_uri(str(item.get("uri", ""))) == current_uri
                for item in entries
            ):
                current_parent = current_uri
                continue
            if not await self._mkdir_uri(current_uri):
                return False
            current_parent = current_uri
        return True

    async def fallback_search(
        self,
        query: str,
        scope_ref: str,
        limit: int,
    ) -> MemorySearchResult:
        """Fallback content-scan search.

        When primary search yields no results, scan recent memories
        for content keyword matches.
        """
        from .base import MemorySearchResult as Result

        agent = scope_ref or "unknown"
        root_uri = self._build_agent_memory_prefix(agent)

        if not await self._namespace_exists(root_uri):
            return Result(memories=[], total=0, query=query)

        leaf_uris = await self._collect_memory_leaf_uris(
            root_uri,
            max_files=max(limit, config.search_fallback_scan_limit),
        )

        matches: List[MemoryRecord] = []
        query_lower = query.lower()

        for uri in leaf_uris:
            content = await self._read_clean_resource_content(uri)
            if not content:
                continue
            # Simple keyword match
            if query_lower not in content.lower():
                continue
            matches.append(MemoryRecord(
                memory_id=uri,
                content=content,
                scope="agent",
                scope_ref=agent,
                metadata={"fallback": "content_scan", "agent": agent},
                score=1.0,
            ))
            if len(matches) >= limit:
                break

        return Result(memories=matches, total=len(matches), query=query)

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()
