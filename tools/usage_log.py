"""
usage_log.py - Wrapper Real Usage Log
======================================
Wrapper 层写入的完整使用日志，与 adapter Decision Log 分开。
每条日志独立一行输出到 stdout，无前缀/后缀。
"""
import json
import sys
from datetime import datetime
from typing import Optional, List


def _get_log_path() -> str:
    """Return the path to the JSONL log file."""
    import os as _os
    return _os.path.join(_os.path.dirname(__file__), "usage_logs.jsonl")


def emit_real_usage_log(
    query: str,
    agent_id: str,
    workspace_id: str,
    scope: str,
    task_type: str,
    context_bypass: bool,
    packed_context_length: int,
    memory_tokens_injected: int,
    baseline_tokens_estimate: int,
    actual_tokens_estimate: int,
    saved_tokens_estimate: int,
    savings_ratio: float,
    matched_keywords: List[str],
    execution_feedback: Optional[str] = None,
    subjective_score: Optional[bool] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Wrapper 侧 Real Usage Log。
    定位：完整的使用记录，由 wrapper 写入。

    同时输出到：
    1. stdout（便于调试/管道）
    2. tools/usage_logs.jsonl（追加写入，持久化）

    identity 字段统一在 _meta 下：
      - agent_id  ：真实调用的 agent（codex / claude_code / openclaw）
      - workspace_id / scope ：请求上下文
    不再使用顶层 agent 字段，避免与 adapter 端 Decision Log 混淆。
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "query": query[:200] if query else "",
        "task_type": task_type,
        "context_bypass": context_bypass,
        "context_stats": {
            "packed_context_length": packed_context_length,
            "memory_tokens_injected": memory_tokens_injected,
            "baseline_tokens_estimate": baseline_tokens_estimate,
            "actual_tokens_estimate": actual_tokens_estimate,
            "saved_tokens_estimate": saved_tokens_estimate,
            "savings_ratio": round(savings_ratio, 3),
        },
        "execution_feedback": execution_feedback,
        "subjective_score": subjective_score,
        "_meta": {
            "request_id": request_id or "wrapper-local",
            "agent_id": agent_id,
            "workspace_id": workspace_id,
            "scope": scope,
            "matched_keywords": matched_keywords,
            "source": "wrapper",
        },
    }
    line = json.dumps(log_entry, ensure_ascii=False)

    # 1. stdout
    print(line)

    # 2. append to JSONL file
    try:
        log_path = _get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"[usage_log] WARNING: could not write to usage_logs.jsonl: {e}", file=sys.stderr)
