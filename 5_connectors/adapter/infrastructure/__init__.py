"""Infrastructure layer for adapter runtime/store/backend access."""

import importlib

runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")
meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
trace_store = importlib.import_module("5_connectors.adapter.infrastructure.trace_store")
compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")
proxy_store = importlib.import_module("5_connectors.adapter.infrastructure.proxy_store")

__all__ = [
    "runtime_bridge",
    "meter_store",
    "trace_store",
    "compile_store",
    "proxy_store",
]
