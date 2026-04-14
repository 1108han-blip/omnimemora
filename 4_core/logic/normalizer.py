"""
标准化器模块：统一数据格式
流程：标准化 → 过滤 → 路由 → 转换

改进：
1. 添加 expire_at 字段（TTL 支持）
2. 统一 JSON 格式
"""
from datetime import datetime
from typing import Dict, Optional, Any


# TTL 配置（天数 -> 秒数）
TTL_SECONDS = {
    "L0": 0,        # 不存储
    "L1": 7 * 86400,      # 7 天
    "L2": 30 * 86400,     # 30 天
    "L3": -1,      # 永久 (-1)
}


def normalize(data: dict) -> dict:
    """
    标准化输入数据为统一 JSON 格式
    """
    return {
        "agent": data.get("agent", "unknown"),
        "type": data.get("type", "general"),
        "content": data.get("content", ""),
        "tags": data.get("tags", []),
        "memory_type": data.get("memory_type"),
        "timestamp": data.get("timestamp", int(datetime.now().timestamp())),
        "format": "normalized"
    }


def calculate_expire_at(memory_level: str, timestamp: int = None) -> Optional[int]:
    """
    计算过期时间

    Args:
        memory_level: 记忆等级 L0/L1/L2/L3
        timestamp: 当前时间戳（秒）

    Returns:
        expire_at: 过期时间戳（秒），-1 表示永久
    """
    if timestamp is None:
        timestamp = int(datetime.now().timestamp())

    ttl = TTL_SECONDS.get(memory_level, -1)

    if ttl == -1:
        return -1  # 永久
    elif ttl == 0:
        return 0   # 立即过期（不存储）
    else:
        return timestamp + ttl


def to_viking_format(
    data: dict,
    memory_type: str = "short_term",
    memory_level: str = "L1",
    score: int = 0,
    content_id: str = ""
) -> dict:
    """
    转换为 OpenViking 存储格式

    改进：添加 expire_at 字段
    """
    timestamp = data.get("timestamp", int(datetime.now().timestamp()))
    expire_at = calculate_expire_at(memory_level, timestamp)

    return {
        "text": data.get("content", ""),
        "metadata": {
            "agent": data.get("agent"),
            "type": data.get("type"),
            "tags": data.get("tags", []),
            "memory_type": memory_type,
            "memory_level": memory_level,
            "score": score,
            "content_id": content_id,
            "timestamp": timestamp,
            "expire_at": expire_at,  # 新增：过期时间
            "adapter_version": "2.1.0"
        }
    }


def parse_viking_response(response: dict) -> dict:
    """
    解析 OpenViking 响应
    """
    return {
        "status": response.get("status", "unknown"),
        "memory_id": response.get("id", ""),
        "memory_type": response.get("type", "unknown")
    }
