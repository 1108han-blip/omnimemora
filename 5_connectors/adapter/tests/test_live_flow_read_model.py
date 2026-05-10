import importlib
import unittest
from unittest import mock


status_read_model = importlib.import_module("5_connectors.adapter.application.status_read_model")
metrics_service = importlib.import_module("5_connectors.adapter.metrics_service")


class LiveFlowReadModelTests(unittest.TestCase):
    def test_agents_live_includes_recent_codex_meter_records(self) -> None:
        class _AgentMetrics:
            @staticmethod
            def get_live_agents(window_minutes=30):
                return []

        recent = [
            {
                "request_id": "req-codex-live",
                "agent": "codex_cli",
                "family_id": "codex_cli",
                "session_id": "session-a",
                "workspace_id": "workspace-a",
                "timestamp": "2099-05-10T06:14:42Z",
                "request_class": "task_non_value",
                "real_input_saved_tokens": 0,
            }
        ]

        with mock.patch.object(status_read_model, "_diag_agent_metrics_module", _AgentMetrics()):
            with mock.patch.object(metrics_service, "get_recent_requests", return_value=recent):
                payload = status_read_model.build_agents_live_payload(window_minutes=120)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["agents"][0]["agent_id"], "codex_cli")
        self.assertEqual(payload["agents"][0]["session_id"], "session-a")
        self.assertEqual(payload["agents"][0]["request_count"], 1)
        self.assertEqual(payload["agents"][0]["integration_type"], "llm_proxy_meter")


if __name__ == "__main__":
    unittest.main()
