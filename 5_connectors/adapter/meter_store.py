"""Compatibility shim: infrastructure implementation moved to adapter.infrastructure.meter_store."""

import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
