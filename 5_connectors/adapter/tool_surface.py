import asyncio
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import config

router = APIRouter()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class ToolSearchRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    max_chars: Optional[int] = None
    timeout_seconds: Optional[float] = None
    agent_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _tool_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    common_paths = [
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]
    existing = env.get("PATH", "")
    parts = [part for part in existing.split(os.pathsep) if part]
    for path in reversed(common_paths):
        if path not in parts:
            parts.insert(0, path)
    env["PATH"] = os.pathsep.join(parts)
    return env


def _cap_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    if max_chars <= 32:
        return text[:max_chars], True
    return text[: max_chars - 32] + "\n[omnimemora_truncated]", True


async def _run_command(args: list[str], timeout_seconds: float) -> CommandResult:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_tool_subprocess_env(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise
    return CommandResult(
        returncode=process.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


def _build_mmx_search_command(query: str, timeout_seconds: float) -> list[str]:
    executable = _resolve_mmx_executable()
    return [
        executable,
        "search",
        "query",
        "--q",
        query,
        "--output",
        "json",
        "--quiet",
        "--non-interactive",
        "--timeout",
        str(max(1, int(timeout_seconds))),
    ]


def _resolve_mmx_executable() -> str:
    explicit = os.getenv("OMNIMEMORA_TOOL_SEARCH_MMX_PATH", "").strip()
    if explicit:
        return explicit
    found = shutil.which("mmx")
    if found:
        return found
    for candidate in (
        os.path.expanduser("~/.local/bin/mmx"),
        "/opt/homebrew/bin/mmx",
        "/usr/local/bin/mmx",
    ):
        if os.path.exists(candidate):
            return candidate
    return "mmx"


def _normalize_search_output(raw_stdout: str, max_chars: int) -> tuple[str, bool, str]:
    cleaned = _strip_ansi(raw_stdout).strip()
    if not cleaned:
        return "", False, "empty"
    try:
        parsed: Any = json.loads(cleaned)
    except json.JSONDecodeError:
        capped, truncated = _cap_text(cleaned, max_chars)
        return capped, truncated, "text"
    normalized = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    capped, truncated = _cap_text(normalized, max_chars)
    return capped, truncated, "json"


@router.post("/tools/search")
async def search_tool(request: ToolSearchRequest) -> dict[str, Any]:
    if not getattr(config, "tool_search_enabled", True):
        raise HTTPException(status_code=403, detail="tool_search_disabled")

    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="empty_query")

    provider = (request.provider or config.tool_search_default_provider or "mmx").strip().lower()
    if provider != "mmx":
        raise HTTPException(status_code=400, detail=f"unsupported_tool_search_provider:{provider}")

    max_query_chars = int(getattr(config, "tool_search_max_query_chars", 500))
    if len(query) > max_query_chars:
        raise HTTPException(status_code=413, detail="query_too_large")

    max_chars = int(request.max_chars or config.tool_search_max_result_chars)
    max_chars = max(256, min(max_chars, int(config.tool_search_max_result_chars)))
    timeout_seconds = float(request.timeout_seconds or config.tool_search_timeout_seconds)
    timeout_seconds = max(1.0, min(timeout_seconds, float(config.tool_search_timeout_seconds)))

    command = _build_mmx_search_command(query, timeout_seconds)
    started = time.perf_counter()
    try:
        result = await _run_command(command, timeout_seconds=timeout_seconds + 1.0)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="mmx_cli_not_found")
    except asyncio.TimeoutError:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        raise HTTPException(
            status_code=504,
            detail={
                "error": "tool_search_timeout",
                "provider": "mmx",
                "elapsed_ms": elapsed_ms,
            },
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    stderr = _strip_ansi(result.stderr).strip()
    if result.returncode != 0:
        capped_stderr, _ = _cap_text(stderr, 1000)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "tool_search_backend_failed",
                "provider": "mmx",
                "returncode": result.returncode,
                "stderr": capped_stderr,
                "elapsed_ms": elapsed_ms,
            },
        )

    content, truncated, output_format = _normalize_search_output(result.stdout, max_chars)
    return {
        "status": "ok",
        "provider": "mmx",
        "backend": "mmx_cli",
        "output_format": output_format,
        "content": content,
        "content_chars": len(content),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
        "agent_id": request.agent_id,
        "trace_id": request.trace_id,
        "retention": "response_only_no_product_log",
    }
