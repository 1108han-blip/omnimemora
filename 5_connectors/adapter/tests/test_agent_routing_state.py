import json
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

agent_routing_state = importlib.import_module("5_connectors.adapter.agent_routing_state")


class AgentRoutingStateTests(unittest.TestCase):
    def test_set_family_routing_enabled_persists_force_and_off(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnimemora-agent-routing-") as tmpdir:
            path = Path(tmpdir) / "agent_modes.json"
            path.write_text(json.dumps({"per_agent_modes": {}, "default_mode": "off"}), encoding="utf-8")

            with mock.patch.object(agent_routing_state, "_agent_modes_path", return_value=path):
                agent_routing_state.reload_agent_modes()
                self.assertFalse(agent_routing_state.routing_enabled("codex_cli"))

                agent_routing_state.set_family_routing_enabled("codex_cli", True)
                self.assertTrue(agent_routing_state.routing_enabled("codex_cli"))

                saved = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(saved["per_agent_modes"]["codex_cli"], "force_if_possible")

                agent_routing_state.set_family_routing_enabled("codex_cli", False)
                self.assertFalse(agent_routing_state.routing_enabled("codex_cli"))

                saved = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(saved["per_agent_modes"]["codex_cli"], "off")


if __name__ == "__main__":
    unittest.main()
