"""
_run_adapter.py - OmniMemora Adapter Launcher Shim
===================================================
解决 Python 数字开头包名（4_core, 5_connectors）无法直接运行的问题。
通过 sys.path 注入项目根目录 + importlib 动态导入，绕过语法层限制。

用法（内部使用，不需手动调用）：
    python tools/_run_adapter.py
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
        reload=False,
    )
