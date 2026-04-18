import asyncio
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

agent_control_api = importlib.import_module("5_connectors.adapter.agent_control_api")
agent_routing_state = importlib.import_module("5_connectors.adapter.agent_routing_state")


class AgentControlApiTests(unittest.TestCase):
    def test_runtime_health_state_accepts_ok(self) -> None:
        async def fake_runtime_request(method: str, path: str, payload=None):
            self.assertEqual(method, "GET")
            self.assertEqual(path, "/health")
            return {"status": "ok"}

        with mock.patch.object(agent_control_api, "_runtime_request", side_effect=fake_runtime_request):
            result = asyncio.run(agent_control_api._runtime_health_state())

        self.assertEqual(result, "healthy")

    def test_runtime_health_state_degrades_unknown_status(self) -> None:
        async def fake_runtime_request(method: str, path: str, payload=None):
            return {"status": "warming"}

        with mock.patch.object(agent_control_api, "_runtime_request", side_effect=fake_runtime_request):
            result = asyncio.run(agent_control_api._runtime_health_state())

        self.assertEqual(result, "degraded")

    def test_enable_disable_persists_routing_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnimemora-agent-control-") as tmpdir:
            path = Path(tmpdir) / "agent_modes.json"
            path.write_text(
                json.dumps(
                    {
                        "per_agent_modes": {
                            "openclaw": "off",
                        },
                        "default_mode": "off",
                    }
                ),
                encoding="utf-8",
            )

            async def fake_runtime_request(method: str, path_value: str, payload=None):
                if path_value == "/health":
                    return {"status": "ok"}
                if path_value == "/agents/control":
                    return {
                        "agents": [
                            {
                                "family_id": "openclaw",
                                "display_name": "OpenClaw",
                                "installed": True,
                                "detected": True,
                                "backup_available": False,
                                "message": "",
                            }
                        ]
                    }
                raise AssertionError(f"unexpected runtime request: {method} {path_value}")

            with mock.patch.object(agent_routing_state, "_agent_modes_path", return_value=path):
                agent_routing_state.reload_agent_modes()
                with mock.patch.object(agent_control_api, "_runtime_request", side_effect=fake_runtime_request):
                    with mock.patch.object(agent_control_api, "_build_metrics_index", return_value={}):
                        enabled = asyncio.run(
                            agent_control_api.enable_agent_control(
                                agent_control_api.AgentControlRequest(family_id="openclaw")
                            )
                        )
                        self.assertTrue(enabled["routing_enabled"])
                        saved = json.loads(path.read_text(encoding="utf-8"))
                        self.assertEqual(saved["per_agent_modes"]["openclaw"], "force_if_possible")

                        disabled = asyncio.run(
                            agent_control_api.disable_agent_control(
                                agent_control_api.AgentControlRequest(family_id="openclaw")
                            )
                        )
                        self.assertFalse(disabled["routing_enabled"])
                        saved = json.loads(path.read_text(encoding="utf-8"))
                        self.assertEqual(saved["per_agent_modes"]["openclaw"], "off")

    def test_get_agents_control_includes_system_status(self) -> None:
        async def fake_runtime_request(method: str, path_value: str, payload=None):
            if path_value == "/health":
                return {"status": "ok"}
            if path_value == "/agents/control":
                return {
                    "agents": [
                        {
                            "family_id": "openclaw",
                            "display_name": "OpenClaw",
                            "installed": True,
                            "detected": True,
                            "backup_available": False,
                            "message": "",
                        }
                    ]
                }
            raise AssertionError(f"unexpected runtime request: {method} {path_value}")

        with tempfile.TemporaryDirectory(prefix="omnimemora-agent-control-") as tmpdir:
            path = Path(tmpdir) / "agent_modes.json"
            path.write_text(
                json.dumps({"per_agent_modes": {"openclaw": "off"}, "default_mode": "off"}),
                encoding="utf-8",
            )
            with mock.patch.object(agent_routing_state, "_agent_modes_path", return_value=path):
                agent_routing_state.reload_agent_modes()
                with mock.patch.object(agent_control_api, "_runtime_request", side_effect=fake_runtime_request):
                    with mock.patch.object(agent_control_api, "_build_metrics_index", return_value={}):
                        payload = asyncio.run(agent_control_api.get_agents_control())

        self.assertIn("system_status", payload)
        self.assertEqual(payload["system_status"]["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
