# backends/__init__.py
"""Backend Abstraction Layer - Factory exports"""

from .base import (
    MemoryBackend,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryWriteRequest,
    MemoryRecord,
    BackendHealth,
)
from .factory import create_backend, get_memory_backend, register_backend

# Import backend implementations to trigger @register_backend decorators
from .omnimemora_runtime_backend import OmniMemoraRuntimeBackend

__all__ = [
    "MemoryBackend",
    "MemorySearchRequest",
    "MemorySearchResult",
    "MemoryWriteRequest",
    "MemoryRecord",
    "BackendHealth",
    "create_backend",
    "get_memory_backend",
    "register_backend",
    "OmniMemoraRuntimeBackend",
]
