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
    def test_get_agents_control_delegates_read_model(self) -> None:
        cards = [
            {
                "family_id": "openclaw",
                "display_name": "OpenClaw",
                "installed": True,
                "routing_enabled": False,
                "detected": True,
                "active": False,
                "health_state": "healthy",
                "message": "",
            }
        ]
        system_status = {"status": "healthy"}

        async def fake_build_cards():
            return cards

        async def fake_build_system_status():
            return system_status

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=fake_build_system_status):
                payload = asyncio.run(agent_control_api.get_agents_control())

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["agents"][0]["family_id"], "openclaw")
        self.assertEqual(payload["system_status"]["status"], "healthy")

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

            async def fake_build_cards():
                routing_enabled = agent_routing_state.routing_enabled("openclaw")
                return [
                    {
                        "family_id": "openclaw",
                        "display_name": "OpenClaw",
                        "installed": True,
                        "routing_enabled": routing_enabled,
                        "detected": True,
                        "active": routing_enabled,
                        "health_state": "healthy",
                        "message": "",
                    }
                ]

            with mock.patch.object(agent_routing_state, "_agent_modes_path", return_value=path):
                agent_routing_state.reload_agent_modes()
                with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_build_cards):
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
        async def fake_build_cards():
            return [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": "",
                }
            ]

        async def fake_build_system_status():
            return {"status": "healthy"}

        with tempfile.TemporaryDirectory(prefix="omnimemora-agent-control-") as tmpdir:
            path = Path(tmpdir) / "agent_modes.json"
            path.write_text(
                json.dumps({"per_agent_modes": {"openclaw": "off"}, "default_mode": "off"}),
                encoding="utf-8",
            )
            with mock.patch.object(agent_routing_state, "_agent_modes_path", return_value=path):
                agent_routing_state.reload_agent_modes()
                with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_build_cards):
                    with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=fake_build_system_status):
                        payload = asyncio.run(agent_control_api.get_agents_control())

        self.assertIn("system_status", payload)
        self.assertEqual(payload["system_status"]["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
