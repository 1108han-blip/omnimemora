"""Ingress layer for 18011 adapter protocol entry points."""

import importlib

llm_proxy = importlib.import_module("5_connectors.adapter.ingress.llm_proxy")

__all__ = ["llm_proxy"]
