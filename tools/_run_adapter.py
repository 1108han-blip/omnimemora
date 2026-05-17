"""
_run_adapter.py - OmniMemora Adapter Launcher Shim
===================================================
解决 Python 数字开头包名（4_core, 5_connectors）无法直接运行的问题。
通过 sys.path 注入项目根目录 + importlib 动态导入，绕过语法层限制。

用法（内部使用，不需手动调用）：
    python tools/_run_adapter.py
"""
from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_provider_env_file() -> None:
    """
    Load user-side provider credentials before adapter config is imported.

    The adapter must not depend on long-lived launchd copies of provider keys:
    they drift when a user rotates MiniMax/OpenClaw credentials. The default
    file keeps the weak-intrusion path aligned with the local client truth.
    """
    if os.getenv("OMNIMEMORA_PROVIDER_ENV_FILE_DISABLE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return

    raw_path = os.getenv("OMNIMEMORA_PROVIDER_ENV_FILE", "~/.openclaw/.env").strip()
    if not raw_path:
        return
    env_path = os.path.expanduser(raw_path)
    if not os.path.isfile(env_path):
        return

    override = os.getenv("OMNIMEMORA_PROVIDER_ENV_FILE_PRECEDENCE", "file").strip().lower() != "process"
    loaded: dict[str, str] = {}
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parsed = _parse_env_line(line)
                if parsed is None:
                    continue
                key, value = parsed
                if override or not os.getenv(key):
                    os.environ[key] = value
                loaded[key] = value
    except OSError:
        return

    minimax_key = loaded.get("MINIMAX_API_KEY") or os.getenv("MINIMAX_API_KEY", "")
    if not minimax_key:
        return

    base_url = os.getenv("OMNIMEMORA_ANTHROPIC_BASE_URL", "")
    model = os.getenv("OMNIMEMORA_ANTHROPIC_MODEL", "")
    minimax_selected = (
        "minimax" in base_url.lower()
        or "minimaxi" in base_url.lower()
        or "minimax" in model.lower()
        or bool(os.getenv("MINIMAX_API_KEY", "").strip())
    )
    if minimax_selected and (override or not os.getenv("OMNIMEMORA_ANTHROPIC_API_KEY")):
        os.environ["OMNIMEMORA_ANTHROPIC_API_KEY"] = minimax_key


_load_provider_env_file()

# P1 fix: meter_store 預設寫入源碼樹，需定向到 running reality 數據目錄
# 避免 adapter 從源碼樹啟動時 meter 數據與 service 讀取的路徑不一致
_service_data_dir = os.path.join(os.path.expanduser("~/.omnimemora/service/current/5_connectors/data"))
os.environ.setdefault("OMNIMEMORA_METER_DATA_DIR", _service_data_dir)

import uvicorn
import importlib

# 动态导入，避免数字开头包名的语法错误
config_module = importlib.import_module("5_connectors.adapter.config")
config = config_module.config

if __name__ == "__main__":
    port = int(os.getenv("PORT", "18011"))
    uvicorn.run(
        "5_connectors.adapter.main:app",
        host=config.adapter_host,
        port=port,
        log_level="info",
        access_log=False,
        reload=False,
    )
