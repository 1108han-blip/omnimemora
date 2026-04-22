"""Infrastructure layer for adapter runtime/store/backend access."""

import importlib

runtime_bridge = importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")
meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
trace_store = importlib.import_module("5_connectors.adapter.infrastructure.trace_store")
compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")
proxy_store = importlib.import_module("5_connectors.adapter.infrastructure.proxy_store")
# Cloud access stays in-place under adapter.cloud; infrastructure re-exports
# the stable entry points so main/application consume infra boundary explicitly.
_cloud = importlib.import_module("5_connectors.adapter.cloud")
load_policy = _cloud.load_policy
load_flags = _cloud.load_flags
report_usage_async = _cloud.report_usage_async

__all__ = [
    "runtime_bridge",
    "meter_store",
    "trace_store",
    "compile_store",
    "proxy_store",
    "load_policy",
    "load_flags",
    "report_usage_async",
]
