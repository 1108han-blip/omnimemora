"""
策略加载器 - 支持云端拉取 + 本地 fallback
"""
import json
import os
from typing import Optional
from .models import Policy
from .client import CloudClient
from ..config import config


def _get_default_policy_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "config", "default_policy.json")
    )


def load_local_default_policy() -> Policy:
    """
    加载本地默认策略
    """
    policy_path = _get_default_policy_path()
    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Policy(**data)
    except Exception:
        # 如果文件读取失败，返回硬编码的默认值
        return Policy()


def load_policy() -> Policy:
    """
    主入口：加载策略
    - 云开启且可用：从云端拉取
    - 其他情况：返回本地默认策略
    """
    if config.cloud.enabled:
        try:
            client = CloudClient(
                base_url=config.cloud.base_url,
                timeout_ms=config.cloud.policy_timeout_ms
            )
            cloud_policy = client.get_policy()
            if cloud_policy is not None:
                return cloud_policy
        except Exception:
            # 任何异常都 fallback 到本地
            pass

    return load_local_default_policy()
