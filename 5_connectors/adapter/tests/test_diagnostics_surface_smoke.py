import asyncio
import importlib
import unittest
from unittest import mock

from fastapi import Response

diagnostics_surface = importlib.import_module("5_connectors.adapter.diagnostics_surface")
status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")


class _DummyConfig:
    enable_rate_limit = True
    rate_limit_per_minute = 60
    memory_backend_url = ""


class _DummyDedupCache:
    def get_stats(self):
        return {"size": 0}


class _DummyRateLimiter:
    def get_current_count(self):
        return 0


class _DummyAgentMetrics:
    def get_live_agents(self, window_minutes=30):
        return []

    def get_agent_metrics(self, agent_id=None, session_id=None):
        return []


class _DummyAgentIdentity:
    def resolve_canonical_agent_id(self, value):
        return value


class DiagnosticsSurfaceSmokeTests(unittest.TestCase):
    def test_metrics_summary_endpoint_sets_kpi_headers_and_delegates(self):
        response = Response()
        with mock.patch.object(
            diagnostics_surface._srm,
            "build_metrics_summary_payload",
            return_value={"tenant": "all", "ok": True},
        ) as mocked:
            payload = asyncio.run(diagnostics_surface.get_metrics_summary(response, tenant="all"))

        mocked.assert_called_once_with("all")
        self.assertEqual(payload["ok"], True)
        self.assertEqual(response.headers["X-OmniMemora-Surface-Role"], "kpi")
        self.assertEqual(response.headers["X-OmniMemora-KPI-Source"], "/metrics/summary")


class StatusReadModelDiagnosticsHelperTests(unittest.TestCase):
    def test_build_health_payload_local_mode(self):
        status_read_model.configure_diagnostics_read_model(
            config_obj=_DummyConfig(),
            get_backend_fn=lambda: None,
            get_dedup_cache_fn=lambda: _DummyDedupCache(),
            rate_limiter=_DummyRateLimiter(),
            adapter_hostname="test-host",
            adapter_started_at="2026-04-22T00:00:00Z",
            agent_metrics_module=_DummyAgentMetrics(),
            agent_identity_module=_DummyAgentIdentity(),
            get_meter_fn=lambda request_id: None,
            support_schema_version="v1",
            support_error_catalog={},
        )

        payload = asyncio.run(status_read_model.build_health_payload(mode="local"))

        self.assertEqual(payload["mode"], "local")
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["interface_policy"]["product_entry_port"], 18011)
        self.assertEqual(payload["rate_limit"]["max_per_minute"], 60)
