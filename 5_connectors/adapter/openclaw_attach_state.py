"""
openclaw_attach_state.py - OpenClaw Attach Metadata & Upstream Truth Snapshot
==============================================================================
在 OpenClaw install/attach 時捕獲原應用當前有效的上游真相快照。

快照內容：
  - wire_api: 協議族 (anthropic_messages | chat_completions | responses)
  - provider: 上游 provider 名稱
  - base_url: 上游 base URL
  - auth_source: auth 來源標記
  - model: 使用的模型
  - config_layer: 生效配置層 (env | config_file | runtime_override)

這些數據在 llm_proxy 處理 OpenClaw 請求時優先使用，
只有 attach truth 缺失時才允許 fallback/default。
"""
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from .agent_identity import resolve_canonical_agent_id

_lock = threading.Lock()
_attach_cache: Dict[str, Dict[str, Any]] = {}


def _openclaw_attach_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "openclaw_attach.json"


def load_openclaw_attach_metadata() -> Dict[str, Dict[str, Any]]:
    """
    加載 OpenClaw attach metadata。
    返回格式：
    {
        "openclaw": {
            "wire_api": "chat_completions",
            "provider": "openai_compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "auth_source": "runtime_authorization_header",
            "model": "gemma4:26b",
            "config_layer": "env",
            "attached_at": 1713000000.0,
        }
    }
    """
    global _attach_cache
    if _attach_cache:
        return _attach_cache

    path = _openclaw_attach_path()
    with _lock:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                _attach_cache = data.get("attach_metadata", {})
                return _attach_cache
        except Exception:
            pass
        _attach_cache = {}
        return _attach_cache


def save_openclaw_attach_metadata(
    wire_api: str,
    provider: str,
    base_url: str,
    auth_source: str,
    model: str,
    config_layer: str,
) -> Dict[str, Any]:
    """
    保存 OpenClaw attach metadata snapshot。

    Args:
        wire_api: 協議族 (anthropic_messages | chat_completions | responses)
        provider: 上游 provider 名稱
        base_url: 上游 base URL
        auth_source: auth 來源標記
        model: 使用的模型
        config_layer: 生效配置層 (env | config_file | runtime_override)

    Returns:
        保存後的 metadata
    """
    import time as _time

    metadata = {
        "wire_api": wire_api,
        "provider": provider,
        "base_url": base_url,
        "auth_source": auth_source,
        "model": model,
        "config_layer": config_layer,
        "attached_at": _time.time(),
    }

    # 規範化 agent_id
    canonical_id = resolve_canonical_agent_id("openclaw")

    path = _openclaw_attach_path()
    with _lock:
        try:
            existing = {}
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

        attach_metadata = existing.get("attach_metadata", {})
        attach_metadata[canonical_id] = metadata

        payload = {
            "_comment": "OpenClaw attach metadata — upstream truth snapshot",
            "attach_metadata": attach_metadata,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        global _attach_cache
        _attach_cache = attach_metadata

    return metadata


def get_openclaw_attach_truth() -> Optional[Dict[str, Any]]:
    """
    獲取 OpenClaw 的 attach upstream truth snapshot。
    如果沒有 attach 過，返回 None。
    """
    metadata = load_openclaw_attach_metadata()
    return metadata.get("openclaw") or metadata.get("openclaw-agent")


def clear_openclaw_attach_metadata() -> None:
    """清除 OpenClaw attach metadata（用於 uninstall）。"""
    path = _openclaw_attach_path()
    with _lock:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                attach_metadata = data.get("attach_metadata", {})
                attach_metadata.pop("openclaw", None)
                attach_metadata.pop("openclaw-agent", None)
                payload = {
                    "_comment": "OpenClaw attach metadata — upstream truth snapshot",
                    "attach_metadata": attach_metadata,
                }
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
        global _attach_cache
        _attach_cache = {}
