"""
agent_runners.py - Agent CLI Launcher
======================================
根据 agent 类型调用对应的 CLI 命令。
支持：claude_code, openclaw, codex。
"""
import subprocess
import sys
from typing import List, Tuple

# CLI commands per agent (first available in PATH is used)
# Note: on Windows, some CLIs are .cmd/.bat files, subprocess needs the extension
import sys
import platform

_is_windows = platform.system() == "Windows"

AGENT_CLI_COMMANDS: dict = {
    "claude_code": ["claude", "claude.cmd", "claude-code", "claude_code"],
    "openclaw":    ["openclaw", "openclaw.ps1"],
    "codex":       ["codex"],
}


def _command_available(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(
            [cmd, "--version"],
            shell=False,
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_agent_cli(agent: str, prompt: str) -> int:
    """
    调用对应 agent 的 CLI，将 prompt 作为命令行参数传入。

    Returns:
        子进程退出码。0 = 成功，非0 = 失败。
    """
    cmd_list = AGENT_CLI_COMMANDS.get(agent)
    if not cmd_list:
        print(f"[agent_runners] ERROR: unknown agent '{agent}'", file=sys.stderr)
        return 1

    # 优先找第一个在 PATH 中可用的命令
    for cmd in cmd_list:
        if _command_available(cmd):
            print(f"[agent_runners] Launching: {cmd} \"{prompt[:80]}...\"")
            try:
                result = subprocess.run(
                    [cmd, prompt],
                    shell=False,
                    timeout=300,
                )
                return result.returncode
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                print(f"[agent_runners] ERROR: {cmd} timed out after 300s", file=sys.stderr)
                return 124

    # 都不存在
    available = ", ".join(cmd_list)
    print(
        f"[agent_runners] ERROR: none of [{available}] found in PATH. "
        f"Is {agent} installed?",
        file=sys.stderr,
    )
    return 127


def get_agent_cli_name(agent: str) -> str:
    """Return the first CLI name defined for an agent (for display purposes)."""
    return AGENT_CLI_COMMANDS.get(agent, [agent])[0]
