import asyncio
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.requests import Request

agent_control_api = importlib.import_module("5_connectors.adapter.agent_control_api")
agent_routing_state = importlib.import_module("5_connectors.adapter.agent_routing_state")
control_snapshot_cache = importlib.import_module("5_connectors.adapter.application.control_snapshot_cache")
data_lifecycle_api = importlib.import_module("5_connectors.adapter.data_lifecycle_api")


class AgentControlApiTests(unittest.TestCase):
    def setUp(self) -> None:
        agent_control_api._invalidate_agents_control_snapshot()

    def tearDown(self) -> None:
        agent_control_api._invalidate_agents_control_snapshot()

    def _request(self, *, origin: str = "", client_host: str = "127.0.0.1") -> Request:
        headers = []
        if origin:
            headers.append((b"origin", origin.encode("utf-8")))
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/agents/control/disable",
                "headers": headers,
                "client": (client_host, 49152),
            }
        )

    def test_control_action_rejects_untrusted_browser_origin(self) -> None:
        with self.assertRaises(Exception) as ctx:
            agent_control_api._require_control_action_authorization(
                self._request(origin="https://example.com")
            )
        self.assertEqual(getattr(ctx.exception, "status_code", None), 403)

    def test_control_action_allows_trusted_local_origin(self) -> None:
        agent_control_api._require_control_action_authorization(
            self._request(origin="http://127.0.0.1:5173")
        )

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
        self.assertEqual(set(payload.keys()), {"agents", "count", "system_status"})

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
                            agent_control_api.AgentControlRequest(family_id="openclaw"),
                            self._request(origin="http://127.0.0.1:5173"),
                        )
                    )
                    self.assertTrue(enabled["routing_enabled"])
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(saved["per_agent_modes"]["openclaw"], "force_if_possible")

                    disabled = asyncio.run(
                        agent_control_api.disable_agent_control(
                            agent_control_api.AgentControlRequest(family_id="openclaw"),
                            self._request(origin="http://127.0.0.1:5173"),
                        )
                    )
                    self.assertFalse(disabled["routing_enabled"])
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(saved["per_agent_modes"]["openclaw"], "off")

    def test_repair_codex_uses_managed_profile_message(self) -> None:
        async def fake_runtime_request(method, path, payload):
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/agents/control/install")
            self.assertEqual(payload, {"family_id": "codex_cli"})
            return {"ok": True}

        async def fake_build_cards():
            return [
                {
                    "family_id": "codex_cli",
                    "display_name": "Codex",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": "",
                }
            ]

        with mock.patch.object(agent_control_api, "_runtime_request", side_effect=fake_runtime_request):
            with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_build_cards):
                repaired = asyncio.run(
                    agent_control_api.repair_agent_control(
                        agent_control_api.AgentControlRequest(family_id="codex_cli"),
                        self._request(origin="http://127.0.0.1:5173"),
                    )
                )

        self.assertEqual(
            repaired["message"],
            "managed Codex profile repaired; official Codex config was not modified",
        )

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

    def test_get_agents_control_reuses_snapshot_within_ttl(self) -> None:
        calls = {"cards": 0, "status": 0}

        async def fake_build_cards():
            calls["cards"] += 1
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
            calls["status"] += 1
            return {"status": "healthy"}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=fake_build_system_status):
                first = asyncio.run(agent_control_api.get_agents_control())
                second = asyncio.run(agent_control_api.get_agents_control())

        self.assertEqual(first, second)
        self.assertEqual(calls["cards"], 1)
        self.assertEqual(calls["status"], 1)

    def test_get_agents_control_rebuilds_after_ttl_expiry(self) -> None:
        calls = {"cards": 0, "status": 0}

        async def fake_build_cards():
            calls["cards"] += 1
            return [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": f"run-{calls['cards']}",
                }
            ]

        async def fake_build_system_status():
            calls["status"] += 1
            return {"status": "healthy", "run": calls["status"]}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=fake_build_system_status):
                first = asyncio.run(agent_control_api.get_agents_control())
                control_snapshot_cache.force_expire_agents_control_snapshot_for_test()
                second = asyncio.run(agent_control_api.get_agents_control())

        self.assertNotEqual(first["agents"][0]["message"], second["agents"][0]["message"])
        self.assertEqual(calls["cards"], 2)
        self.assertEqual(calls["status"], 2)

    def test_rescan_invalidates_snapshot_cache(self) -> None:
        async def warm_build_cards():
            return [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": "warm",
                }
            ]

        async def warm_status():
            return {"status": "healthy"}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=warm_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=warm_status):
                _ = asyncio.run(agent_control_api.get_agents_control())
                _ = asyncio.run(agent_control_api.get_agents_control())

        action_cards = [
            [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": "before",
                }
            ],
            [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": "after",
                }
            ],
        ]

        async def fake_rescan_build_cards():
            return action_cards.pop(0)

        async def fake_runtime_request(_method, _path, _payload):
            return {"ok": True}

        async def fake_rescan_system_status():
            return {"status": "healthy"}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=fake_rescan_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=fake_rescan_system_status):
                with mock.patch.object(agent_control_api, "_runtime_request", side_effect=fake_runtime_request):
                    _ = asyncio.run(agent_control_api.rescan_agents_control(self._request(origin="http://127.0.0.1:5173")))

        after_calls = {"cards": 0, "status": 0}

        async def post_build_cards():
            after_calls["cards"] += 1
            return [
                {
                    "family_id": "openclaw",
                    "display_name": "OpenClaw",
                    "installed": True,
                    "routing_enabled": False,
                    "detected": True,
                    "active": False,
                    "health_state": "healthy",
                    "message": "post-rescan",
                }
            ]

        async def post_status():
            after_calls["status"] += 1
            return {"status": "healthy"}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=post_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=post_status):
                _ = asyncio.run(agent_control_api.get_agents_control())

        self.assertEqual(after_calls["cards"], 1)
        self.assertEqual(after_calls["status"], 1)

    def test_disable_invalidates_snapshot_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnimemora-agent-control-") as tmpdir:
            path = Path(tmpdir) / "agent_modes.json"
            path.write_text(
                json.dumps({"per_agent_modes": {"openclaw": "force_if_possible"}, "default_mode": "off"}),
                encoding="utf-8",
            )

            async def warm_build_cards():
                return [
                    {
                        "family_id": "openclaw",
                        "display_name": "OpenClaw",
                        "installed": True,
                        "routing_enabled": True,
                        "detected": True,
                        "active": True,
                        "health_state": "healthy",
                        "message": "",
                    }
                ]

            async def warm_status():
                return {"status": "healthy"}

            with mock.patch.object(agent_routing_state, "_agent_modes_path", return_value=path):
                agent_routing_state.reload_agent_modes()
                with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=warm_build_cards):
                    with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=warm_status):
                        _ = asyncio.run(agent_control_api.get_agents_control())
                        _ = asyncio.run(agent_control_api.get_agents_control())

                async def disable_build_cards():
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

                with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=disable_build_cards):
                    _ = asyncio.run(
                        agent_control_api.disable_agent_control(
                            agent_control_api.AgentControlRequest(family_id="openclaw"),
                            self._request(origin="http://127.0.0.1:5173"),
                        )
                    )

                after_calls = {"cards": 0, "status": 0}

                async def post_build_cards():
                    after_calls["cards"] += 1
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

                async def post_status():
                    after_calls["status"] += 1
                    return {"status": "healthy"}

                with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=post_build_cards):
                    with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=post_status):
                        _ = asyncio.run(agent_control_api.get_agents_control())

                self.assertEqual(after_calls["cards"], 1)
                self.assertEqual(after_calls["status"], 1)

    def test_manual_refresh_success_invalidates_snapshot_cache(self) -> None:
        warm_calls = {"cards": 0, "status": 0}

        async def warm_build_cards():
            warm_calls["cards"] += 1
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

        async def warm_status():
            warm_calls["status"] += 1
            return {"status": "healthy"}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=warm_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=warm_status):
                _ = asyncio.run(agent_control_api.get_agents_control())
                _ = asyncio.run(agent_control_api.get_agents_control())

        self.assertEqual(warm_calls["cards"], 1)
        self.assertEqual(warm_calls["status"], 1)

        class FakeManager:
            def __init__(self, *, policy):
                self.policy = policy

            def run_once(self, trigger: str):
                return {
                    "cycle_id": "cycle-manual-refresh",
                    "trigger": trigger,
                    "status": "success",
                    "error": None,
                }

        with mock.patch.object(
            data_lifecycle_api._maintenance_manager_mod, "MaintenanceManager", side_effect=FakeManager
        ):
            _ = asyncio.run(data_lifecycle_api.post_data_lifecycle_manual_refresh())

        after_calls = {"cards": 0, "status": 0}

        async def after_build_cards():
            after_calls["cards"] += 1
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

        async def after_status():
            after_calls["status"] += 1
            return {"status": "healthy"}

        with mock.patch.object(agent_control_api._srm, "build_control_cards", side_effect=after_build_cards):
            with mock.patch.object(agent_control_api._srm, "build_system_status", side_effect=after_status):
                _ = asyncio.run(agent_control_api.get_agents_control())

        self.assertEqual(after_calls["cards"], 1)
        self.assertEqual(after_calls["status"], 1)


if __name__ == "__main__":
    unittest.main()
