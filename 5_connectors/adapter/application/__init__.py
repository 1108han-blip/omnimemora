"""
application/ — Application layer modules for 18011 adapter
==========================================================
Contains application-level orchestration that is NOT transport/infrastructure.

Modules:
- status_read_model: read-only aggregation of control state, metrics, truth surfaces
"""

import importlib

status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")
compile_orchestrator = importlib.import_module("5_connectors.adapter.application.compile_orchestrator")

__all__ = ["status_read_model", "compile_orchestrator"]