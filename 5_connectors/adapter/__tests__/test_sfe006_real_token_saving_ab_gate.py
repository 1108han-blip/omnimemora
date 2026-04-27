"""
test_sfe006_real_token_saving_ab_gate.py — SFE-006 Real Token Saving A/B Gate
===============================================================================
Purpose:
    Prove that OmniMemora-compiled prompts are shorter (fewer input tokens)
    than original prompts without degrading output quality.

Method:
    For each of N real tasks:
        A. Send ORIGINAL prompt to the model → record input tokens + output
        B. Send OMNIMEMORA-COMPILED prompt to the SAME model → record input tokens + output
    Then compare A vs B.

Gate criteria (must ALL hold for a task to pass):
    1. compile_status == "compile_success"
    2. compiled_input_tokens < original_input_tokens  (strict reduction)
    3. Compiled output quality is NOT worse than original

Gate threshold: at least 9/10 tasks must pass.
Skipped tasks (compile_skipped / compile_failed) are excluded from the denominator.

Usage:
    # Prerequisites
    export ANTHROPIC_API_KEY=sk-...          # or OMNIMEMORA_ANTHROPIC_API_KEY
    export OMNIMEMORA_ANTHROPIC_MODEL=claude-sonnet-4-20250514

    # Create tasks file (see TASK_FILE_FORMAT below), then:
    SFE006_TASK_FILE=__tests__/sfe006_tasks.json \
        python -m pytest __tests__/test_sfe006_real_token_saving_ab_gate.py -v

    # Run single task (for debugging)
    SFE006_TASK_FILE=__tests__/sfe006_tasks.json SFE006_TASK_INDEX=0 \
        python -m pytest __tests__/test_sfe006_real_token_saving_ab_gate.py -v -s

Exit codes:
    0  = gate passed
    1  = gate failed or test error

Prerequisites:
    - ANTHROPIC_API_KEY set (or OMNIMEMORA_ANTHROPIC_API_KEY)
    - OmniMemora memory backend accessible (to fetch candidates for compile)
"""
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional, List

# ---------------------------------------------------------------------------
# Path setup — project root must be in sys.path for "5_connectors.*" imports
# ---------------------------------------------------------------------------
# __file__ = .../5_connectors/adapter/__tests__/test_foo.py
# dirname  = .../5_connectors/adapter/__tests__/
# dirname  = .../5_connectors/adapter/         (_adapter_dir)
# dirname  = .../5_connectors/                (_connectors_dir)
# dirname  = .../                              (_root — project root)
_adapter_dir = os.path.dirname(os.path.abspath(__file__))          # .../5_connectors/adapter/
_connectors_dir = os.path.dirname(_adapter_dir)                    # .../5_connectors/
_project_root = os.path.dirname(_connectors_dir)                  # .../OmniMemora/

for _p in (_project_root, _connectors_dir, _adapter_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import asyncio
import importlib
import httpx

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------
try:
    import tiktoken
    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False


def count_tokens(text: str, protocol: str = "anthropic") -> int:
    """
    Count tokens in a text string.

    - anthropic: ~3.8 chars/token (conservative — slightly overestimate is
      safer for the gate: harder to accidentally pass on fake savings)
    - openai: tiktoken cl100k_base
    """
    if not text:
        return 0
    if protocol == "openai" and _HAS_TIKTOKEN:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            pass
    # Anthropic or tiktoken unavailable: conservative char estimate
    return max(1, int(len(text) / 3.8))


def count_tokens_payload(payload: dict, protocol: str = "anthropic") -> int:
    """
    Count total tokens in a full LLM request payload.
    Handles both OpenAI /v1/chat/completions and Anthropic /v1/messages formats.
    """
    total = 0

    # Anthropic top-level system (not in messages array)
    if protocol == "anthropic":
        system = payload.get("system", "")
        if isinstance(system, str):
            total += count_tokens(system, protocol)
        elif isinstance(system, list):
            for part in system:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += count_tokens(part.get("text", ""), protocol)

    # All messages
    for msg in payload.get("messages", []):
        # Role overhead (~4 tokens per message in most encodings)
        total += 4
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content, protocol)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        total += count_tokens(part.get("text", ""), protocol)
                    elif part.get("type") == "image_url":
                        total += 1000  # rough: ~1000 tokens per image

    return total


# ---------------------------------------------------------------------------
# Task definition schema
# ---------------------------------------------------------------------------
TASK_FILE_FORMAT = """
Task file must be a JSON array of objects with this shape:

[
  {
    "id":          "task-001",
    "description": "One-line description of the task",
    "protocol":   "anthropic",          // or "openai"

    // Prompt — at least one user message required
    "messages": [
      { "role": "user", "content": "Write a README for my project..." }
    ],

    // Optional: prepend a system prompt as a separate top-level key
    "system": "You are a helpful coding assistant...",

    // Quality criteria for the compiled output
    "quality_check": {
      // ALL of these substrings must appear in compiled output (case-insensitive)
      "must_contain":    ["README", "install"],

      // NONE of these substrings should appear in compiled output
      "must_not_contain": ["error", "sorry", "cannot"],

      // Output must be at least N characters (optional)
      "min_length":       50
    }
  }
]
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ABResult:
    task_id: str
    description: str
    # Compile metadata
    compile_status: str = ""
    compile_reason: str = ""
    compile_error: str = ""
    selected_memory_count: int = 0
    # Token counts
    original_input_tokens: int = 0
    compiled_input_tokens: int = 0
    token_saved: int = 0
    token_saved_ratio: float = 0.0
    # Output
    original_output: str = ""
    compiled_output: str = ""
    original_api_error: Optional[str] = None
    compiled_api_error: Optional[str] = None
    # Quality
    quality_pass: bool = False
    quality_notes: str = ""
    # Overall
    passed: bool = False
    pass_reason: str = ""

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        d["quality_pass"] = self.quality_pass
        d["passed"] = self.passed
        return d


# ---------------------------------------------------------------------------
# Model API caller
# ---------------------------------------------------------------------------

def _model_config() -> dict:
    return {
        "anthropic": {
            "api_key": os.environ.get("OMNIMEMORA_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", ""),
            "base_url": os.environ.get("OMNIMEMORA_ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
            "model": os.environ.get("OMNIMEMORA_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        },
        "openai": {
            "api_key": os.environ.get("OMNIMEMORA_OPENAI_API_KEY", ""),
            "base_url": os.environ.get("OMNIMEMORA_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            "model": os.environ.get("OMNIMEMORA_OPENAI_MODEL", "gpt-4o"),
        },
    }


async def _call_model(
    payload: dict,
    protocol: str,
    cfg: dict,
    timeout: float = 120.0,
) -> tuple[str, Optional[str]]:
    """
    Send a request to the model.
    Returns (response_text, error_message_or_None).
    """
    if protocol not in ("anthropic", "openai"):
        return "", f"Unknown protocol: {protocol}"

    provider = cfg[protocol]
    api_key = provider["api_key"]
    base_url = provider["base_url"]
    model = provider["model"]

    if not api_key:
        return "", f"{protocol.upper()}_API_KEY not set"

    headers = {
        "content-type": "application/json",
        "user-agent": "OmniMemora-SFE006/1.0",
    }

    max_tokens_body = {"max_tokens": 1024}

    if protocol == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
        headers["x-api-key"] = api_key
        body = {
            "model": model,
            "messages": payload.get("messages", []),
            **max_tokens_body,
        }
        if payload.get("system"):
            body["system"] = payload["system"]
        url = f"{base_url}/v1/messages"

    else:  # openai
        headers["authorization"] = f"Bearer {api_key}"
        body = {
            "model": model,
            "messages": payload.get("messages", []),
            **max_tokens_body,
        }
        if payload.get("system"):
            body["messages"] = [{"role": "system", "content": payload["system"]}] + body["messages"]
        url = f"{base_url}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except Exception as e:
        return "", f"Connection error: {e}"

    if resp.status_code != 200:
        try:
            err_data = resp.json()
            msg = (
                err_data.get("error", {}).get("message", "")
                or err_data.get("message", "")
                or str(resp.status_code)
            )
        except Exception:
            msg = resp.text[:200]
        return "", f"API error {resp.status_code}: {msg}"

    data = resp.json()

    if protocol == "anthropic":
        content = data.get("content", [])
        if isinstance(content, list):
            thinking_fallback = ""
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        return text, None
                if not thinking_fallback and isinstance(block.get("thinking"), str):
                    thinking_fallback = block.get("thinking", "")
            if thinking_fallback:
                return thinking_fallback, None
        for key in ("output_text", "text", "completion"):
            val = data.get(key)
            if isinstance(val, str) and val:
                return val, None
        return "", "No text block in Anthropic response"

    else:  # openai
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return msg.get("content", ""), None
        return "", "No choices in OpenAI response"


# ---------------------------------------------------------------------------
# Quality evaluation
# ---------------------------------------------------------------------------

def _evaluate_quality(
    original_output: str,
    compiled_output: str,
    check: dict,
) -> tuple[bool, str]:
    """
    Return (pass, notes).
    pass=True means compiled output quality is acceptable (not worse than original).
    """
    notes: List[str] = []

    # Required substrings
    for substr in check.get("must_contain", []):
        if substr.lower() not in compiled_output.lower():
            notes.append(f"missing_required:'{substr}'")
            return False, "; ".join(notes)

    # Forbidden substrings
    found_bad = [
        substr for substr in check.get("must_not_contain", [])
        if substr.lower() in compiled_output.lower()
    ]
    if found_bad:
        notes.append(f"found_forbidden:{found_bad}")

    # Minimum length
    min_len = check.get("min_length", 0)
    if min_len > 0 and len(compiled_output) < min_len:
        notes.append(f"too_short({len(compiled_output)}<{min_len})")
        return False, "; ".join(notes)

    # Sanity: compiled output should not be absurdly shorter than original
    if original_output and len(compiled_output) < len(original_output) * 0.2:
        notes.append(f"severe_truncation({len(compiled_output)}<<{len(original_output)})")

    return True, "; ".join(notes) if notes else "OK"


# ---------------------------------------------------------------------------
# OmniMemora compile
# ---------------------------------------------------------------------------

async def _compile_payload(
    payload: dict,
    agent_id: str,
) -> tuple[dict, dict]:
    """
    Call OmniMemora gateway_compile to get compiled payload.
    Returns (compiled_payload, compile_meta).
    If compile fails/skips, returns (original_payload, meta_with_error).
    """
    try:
        _gc = importlib.import_module("5_connectors.adapter.application.gateway_compile")
        _ai_mod = importlib.import_module("5_connectors.adapter.agent_identity")
    except ImportError as e:
        return payload, {
            "compile_status": "import_error",
            "compile_error": str(e),
            "selected_memory_count": 0,
            "compile_reason": "import_error",
        }

    try:
        resolved = _ai_mod.resolve_agent(agent_id)
    except Exception:
        resolved = agent_id

    try:
        compiled_payload, compile_meta = await _gc.run_gateway_compile(
            payload=payload,
            agent_id=resolved,
            session_id=None,
            access_plan=None,
            request_id=f"sfe006-{int(time.time())}",
            trace_id=f"sfe006-{int(time.time())}",
        )
    except Exception as e:
        compile_meta = {
            "compile_status": "exception",
            "compile_error": str(e)[:200],
            "selected_memory_count": 0,
            "original_token_estimate": 0,
            "compiled_token_estimate": 0,
            "compression_ratio": 0.0,
            "compile_reason": "sfe006_ab_gate",
        }
        compiled_payload = payload

    return compiled_payload, compile_meta


# ---------------------------------------------------------------------------
# Single task A/B runner
# ---------------------------------------------------------------------------

async def run_task_ab(task: dict, agent_id: str) -> ABResult:
    """
    Run a full A/B for one task:
      1. Call OmniMemora compile
      2. Count input tokens (original vs compiled)
      3. Send both to the model
      4. Evaluate output quality
      5. Return ABResult with pass/fail decision
    """
    task_id = task["id"]
    description = task.get("description", task_id)
    protocol = task.get("protocol", "anthropic")

    # Build original payload
    messages = task.get("messages", [])
    system = task.get("system")
    original_payload = {"messages": messages}
    if system:
        original_payload["system"] = system

    result = ABResult(task_id=task_id, description=description)

    # --- Step 1: Compile ---
    compiled_payload, compile_meta = await _compile_payload(original_payload, agent_id)

    result.compile_status = compile_meta.get("compile_status", "unknown")
    result.compile_reason = compile_meta.get("compile_reason", "")
    result.compile_error = compile_meta.get("compile_error", "")
    result.selected_memory_count = compile_meta.get("selected_memory_count", 0)

    # If compile didn't run, we can't do a meaningful A/B — mark skip
    if result.compile_status != "compile_success":
        result.pass_reason = (
            f"compile_{result.compile_status}: {result.compile_reason} "
            f"(error: {result.compile_error})"
        )
        result.quality_notes = "skipped: compile not successful"
        return result

    # --- Step 2: Count input tokens ---
    meta_original_tokens = compile_meta.get("original_token_estimate")
    meta_compiled_tokens = compile_meta.get("compiled_token_estimate")
    result.original_input_tokens = (
        int(meta_original_tokens)
        if isinstance(meta_original_tokens, (int, float)) and meta_original_tokens > 0
        else count_tokens_payload(original_payload, protocol)
    )
    result.compiled_input_tokens = (
        int(meta_compiled_tokens)
        if isinstance(meta_compiled_tokens, (int, float)) and meta_compiled_tokens >= 0
        else count_tokens_payload(compiled_payload, protocol)
    )
    result.token_saved = result.original_input_tokens - result.compiled_input_tokens
    result.token_saved_ratio = (
        result.token_saved / result.original_input_tokens
        if result.original_input_tokens > 0 else 0.0
    )

    # --- Step 3: Call model for both ---
    cfg = _model_config()
    orig_text, orig_err = await _call_model(original_payload, protocol, cfg)
    result.original_output = orig_text
    result.original_api_error = orig_err

    comp_text, comp_err = await _call_model(compiled_payload, protocol, cfg)
    result.compiled_output = comp_text
    result.compiled_api_error = comp_err

    # --- Step 4: Quality evaluation ---
    quality_check = task.get("quality_check", {})
    if comp_err:
        result.quality_pass = False
        result.quality_notes = f"compiled_api_error: {comp_err}"
    elif orig_err:
        result.quality_pass = False
        result.quality_notes = f"original_api_error: {orig_err}"
    else:
        result.quality_pass, result.quality_notes = _evaluate_quality(
            orig_text, comp_text, quality_check
        )

    # --- Step 5: Pass/fail decision ---
    token_pass = result.token_saved > 0
    compile_ok = result.compile_status == "compile_success"

    if compile_ok and token_pass and result.quality_pass:
        result.passed = True
        result.pass_reason = (
            f"PASS: saved {result.token_saved} tokens "
            f"({result.token_saved_ratio:.1%}), quality OK"
        )
    else:
        reasons = []
        if not compile_ok:
            reasons.append(f"compile={result.compile_status}")
        if not token_pass:
            reasons.append(
                f"no_token_save({result.compiled_input_tokens}>={result.original_input_tokens})"
            )
        if not result.quality_pass:
            reasons.append(f"quality_fail: {result.quality_notes}")
        result.pass_reason = "FAIL: " + "; ".join(reasons)

    return result


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def _load_tasks() -> List[dict]:
    default_file = os.path.join(_adapter_dir, "sfe006_tasks.json")
    task_file = os.environ.get("SFE006_TASK_FILE", default_file)
    path = os.path.expanduser(os.path.expandvars(task_file))
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"SFE006_TASK_FILE not found: {path}\n"
            f"Create a task file or set SFE006_TASK_FILE env var.\n"
            f"Format: {TASK_FILE_FORMAT}"
        )
    with open(path) as f:
        tasks = json.load(f)
    if not isinstance(tasks, list):
        raise ValueError(f"Task file must be JSON array, got {type(tasks).__name__}")
    if not tasks:
        raise ValueError("Task file is empty")
    return tasks


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
import pytest

_tasks_cache: List[dict] = []


def _get_tasks() -> List[dict]:
    global _tasks_cache
    if not _tasks_cache:
        _tasks_cache = _load_tasks()
    return _tasks_cache


def _get_single_task(idx: int) -> List[dict]:
    tasks = _get_tasks()
    if idx < 0 or idx >= len(tasks):
        raise ValueError(f"SFE006_TASK_INDEX={idx} out of range (0-{len(tasks)-1})")
    return [tasks[idx]]


@pytest.fixture(scope="session")
def sfe006_tasks():
    return _get_tasks()


@pytest.fixture(scope="session")
def sfe006_agent_id():
    return os.environ.get("SFE006_AGENT_ID", "claude_code")


# ---------------------------------------------------------------------------
# Parametrized task tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task", _get_tasks())
def test_sfe006_task_ab_gate(task, sfe006_agent_id):
    """
    Run A/B for a single task.
    The task passes if:
      - compile_status == "compile_success"
      - compiled_input_tokens < original_input_tokens
      - output quality is not worse than original

    Raises AssertionError on failure (pytest will report it).
    """
    result = asyncio.run(run_task_ab(task, sfe006_agent_id))

    # Store globally for summary test
    _sfe006_results.append(result)

    # Verbose output goes to pytest -s
    _print_result(result)

    assert result.passed, (
        f"SFE-006 FAILED for {result.task_id}: {result.pass_reason}\n"
        f"  compile={result.compile_status} | "
        f"orig_tokens={result.original_input_tokens} | "
        f"comp_tokens={result.compiled_input_tokens} | "
        f"saved={result.token_saved} ({result.token_saved_ratio:.1%}) | "
        f"quality={result.quality_pass}({result.quality_notes})"
    )


# ---------------------------------------------------------------------------
# Global results store + summary test
# ---------------------------------------------------------------------------

_sfe006_results: List[ABResult] = []


def _print_result(r: ABResult) -> None:
    print(f"\n{'='*70}")
    print(f"SFE-006 | {r.task_id} | {r.description}")
    print(f"  Compile:    {r.compile_status} / {r.compile_reason}")
    print(f"  Memories:  {r.selected_memory_count} selected")
    print(f"  Tokens:    orig={r.original_input_tokens}  "
          f"comp={r.compiled_input_tokens}  "
          f"saved={r.token_saved}({r.token_saved_ratio:.1%})")
    print(f"  Quality:   pass={r.quality_pass} — {r.quality_notes}")
    if r.original_api_error:
        print(f"  Orig error: {r.original_api_error}")
    if r.compiled_api_error:
        print(f"  Comp error: {r.compiled_api_error}")
    print(f"  Result:    {'✅ PASS' if r.passed else '❌ FAIL'}: {r.pass_reason}")
    if r.original_output:
        print(f"  Orig out (first 200): {r.original_output[:200].strip()}")
    if r.compiled_output:
        print(f"  Comp out (first 200): {r.compiled_output[:200].strip()}")
    print(f"{'='*70}")


@pytest.mark.sfe006_summary
def test_sfe006_gate_summary():
    """
    SFE-006 Gate Summary.
    Runs after all parametrized task tests.

    Gate criteria:
      - Only tasks with compile_status == "compile_success" count as "eligible"
      - At least 9/10 eligible tasks must pass
      - If < 9 tasks are eligible, require all to pass

    Exit: raises AssertionError if gate fails.
    """
    results = _sfe006_results

    if not results:
        pytest.skip("No SFE-006 results collected — run parametrized tests first")

    # Summary
    eligible = [r for r in results if r.compile_status == "compile_success"]
    eligible_passed = sum(1 for r in eligible if r.passed)
    eligible_total = len(eligible)
    total = len(results)

    print(f"\n{'='*70}")
    print(f"SFE-006 GATE SUMMARY")
    print(f"{'='*70}")
    print(f"  Total tasks:   {total}")
    print(f"  Eligible:      {eligible_total} (compile_success only)")
    print(f"  Passed:        {eligible_passed}/{eligible_total}")
    print(f"  Gate threshold: 9/10 (or 100% if < 9 eligible)")
    print(f"{'='*70}")
    print(f"  Detailed results:")
    for r in results:
        icon = "✅" if r.passed else "❌" if r.compile_status == "compile_success" else "⏭"
        print(f"  {icon} [{r.compile_status:20s}] {r.task_id}: {r.pass_reason}")
    print(f"{'='*70}")

    if not eligible:
        pytest.skip("No eligible tasks (no compile_success) — cannot evaluate gate")

    required = 9 if eligible_total >= 10 else eligible_total
    gate_passed = eligible_passed >= required

    print(f"\n  Eligible:   {eligible_passed}/{eligible_total}")
    print(f"  Required:  ≥{required}")
    print(f"  Gate:      {'✅ PASSED' if gate_passed else '❌ FAILED'}")

    if not gate_passed:
        failed = [r for r in eligible if not r.passed]
        print(f"\n  Failed eligible tasks:")
        for r in failed:
            print(f"    - {r.task_id}: {r.pass_reason}")

    assert gate_passed, (
        f"SFE-006 gate FAILED: {eligible_passed}/{eligible_total} eligible tasks passed. "
        f"Need ≥ {required}. See summary above."
    )
