"""
规则定义层 - 纯数据对象
所有规则从外部注入，logic 层不读配置
"""
from dataclasses import dataclass, field
from typing import Dict, List


DEFAULT_SCORE_RULES: Dict[str, int] = {
    "length_gt_100": 1,
    "length_gt_500": 1,
    "success_keyword": 2,
    "strategy_keyword": 2,
    "important_keyword": 2,
    "knowledge_keyword": 2,
    "failure_experience": 2,
    "type_strategy": 2,
    "type_result": 1,
    "type_failure": 2,
}


@dataclass(frozen=True)
class FilterRules:
    min_content_length: int = 20
    exclude_types: List[str] = field(default_factory=lambda: ["chat", "thinking", "debug", "log"])
    route_score_rules: Dict[str, int] = field(default_factory=lambda: DEFAULT_SCORE_RULES.copy())
    long_term_threshold: int = 2


@dataclass(frozen=True)
class RoutingRules:
    route_score_rules: Dict[str, int] = field(default_factory=lambda: DEFAULT_SCORE_RULES.copy())
    long_term_threshold: int = 2
