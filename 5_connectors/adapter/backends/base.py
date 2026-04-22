# base.py
"""MemoryBackend Interface Definition - Backend-neutral abstraction

This module defines the unified interface for memory backends.
No backend-specific concepts (viking, mcp, /api/v1/, viking://) allowed here.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class MemoryScope(Enum):
    """Memory scope types - backend neutral"""
    AGENT = "agent"
    WORKSPACE = "workspace"
    TENANT = "tenant"


@dataclass
class MemorySearchRequest:
    """Backend-neutral search request"""
    query: str
    limit: int = 10
    scope: str = "agent"
    scope_ref: str = "default"
    score_threshold: float = 0.0
    metadata_filter: Optional[Dict[str, Any]] = None


@dataclass
class MemoryRecord:
    """Backend-neutral memory record"""
    memory_id: str
    content: str
    scope: str
    scope_ref: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    score: Optional[float] = None


@dataclass
class MemorySearchResult:
    """Backend-neutral search result"""
    memories: List[MemoryRecord]
    total: int
    query: Optional[str] = None


@dataclass
class MemoryWriteRequest:
    """Backend-neutral write request"""
    content: str
    scope: str
    scope_ref: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    overwrite: bool = False


@dataclass
class BackendHealth:
    """Backend health status"""
    healthy: bool
    backend_type: str
    details: Optional[Dict[str, Any]] = None


class MemoryBackend(ABC):
    """Abstract interface for memory backends

    All backends must implement this interface.
    Backend-specific logic stays inside the adapter implementation.
    """

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return backend type identifier (e.g., 'omnimemora_runtime')."""
        pass

    @abstractmethod
    async def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        """Search memory records

        Args:
            request: Search parameters

        Returns:
            MemorySearchResult with matched records
        """
        pass

    @abstractmethod
    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        """Write a memory record

        Args:
            request: Write parameters

        Returns:
            MemoryRecord with assigned memory_id
        """
        pass

    @abstractmethod
    async def read(self, memory_id: str) -> Optional[MemoryRecord]:
        """Read a memory record by ID

        Args:
            memory_id: Memory record identifier

        Returns:
            MemoryRecord if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory record

        Args:
            memory_id: Memory record identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def health(self) -> BackendHealth:
        """Check backend health

        Returns:
            BackendHealth status
        """
        pass

    async def prepare_namespace(self, scope: str, scope_ref: str) -> bool:
        """Prepare namespace tree before write operations.

        For backends that require namespace creation,
        this ensures the target namespace exists before writing.

        Args:
            scope: Memory scope (e.g., 'agent', 'workspace')
            scope_ref: Scope identifier (e.g., agent name)

        Returns:
            True if namespace is ready, False otherwise
        """
        # Default implementation: no-op for backends that don't need it
        return True

    async def fallback_search(
        self,
        query: str,
        scope_ref: str,
        limit: int,
    ) -> MemorySearchResult:
        """Fallback content-scan search when primary search yields no results.

        This is a legacy concept where, when the main search
        doesn't find matches, a content scan of recent memories is performed.

        Args:
            query: Search query
            scope_ref: Agent/workspace identifier
            limit: Maximum results

        Returns:
            MemorySearchResult with fallback matches
        """
        # Default implementation: no fallback
        return MemorySearchResult(memories=[], total=0, query=query)
