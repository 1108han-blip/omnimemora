import importlib
import json
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "application"
sys.path.insert(0, str(APP_DIR))
token_intelligence = importlib.import_module("token_intelligence")
cli = importlib.import_module("token_intelligence.cli")


def test_default_config_write_does_not_store_raw_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNI_AUDIT_UPSTREAM_API_KEY", "secret-value-should-not-be-written")
    config_path = tmp_path / "config.json"

    token_intelligence.write_default_config(config_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["upstream"]["api_key_env"] == "OMNI_AUDIT_UPSTREAM_API_KEY"
    assert "secret-value-should-not-be-written" not in config_path.read_text(encoding="utf-8")
    assert payload["privacy"]["content_mode"] == "metadata_only"
    assert payload["privacy"]["store_raw_prompt"] is False
    assert payload["privacy"]["store_raw_response"] is False


def test_config_resolves_api_key_from_environment_without_persisting_it(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 18081},
                "upstream": {
                    "base_url": "https://relay.example/v1",
                    "api_key_env": "TEST_UPSTREAM_KEY",
                    "timeout_seconds": 5,
                },
                "privacy": {
                    "content_mode": "metadata_only",
                    "store_raw_prompt": False,
                    "store_raw_response": False,
                },
                "audit": {"enabled": True, "fail_open": True},
                "updates": {
                    "enabled": True,
                    "metadata_url": "https://doloclaw.com/releases/token-intelligence/latest.json",
                    "channel": "beta",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_UPSTREAM_KEY", "resolved-secret")

    config = token_intelligence.load_config(config_path)
    local_proxy_config = config.to_local_proxy_config()

    assert config.resolved_upstream_api_key() == "resolved-secret"
    assert local_proxy_config.upstream_api_key == "resolved-secret"
    assert "resolved-secret" not in config_path.read_text(encoding="utf-8")


def test_invalid_config_blocks_port_open_before_proxy_creation():
    config = token_intelligence.TokenIntelligenceConfig(
        server=token_intelligence.ServerConfig(host="0.0.0.0", port=18081),
    )

    with pytest.raises(ValueError, match="server.host"):
        config.to_local_proxy_config()


def test_full_content_config_is_rejected():
    config = token_intelligence.TokenIntelligenceConfig(
        privacy=token_intelligence.PrivacyConfig(content_mode="full_content"),
    )

    with pytest.raises(ValueError, match="metadata_only"):
        token_intelligence.validate_config(config)


def test_cli_init_and_version(tmp_path, capsys):
    config_path = tmp_path / "cli-config.json"

    assert cli.main(["init", "--config", str(config_path)]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["status"] == "created"
    assert Path(created["config_path"]) == config_path
    assert config_path.exists()

    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == "0.1.0-dev"


def test_cli_proxy_status_reports_unreachable_for_stopped_proxy(tmp_path, capsys):
    config_path = tmp_path / "config.json"
    token_intelligence.write_default_config(config_path)

    assert cli.main(["proxy", "status", "--config", str(config_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unreachable"
    assert payload["url"] == "http://127.0.0.1:18081/health"
