import importlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "application"
REPO_ROOT = Path(__file__).resolve().parents[3]
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
    assert capsys.readouterr().out.strip() == "0.1.0-beta.1"


def test_cli_proxy_status_reports_unreachable_for_stopped_proxy(tmp_path, capsys):
    config_path = tmp_path / "config.json"
    token_intelligence.write_default_config(config_path)

    assert cli.main(["proxy", "status", "--config", str(config_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unreachable"
    assert payload["url"] == "http://127.0.0.1:18081/health"


def test_cli_doctor_attach_and_detach_are_profile_only(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    attach_dir = tmp_path / "agents"
    monkeypatch.setenv("OMNI_AUDIT_UPSTREAM_API_KEY", "secret-value-not-written")
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_ATTACH_DIR", str(attach_dir))
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 18081},
                "upstream": {
                    "base_url": "https://relay.example/v1",
                    "api_key_env": "OMNI_AUDIT_UPSTREAM_API_KEY",
                    "timeout_seconds": 120,
                },
                "privacy": {"content_mode": "metadata_only"},
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

    assert cli.main(["doctor", "--config", str(config_path)]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["config_valid"] is True
    assert doctor["upstream_api_key_env"] == "OMNI_AUDIT_UPSTREAM_API_KEY"
    assert doctor["upstream_api_key_present"] is True
    assert doctor["proxy_health"]["reachable"] is False
    assert "secret-value-not-written" not in json.dumps(doctor, sort_keys=True)

    assert cli.main(["attach", "openclaw", "--config", str(config_path), "--with-launcher"]) == 0
    profile = json.loads(capsys.readouterr().out)
    profile_path = attach_dir / "openclaw.json"
    env_path = attach_dir / "openclaw.env"
    launcher_path = attach_dir / "openclaw-launch.sh"
    written = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["status"] == "profile_written"
    assert profile["agent_config_mutated"] is False
    assert profile["proxy_base_url"] == "http://127.0.0.1:18081/v1"
    assert profile["launcher"]["script_path"] == str(launcher_path)
    assert written["client_headers"] == {"x-omni-agent-id": "openclaw"}
    assert env_path.exists()
    assert launcher_path.exists()
    assert "OPENAI_BASE_URL='http://127.0.0.1:18081/v1'" in env_path.read_text(encoding="utf-8")
    assert "secret-value-not-written" not in json.dumps(written, sort_keys=True)
    assert "secret-value-not-written" not in env_path.read_text(encoding="utf-8")

    assert cli.main(["attach", "claude_code", "--config", str(config_path), "--dry-run", "--with-launcher"]) == 0
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["target"] == "claude-code"
    assert dry_run["agent_id"] == "claude_code"
    assert dry_run["launcher"]["script_path"] == str(attach_dir / "claude-code-launch.sh")
    assert not (attach_dir / "claude-code.json").exists()
    assert not (attach_dir / "claude-code.env").exists()

    assert cli.main(["detach", "openclaw"]) == 0
    detached = json.loads(capsys.readouterr().out)
    assert detached["status"] == "detached"
    assert detached["agent_config_mutated"] is False
    assert detached["removed_launcher"] is True
    assert detached["removed_env"] is True
    assert not profile_path.exists()
    assert not env_path.exists()
    assert not launcher_path.exists()


def test_cli_snippets_are_copy_paste_only_and_do_not_store_secret(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OMNI_AUDIT_UPSTREAM_API_KEY", "secret-value-not-written")
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 18081},
                "upstream": {
                    "base_url": "https://relay.example/v1",
                    "api_key_env": "OMNI_AUDIT_UPSTREAM_API_KEY",
                    "timeout_seconds": 120,
                },
                "privacy": {"content_mode": "metadata_only"},
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

    assert cli.main(["snippets", "--list"]) == 0
    supported = json.loads(capsys.readouterr().out)
    assert "openai-sdk-python" in supported["supported_snippets"]
    assert "openclaw" in supported["supported_snippets"]

    assert cli.main(["snippets", "openai-sdk-python", "--config", str(config_path)]) == 0
    python_snippet = json.loads(capsys.readouterr().out)
    assert python_snippet["mutates_files"] is False
    assert python_snippet["stores_api_key_value"] is False
    assert "http://127.0.0.1:18081/v1" in python_snippet["content"]
    assert "OMNI_AUDIT_UPSTREAM_API_KEY" in python_snippet["content"]
    assert "secret-value-not-written" not in json.dumps(python_snippet, sort_keys=True)

    assert cli.main(["snippets", "openclaw", "--config", str(config_path)]) == 0
    openclaw_snippet = json.loads(capsys.readouterr().out)
    assert "attach openclaw --with-launcher" in openclaw_snippet["content"]
    assert openclaw_snippet["mutates_files"] is False


def test_cli_receipt_get_reads_metadata_only_receipt(tmp_path, monkeypatch, capsys):
    sqlite_path = tmp_path / "audit.sqlite3"
    monkeypatch.setenv("OMNIMEMORA_TOKEN_INTELLIGENCE_DB", str(sqlite_path))
    secret_prompt = "SECRET_PROMPT_NOT_IN_CLI_RECEIPT"
    usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}},
        usage_source="relay_reported",
    )
    event = token_intelligence.build_audit_event(
        request_id="req-cli-receipt",
        request_payload={"messages": [{"role": "user", "content": secret_prompt}]},
        response_payload={"id": "chatcmpl-cli", "usage": {"total_tokens": 5}},
        upstream_base_url="https://relay.example/v1",
        provider="local_proxy",
        model_requested="relay-model",
        model_reported="relay-model",
        usage=usage,
        latency_ms=12,
        status_code=200,
    )
    token_intelligence.record_audit_event(event)

    assert cli.main(["receipt", "get", event.audit_id]) == 0
    receipt = json.loads(capsys.readouterr().out)

    assert receipt["audit_id"] == event.audit_id
    assert receipt["usage"]["source"] == "relay_reported"
    assert secret_prompt not in json.dumps(receipt, sort_keys=True)


def test_cli_update_check_reads_metadata_without_download(tmp_path, capsys):
    metadata_path = tmp_path / "latest.json"
    metadata_path.write_text(
        json.dumps(
            {
                "product": "omnimemora-token-intelligence",
                "channel": "beta",
                "version": "0.1.0-beta.1",
                "minimum_supported_version": "0.1.0-beta.1",
                "force_update": False,
                "platforms": {
                    "darwin-arm64": {
                        "download_url": "https://doloclaw.com/download/file/token-intelligence/darwin-arm64",
                        "unsigned_beta": True,
                        "gatekeeper_note": "Manual Privacy & Security approval may be required during beta.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    token_intelligence.write_default_config(config_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["updates"]["metadata_url"] = metadata_path.as_uri()
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    assert cli.main(["update", "check", "--config", str(config_path)]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["latest_version"] == "0.1.0-beta.1"
    assert result["unsigned_beta"] is True
    assert "Privacy & Security" in result["gatekeeper_note"]
    assert "download_url" not in result


def test_cli_report_summary_and_potential_savings_are_metadata_only(tmp_path, capsys):
    sqlite_path = tmp_path / "audit.sqlite3"
    secret_prompt = "SECRET_REPORT_PROMPT_NOT_IN_CLI"
    usage = token_intelligence.normalize_openai_compatible_usage(
        {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        usage_source="relay_reported",
    )
    event = token_intelligence.build_audit_event(
        request_id="req-report",
        request_payload={"messages": [{"role": "user", "content": secret_prompt}]},
        response_payload={"id": "req-report"},
        upstream_base_url="https://relay.example/v1",
        provider="local_proxy",
        model_requested="relay-model",
        usage=usage,
        opportunities=[
            {
                "detector_id": "duplicate_context_v1",
                "category": "duplicate_context",
                "reason_code": "repeated_message_content",
                "token_estimate": 12,
                "potential_saving_tokens": 12,
                "item_count": 1,
                "severity": "medium",
                "source": "local_estimated",
                "confidence": "compatible_estimate",
            }
        ],
    )
    token_intelligence.record_audit_event(event, path=str(sqlite_path))

    assert cli.main(["report", "summary", "--db", str(sqlite_path), "--limit", "5000"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["window"] == {"bounded": True, "limit": 1000}
    assert summary["event_count"] == 1
    assert secret_prompt not in json.dumps(summary, sort_keys=True)

    assert cli.main(["report", "potential-savings", "--db", str(sqlite_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["potential_saving_tokens"] == 12
    assert report["top_opportunities"][0]["category"] == "duplicate_context"
    assert secret_prompt not in json.dumps(report, sort_keys=True)

    assert cli.main(["report", "top-requests", "--db", str(sqlite_path), "--limit", "5000"]) == 0
    top_requests = json.loads(capsys.readouterr().out)
    assert top_requests["window"] == {"bounded": True, "limit": 1000}
    assert top_requests["top_by_tokens"][0]["request_id"] == "req-report"
    assert top_requests["top_by_tokens"][0]["total_tokens"] == 15
    assert secret_prompt not in json.dumps(top_requests, sort_keys=True)


def test_local_package_builder_outputs_checksum_metadata_and_launcher(tmp_path):
    script = REPO_ROOT / "tools" / "token_intelligence" / "build_local_package.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--output-dir",
            str(tmp_path),
            "--version",
            "0.1.0-test",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    zip_path = Path(payload["zip"])
    metadata_path = Path(payload["metadata"])
    checksum_path = tmp_path / "SHA256SUMS.txt"
    assert zip_path.exists()
    assert metadata_path.exists()
    assert checksum_path.exists()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["version"] == "0.1.0-test"
    assert metadata["platforms"]["darwin-arm64"]["sha256"] == payload["sha256"]
    assert metadata["platforms"]["darwin-arm64"]["unsigned_beta"] is True

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        launcher_info = archive.getinfo("omni-token-audit-0.1.0-test-local/omni-token-audit")
    assert "omni-token-audit-0.1.0-test-local/omni-token-audit" in names
    assert "omni-token-audit-0.1.0-test-local/token_intelligence/cli.py" in names
    assert all("__pycache__" not in name for name in names)
    assert ((launcher_info.external_attr >> 16) & 0o111) != 0
    assert payload["sha256"] in checksum_path.read_text(encoding="utf-8")
