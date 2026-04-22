"""
策略加载器 - V1 Local-First Quality Control Loop
==================================================
V1 策略: 本地 active 版本优先，云端 policy/flags 是非主路径，不能覆盖本地 active。
"""
from typing import Optional, Tuple
from .models import Policy
from ..policy_version_manager import load_active_policy, load_candidate_policy


def load_policy() -> Policy:
    """
    主入口：加载策略 (V1 Local-First)
    - 始终使用本地 active 版本（来自 versioned policies 目录）
    - 云端 policy 在 V1 中是非主路径，不覆盖本地 active 选择
    - cloud.enabled 仅用于 observation/secondary 场景
    """
    return load_active_policy()


def load_policy_with_candidate() -> Tuple[Policy, Optional[Policy]]:
    """
    返回 (active_policy, candidate_policy)。
    用于 golden-case runner 对比 active vs candidate。
    """
    active = load_active_policy()
    candidate = load_candidate_policy()
    return active, candidate
