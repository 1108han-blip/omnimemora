"""
proxy_store.py — OmniMemora LLM Proxy 事件存儲
================================================
專門記錄 LLM Proxy 層事件，供 UI 和狀態 API 使用。
不和舊 meter_store 混在一起。
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from ..log_segments import enforce_jsonl_retention, read_segment_lines

EVENTS_PATH = Path.home() / ".omnimemora" / "adapter" / "proxy_events.jsonl"
_MAX_FILE_SIZE_MB = int(os.getenv("OMNIMEMORA_PROXY_EVENTS_MAX_MB", "10"))
_MAX_EVENTS_IN_MEMORY = 1000
RETENTION_DAYS = int(os.getenv("OMNIMEMORA_PROXY_EVENTS_RETENTION_DAYS", os.getenv("OMNIMEMORA_INTERNAL_LOG_RETENTION_DAYS", "7")))
MAX_RECENT_READ_LINES = int(os.getenv("OMNIMEMORA_PROXY_EVENTS_MAX_READ_LINES", "1000"))


def _ensure_store():
    """確保目錄和文件存在。"""
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EVENTS_PATH.exists():
        EVENTS_PATH.touch()


def append_event(event: dict) -> None:
    """寫入一條代理事件到 JSONL。線程安全。"""
    _ensure_store()
    enforce_jsonl_retention(EVENTS_PATH, retention_days=RETENTION_DAYS, max_active_lines=MAX_RECENT_READ_LINES)

    # 滾轉：如果文件太大就先滾轉，再寫入當前文件
    try:
        size = EVENTS_PATH.stat().st_size if EVENTS_PATH.exists() else 0
        if size > _MAX_FILE_SIZE_MB * 1024 * 1024:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            rotated = EVENTS_PATH.parent / f"proxy_events.{ts}.jsonl"
            EVENTS_PATH.rename(rotated)
    except Exception:
        pass

    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(line)


def read_recent_events(limit: int = 500) -> list[dict]:
    """讀取最近 N 條代理事件。"""
    _ensure_store()
    events = []
    cutoff = time.time() - RETENTION_DAYS * 86400
    try:
        lines = read_segment_lines(EVENTS_PATH, max_lines=max(min(MAX_RECENT_READ_LINES, limit * 4), limit))
        for line in reversed(lines):
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    if event.get("timestamp", 0) < cutoff:
                        continue
                    events.insert(0, event)
                    if len(events) >= limit:
                        break
                except Exception:
                    pass
    except Exception:
        pass
    return events


def summarize_agent_status(window_minutes: int = 30) -> dict:
    """
    汇总每个 agent 的接入狀態。
    返回結構：
    {
      "claude_code": {"connected": bool, "last_seen": float, "proxied_requests": int, "failed_requests": int},
      ...
    }
    """
    events = read_recent_events(limit=2000)
    cutoff = time.time() - window_minutes * 60
    now = time.time()

    status: dict[str, dict] = {}
    # 初始化常見 agent
    for agent in ["claude_code", "codex", "openclaw", "unknown"]:
        status[agent] = {
            "connected": False,
            "last_seen": None,
            "proxied_requests": 0,
            "failed_requests": 0,
        }

    for event in events:
        agent = event.get("agent_id", "unknown")
        if agent not in status:
            status[agent] = {"connected": False, "last_seen": None, "proxied_requests": 0, "failed_requests": 0}

        ts = event.get("timestamp", 0)
        if ts < cutoff:
            continue

        event_type = event.get("type", "")
        if event_type in ("proxy_request", "proxy_response"):
            status[agent]["proxied_requests"] += 1
            if status[agent]["last_seen"] is None or ts > status[agent]["last_seen"]:
                status[agent]["last_seen"] = ts

        elif event_type == "proxy_error":
            status[agent]["failed_requests"] += 1
            if status[agent]["last_seen"] is None or ts > status[agent]["last_seen"]:
                status[agent]["last_seen"] = ts

    # 計算 connected（窗口內有成功請求）
    for agent, data in status.items():
        if data["proxied_requests"] > 0:
            data["connected"] = True
        elif data["last_seen"] is not None and (now - data["last_seen"]) < window_minutes * 60:
            data["connected"] = False  # 只有失敗記錄
        else:
            data["connected"] = False

    return status


def reset_proxy_events() -> None:
    """清空事件文件（測試用）。"""
    _ensure_store()
    with open(EVENTS_PATH, "w") as f:
        f.write("")
