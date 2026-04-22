"""Compatibility shim: infrastructure implementation moved to adapter.infrastructure.runtime_bridge."""

import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("5_connectors.adapter.infrastructure.runtime_bridge")
