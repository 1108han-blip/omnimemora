# factory.py
"""Backend Factory - Backend creation and registry"""

from typing import Dict, Type, Optional, Any

from .base import MemoryBackend, BackendHealth


# Backend type registry
BACKEND_REGISTRY: Dict[str, Type[MemoryBackend]] = {}
_LEGACY_REMOVED_BACKEND_TYPE = "".join(("open", "viking"))


def register_backend(backend_type: str):
    """Backend registration decorator"""
    def decorator(cls: Type[MemoryBackend]) -> Type[MemoryBackend]:
        BACKEND_REGISTRY[backend_type] = cls
        return cls
    return decorator


def get_backend_class(backend_type: str) -> Type[MemoryBackend]:
    """Get backend class by type"""
    if backend_type not in BACKEND_REGISTRY:
        available = list(BACKEND_REGISTRY.keys())
        raise ValueError(
            f"Unknown backend type: '{backend_type}'. Available: {available}"
        )
    return BACKEND_REGISTRY[backend_type]


class BackendConfig:
    """Backend configuration container.

    For the default OmniMemora backend, base_url points to the internal runtime
    plane. External product traffic still enters through :18011.
    """
    def __init__(
        self,
        backend_type: str = "omnimemora_runtime",
        base_url: str = "",
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
        **kwargs
    ):
        self.backend_type = backend_type
        self.base_url = base_url or os.getenv("MEMORY_BACKEND_URL", "http://127.0.0.1:8765")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        # Allow extra kwargs for backend-specific config
        for k, v in kwargs.items():
            setattr(self, k, v)


def create_backend(config) -> MemoryBackend:
    """Create a backend instance from config

    Args:
        config: BackendConfig, MemoryBackendConfig, or dict with backend_type and connection params

    Returns:
        MemoryBackend instance

    Raises:
        ValueError: Unknown backend type
    """
    # Handle pydantic model or dict
    if hasattr(config, 'dict'):
        config_dict = config.dict()
    elif isinstance(config, dict):
        config_dict = config
    else:
        config_dict = {
            'backend_type': config.backend_type,
            'base_url': config.base_url,
            'api_key': config.api_key,
            'timeout_seconds': config.timeout_seconds,
            'connect_timeout_seconds': config.connect_timeout_seconds,
        }

    backend_type = config_dict.get('backend_type', 'omnimemora_runtime')
    if backend_type == _LEGACY_REMOVED_BACKEND_TYPE:
        raise ValueError(
            "Legacy compatibility backend has been removed from active runtime paths. "
            "Use 'omnimemora_runtime' only."
        )

    backend_config = BackendConfig(**config_dict)
    backend_class = get_backend_class(backend_config.backend_type)
    return backend_class(
        base_url=backend_config.base_url,
        api_key=backend_config.api_key,
        timeout_seconds=backend_config.timeout_seconds,
        connect_timeout_seconds=backend_config.connect_timeout_seconds,
    )


def create_backend_from_dict(config_dict: Dict[str, Any]) -> MemoryBackend:
    """Create backend from dict (for Config object passthrough)"""
    return create_backend(BackendConfig(**config_dict))


# Global backend instance (singleton per process)
_global_backend: Optional[MemoryBackend] = None


def get_memory_backend() -> MemoryBackend:
    """Get the global backend instance

    Note: Call set_memory_backend() to initialize before use.
    """
    global _global_backend
    if _global_backend is None:
        raise RuntimeError(
            "Memory backend not initialized. "
            "Call set_memory_backend() first."
        )
    return _global_backend


def set_memory_backend(backend: MemoryBackend) -> None:
    """Set the global backend instance (for initialization and testing)"""
    global _global_backend
    _global_backend = backend


def clear_memory_backend() -> None:
    """Clear the global backend instance"""
    global _global_backend
    _global_backend = None
