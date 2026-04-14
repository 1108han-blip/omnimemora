"""Shared tool registry for CLI wrappers and MCP exposure."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ov_enterprise_common import DEFAULT_ADAPTER_URL, DEFAULT_OPENVIKING_URL
from ov_enterprise_context_kernel import (
    create_context,
    list_contexts,
    resume_context,
    show_context,
    status_context,
    suspend_context,
    update_context,
)
from ov_enterprise_context_package_kernel import context_export, context_import
from ov_enterprise_context_snapshot_kernel import context_backup, context_restore, context_rollback
from ov_enterprise_context_tool_kernel import context_doctor, context_verify
from ov_enterprise_runtime_kernel import runtime_restart, runtime_start, runtime_status, runtime_stop


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _schema_with_properties(required: list[str], properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    legacy_command: str | None = None
    public: bool = True


def _tool_dir() -> Path:
    return Path(__file__).resolve().parent


def _invoke_python_tool(tool_path: Path, args: list[str]) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(tool_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout = proc.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": stdout}
    else:
        payload = {"raw_stdout": ""}
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()
    return proc.returncode, payload


def _normalize_context_id(arguments: dict[str, Any]) -> str | None:
    for key in ("context_id", "tenant_id", "tenant"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _delegate_host_script(tool_name: str, script_name: str, extra_args_builder: Callable[[dict[str, Any]], list[str]] | None = None) -> ToolHandler:
    def _handler(arguments: dict[str, Any]) -> dict[str, Any]:
        script_args: list[str] = []
        if extra_args_builder:
            script_args.extend(extra_args_builder(arguments))
        exit_code, payload = _invoke_python_tool(_tool_dir() / script_name, script_args)
        status = payload.get("status")
        effective_status = "pass" if exit_code == 0 and status in {"pass", "warn"} else "fail"
        return {
            "tool": tool_name,
            "status": effective_status,
            "exit_code": exit_code,
            "report_path": payload.get("report_path"),
            "summary": payload.get("summary"),
            "payload": payload,
            "delegate_status": status,
        }

    return _handler


def _normalize_tool_payload(spec_name: str, payload: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    source_tool = normalized.get("tool")
    status = str(normalized.get("status") or "fail")
    summary = normalized.get("summary")
    if not isinstance(summary, dict):
        summary = {"status": status}
    checks = normalized.get("checks")
    if not isinstance(checks, list):
        checks = []
    operations = normalized.get("operations")
    if not isinstance(operations, list):
        operations = []
    artifacts = normalized.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}

    context_id = _normalize_context_id(normalized) or _normalize_context_id(arguments)
    report_path = normalized.get("report_path")
    if report_path:
        artifacts.setdefault("report", str(report_path))

    normalized["status"] = status
    normalized["summary"] = summary
    normalized["checks"] = checks
    normalized["operations"] = operations
    normalized["artifacts"] = artifacts
    normalized["report_path"] = str(report_path) if report_path else None
    normalized["runtime_window"] = normalized.get("runtime_window")
    normalized["context_id"] = context_id
    normalized["tenant_id"] = context_id or normalized.get("tenant_id")
    normalized["exit_code"] = int(normalized.get("exit_code", 0 if status in {"pass", "warn"} else 1))
    if source_tool is not None:
        normalized["source_tool"] = source_tool
    normalized["tool"] = spec_name
    return normalized


COMMON_CONTEXT_PROPERTIES = {
    "context_id": {"type": "string", "description": "Canonical context identifier."},
    "tenant_id": {"type": "string", "description": "Legacy tenant identifier alias."},
    "instance_root": {"type": "string", "description": "Runtime root directory."},
    "registry_path": {"type": "string", "description": "Context registry path."},
    "policy_path": {"type": "string", "description": "Policy profile path."},
    "adapter_url": {"type": "string", "description": "Memory adapter base URL."},
    "openviking_url": {"type": "string", "description": "OpenViking base URL."},
    "agent_id": {"type": "string", "description": "Agent id used for derived context scoping."},
}

COMMON_HOST_PROPERTIES = {
    "adapter_url": {"type": "string", "description": "Memory adapter base URL."},
    "openviking_url": {"type": "string", "description": "OpenViking base URL."},
    "backup_dir": {"type": "string", "description": "Backup directory path."},
    "archive_root": {"type": "string", "description": "Archive directory path."},
    "label": {"type": "string", "description": "Optional archive label."},
    "execute": {"type": "boolean", "description": "Apply the action instead of dry-run."},
    "startup_wait_seconds": {"type": "number"},
    "poll_interval_seconds": {"type": "number"},
    "request_timeout": {"type": "number"},
    "search_window_seconds": {"type": "number"},
    "minimum_support_level": {"type": "string"},
    "from_version": {"type": "string"},
    "to_version": {"type": "string"},
    "execute_window_report": {"type": "string"},
    "window_packet_report": {"type": "string"},
}

COMMON_RUNTIME_PROPERTIES = {
    "adapter_url": {"type": "string", "description": "Memory adapter base URL."},
    "openviking_url": {"type": "string", "description": "OpenViking base URL."},
    "execute": {"type": "boolean", "description": "Apply the action instead of dry-run."},
    "startup_wait_seconds": {"type": "number"},
    "poll_interval_seconds": {"type": "number"},
}

_TOOL_SPECS: dict[str, ToolSpec] = {}


def _register(spec: ToolSpec, *, aliases: list[str] | None = None) -> None:
    _TOOL_SPECS[spec.name] = spec
    for alias in aliases or []:
        _TOOL_SPECS[alias] = ToolSpec(
            name=spec.name,
            description=spec.description,
            input_schema=spec.input_schema,
            handler=spec.handler,
            legacy_command=spec.legacy_command,
            public=False,
        )


_register(
    ToolSpec(
        name="context_list",
        description="List registered contexts.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_CONTEXT_PROPERTIES.items() if k in {"instance_root", "registry_path", "policy_path"}}),
        handler=list_contexts,
        legacy_command="ov tenant list",
    ),
    aliases=["tenant_list"],
)
_register(
    ToolSpec(
        name="context_show",
        description="Show one registered context.",
        input_schema=_schema_with_properties(["context_id"], COMMON_CONTEXT_PROPERTIES),
        handler=show_context,
        legacy_command="ov tenant show --tenant <id>",
    ),
    aliases=["tenant_show"],
)
_register(
    ToolSpec(
        name="context_create",
        description="Create a shared-runtime context.",
        input_schema=_schema_with_properties(
            ["context_id"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "display_name": {"type": "string"},
                "namespace": {"type": "string"},
                "policy_profile": {"type": "string"},
                "config_path": {"type": "string"},
                "workspace_root": {"type": "string"},
            },
        ),
        handler=create_context,
        legacy_command="ov tenant create --tenant <id>",
    ),
    aliases=["tenant_create"],
)
_register(
    ToolSpec(
        name="context_update",
        description="Update context policy profile.",
        input_schema=_schema_with_properties(["context_id", "policy_profile"], {**COMMON_CONTEXT_PROPERTIES, "policy_profile": {"type": "string"}}),
        handler=update_context,
        legacy_command="ov tenant update --tenant <id>",
    ),
    aliases=["tenant_update"],
)
_register(
    ToolSpec(
        name="context_suspend",
        description="Suspend a context.",
        input_schema=_schema_with_properties(["context_id"], COMMON_CONTEXT_PROPERTIES),
        handler=suspend_context,
        legacy_command="ov tenant suspend --tenant <id>",
    ),
    aliases=["tenant_suspend"],
)
_register(
    ToolSpec(
        name="context_resume",
        description="Resume a suspended context.",
        input_schema=_schema_with_properties(["context_id"], COMMON_CONTEXT_PROPERTIES),
        handler=resume_context,
        legacy_command="ov tenant resume --tenant <id>",
    ),
    aliases=["tenant_resume"],
)
_register(
    ToolSpec(
        name="context_status",
        description="Load current context status.",
        input_schema=_schema_with_properties(["context_id"], COMMON_CONTEXT_PROPERTIES),
        handler=status_context,
        legacy_command="ov tenant status --tenant <id>",
    ),
    aliases=["tenant_status"],
)
_register(
    ToolSpec(
        name="context_doctor",
        description="Run context-scoped doctor checks and return support/readiness evidence.",
        input_schema=_schema_with_properties(["context_id"], COMMON_CONTEXT_PROPERTIES),
        handler=context_doctor,
        legacy_command="ov tenant doctor --tenant <id>",
    ),
    aliases=["tenant_doctor"],
)
_register(
    ToolSpec(
        name="context_verify",
        description="Run context-scoped verify checks including write/search/read/delete validation.",
        input_schema=_schema_with_properties(
            ["context_id"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "request_timeout": {"type": "number", "description": "HTTP timeout for each verify request."},
                "search_window_seconds": {"type": "number", "description": "Polling window for search visibility."},
            },
        ),
        handler=context_verify,
        legacy_command="ov tenant verify --tenant <id>",
    ),
    aliases=["tenant_verify"],
)
_register(
    ToolSpec(
        name="context_backup",
        description="Create a context-scoped snapshot with memory export, metadata, policy, and artifact manifest.",
        input_schema=_schema_with_properties(
            ["context_id"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "snapshot_type": {"type": "string", "description": "Snapshot label such as manual or pre-restore."},
                "tag": {"type": "string", "description": "Optional operator tag attached to the snapshot."},
                "execute": {"type": "boolean", "description": "Write the snapshot instead of planning it."},
            },
        ),
        handler=context_backup,
        legacy_command="ov tenant backup --tenant <id>",
    ),
    aliases=["tenant_backup"],
)
_register(
    ToolSpec(
        name="context_restore",
        description="Restore one context from a snapshot with optional replace/merge behavior and pre-snapshot safety capture.",
        input_schema=_schema_with_properties(
            ["context_id", "snapshot"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "snapshot": {"type": "string", "description": "Snapshot directory to restore from."},
                "mode": {"type": "string", "enum": ["merge", "replace"], "description": "Whether to merge or replace current context state."},
                "request_timeout": {"type": "number", "description": "HTTP timeout for search consistency checks."},
                "search_window_seconds": {"type": "number", "description": "Polling window for post-restore search consistency."},
                "poll_interval_seconds": {"type": "number", "description": "Polling interval for post-restore search consistency."},
                "execute": {"type": "boolean", "description": "Apply the restore instead of dry-run planning."},
            },
        ),
        handler=context_restore,
        legacy_command="ov tenant restore --tenant <id>",
    ),
    aliases=["tenant_restore"],
)
_register(
    ToolSpec(
        name="context_rollback",
        description="Rollback one context to the last-known-good or a specific snapshot target.",
        input_schema=_schema_with_properties(
            ["context_id"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "to": {"type": "string", "description": "Rollback target, defaulting to last-known-good."},
                "request_timeout": {"type": "number", "description": "HTTP timeout for search consistency checks."},
                "search_window_seconds": {"type": "number", "description": "Polling window for post-rollback search consistency."},
                "poll_interval_seconds": {"type": "number", "description": "Polling interval for post-rollback search consistency."},
                "execute": {"type": "boolean", "description": "Apply the rollback instead of dry-run planning."},
            },
        ),
        handler=context_rollback,
        legacy_command="ov tenant rollback --tenant <id>",
    ),
    aliases=["tenant_rollback"],
)
_register(
    ToolSpec(
        name="context_export",
        description="Export one context into a portable tenant package with forward-compatible instance metadata.",
        input_schema=_schema_with_properties(
            ["context_id"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "output": {"type": "string", "description": "Output directory for the exported package."},
                "target_instance": {"type": "string", "description": "Reserved future target instance hint."},
                "execute": {"type": "boolean", "description": "Write the package instead of dry-run planning."},
            },
        ),
        handler=context_export,
        legacy_command="ov tenant export --tenant <id>",
    ),
    aliases=["tenant_export"],
)
_register(
    ToolSpec(
        name="context_import",
        description="Import one tenant package into a target context with optional replace behavior.",
        input_schema=_schema_with_properties(
            ["context_id", "input"],
            {
                **COMMON_CONTEXT_PROPERTIES,
                "input": {"type": "string", "description": "Directory containing tenant.package.json and payload files."},
                "mode": {"type": "string", "enum": ["merge", "replace"], "description": "Whether to merge or replace the target context state."},
                "target_instance": {"type": "string", "description": "Reserved future target instance hint."},
                "execute": {"type": "boolean", "description": "Apply the import instead of dry-run planning."},
            },
        ),
        handler=context_import,
        legacy_command="ov tenant import --tenant <id>",
    ),
    aliases=["tenant_import"],
)
_register(
    ToolSpec(
        name="runtime_status",
        description="Inspect runtime state and readiness surfaces.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_RUNTIME_PROPERTIES.items() if k in {"adapter_url", "openviking_url", "startup_wait_seconds", "poll_interval_seconds"}}),
        handler=runtime_status,
        legacy_command="ov status",
    ),
    aliases=["status"],
)
_register(
    ToolSpec(
        name="runtime_start",
        description="Start baseline runtime containers.",
        input_schema=_schema_with_properties([], COMMON_RUNTIME_PROPERTIES),
        handler=runtime_start,
        legacy_command="ov start",
    ),
    aliases=["start"],
)
_register(
    ToolSpec(
        name="runtime_stop",
        description="Stop baseline runtime containers.",
        input_schema=_schema_with_properties([], COMMON_RUNTIME_PROPERTIES),
        handler=runtime_stop,
        legacy_command="ov stop",
    ),
    aliases=["stop"],
)
_register(
    ToolSpec(
        name="runtime_restart",
        description="Restart baseline runtime containers.",
        input_schema=_schema_with_properties([], COMMON_RUNTIME_PROPERTIES),
        handler=runtime_restart,
        legacy_command="ov restart",
    ),
    aliases=["restart"],
)
_register(
    ToolSpec(
        name="install_check",
        description="Run install preflight checks.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"adapter_url"}}),
        handler=_delegate_host_script(
            "install_check",
            "ov_enterprise_install_check.py",
            lambda args: ["--adapter-url", str(args.get("adapter_url") or DEFAULT_ADAPTER_URL)],
        ),
        legacy_command="ov install-check",
    )
)
_register(
    ToolSpec(
        name="install",
        description="Run guarded install flow.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"adapter_url", "backup_dir", "execute"}}),
        handler=_delegate_host_script(
            "install",
            "ov_enterprise_install.py",
            lambda args: [
                "--adapter-url",
                str(args.get("adapter_url") or DEFAULT_ADAPTER_URL),
                *(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else []),
                *(["--execute"] if bool(args.get("execute")) else []),
            ],
        ),
        legacy_command="ov install",
    )
)
_register(
    ToolSpec(
        name="doctor",
        description="Run product doctor checks.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"minimum_support_level"}}),
        handler=_delegate_host_script(
            "doctor",
            "ov_enterprise_doctor.py",
            lambda args: ["--minimum-support-level", str(args.get("minimum_support_level") or "B")],
        ),
        legacy_command="ov doctor",
    )
)
_register(
    ToolSpec(
        name="verify",
        description="Run product verify checks.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"request_timeout", "search_window_seconds"}}),
        handler=_delegate_host_script(
            "verify",
            "ov_enterprise_verify.py",
            lambda args: [
                "--request-timeout",
                str(args.get("request_timeout") or 45.0),
                "--search-window-seconds",
                str(args.get("search_window_seconds") or 45.0),
            ],
        ),
        legacy_command="ov verify",
    )
)
_register(
    ToolSpec(
        name="backup",
        description="Create a guarded host backup.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"execute"}}),
        handler=_delegate_host_script(
            "backup",
            "ov_enterprise_backup.py",
            lambda args: [*(["--execute"] if bool(args.get("execute")) else [])],
        ),
        legacy_command="ov backup",
    )
)
_register(
    ToolSpec(
        name="upgrade",
        description="Run guarded upgrade flow.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"adapter_url", "backup_dir", "execute", "from_version", "to_version"}}),
        handler=_delegate_host_script(
            "upgrade",
            "ov_enterprise_upgrade.py",
            lambda args: [
                "--adapter-url",
                str(args.get("adapter_url") or DEFAULT_ADAPTER_URL),
                *(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else []),
                *(["--from-version", str(args["from_version"])] if args.get("from_version") else []),
                *(["--to-version", str(args["to_version"])] if args.get("to_version") else []),
                *(["--execute"] if bool(args.get("execute")) else []),
            ],
        ),
        legacy_command="ov upgrade",
    )
)
_register(
    ToolSpec(
        name="restore",
        description="Run guarded host restore flow.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"adapter_url", "backup_dir", "execute", "startup_wait_seconds", "poll_interval_seconds"}}),
        handler=_delegate_host_script(
            "restore",
            "ov_enterprise_restore.py",
            lambda args: [
                "--adapter-url",
                str(args.get("adapter_url") or DEFAULT_ADAPTER_URL),
                *(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else []),
                *(["--execute"] if bool(args.get("execute")) else []),
                "--startup-wait-seconds",
                str(args.get("startup_wait_seconds") or 30.0),
                "--poll-interval-seconds",
                str(args.get("poll_interval_seconds") or 3.0),
            ],
        ),
        legacy_command="ov restore",
    )
)
_register(
    ToolSpec(
        name="rollback",
        description="Run guarded host rollback flow.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"adapter_url", "backup_dir", "execute", "startup_wait_seconds", "poll_interval_seconds"}}),
        handler=_delegate_host_script(
            "rollback",
            "ov_enterprise_rollback.py",
            lambda args: [
                "--adapter-url",
                str(args.get("adapter_url") or DEFAULT_ADAPTER_URL),
                *(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else []),
                *(["--execute"] if bool(args.get("execute")) else []),
                "--startup-wait-seconds",
                str(args.get("startup_wait_seconds") or 30.0),
                "--poll-interval-seconds",
                str(args.get("poll_interval_seconds") or 3.0),
            ],
        ),
        legacy_command="ov rollback",
    )
)
_register(
    ToolSpec(
        name="uninstall",
        description="Run guarded uninstall flow.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"adapter_url", "backup_dir", "execute"}}),
        handler=_delegate_host_script(
            "uninstall",
            "ov_enterprise_uninstall.py",
            lambda args: [
                "--adapter-url",
                str(args.get("adapter_url") or DEFAULT_ADAPTER_URL),
                *(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else []),
                *(["--execute"] if bool(args.get("execute")) else []),
            ],
        ),
        legacy_command="ov uninstall",
    )
)
_register(
    ToolSpec(
        name="rehearsal",
        description="Run rehearsal aggregation.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"backup_dir"}}),
        handler=_delegate_host_script(
            "rehearsal",
            "ov_enterprise_rehearsal.py",
            lambda args: [*(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else [])],
        ),
        legacy_command="ov rehearsal",
    )
)
_register(
    ToolSpec(
        name="execute_window",
        description="Build execute-window readiness packet.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"backup_dir"}}),
        handler=_delegate_host_script(
            "execute_window",
            "ov_enterprise_execute_window.py",
            lambda args: [*(["--backup-dir", str(args["backup_dir"])] if args.get("backup_dir") else [])],
        ),
        legacy_command="ov execute-window",
    )
)
_register(
    ToolSpec(
        name="window_packet",
        description="Generate execute window scripts and runbook.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"execute_window_report"}}),
        handler=_delegate_host_script(
            "window_packet",
            "ov_enterprise_window_packet.py",
            lambda args: [*(["--execute-window-report", str(args["execute_window_report"])] if args.get("execute_window_report") else [])],
        ),
        legacy_command="ov window-packet",
    )
)
_register(
    ToolSpec(
        name="window_packet_verify",
        description="Validate generated execute-window packet.",
        input_schema=_schema_with_properties([], {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"window_packet_report"}}),
        handler=_delegate_host_script(
            "window_packet_verify",
            "ov_enterprise_window_packet_verify.py",
            lambda args: [*(["--window-packet-report", str(args["window_packet_report"])] if args.get("window_packet_report") else [])],
        ),
        legacy_command="ov window-packet-verify",
    )
)
_register(
    ToolSpec(
        name="execute_smoke",
        description="Aggregate repeated execute-smoke evidence.",
        input_schema=_schema_with_properties([], {}),
        handler=_delegate_host_script("execute_smoke", "ov_enterprise_execute_smoke.py", lambda _args: []),
        legacy_command="ov execute-smoke",
    )
)
_register(
    ToolSpec(
        name="phase2_reserved_fields",
        description="Emit the forward-compatible Phase 2 reserved field contract for delivery and integration consumers.",
        input_schema=_schema_with_properties([], {}),
        handler=_delegate_host_script(
            "phase2_reserved_fields",
            "ov_enterprise_phase2_reserved_fields.py",
        ),
        legacy_command="ov phase2-reserved-fields",
        public=False,
    )
)
_register(
    ToolSpec(
        name="evidence_archive",
        description="Archive the current delivery evidence bundle into a versioned snapshot directory.",
        input_schema=_schema_with_properties(
            [],
            {k: v for k, v in COMMON_HOST_PROPERTIES.items() if k in {"archive_root", "label", "execute"}},
        ),
        handler=_delegate_host_script(
            "evidence_archive",
            "ov_enterprise_evidence_archive.py",
            lambda args: [
                *(["--archive-root", str(args["archive_root"])] if args.get("archive_root") else []),
                *(["--label", str(args["label"])] if args.get("label") else []),
                *(["--execute"] if args.get("execute") else []),
            ],
        ),
        legacy_command="ov evidence-archive",
    )
)


def list_tool_specs(*, public_only: bool = True) -> list[dict[str, Any]]:
    specs = []
    seen: set[str] = set()
    for name, spec in _TOOL_SPECS.items():
        if spec.name in seen:
            continue
        seen.add(spec.name)
        if public_only and not spec.public:
            continue
        specs.append(
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_schema,
                "legacy_command": spec.legacy_command,
            }
        )
    return sorted(specs, key=lambda item: item["name"])


def invoke_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in _TOOL_SPECS:
        raise KeyError(f"unknown tool '{name}'")
    spec = _TOOL_SPECS[name]
    raw_arguments = dict(arguments or {})
    payload = _normalize_tool_payload(spec.name, spec.handler(raw_arguments), raw_arguments)
    payload.setdefault("tool", name)
    payload["requested_tool"] = name
    payload["canonical_tool"] = spec.name
    return payload
