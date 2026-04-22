"""Compatibility shim: application implementation moved to adapter.application.gateway_compile."""

import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("5_connectors.adapter.application.gateway_compile")
