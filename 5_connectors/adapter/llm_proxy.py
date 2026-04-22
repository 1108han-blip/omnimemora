"""Compatibility shim: ingress implementation moved to adapter.ingress.llm_proxy."""

import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("5_connectors.adapter.ingress.llm_proxy")
