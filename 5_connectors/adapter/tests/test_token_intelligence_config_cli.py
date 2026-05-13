import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "application"
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_DIR))
token_intelligence = importlib.import_module("token_intelligence")
cli = importlib.import_module("token_intelligence.cli")


class _ClientSmokeUpstreamHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib handler API
        content_length = int(self.headers.get("content-length") or "0")
        body = self.rfile.read(content_length)
        self.server.state["last_path"] = self.path
        self.server.state["last_body"] = body
        self.server.state["last_authorization"] = self.headers.get("authorization")

        response_body = json.dumps(
            {
                "id": "chatcmpl-ti020-real-client",
                "object": "chat.completion",
                "model": "relay-model-reported",
                "choices": [{"message": {"role": "assistant", "content": "TI020_OK"}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12},
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, _format, *_args):
        return


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


def test_local_package_real_client_minimal_attach_flow(tmp_path):
    unzip = shutil.which("unzip")
    if unzip is None:
        pytest.skip("system unzip is required to validate executable-bit package unpacking")

    script = REPO_ROOT / "tools" / "token_intelligence" / "build_local_package.py"
    build_dir = tmp_path / "build"
    unpack_dir = tmp_path / "unpacked"
    home_dir = tmp_path / "home"
    attach_dir = tmp_path / "agents"
    db_path = tmp_path / "audit.sqlite3"
    proxy_port = _free_port()
    upstream = _start_client_smoke_upstream()
    proxy_process = None
    secret_value = "ti020-upstream-secret-not-persisted"
    try:
        build_result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output-dir",
                str(build_dir),
                "--version",
                "0.1.0-test",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        package_payload = json.loads(build_result.stdout)
        zip_path = Path(package_payload["zip"])
        subprocess.run([unzip, "-q", str(zip_path), "-d", str(unpack_dir)], check=True)
        package_dir = unpack_dir / "omni-token-audit-0.1.0-test-local"
        launcher = package_dir / "omni-token-audit"
        assert launcher.exists()
        assert launcher.stat().st_mode & 0o111

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "server": {"host": "127.0.0.1", "port": proxy_port},
                    "upstream": {
                        "base_url": f"{_base_url(upstream)}/v1",
                        "api_key_env": "TI020_UPSTREAM_KEY",
                        "timeout_seconds": 5,
                    },
                    "privacy": {"content_mode": "metadata_only"},
                    "audit": {"enabled": True, "fail_open": True},
                    "updates": {
                        "enabled": False,
                        "metadata_url": "https://doloclaw.com/releases/token-intelligence/latest.json",
                        "channel": "beta",
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        env = {
            **os_environ_without_pythonpath(),
            "HOME": str(home_dir),
            "TI020_UPSTREAM_KEY": secret_value,
            "OMNIMEMORA_TOKEN_INTELLIGENCE_DB": str(db_path),
            "OMNIMEMORA_TOKEN_INTELLIGENCE_ATTACH_DIR": str(attach_dir),
        }

        attach_result = subprocess.run(
            [str(launcher), "attach", "openclaw", "--config", str(config_path), "--with-launcher"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(package_dir),
        )
        attach_payload = json.loads(attach_result.stdout)
        assert attach_payload["status"] == "profile_written"
        assert attach_payload["proxy_base_url"] == f"http://127.0.0.1:{proxy_port}/v1"
        assert attach_payload["agent_config_mutated"] is False
        assert (attach_dir / "openclaw-launch.sh").exists()

        proxy_process = subprocess.Popen(
            [str(launcher), "proxy", "start", "--config", str(config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(package_dir),
        )
        _wait_for_health(f"http://127.0.0.1:{proxy_port}/health", proxy_process)

        status, response_body, response_headers = _post_real_client_json(
            f"http://127.0.0.1:{proxy_port}/v1/chat/completions",
            {
                "model": "relay-model-requested",
                "messages": [{"role": "user", "content": "TI020_REAL_CLIENT_PROMPT"}],
            },
            headers={
                "authorization": "Bearer client-placeholder",
                "x-omni-agent-id": "openclaw",
                "x-omni-workflow-tag": "coding",
            },
        )
        response_payload = json.loads(response_body)
        audit_id = response_headers["x-omni-token-audit-id"]

        receipt_result = subprocess.run(
            [str(launcher), "receipt", "get", audit_id],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(package_dir),
        )
        summary_result = subprocess.run(
            [str(launcher), "report", "summary", "--limit", "100"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(package_dir),
        )
        top_result = subprocess.run(
            [str(launcher), "report", "top-requests", "--limit", "100"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(package_dir),
        )
        detach_result = subprocess.run(
            [str(launcher), "detach", "openclaw"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(package_dir),
        )
        receipt = json.loads(receipt_result.stdout)
        summary = json.loads(summary_result.stdout)
        top_requests = json.loads(top_result.stdout)
        detach_payload = json.loads(detach_result.stdout)
    finally:
        if proxy_process is not None:
            _stop_process(proxy_process)
        _stop_server(upstream)

    assert status == 200
    assert response_payload["choices"][0]["message"]["content"] == "TI020_OK"
    assert upstream.state["last_path"] == "/v1/chat/completions"
    assert upstream.state["last_authorization"] == f"Bearer {secret_value}"
    assert json.loads(upstream.state["last_body"])["model"] == "relay-model-requested"
    assert receipt["usage"]["source"] == "relay_reported"
    assert receipt["usage"]["total_tokens"] == 12
    assert summary["event_count"] == 1
    assert summary["usage"]["total_tokens"] == 12
    assert summary["top_agents"][0]["agent_id"] == "openclaw"
    assert summary["top_workflows"][0]["workflow_tag"] == "coding"
    assert top_requests["top_by_tokens"][0]["request_id"] == "chatcmpl-ti020-real-client"
    assert top_requests["top_by_tokens"][0]["agent_id"] == "openclaw"
    assert top_requests["top_by_tokens"][0]["workflow_tag"] == "coding"
    assert detach_payload["status"] == "detached"
    assert detach_payload["removed_launcher"] is True
    assert not (attach_dir / "openclaw-launch.sh").exists()
    serialized_outputs = "\n".join(
        [
            attach_result.stdout,
            receipt_result.stdout,
            summary_result.stdout,
            top_result.stdout,
            detach_result.stdout,
            config_path.read_text(encoding="utf-8"),
        ]
    )
    assert secret_value not in serialized_outputs
    assert "TI020_REAL_CLIENT_PROMPT" not in serialized_outputs


def os_environ_without_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _start_client_smoke_upstream():
    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), _ClientSmokeUpstreamHandler)
    server.daemon_threads = True
    server.state = {}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.thread = thread
    return server


def _stop_server(server):
    server.shutdown()
    server.server_close()
    server.thread.join(timeout=2)


def _base_url(server) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 5
    last_error = ""
    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(f"proxy exited early: stdout={stdout} stderr={stderr}")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if int(response.status) == 200:
                    return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.05)
    raise AssertionError(f"proxy health did not become ready: {last_error}")


def _post_real_client_json(url: str, payload: dict, *, headers: dict[str, str] | None = None):
    request_headers = {"content-type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return (
            int(response.status),
            response.read(),
            {key.lower(): value for key, value in response.headers.items()},
        )


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=3)
