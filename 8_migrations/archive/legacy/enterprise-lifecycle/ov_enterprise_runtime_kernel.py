"""Shared runtime control tools for CLI wrappers and MCP exposure."""

from __future__ import annotations

from typing import Any

from ov_enterprise_common import (
    BASELINE_CONTAINERS,
    DEFAULT_ADAPTER_URL,
    DEFAULT_OPENVIKING_URL,
    adapter_support_surface,
    docker_runtime_baseline_state,
    openviking_support_surface,
    run_command,
    wait_for_runtime_ready,
)


def _check_record(
    check_id: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details,
    }


def _overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = [str(check.get("status") or "fail") for check in checks]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "warn" for status in statuses):
        return "warn"
    return "pass"


def _container_order(action: str) -> list[str]:
    if action == "stop":
        return list(reversed(BASELINE_CONTAINERS))
    return list(BASELINE_CONTAINERS)


def _runtime_surfaces(adapter_url: str, openviking_url: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    runtime_state = docker_runtime_baseline_state()
    adapter_surface = adapter_support_surface(adapter_url)
    openviking_surface = openviking_support_surface(openviking_url)
    return runtime_state, adapter_surface, openviking_surface


def _run_container_action(action: str, *, execute: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    operations: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    current_state = docker_runtime_baseline_state()
    running = set(current_state["running"])

    for name in _container_order(action):
        if action == "stop":
            needed = name in running
        elif action == "start":
            needed = name not in running
        else:
            needed = True

        operation = {
            "container": name,
            "action": action,
            "status": "planned" if needed else "noop",
        }
        if execute and needed:
            ok, output = run_command(["docker", action, name])
            operation["status"] = "applied" if ok else "fail"
            operation["output"] = output.strip()
            checks.append(
                _check_record(
                    f"{action}_{name}",
                    "pass" if ok else "fail",
                    f"docker {action} {name} {'succeeded' if ok else 'failed'}",
                    {"output": output.strip()},
                )
            )
        elif not needed:
            checks.append(
                _check_record(
                    f"{action}_{name}",
                    "pass",
                    f"Container {name} already in desired state for {action}",
                )
            )
        else:
            checks.append(
                _check_record(
                    f"{action}_{name}",
                    "pass",
                    f"Container {name} scheduled for {action}",
                )
            )
        operations.append(operation)
    return operations, checks


def runtime_status(arguments: dict[str, Any]) -> dict[str, Any]:
    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    startup_wait_seconds = float(arguments.get("startup_wait_seconds") or 10.0)
    poll_interval_seconds = float(arguments.get("poll_interval_seconds") or 2.0)

    runtime_state, adapter_surface, openviking_surface = _runtime_surfaces(adapter_url, openviking_url)
    runtime_window = wait_for_runtime_ready(
        adapter_url=adapter_url,
        openviking_url=openviking_url,
        wait_seconds=startup_wait_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )

    checks = [
        _check_record(
            "runtime_state",
            "pass" if runtime_state["state"] == "online" else "warn",
            f"Runtime baseline is {runtime_state['state']}",
            runtime_state,
        ),
        _check_record(
            "adapter_support",
            "pass" if adapter_surface["health"]["ok"] else "warn",
            "Adapter support surface reachable" if adapter_surface["health"]["ok"] else "Adapter support surface degraded",
            adapter_surface,
        ),
        _check_record(
            "openviking_support",
            "pass" if openviking_surface["health"]["ok"] else "warn",
            "OpenViking health reachable" if openviking_surface["health"]["ok"] else "OpenViking health degraded",
            openviking_surface,
        ),
        _check_record(
            "startup_window",
            "pass" if runtime_window["status"] == "ready" else "warn",
            f"Runtime readiness window result: {runtime_window['status']}",
            {
                "attempt_count": runtime_window["attempt_count"],
                "wait_seconds": runtime_window["wait_seconds"],
            },
        ),
    ]
    status = _overall_status(checks)
    return {
        "tool": "runtime_status",
        "status": status,
        "exit_code": 0 if status in {"pass", "warn"} else 1,
        "summary": {
            "action": "runtime_status",
            "status": status,
            "runtime_state": runtime_state["state"],
        },
        "checks": checks,
        "runtime_state": runtime_state,
        "support_surface": {
            "adapter": adapter_surface,
            "openviking": openviking_surface,
        },
        "runtime_window": runtime_window,
        "operations": [],
    }


def runtime_action(arguments: dict[str, Any], action: str) -> dict[str, Any]:
    adapter_url = str(arguments.get("adapter_url") or DEFAULT_ADAPTER_URL)
    openviking_url = str(arguments.get("openviking_url") or DEFAULT_OPENVIKING_URL)
    execute = bool(arguments.get("execute"))
    startup_wait_seconds = float(arguments.get("startup_wait_seconds") or 30.0)
    poll_interval_seconds = float(arguments.get("poll_interval_seconds") or 3.0)

    checks: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    runtime_window: dict[str, Any] | None = None

    if action == "restart":
        stop_operations, stop_checks = _run_container_action("stop", execute=execute)
        start_operations, start_checks = _run_container_action("start", execute=execute)
        operations.extend(stop_operations)
        operations.extend(start_operations)
        checks.extend(stop_checks)
        checks.extend(start_checks)
    else:
        action_operations, action_checks = _run_container_action(action, execute=execute)
        operations.extend(action_operations)
        checks.extend(action_checks)

    if execute and action in {"start", "restart"}:
        runtime_window = wait_for_runtime_ready(
            adapter_url=adapter_url,
            openviking_url=openviking_url,
            wait_seconds=startup_wait_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        checks.append(
            _check_record(
                "post_startup_window",
                "pass" if runtime_window["status"] == "ready" else "warn",
                f"Post-{action} runtime readiness: {runtime_window['status']}",
                {
                    "attempt_count": runtime_window["attempt_count"],
                    "wait_seconds": runtime_window["wait_seconds"],
                },
            )
        )

    runtime_state, adapter_surface, openviking_surface = _runtime_surfaces(adapter_url, openviking_url)
    status = _overall_status(checks)
    return {
        "tool": f"runtime_{action}",
        "status": status,
        "exit_code": 0 if status in {"pass", "warn"} else 1,
        "summary": {
            "action": f"runtime_{action}",
            "status": status,
            "execute": execute,
            "runtime_state": runtime_state["state"],
        },
        "checks": checks,
        "runtime_state": runtime_state,
        "support_surface": {
            "adapter": adapter_surface,
            "openviking": openviking_surface,
        },
        "runtime_window": runtime_window,
        "operations": operations,
    }


def runtime_start(arguments: dict[str, Any]) -> dict[str, Any]:
    return runtime_action(arguments, "start")


def runtime_stop(arguments: dict[str, Any]) -> dict[str, Any]:
    return runtime_action(arguments, "stop")


def runtime_restart(arguments: dict[str, Any]) -> dict[str, Any]:
    return runtime_action(arguments, "restart")
