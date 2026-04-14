"""Formal doctor tool for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ov_enterprise_common import (
    BASELINE_CONTAINERS,
    CRITICAL_CONTAINERS,
    DEFAULT_ADAPTER_URL,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_COMPATIBILITY_REPORT,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_EXPECTED_OPENCLAW_VERSION,
    DEFAULT_EXPECTED_PLUGIN_BASE_URL,
    DEFAULT_MEMORY_ADAPTER_DIR,
    DEFAULT_MIN_PLUGIN_TIMEOUT_MS,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_OPENCLAW_CONFIG_DIR,
    DEFAULT_SUPPORTED_OPENCLAW_VERSIONS,
    DEFAULT_VERIFY_REPORT,
    DEFAULT_OPENVIKING_SOURCE,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_PLUGIN_DIR,
    ResultRecord,
    classify_support_level,
    docker_names,
    docker_networks,
    evaluate_openclaw_version_policy,
    extract_request_id,
    http_json,
    http_json_with_meta,
    json_load,
    make_run_id,
    monotonic_ms,
    path_writable,
    record_ids_by_status,
    render_records,
    report_metadata,
    resolve_known_agents,
    resolve_openclaw_version,
    resolve_plugin_config,
    result_counts,
    threshold_passed,
    write_json_report,
)


def _resolve_report_path(report_path: Path | None, write_report: Path | None) -> Path:
    if report_path and write_report and report_path != write_report:
        raise ValueError("--report-path and --write-report must match when both are provided")
    return report_path or write_report or DEFAULT_COMPATIBILITY_REPORT


def _check_timeout(value: Any, minimum: int) -> tuple[str, str]:
    if not isinstance(value, int):
        return "fail", "Plugin timeoutMs is missing or not an integer"
    if value < minimum:
        return "warn", f"Plugin timeoutMs={value} is below the recommended baseline of {minimum}"
    return "pass", f"Plugin timeoutMs={value} meets the commercialization baseline"


def _capabilities(support_level: str, *, auto_recall: Any, auto_capture: Any) -> tuple[list[str], list[str]]:
    enabled = ["api", "diagnostics"]
    disabled: list[str] = []
    if support_level in {"A", "B"}:
        enabled.append("plugin_memory_slot")
    else:
        disabled.append("plugin_memory_slot")
    if support_level == "A":
        enabled.append("release_baseline")
    else:
        disabled.append("release_baseline")
    if auto_capture is True and support_level in {"A", "B"}:
        enabled.append("auto_write")
    else:
        disabled.append("auto_write")
    if auto_recall is True and support_level in {"A", "B"}:
        enabled.append("auto_recall")
    else:
        disabled.append("auto_recall")
    if support_level in {"A", "B"}:
        enabled.append("customer_delivery_reports")
    else:
        disabled.append("customer_delivery_reports")
    return enabled, disabled


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization doctor")
    parser.add_argument("--openclaw-config", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN_DIR)
    parser.add_argument("--openclaw-config-dir", type=Path, default=DEFAULT_OPENCLAW_CONFIG_DIR)
    parser.add_argument("--memory-adapter-dir", type=Path, default=DEFAULT_MEMORY_ADAPTER_DIR)
    parser.add_argument("--openviking-source", type=Path, default=DEFAULT_OPENVIKING_SOURCE)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--openviking-url", default=DEFAULT_OPENVIKING_URL)
    parser.add_argument("--expected-openclaw-version", default=DEFAULT_EXPECTED_OPENCLAW_VERSION)
    parser.add_argument(
        "--supported-openclaw-versions",
        nargs="*",
        default=list(DEFAULT_SUPPORTED_OPENCLAW_VERSIONS),
        help="Compatible but non-recommended OpenClaw versions",
    )
    parser.add_argument("--expected-plugin-base-url", default=DEFAULT_EXPECTED_PLUGIN_BASE_URL)
    parser.add_argument("--expected-agent-id", default=DEFAULT_EXPECTED_AGENT_ID)
    parser.add_argument("--min-plugin-timeout-ms", type=int, default=DEFAULT_MIN_PLUGIN_TIMEOUT_MS)
    parser.add_argument("--expected-support-schema-version", default="ov-support/v1")
    parser.add_argument("--minimum-support-level", choices=["A", "B", "C", "D"], default="B")
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--write-report", type=Path, help="Compatibility alias for --report-path")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("doctor")
    report_path = _resolve_report_path(args.report_path, args.write_report)

    checks: list[ResultRecord] = []
    config: dict[str, Any] = {}

    if args.openclaw_config.exists():
        try:
            config = json_load(args.openclaw_config)
            checks.append(ResultRecord("openclaw_config", "pass", "OpenClaw config loaded"))
        except Exception as exc:  # noqa: BLE001
            checks.append(ResultRecord("openclaw_config", "fail", f"Failed to parse OpenClaw config: {exc}"))
    else:
        checks.append(ResultRecord("openclaw_config", "fail", "OpenClaw config file not found"))

    openclaw_version = resolve_openclaw_version(config) if config else None
    version_policy = evaluate_openclaw_version_policy(
        openclaw_version,
        baseline_version=args.expected_openclaw_version,
        supported_versions=tuple(args.supported_openclaw_versions),
    )
    if openclaw_version:
        status = version_policy["check_status"]
        message = f"OpenClaw {openclaw_version} detected"
        if version_policy["classification"] == "recommended":
            message += "; version matches the recommended baseline"
        elif version_policy["classification"] == "compatible":
            message += f"; supported compatible version, baseline remains {args.expected_openclaw_version}"
        else:
            message += f"; not in supported version policy, recommended baseline is {args.expected_openclaw_version}"
        checks.append(
            ResultRecord(
                "openclaw_version",
                status,
                message,
                {
                    "detected": openclaw_version,
                    "expected": args.expected_openclaw_version,
                    "supported_versions": list(args.supported_openclaw_versions),
                    "classification": version_policy["classification"],
                    "is_recommended": version_policy["is_recommended"],
                    "is_supported": version_policy["is_supported"],
                    "reason_code": version_policy["reason_code"],
                    "action_suggestion": version_policy["action_suggestion"],
                },
            )
        )
    else:
        checks.append(ResultRecord("openclaw_version", "fail", "OpenClaw version could not be resolved from config"))

    plugins = config.get("plugins", {}) if isinstance(config, dict) else {}
    slot_ok = (
        plugins.get("enabled") is True
        and plugins.get("slots", {}).get("memory") == "memory-openviking"
        and "memory-openviking" in plugins.get("allow", [])
    )
    checks.append(
        ResultRecord(
            "plugin_slot",
            "pass" if slot_ok else "fail",
            "memory-openviking is wired into the memory slot"
            if slot_ok
            else "memory-openviking slot wiring is incomplete",
        )
    )

    plugin_config = resolve_plugin_config(config) if config else {}
    plugin_base_url = plugin_config.get("baseUrl")
    if not plugin_base_url:
        checks.append(ResultRecord("plugin_base_url", "fail", "Plugin baseUrl is missing"))
    else:
        status = "pass" if plugin_base_url == args.expected_plugin_base_url else "warn"
        message = f"Plugin baseUrl is '{plugin_base_url}'"
        if status == "warn":
            message += f"; expected packaged baseline is '{args.expected_plugin_base_url}'"
        checks.append(
            ResultRecord(
                "plugin_base_url",
                status,
                message,
                {"detected": plugin_base_url, "expected": args.expected_plugin_base_url},
            )
        )

    timeout_status, timeout_message = _check_timeout(plugin_config.get("timeoutMs"), args.min_plugin_timeout_ms)
    checks.append(
        ResultRecord(
            "plugin_timeout",
            timeout_status,
            timeout_message,
            {"detected": plugin_config.get("timeoutMs"), "minimum": args.min_plugin_timeout_ms},
        )
    )

    auto_recall = plugin_config.get("autoRecall")
    auto_capture = plugin_config.get("autoCapture")
    flags_ok = isinstance(auto_recall, bool) and isinstance(auto_capture, bool) and auto_recall and auto_capture
    checks.append(
        ResultRecord(
            "plugin_flags",
            "pass" if flags_ok else "warn",
            "Plugin autoCapture and autoRecall align with the validated baseline"
            if flags_ok
            else "Plugin autoCapture or autoRecall differ from the validated baseline",
            {"autoRecall": auto_recall, "autoCapture": auto_capture},
        )
    )

    known_agents = resolve_known_agents(config) if config else []
    agent_id = plugin_config.get("agentId")
    if agent_id:
        status = "pass" if agent_id == args.expected_agent_id else "warn"
        message = f"Plugin agentId is '{agent_id}'"
        if status == "warn":
            message += f"; packaged baseline expects '{args.expected_agent_id}'"
        checks.append(
            ResultRecord(
                "agent_id",
                status,
                message,
                {"detected": agent_id, "expected": args.expected_agent_id},
            )
        )
        registry_status = "pass" if not known_agents or agent_id in known_agents else "fail"
        registry_message = "Configured plugin agentId is aligned with the declared OpenClaw agent list"
        if registry_status == "fail":
            registry_message = "Configured plugin agentId is not present in the declared OpenClaw agent list"
        checks.append(
            ResultRecord(
                "agent_id_registry",
                registry_status,
                registry_message,
                {"agentId": agent_id, "knownAgents": known_agents},
            )
        )
    else:
        checks.append(ResultRecord("agent_id", "fail", "Plugin agentId is missing"))
        checks.append(ResultRecord("agent_id_registry", "fail", "Cannot validate agentId against agent registry"))

    checks.append(
        ResultRecord(
            "plugin_dir",
            "pass" if args.plugin_dir.exists() else "fail",
            "Plugin directory exists" if args.plugin_dir.exists() else "Plugin directory is missing",
        )
    )

    key_dirs = {
        "openclaw_config_dir": args.openclaw_config_dir,
        "memory_adapter_dir": args.memory_adapter_dir,
        "openviking_source": args.openviking_source,
    }
    missing_dirs = [name for name, path in key_dirs.items() if not path.exists()]
    checks.append(
        ResultRecord(
            "key_dirs",
            "pass" if not missing_dirs else "warn",
            "Key commercialization directories exist"
            if not missing_dirs
            else "Some expected commercialization directories are missing",
            {"missing": missing_dirs} if missing_dirs else None,
        )
    )

    report_root_ok = path_writable(report_path)
    checks.append(
        ResultRecord(
            "report_path",
            "pass" if report_root_ok else "fail",
            "Report path is writable" if report_root_ok else "Report path is not writable",
            {"path": str(report_path)},
        )
    )

    status_code, adapter_payload, adapter_meta = http_json_with_meta(f"{args.adapter_url.rstrip('/')}/health", timeout=5.0)
    adapter_ok = status_code == 200 and isinstance(adapter_payload, dict) and adapter_payload.get("status") in {"healthy", "ok"}
    adapter_request_id = extract_request_id(adapter_meta)
    checks.append(
        ResultRecord(
            "adapter_health",
            "pass" if adapter_ok else "fail",
            "Memory Adapter health check passed" if adapter_ok else "Memory Adapter health check failed",
            (
                {
                    **adapter_payload,
                    "request_id": adapter_request_id,
                }
                if isinstance(adapter_payload, dict)
                else {"response": adapter_payload, "request_id": adapter_request_id}
            ),
        )
    )

    adapter_error_policy = adapter_payload.get("error_policy") if isinstance(adapter_payload, dict) else None
    error_policy_ok = (
        isinstance(adapter_error_policy, dict)
        and adapter_error_policy.get("schema_version") == args.expected_support_schema_version
        and adapter_error_policy.get("request_id_header") == "X-Request-ID"
        and adapter_error_policy.get("catalog_endpoint") == "/support/error-codes"
    )
    checks.append(
        ResultRecord(
            "adapter_error_policy",
            "pass" if error_policy_ok else "warn",
            "Adapter error policy is exposed with the expected support schema"
            if error_policy_ok
            else "Adapter error policy is missing or differs from the expected support schema",
            {
                "detected": adapter_error_policy,
                "expected": {
                    "schema_version": args.expected_support_schema_version,
                    "request_id_header": "X-Request-ID",
                    "catalog_endpoint": "/support/error-codes",
                },
                "request_id": adapter_request_id,
            },
        )
    )

    status_code, catalog_payload, catalog_meta = http_json_with_meta(f"{args.adapter_url.rstrip('/')}/support/error-codes", timeout=5.0)
    catalog_ok = (
        status_code == 200
        and isinstance(catalog_payload, dict)
        and catalog_payload.get("schema_version") == args.expected_support_schema_version
        and isinstance(catalog_payload.get("count"), int)
        and catalog_payload.get("count", 0) >= 1
    )
    checks.append(
        ResultRecord(
            "adapter_error_catalog",
            "pass" if catalog_ok else "warn",
            "Adapter support error catalog is available"
            if catalog_ok
            else "Adapter support error catalog is missing or incomplete",
            (
                {
                    **catalog_payload,
                    "request_id": extract_request_id(catalog_meta),
                }
                if isinstance(catalog_payload, dict)
                else {"response": catalog_payload, "request_id": extract_request_id(catalog_meta)}
            ),
        )
    )

    status_code, openviking_payload = http_json(f"{args.openviking_url.rstrip('/')}/health", timeout=5.0)
    openviking_ok = status_code == 200 and isinstance(openviking_payload, dict) and openviking_payload.get("status") == "ok"
    checks.append(
        ResultRecord(
            "openviking_health",
            "pass" if openviking_ok else "fail",
            "OpenViking health check passed" if openviking_ok else "OpenViking health check failed",
            openviking_payload if isinstance(openviking_payload, dict) else {"response": openviking_payload},
        )
    )

    container_names = docker_names()
    network_names = docker_networks()
    checks.append(
        ResultRecord(
            "docker_primary_gateway",
            "pass" if "openclaw-openclaw-gateway-1" in container_names else "fail",
            "Primary OpenClaw gateway container is running"
            if "openclaw-openclaw-gateway-1" in container_names
            else "Primary OpenClaw gateway container is not running",
        )
    )

    missing_baseline_containers = [name for name in CRITICAL_CONTAINERS if name not in container_names]
    checks.append(
        ResultRecord(
            "docker_runtime_baseline",
            "pass" if not missing_baseline_containers else "fail",
            "Critical runtime containers are present"
            if not missing_baseline_containers
            else "Critical runtime containers are missing",
            {"missing": missing_baseline_containers} if missing_baseline_containers else None,
        )
    )

    checks.append(
        ResultRecord(
            "docker_network",
            "pass" if "openclaw_internal" in network_names else "fail",
            "Primary Docker network openclaw_internal exists"
            if "openclaw_internal" in network_names
            else "Primary Docker network openclaw_internal is missing",
        )
    )

    staging_running = any("staging" in name.lower() for name in container_names)
    checks.append(
        ResultRecord(
            "staging_parallel",
            "warn" if staging_running else "pass",
            "A staging runtime is running in parallel with the primary baseline"
            if staging_running
            else "No parallel staging runtime detected",
        )
    )

    archived_staging = []
    if args.archive_root.exists():
        archived_staging = sorted(path.name for path in args.archive_root.iterdir() if "staging" in path.name.lower())
    checks.append(
        ResultRecord(
            "staging_archive",
            "pass",
            "Archived staging assets detected" if archived_staging else "No archived staging assets detected",
            {"archives": archived_staging} if archived_staging else None,
        )
    )

    support_level, risks, suggestions = classify_support_level(checks)
    counts = result_counts(checks)
    evidence = record_ids_by_status(checks)
    status = "pass" if support_level == "A" else "warn" if support_level == "B" else "fail"
    enabled_capabilities, disabled_capabilities = _capabilities(
        support_level,
        auto_recall=auto_recall,
        auto_capture=auto_capture,
    )
    acceptance_verdict = "accepted" if support_level == "A" else "conditional" if support_level == "B" else "rejected"
    support_scope = "full" if support_level == "A" else "conditional" if support_level == "B" else "diagnostic_only"
    acceptance = {
        "verdict": acceptance_verdict,
        "release_ready": support_level == "A",
        "customer_handoff_ready": support_level in {"A", "B"},
        "support_scope": support_scope,
        "reasons": risks or ["Environment aligns with the frozen commercialization baseline."],
        "required_followups": [] if support_level == "A" else suggestions,
    }
    report = {
        **report_metadata("ov-enterprise-doctor", run_id, started_ms),
        "report_kind": "compatibility_report",
        "status": status,
        "exit_code": 0 if threshold_passed(support_level, args.minimum_support_level) else 1,
        "support_level": support_level,
        "summary": {"status": status, "support_level": support_level, "counts": counts},
        "baseline": {
            "mode": "primary_only",
            "version_policy_mode": "baseline_plus_supported_whitelist",
            "baseline_version": args.expected_openclaw_version,
            "recommended_version": args.expected_openclaw_version,
            "supported_versions": list(args.supported_openclaw_versions),
            "expected_openclaw_version": args.expected_openclaw_version,
            "expected_plugin_base_url": args.expected_plugin_base_url,
            "expected_agent_id": args.expected_agent_id,
            "min_plugin_timeout_ms": args.min_plugin_timeout_ms,
            "expected_support_schema_version": args.expected_support_schema_version,
            "adapter_url": args.adapter_url,
            "openviking_url": args.openviking_url,
            "critical_containers": CRITICAL_CONTAINERS,
            "baseline_containers": BASELINE_CONTAINERS,
        },
        "detected": {
            "openclaw_version": openclaw_version,
            "plugin_config": {
                "baseUrl": plugin_base_url,
                "timeoutMs": plugin_config.get("timeoutMs"),
                "autoRecall": auto_recall,
                "autoCapture": auto_capture,
                "agentId": agent_id,
            },
            "adapter_support": {
                "request_id_header": (
                    adapter_error_policy.get("request_id_header")
                    if isinstance(adapter_error_policy, dict)
                    else None
                ),
                "catalog_endpoint": (
                    adapter_error_policy.get("catalog_endpoint")
                    if isinstance(adapter_error_policy, dict)
                    else None
                ),
                "catalog_count": catalog_payload.get("count") if isinstance(catalog_payload, dict) else None,
            },
            "known_agents": known_agents,
            "docker_containers_seen": sorted(
                name
                for name in container_names
                if "openclaw" in name or "brain" in name or "memory-adapter" in name or "openviking" in name or name == "supervisor"
            ),
            "docker_networks_seen": sorted(name for name in network_names if "openclaw" in name),
            "archived_staging_assets": archived_staging,
        },
        "detected_version": openclaw_version,
        "baseline_version": args.expected_openclaw_version,
        "supported_versions": list(args.supported_openclaw_versions),
        "classification": version_policy["classification"],
        "is_recommended": version_policy["is_recommended"],
        "is_supported": version_policy["is_supported"],
        "reason_code": version_policy["reason_code"],
        "message": version_policy["message"],
        "action_suggestion": version_policy["action_suggestion"],
        "capabilities": {
            "enabled": enabled_capabilities,
            "disabled": disabled_capabilities,
        },
        "acceptance": acceptance,
        "support_boundary": {
            "baseline_mode": "primary_only",
            "staging_policy": "archived_only",
            "core_modification_policy": "do_not_modify_openclaw_core",
            "upgrade_chain_policy": "preserve_official_openclaw_upgrade_path",
        },
        "environment": {
            "config_paths": {
                "openclaw_config": str(args.openclaw_config),
                "plugin_dir": str(args.plugin_dir),
                "openclaw_config_dir": str(args.openclaw_config_dir),
                "memory_adapter_dir": str(args.memory_adapter_dir),
                "openviking_source": str(args.openviking_source),
            },
            "service_endpoints": {
                "adapter_url": args.adapter_url,
                "openviking_url": args.openviking_url,
            },
            "runtime": {
                "critical_containers_present": all(name in container_names for name in CRITICAL_CONTAINERS),
                "baseline_container_count": len(BASELINE_CONTAINERS),
                "containers_seen_count": len(container_names),
            },
            "support_surface": {
                "schema_version": (
                    adapter_error_policy.get("schema_version")
                    if isinstance(adapter_error_policy, dict)
                    else None
                ),
                "health_request_id": adapter_request_id,
                "catalog_request_id": extract_request_id(catalog_meta),
            },
        },
        "evidence": evidence,
        "companion_artifacts": {
            "verify_report": str(DEFAULT_VERIFY_REPORT),
            "install_check_report": str(report_path.parent / "install_check.current.json"),
            "backup_report": str(report_path.parent / "backup.current.json"),
        },
        "checks": render_records(checks),
        "risks": risks,
        "suggestions": suggestions,
        "report_path": str(report_path),
    }

    write_json_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
