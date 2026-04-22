"""
memrun.py - OmniMemora Unified CLI Wrapper
===========================================
统一入口，按 --agent 分流到对应 runner。

用法：
    python memrun.py --agent codex "how does auth work"
    python memrun.py --agent claude_code "explain this function"
    python memrun.py --agent openclaw "summarize the codebase"

快捷入口（各自固定对应 agent）：
    python ccm.py "query..."   <- claude_code
    python ocm.py "query..."   <- openclaw
    python cxm.py "query..."   <- codex
"""
import argparse
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests

from agent_runners import run_agent_cli
from prompt_builder import build_final_prompt
from usage_log import emit_real_usage_log

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
def _default_adapter_url() -> str:
    explicit = os.getenv("OMNIMEMORA_ADAPTER_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = os.getenv("OMNIMEMORA_ADAPTER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.getenv("OMNIMEMORA_ADAPTER_PORT", "18011").strip() or "18011"
    return f"http://{host}:{port}"


ADAPTER_URL = _default_adapter_url()
MEMORY_QUERY_ENDPOINT = f"{ADAPTER_URL}/memory/query"

SUPPORTED_AGENTS = {"claude_code", "openclaw", "codex"}


# -------------------------------------------------------------------------
# Service availability check + auto-start
# -------------------------------------------------------------------------

def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _start_script_path() -> str:
    if os.name == "nt":
        return os.path.join(os.path.dirname(__file__), "start_omnimemora.bat")
    return os.path.join(_project_root(), "start.sh")


def _adapter_socket_target(adapter_url: str) -> tuple[str, int]:
    parsed = urlparse(adapter_url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port:
        return host, parsed.port
    if parsed.scheme == "https":
        return host, 443
    return host, 80


def _is_service_up(url: str, adapter_url: str) -> bool:
    """
    Two-stage service availability check.

    Stage 1: Try GET /health endpoint.
              - Returns True if any 2xx is received (even "degraded" counts as up)
              - Fast and informative
    Stage 2: Fall back to TCP port probe on adapter host/port.
              - Works even if /health endpoint is removed in the future
              - No dependency on adapter internals

    Returns True if either stage confirms the service is listening.
    """
    # Stage 1: HTTP health probe
    try:
        r = requests.get(url, timeout=3)
        if r.status_code < 400:
            return True
    except requests.RequestException:
        pass  # fall through to stage 2

    # Stage 2: TCP port probe
    target_host, target_port = _adapter_socket_target(adapter_url)
    try:
        sock = socket.create_connection((target_host, target_port), timeout=3)
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False

    return False


def ensure_service_running(adapter_url: str, *, auto_start: bool = True) -> None:
    """
    Check if OmniMemora adapter is running; auto-start if not.

    Uses two-stage availability check:
      1. HTTP probe  → GET /health?mode=local (any 2xx = up, no viking dependency)
      2. TCP probe   → connect adapter host/port (fallback if /health absent)

    If auto_start=True and service is down, launches start_omnimemora.bat
    and polls for up to 15 seconds.

    Raises:
        RuntimeError if service is unavailable after auto-start attempts.
    """
    health_url = f"{adapter_url}/health?mode=local"
    start_script = _start_script_path()

    if _is_service_up(health_url, adapter_url):
        return

    if not auto_start:
        raise RuntimeError(
            f"[memrun] OmniMemora service is not running at {adapter_url}\n"
            f"         Run startup script manually: {start_script}\n"
            f"         or remove --no-auto-start to let memrun auto-start it."
        )

    print(f"[memrun] OmniMemora service not detected at {adapter_url}", file=sys.stderr)
    print(f"[memrun] Auto-starting via {start_script} ...", file=sys.stderr)

    if not os.path.exists(start_script):
        raise RuntimeError(
            f"[memrun] startup script not found at:\n"
            f"         {start_script}\n"
            f"         Please create it first."
        )

    if os.name == "nt":
        subprocess.Popen(
            ["cmd", "/c", "start", "OmniMemora Adapter", "cmd", "/k", start_script],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        subprocess.Popen(
            ["bash", start_script],
            cwd=_project_root(),
            start_new_session=True,
        )

    # Give the server time to start up
    for attempt in range(1, 6):
        time.sleep(3)
        print(f"[memrun] Waiting for service... ({attempt}/5)", file=sys.stderr)
        if _is_service_up(health_url, adapter_url):
            print(f"[memrun] Service is up!", file=sys.stderr)
            return

    raise RuntimeError(
        f"[memrun] Service did not come up after 15 seconds.\n"
        f"         Check the OmniMemora Adapter window for errors.\n"
        f"         Or run: {start_script}"
    )


# -------------------------------------------------------------------------
# OmniMemora API client
# -------------------------------------------------------------------------

def query_omnimemora(
    query: str,
    tenant: str,
    user: str,
    agent: str,
    agent_id: str,
    workspace_id: str,
    scope: str,
) -> dict:
    """
    Call OmniMemora /memory/query.

    Raises:
        requests.HTTPError on non-2xx response.
    """
    payload = {
        "tenant": tenant,
        "user": user,
        "agent": agent,
        "query": query,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "scope": scope,
    }
    response = requests.post(
        MEMORY_QUERY_ENDPOINT,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# -------------------------------------------------------------------------
# Main dispatch
# -------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OmniMemora Unified Wrapper")
    parser.add_argument(
        "--agent",
        choices=SUPPORTED_AGENTS,
        required=True,
        help="Agent to use: claude_code | openclaw | codex",
    )
    parser.add_argument(
        "query_pos",
        nargs="?",
        default=None,
        help="User query / task description (positional shortcut)",
    )
    parser.add_argument(
        "--query", "-q",
        dest="query",
        default=None,
        help="User query / task description",
    )
    parser.add_argument(
        "--tenant",
        default=os.getenv("OMNIMEMORA_TENANT", "default-tenant"),
        help="Tenant name",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("OMNIMEMORA_USER", "default-user"),
        help="User name",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="Agent instance ID (default: same as --agent)",
    )
    parser.add_argument(
        "--workspace-id",
        default=os.getenv("OMNIMEMORA_WORKSPACE_ID", "default-workspace"),
        help="Workspace ID",
    )
    parser.add_argument(
        "--scope",
        default="workspace",
        choices=["workspace", "server", "global"],
        help="Scope of the request",
    )
    parser.add_argument(
        "--no-inject",
        action="store_true",
        help="Skip OmniMemora API call, directly pass query to agent CLI",
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Do not auto-start OmniMemora service if not running",
    )

    args = parser.parse_args()

    agent        = args.agent
    query        = args.query or args.query_pos
    if not query:
        parser.error("the following arguments are required: --query/-q (or positional query)")
    tenant       = args.tenant
    user         = args.user
    agent_id     = args.agent_id or agent
    workspace_id = args.workspace_id
    scope        = args.scope

    # --- Step 0: Ensure OmniMemora service is running ---
    if not args.no_inject:
        try:
            ensure_service_running(ADAPTER_URL, auto_start=not args.no_auto_start)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    # --- Step 1: Call OmniMemora ---
    context_bypass         = False
    packed_context         = ""
    memory_tokens_injected = 0
    task_type              = "unknown"
    matched_keywords: list  = []
    baseline_tokens_estimate = 0
    actual_tokens_estimate   = 0
    saved_tokens_estimate    = 0
    savings_ratio            = 0.0
    request_id              = "wrapper-local"
    policy_version          = "unknown"

    if not args.no_inject:
        print(f"[memrun] Calling OmniMemora /memory/query ...")
        try:
            result = query_omnimemora(
                query=query,
                tenant=tenant,
                user=user,
                agent=agent,
                agent_id=agent_id,
                workspace_id=workspace_id,
                scope=scope,
            )
            context_bypass         = result.get("context_bypass", False)
            packed_context         = result.get("packed_context", "")
            memory_tokens_injected = result.get("memory_tokens_injected", 0)
            task_type              = result.get("task_type", "unknown")
            matched_keywords        = result.get("matched_keywords", [])
            meter                  = result.get("meter_artifact", {})
            policy_version          = result.get("policy_version", "unknown")

            baseline_tokens_estimate = meter.get("baseline_tokens_estimate", 0)
            actual_tokens_estimate   = meter.get("actual_tokens_estimate", 0)
            saved_tokens_estimate    = meter.get("saved_tokens_estimate", 0)
            savings_ratio            = meter.get("savings_ratio", 0.0)
            request_id              = result.get("request_id", "wrapper-local")

            print(
                f"[memrun] OmniMemora: task_type={task_type}, bypass={context_bypass}, "
                f"packed_ctx_len={len(packed_context)}"
            )
        except requests.RequestException as e:
            print(f"[memrun] WARNING: OmniMemora API call failed: {e}", file=sys.stderr)
            print(f"[memrun] Falling back to direct agent call (no context injection).")
            context_bypass = True

    # --- Step 2: Build final prompt ---
    if context_bypass or not packed_context:
        final_prompt = query
        print(f"[memrun] Context bypass=True/empty -> passing original query to agent")
    else:
        final_prompt = build_final_prompt(query, packed_context)
        print(f"[memrun] Context injected ({len(packed_context)} chars) -> augmented prompt")

    # --- Step 3: Call agent CLI ---
    print(f"[memrun] Launching agent: {agent}")
    exit_code = run_agent_cli(agent, final_prompt)

    # --- Step 4: Emit Real Usage Log ---
    emit_real_usage_log(
        query=query,
        agent_id=agent_id,
        workspace_id=workspace_id,
        scope=scope,
        task_type=task_type,
        context_bypass=context_bypass,
        packed_context_length=len(packed_context),
        memory_tokens_injected=memory_tokens_injected,
        baseline_tokens_estimate=baseline_tokens_estimate,
        actual_tokens_estimate=actual_tokens_estimate,
        saved_tokens_estimate=saved_tokens_estimate,
        savings_ratio=savings_ratio,
        matched_keywords=matched_keywords,
        execution_feedback=None,
        subjective_score=None,
        request_id=request_id,
        policy_version=policy_version,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
