import importlib
import unittest

UsageReport = importlib.import_module("5_connectors.adapter.cloud.models").UsageReport


class TestCloudUsageSchema(unittest.TestCase):
    def test_usage_report_minimal_schema_excludes_tenant(self):
        usage = UsageReport(
            request_id="req-1",
            route="/memory/query",
            version="2.2.0",
            saved_tokens=12,
            savings_ratio=0.4,
            optimization_enabled=True,
            error_code=None,
            timestamp="2026-04-18T00:00:00Z",
        )

        payload = usage.model_dump()

        self.assertNotIn("tenant", payload)
        self.assertEqual(payload["route"], "/memory/query")
        self.assertEqual(payload["version"], "2.2.0")
        self.assertEqual(payload["saved_tokens"], 12)
        self.assertEqual(payload["optimization_enabled"], True)


if __name__ == "__main__":
    unittest.main()
