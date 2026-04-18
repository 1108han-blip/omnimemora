import importlib
import os
import sys
import unittest
from unittest.mock import patch


class TestCloudConfigConsent(unittest.TestCase):
    def _load_module(self):
        sys.modules.pop("5_connectors.adapter.config", None)
        return importlib.import_module("5_connectors.adapter.config")

    def test_pure_local_mode_defaults_cloud_and_usage_reporting_off(self):
        with patch.dict(
            os.environ,
            {
                "CLOUD_ENABLED": "false",
                "OMNIMEMORA_CLOUD_POLICY_UPDATES_ENABLED": "false",
            },
            clear=False,
        ):
            os.environ.pop("CLOUD_USAGE_REPORT_ENABLED", None)
            config_module = self._load_module()
            cloud = config_module.CloudIntegrationConfig()

        self.assertFalse(cloud.enabled)
        self.assertFalse(cloud.usage_report_enabled)

    def test_cloud_policy_updates_enable_minimal_usage_reporting_by_default(self):
        with patch.dict(
            os.environ,
            {
                "OMNIMEMORA_CLOUD_POLICY_UPDATES_ENABLED": "true",
            },
            clear=False,
        ):
            os.environ.pop("CLOUD_USAGE_REPORT_ENABLED", None)
            config_module = self._load_module()
            cloud = config_module.CloudIntegrationConfig()

        self.assertTrue(cloud.enabled)
        self.assertTrue(cloud.usage_report_enabled)

    def test_explicit_usage_override_can_disable_reporting(self):
        with patch.dict(
            os.environ,
            {
                "OMNIMEMORA_CLOUD_POLICY_UPDATES_ENABLED": "true",
                "CLOUD_USAGE_REPORT_ENABLED": "false",
            },
            clear=False,
        ):
            config_module = self._load_module()
            cloud = config_module.CloudIntegrationConfig()

        self.assertTrue(cloud.enabled)
        self.assertFalse(cloud.usage_report_enabled)


if __name__ == "__main__":
    unittest.main()
