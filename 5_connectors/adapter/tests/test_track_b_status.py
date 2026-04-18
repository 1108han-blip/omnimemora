import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

status_api = importlib.import_module("5_connectors.adapter.status_api")
track_b_status = importlib.import_module("5_connectors.adapter.track_b_status")
BackendHealth = importlib.import_module("5_connectors.adapter.backends.base").BackendHealth


class TrackBStatusTests(unittest.TestCase):
    def test_build_track_b_status_healthy(self) -> None:
        payload = track_b_status.build_track_b_status(
            backend_health=BackendHealth(healthy=True, backend_type="omnimemora_runtime"),
            routing_enabled=True,
        )
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["gateway_health"], "healthy")
        self.assertEqual(payload["capability_health"], "healthy")
        self.assertTrue(payload["routing_effective"])
        self.assertFalse(payload["user_action_required"])
        self.assertEqual(payload["recommended_action"], "none")
        self.assertIsNone(payload["error_code"])

    def test_build_track_b_status_degraded_capability(self) -> None:
        payload = track_b_status.build_track_b_status(
            backend_health=BackendHealth(
                healthy=False,
                backend_type="omnimemora_runtime",
                details={"status": "All connection attempts failed"},
            ),
            routing_enabled=True,
        )
        self.assertEqual(payload["status"], "degraded-capability")
        self.assertEqual(payload["gateway_health"], "healthy")
        self.assertEqual(payload["capability_health"], "degraded")
        self.assertFalse(payload["routing_effective"])
        self.assertFalse(payload["user_action_required"])
        self.assertEqual(payload["recommended_action"], "degrade_to_passthrough")
        self.assertEqual(payload["error_code"], "all_connection_attempts_failed")

    def test_build_track_b_status_user_decision_override(self) -> None:
        payload = track_b_status.build_track_b_status(
            backend_health=BackendHealth(healthy=False, backend_type="omnimemora_runtime"),
            routing_enabled=True,
            override={"status": "user-decision-required"},
        )
        self.assertEqual(payload["status"], "user-decision-required")
        self.assertEqual(payload["gateway_health"], "unhealthy")
        self.assertTrue(payload["user_action_required"])
        self.assertFalse(payload["routing_effective"])
        self.assertEqual(payload["recommended_action"], "disable_route_or_uninstall")

    def test_read_status_override_uses_file_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnimemora-track-b-status-") as tmpdir:
            path = Path(tmpdir) / "track_b_status.json"
            path.write_text(
                json.dumps({"status": "recovering-gateway", "error_code": "runtime_restart"}),
                encoding="utf-8",
            )
            with mock.patch.dict("os.environ", {"OMNIMEMORA_TRACK_B_STATUS_PATH": str(path)}, clear=False):
                payload = track_b_status.read_status_override()
        self.assertEqual(payload, {"status": "recovering-gateway", "error_code": "runtime_restart"})

    def test_write_status_override_sanitizes_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnimemora-track-b-status-") as tmpdir:
            path = Path(tmpdir) / "track_b_status.json"
            with mock.patch.dict("os.environ", {"OMNIMEMORA_TRACK_B_STATUS_PATH": str(path)}, clear=False):
                saved = track_b_status.write_status_override(
                    {
                        "status": "user-decision-required",
                        "user_action_required": True,
                        "unknown_field": "ignored",
                    }
                )
                payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"status": "user-decision-required", "user_action_required": True})
        self.assertEqual(payload, {"status": "user-decision-required", "user_action_required": True})


class TrackBStatusApiTests(unittest.TestCase):
    def test_proxy_system_status_endpoint(self) -> None:
        app = FastAPI()
        app.include_router(status_api.router)

        async def fake_build_system_status():
            return {"status": "degraded-capability", "routing_effective": False}

        with mock.patch.object(status_api, "_build_system_status", side_effect=fake_build_system_status):
            client = TestClient(app)
            response = client.get("/proxy/system-status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded-capability")

    def test_proxy_status_can_include_system_status(self) -> None:
        app = FastAPI()
        app.include_router(status_api.router)

        async def fake_build_system_status():
            return {"status": "healthy"}

        fake_proxy_store = mock.Mock()
        fake_proxy_store.summarize_agent_status.return_value = {"openclaw": {"connected": True}}

        original_import_module = status_api.importlib.import_module

        def fake_import_module(name: str):
            if name == "5_connectors.adapter.proxy_store":
                return fake_proxy_store
            return original_import_module(name)

        with mock.patch.object(status_api, "_build_system_status", side_effect=fake_build_system_status):
            with mock.patch.object(status_api.importlib, "import_module", side_effect=fake_import_module):
                client = TestClient(app)
                response = client.get("/proxy/status?include_system=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["system_status"]["status"], "healthy")
        self.assertEqual(response.json()["agents"]["openclaw"]["connected"], True)

    def test_override_endpoint_requires_internal_token(self) -> None:
        app = FastAPI()
        app.include_router(status_api.router)
        client = TestClient(app)
        response = client.post("/proxy/system-status/override", json={"status": "recovering-gateway"})
        self.assertEqual(response.status_code, 500)

    def test_override_endpoint_writes_and_clears_status(self) -> None:
        app = FastAPI()
        app.include_router(status_api.router)

        async def fake_build_system_status():
            return {"status": "recovering-gateway", "user_action_required": False}

        with tempfile.TemporaryDirectory(prefix="omnimemora-track-b-status-api-") as tmpdir:
            path = Path(tmpdir) / "track_b_status.json"
            env = {
                "OMNIMEMORA_TRACK_B_STATUS_PATH": str(path),
                "OMNIMEMORA_INTERNAL_API_TOKEN": "secret-token",
            }
            with mock.patch.dict("os.environ", env, clear=False):
                with mock.patch.object(status_api, "_build_system_status", side_effect=fake_build_system_status):
                    client = TestClient(app)
                    set_response = client.post(
                        "/proxy/system-status/override",
                        headers={"X-Internal-Token": "secret-token"},
                        json={"status": "recovering-gateway", "recommended_action": "wait_for_recovery"},
                    )
                    clear_response = client.delete(
                        "/proxy/system-status/override",
                        headers={"X-Internal-Token": "secret-token"},
                    )

        self.assertEqual(set_response.status_code, 200)
        self.assertEqual(clear_response.status_code, 200)
        self.assertFalse(path.exists())
