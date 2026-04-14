"""
过滤器模块：只负责判断内容是否应该存储
规则从外部注入，不读世界
"""
from .rules import FilterRules


def should_store(content: str, content_type: str = "general", rules: FilterRules = None) -> tuple[bool, str]:
    """
    过滤器：判断内容是否应该存储
    返回: (should_store, reason)

    过滤规则：
    1. 内容为空 → 不存储
    2. 内容长度 < min_content_length → 不存储
    3. type 为 chat/thinking/debug/log → 不存储（Agent 思考垃圾）
    4. 错误内容不再过滤，而是转换为 failure_experience 类型并加分
    """
    if rules is None:
        rules = FilterRules()

    if not content:
        return False, "empty_content"

    # 1. 长度过滤
    if len(content) < rules.min_content_length:
        return False, "too_short"

    # 2. Type 过滤（过滤 Agent 思考类内容）
    if content_type in rules.exclude_types:
        return False, f"type_blocked:{content_type}"

    # 3. 允许存储
    return True, "allowed"


def detect_failure_content(content: str) -> tuple[bool, str]:
    """
    检测失败/错误内容
    返回: (is_failure, transformed_type)

    关键改进：错误内容不再是"垃圾"，而是"失败经验"
    """
    content_lower = content.lower()
    error_keywords = ["错误", "error", "失败", "fail", "异常", "exception", "失败原因"]

    for keyword in error_keywords:
        if keyword in content_lower:
            return True, "failure_experience"

    return False, "general"


def filter_with_score(content: str, metadata: dict = None, rules: FilterRules = None) -> tuple[bool, str, int]:
    """
    带评分的过滤器
    返回: (should_store, reason, score)

    评分用于决定记忆等级
    """
    if rules is None:
        rules = FilterRules()

    content_type = metadata.get("type", "general") if metadata else "general"
    should_store_result, reason = should_store(content, content_type, rules)

    if not should_store_result:
        return False, reason, 0

    # 计算评分
    score = 0
    score_rules = rules.route_score_rules
    content_lower = content.lower()

    # 长度评分
    if len(content) > 100:
        score += score_rules.get("length_gt_100", 0)
    if len(content) > 500:
        score += score_rules.get("length_gt_500", 0)

    # 成功关键词评分
    success_keywords = ["成功", "完成", "success", "done", "completed"]
    for kw in success_keywords:
        if kw in content_lower:
            score += score_rules.get("success_keyword", 0)
            break

    # 策略关键词评分
    strategy_keywords = ["策略", "规划", "policy", "strategy", "方案"]
    for kw in strategy_keywords:
        if kw in content_lower:
            score += score_rules.get("strategy_keyword", 0)
            break

    # 重要关键词评分
    important_keywords = ["重要", "关键", "important", "critical", "核心"]
    for kw in important_keywords:
        if kw in content_lower:
            score += score_rules.get("important_keyword", 0)
            break

    # 知识关键词评分
    knowledge_keywords = ["知识", "规则", "knowledge", "rule", "原则"]
    for kw in knowledge_keywords:
        if kw in content_lower:
            score += score_rules.get("knowledge_keyword", 0)
            break

    # 失败经验评分（新增：不再过滤，而是加分）
    is_failure, failure_type = detect_failure_content(content)
    if is_failure:
        score += score_rules.get("failure_experience", 2)

    # metadata 评分
    if metadata:
        if content_type == "strategy":
            score += score_rules.get("type_strategy", 0)
        elif content_type == "result":
            score += score_rules.get("type_result", 0)
        elif content_type == "failure_experience":
            score += score_rules.get("failure_experience", 0)

    return True, "allowed", score
