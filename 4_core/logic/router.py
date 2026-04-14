"""
路由器模块：基于评分决定记忆类型和等级
规则从外部注入，不读世界
"""
from .rules import RoutingRules
from .filter import detect_failure_content


def calculate_memory_score_detailed(content: str, metadata: dict = None, rules: RoutingRules = None) -> tuple[int, int, int, int, bool]:
    """
    计算记忆评分（详细维度版本）

    返回: (relevance_score, type_weight, length_penalty, final_score, is_failure)

    公式：final_score = relevance_score * type_weight - length_penalty

    维度定义：
    - relevance_score：关键词命中数 × 命中权重（使用现有 DEFAULT_SCORE_RULES）
    - type_weight：strategy=3, failure=3, knowledge=2, result=1, general=1
    - length_penalty：轻微扣分（content_len // 500）
    - is_failure：是否包含失败经验（用于调用方做最低分强制）
    """
    if rules is None:
        rules = RoutingRules()

    score_rules = rules.route_score_rules

    # ========== 维度1: relevance_score（关键词命中） ==========
    relevance_score = 0

    # 中文关键词采用更宽泛匹配（直接用原始 content，避免 lower() 对中文无意义的影响）
    # 英文关键词额外用 lower() 确保匹配
    content_lower = None

    def _match_keywords(cn_kws: list, en_kws: list, rule_name: str) -> int:
        """匹配单类关键词：中文 3 倍权重，英文正常权重。"""
        nonlocal content_lower
        for kw in cn_kws:
            if kw in content:
                return score_rules.get(rule_name, 0) * 3
        # 中文没匹配到，再试英文（lazy 计算 content_lower）
        if content_lower is None:
            content_lower = content.lower()
        for kw in en_kws:
            if kw in content_lower:
                return score_rules.get(rule_name, 0)
        return 0

    # 成功/完成关键词
    relevance_score += _match_keywords(
        ["成功", "完成", "搞定", "胜利", "顺利"],
        ["success", "done", "completed", "finished", "accomplished"],
        "success_keyword",
    )
    # 策略/规划关键词
    relevance_score += _match_keywords(
        ["策略", "规划", "方案", "计划", "安排"],
        ["policy", "strategy", "plan"],
        "strategy_keyword",
    )
    # 重要/关键关键词
    relevance_score += _match_keywords(
        ["重要", "关键", "核心", "必要", "主要", "至关重要"],
        ["important", "critical", "essential", "key", "core", "vital"],
        "important_keyword",
    )
    # 知识/规则关键词
    relevance_score += _match_keywords(
        ["知识", "规则", "原则", "方法", "理论", "准则", "规律"],
        ["knowledge", "rule", "principle", "method", "theory"],
        "knowledge_keyword",
    )

    # 失败经验评分
    is_failure, failure_type = detect_failure_content(content)
    if is_failure:
        relevance_score += score_rules.get("failure_experience", 0)

    # ========== 维度2: type_weight（类型权重） ==========
    content_type = "general"
    if metadata:
        content_type = metadata.get("type", "general")

    type_weight = 1
    if content_type in ["strategy", "failure", "failure_experience"]:
        type_weight = 3
    elif content_type == "knowledge":
        type_weight = 2
    elif content_type == "result":
        type_weight = 1

    # ========== 维度3: length_penalty（长度惩罚） ==========
    content_len = len(content)
    length_penalty = content_len // 500

    # ========== 计算 final_score ==========
    final_score = relevance_score * type_weight - length_penalty

    # 确保至少有1分（向后兼容）
    if final_score <= 0:
        final_score = 1

    return relevance_score, type_weight, length_penalty, final_score, is_failure


def calculate_memory_score(content: str, metadata: dict = None, rules: RoutingRules = None) -> int:
    """
    计算记忆评分（兼容封装）
    评分越高，内容越重要

    向后兼容：调用 calculate_memory_score_detailed() 并只返回 final_score
    """
    _, _, _, final_score, _ = calculate_memory_score_detailed(content, metadata, rules)
    return final_score


def get_memory_level(score: int) -> str:
    """
    根据评分获取记忆等级

    L0: 0分 - 垃圾/不存
    L1: 1-2分 - 短期缓存
    L2: 3-4分 - 经验记忆
    L3: 5+分 - 核心知识
    """
    if score <= 0:
        return "L0"
    elif score <= 2:
        return "L1"
    elif score <= 4:
        return "L2"
    else:
        return "L3"


def route_memory_type_and_level(content: str, metadata: dict = None, rules: RoutingRules = None) -> tuple[str, str, int]:
    """
    路由：决定记忆类型和等级

    返回: (memory_type, memory_level, score)
    - memory_type: "long_term" 或 "short_term"
    - memory_level: "L0", "L1", "L2", "L3"
    - score: 计算出的评分

    改进：失败经验自动进入长期记忆
    """
    if rules is None:
        rules = RoutingRules()

    # 计算评分（is_failure 从 scoring 阶段复用，不再重复检测）
    _, _, _, score, is_failure = calculate_memory_score_detailed(content, metadata, rules)

    # 如果是失败经验，强制提高评分确保进入 L2
    if is_failure and score < 3:
        score = 3

    # 决定记忆类型
    memory_type = "long_term" if score >= rules.long_term_threshold else "short_term"

    # 决定记忆等级
    memory_level = get_memory_level(score)

    return memory_type, memory_level, score
