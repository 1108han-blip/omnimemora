"""
去重模块：基于内容哈希的去重机制
改进：
1. 内容标准化：strip().lower() 后再 hash
2. 支持 TTL 过期清理
"""
import hashlib
from typing import Optional, Set, Dict
from datetime import datetime


def normalize_for_hash(content: str) -> str:
    """
    标准化内容用于哈希
    去除首尾空格 + 转小写
    """
    return content.strip().lower()


class DeduplicationCache:
    """
    内存去重缓存
    生产环境可替换为 Redis
    """

    def __init__(self, max_size: int = 10000, ttl_hours: int = 24):
        self._cache: Set[str] = set()
        self._timestamps: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl_hours = ttl_hours

    def generate_id(self, content: str) -> str:
        """
        生成内容唯一ID
        改进：先标准化再 hash
        """
        normalized = normalize_for_hash(content)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def is_duplicate(self, content: str) -> bool:
        """检查内容是否已存在"""
        content_id = self.generate_id(content)

        # 清理过期项
        self._cleanup()

        return content_id in self._cache

    def add(self, content: str) -> str:
        """添加内容到缓存，返回ID"""
        content_id = self.generate_id(content)

        # 清理过期项
        self._cleanup()

        # 如果缓存已满，删除最早的项
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._timestamps, key=self._timestamps.get)
            self._cache.discard(oldest_key)
            self._timestamps.pop(oldest_key, None)

        self._cache.add(content_id)
        self._timestamps[content_id] = datetime.now().timestamp()

        return content_id

    def _cleanup(self):
        """清理过期项"""
        now = datetime.now().timestamp()
        expired_keys = [
            key for key, ts in self._timestamps.items()
            if now - ts > self.ttl_hours * 3600
        ]
        for key in expired_keys:
            self._cache.discard(key)
            self._timestamps.pop(key, None)

    def get_stats(self) -> dict:
        """获取缓存状态"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_hours": self.ttl_hours
        }


# 全局去重缓存实例
_dedup_cache: Optional[DeduplicationCache] = None


def get_dedup_cache() -> DeduplicationCache:
    """获取去重缓存实例"""
    global _dedup_cache
    if _dedup_cache is None:
        _dedup_cache = DeduplicationCache()
    return _dedup_cache


def check_duplicate(content: str) -> tuple[bool, str]:
    """
    检查内容是否重复
    返回: (is_duplicate, content_id)
    """
    cache = get_dedup_cache()
    content_id = cache.generate_id(content)
    is_dup = cache.is_duplicate(content)
    return is_dup, content_id


def add_to_dedup(content: str) -> str:
    """
    添加内容到去重缓存
    返回: content_id
    """
    cache = get_dedup_cache()
    return cache.add(content)
