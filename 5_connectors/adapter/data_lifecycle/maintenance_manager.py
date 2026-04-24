"""Maintenance manager for Data Lifecycle Plane (non-destructive batch-1)."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .policy import DataLifecyclePolicy, load_policy
from . import state_store, summary_builder, summary_store


def _safe_file_size(path_value: Any) -> int:
    try:
        path = Path(str(path_value)).expanduser()
        if path.exists():
            return int(path.stat().st_size)
    except Exception:
        return 0
    return 0


class MaintenanceManager:
    def __init__(
        self,
        *,
        policy: Optional[DataLifecyclePolicy] = None,
        meter_export_fn: Optional[Callable[[], list[Any]]] = None,
        compile_rows_30m_fn: Optional[Callable[[], list[dict[str, Any]]]] = None,
        compile_rows_24h_fn: Optional[Callable[[], list[dict[str, Any]]]] = None,
        proxy_rows_30m_fn: Optional[Callable[[], list[dict[str, Any]]]] = None,
        is_default_overview_request_fn: Optional[Callable[[Any], bool]] = None,
        is_value_qualified_fn: Optional[Callable[[Any], bool]] = None,
        collapse_retry_bursts_fn: Optional[Callable[[list[Any]], list[Any]]] = None,
        bytes_scanned_fn: Optional[Callable[[], int]] = None,
    ) -> None:
        self._policy = policy or load_policy()
        self._meter_export_fn = meter_export_fn
        self._compile_rows_30m_fn = compile_rows_30m_fn
        self._compile_rows_24h_fn = compile_rows_24h_fn
        self._proxy_rows_30m_fn = proxy_rows_30m_fn
        self._is_default_overview_request_fn = is_default_overview_request_fn
        self._is_value_qualified_fn = is_value_qualified_fn
        self._collapse_retry_bursts_fn = collapse_retry_bursts_fn
        self._bytes_scanned_fn = bytes_scanned_fn

    def _resolve_dependencies(self) -> None:
        if self._meter_export_fn is not None:
            return

        meter_store = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
        compile_store = importlib.import_module("5_connectors.adapter.infrastructure.compile_store")
        proxy_store = importlib.import_module("5_connectors.adapter.infrastructure.proxy_store")
        request_classifier = importlib.import_module("5_connectors.adapter.request_classifier")

        self._meter_export_fn = meter_store.export_meters_for_summary
        self._compile_rows_30m_fn = lambda: compile_store.read_recent_compile_events(limit=5000, window_minutes=30)
        self._compile_rows_24h_fn = lambda: compile_store.read_recent_compile_events(limit=5000, window_minutes=24 * 60)
        self._proxy_rows_30m_fn = lambda: proxy_store.read_recent_events(limit=2000)
        self._is_default_overview_request_fn = request_classifier.is_default_overview_request
        self._is_value_qualified_fn = request_classifier.is_value_qualified
        self._collapse_retry_bursts_fn = request_classifier.collapse_retry_bursts

        if self._bytes_scanned_fn is None:
            self._bytes_scanned_fn = lambda: (
                _safe_file_size(getattr(compile_store, "COMPILE_EVENTS_PATH", ""))
                + _safe_file_size(getattr(proxy_store, "EVENTS_PATH", ""))
                + _safe_file_size(meter_store._meter_index_path())
            )

    def run_once(self, trigger: str) -> dict[str, Any]:
        self._resolve_dependencies()
        cycle_id = state_store.new_cycle_id()
        started_at = datetime.now(timezone.utc)

        try:
            meters = list(self._meter_export_fn() if self._meter_export_fn else [])
            compile_rows_30m = list(self._compile_rows_30m_fn() if self._compile_rows_30m_fn else [])
            compile_rows_24h = list(self._compile_rows_24h_fn() if self._compile_rows_24h_fn else [])
            proxy_rows_30m = list(self._proxy_rows_30m_fn() if self._proxy_rows_30m_fn else [])

            summary_payload = summary_builder.build_family_window_summary(
                meters=meters,
                compile_rows_30m=compile_rows_30m,
                compile_rows_24h=compile_rows_24h,
                proxy_rows_30m=proxy_rows_30m,
                is_default_overview_request=self._is_default_overview_request_fn,
                is_value_qualified=self._is_value_qualified_fn,
                collapse_retry_bursts=self._collapse_retry_bursts_fn,
            )
            summary_store.write_summary_atomic(summary_payload, policy=self._policy)

            completed_at = datetime.now(timezone.utc)
            bytes_scanned = int(self._bytes_scanned_fn() if self._bytes_scanned_fn else 0)
            record = state_store.build_record(
                cycle_id=cycle_id,
                trigger=trigger,
                started_at=started_at,
                completed_at=completed_at,
                status="success",
                bytes_scanned=bytes_scanned,
                error=None,
            )
            state_store.append_state_record(record, policy=self._policy)
            return record
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            bytes_scanned = int(self._bytes_scanned_fn() if self._bytes_scanned_fn else 0)
            record = state_store.build_record(
                cycle_id=cycle_id,
                trigger=trigger,
                started_at=started_at,
                completed_at=completed_at,
                status="failed",
                bytes_scanned=bytes_scanned,
                error=str(exc),
            )
            state_store.append_state_record(record, policy=self._policy)
            return record
