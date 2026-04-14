"""
云端 HTTP 客户端 - 预留接口
今日暂不实现真实云端调用，只做 mock 骨架
"""
import httpx
from typing import Optional
from .models import Policy, FeatureFlags, UsageReport


class CloudClient:
    def __init__(self, base_url: str, timeout_ms: float = 1000.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_ms / 1000.0

    def get_policy(self) -> Optional[Policy]:
        """
        预留接口：从云端拉取策略
        今日暂不实现，返回 None 触发 fallback
        """
        # TODO: 实现真实云端调用
        # try:
        #     resp = httpx.get(f"{self.base_url}/policy", timeout=self.timeout_seconds)
        #     resp.raise_for_status()
        #     return Policy(**resp.json())
        # except Exception:
        #     return None
        return None

    def get_flags(self) -> Optional[FeatureFlags]:
        """
        预留接口：从云端拉取 feature flags
        今日暂不实现，返回 None 触发 fallback
        """
        # TODO: 实现真实云端调用
        # try:
        #     resp = httpx.get(f"{self.base_url}/flags", timeout=self.timeout_seconds)
        #     resp.raise_for_status()
        #     return FeatureFlags(**resp.json())
        # except Exception:
        #     return None
        return None

    def report_usage(self, usage: UsageReport) -> bool:
        """
        预留接口：上报 usage
        今日暂不实现，返回 False
        """
        # TODO: 实现真实云端调用
        # try:
        #     resp = httpx.post(
        #         f"{self.base_url}/usage",
        #         json=usage.model_dump(),
        #         timeout=self.timeout_seconds
        #     )
        #     resp.raise_for_status()
        #     return True
        # except Exception:
        #     return False
        return False
