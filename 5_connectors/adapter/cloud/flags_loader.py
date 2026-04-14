"""
Feature Flags 加载器 - 支持云端拉取 + 本地 fallback
"""
import json
import os
from typing import Optional
from .models import FeatureFlags
from .client import CloudClient
from ..config import config


def _get_default_flags_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "config", "default_flags.json")
    )


def load_local_default_flags() -> FeatureFlags:
    """
    加载本地默认 flags
    """
    flags_path = _get_default_flags_path()
    try:
        with open(flags_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return FeatureFlags(**data)
    except Exception:
        # 如果文件读取失败，返回硬编码的默认值
        return FeatureFlags()


def load_flags() -> FeatureFlags:
    """
    主入口：加载 feature flags
    - 云开启且可用：从云端拉取
    - 其他情况：返回本地默认 flags
    """
    if config.cloud.enabled:
        try:
            client = CloudClient(
                base_url=config.cloud.base_url,
                timeout_ms=config.cloud.flags_timeout_ms
            )
            cloud_flags = client.get_flags()
            if cloud_flags is not None:
                return cloud_flags
        except Exception:
            # 任何异常都 fallback 到本地
            pass

    return load_local_default_flags()
