"""
Task Classifier - Policy v1 Implementation
==========================================
Rule-based, lightweight task classification for context injection control.

Classifies queries into three types:
- implementation: Code/file/technical tasks -> SKIP context injection
- decision: Choice/evaluation tasks -> proceed with optimize_context
- continuation: Query/status tasks -> proceed with optimize_context (default)

No embedding, semantic similarity, or query rewrite is used.
All classification is keyword-based and fully observable.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set


# ------------------------------------------------------------------
# Keyword definitions
# ------------------------------------------------------------------

# Implementation keywords (HIGHEST PRIORITY - any match = implementation)
# Uses substring matching for precision
IMPL_KEYWORDS: List[str] = [
    # Code operations
    "write code", "write a", "write the", "implement", "implementation",
    "create function", "create class", "create method", "create component",
    "add function", "add class", "add method", "add code",
    "fix code", "fix bug", "fix the", "fix my",
    "refactor", "restructure", "rewrite",
    "modify code", "modify function", "modify class",
    "update code", "update function", "update class",
    "delete code", "remove code", "delete function", "remove function",
    "edit code", "edit function", "edit file",

    # File/directory operations
    "create file", "create directory", "create folder",
    "delete file", "delete directory", "delete folder",
    "remove file", "remove directory",
    "move file", "copy file", "rename file",

    # Technical operations
    "compile", "build", "run", "execute", "deploy", "install", "setup", "configure",
    "debug", "test case", "run test", "execute test",
    "setup project", "initialize project", "bootstrap",

    # Development tasks
    "coding", "program", "script", "develop feature", "build feature",
    "extract function", "rename refactor", "inline function",
    "write test", "create test",

    # Infrastructure
    "dockerfile", "config file", "yaml", "json config",

    # Chinese implementation keywords
    "写代码", "编写", "实现", "实现功能", "实现一个",
    "创建函数", "创建类", "创建方法", "新增函数", "新增类",
    "修复", "修复 bug", "修一下", "修这个", "改一下", "改动",
    "重构", "重写", "修改", "更新代码",
    "写文件", "创建文件", "删除文件",
    "编译", "构建", "运行", "部署", "安装", "配置",
    "写测试", "创建测试", "调试",
]

# Decision keywords - uses word-based matching for flexibility
# Strong individual words that indicate decision-making
DECISION_WORDS: Set[str] = {
    "choose", "select", "decide", "determine",
    "recommend", "recommendation", "suggest", "suggestion",
    "better", "best", "worst",
    "compare", "comparison", "versus", "vs",
    "alternative", "alternatives", "instead",
    "pros", "cons", "advantage", "disadvantage",
    "should", "ought",
}

# Decision phrases (must match as contiguous substring)
DECISION_PHRASES: List[str] = [
    "which one", "which should", "which would", "which is better",
    "should i", "should we", "ought to",
    "pros and cons", " advantages", "disadvantages",
    "best approach", "better option", "optimal", "preferred",
    "analyze", "evaluate", "assess", "review",
]

# Continuation keywords - informational queries
# NOTE: Generic question words (what/how/why/when/where/who) are NOT included
# because they appear in ALL query types and don't discriminate continuation.
# Only specific patterns that indicate informational queries are used.
CONTINUATION_PHRASES: List[str] = [
    # Explicit informational patterns
    "what is the", "what's the", "what are the",
    "how to", "how do i", "how does it", "how should i",
    "why does it", "why is it", "why did it",
    "when was the", "when did the", "when will the",
    "where is the", "where did the", "where do i",
    "tell me about", "explain the", "describe the",
    "show me the", "give me the", "provide me with",
    "list of", "find the", "lookup the",
    "status of", "progress on", "current status",
    "what's new", "what changed", "any update",
    "latest", "recent", "up to date",
]

# Continuation indicator words (more specific than generic question words)
CONTINUATION_INDICATORS: Set[str] = {
    "status", "progress", "update", "current", "latest", "recent",
    "new", "changed", "difference", "different", "summary",
    "overview", "report", "list", "find", "search", "lookup",
    "explain", "describe", "show", "tell", "give", "provide",
    "understand", "know", "learn", "discover",
}


@dataclass
class TaskClassification:
    """
    Result of task classification.

    Attributes:
        task_type: One of "implementation", "decision", "continuation"
        matched_keywords: List of keywords that were matched (for observability)
        confidence: "high" if explicit keyword match, "low" if default
    """
    task_type: str
    matched_keywords: List[str] = field(default_factory=list)
    confidence: str = "low"

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "matched_keywords": self.matched_keywords,
            "confidence": self.confidence,
        }


def _check_substring_matches(query_lower: str, phrases: List[str]) -> List[str]:
    """Check which phrases match as substrings in the query."""
    matches = []
    for phrase in phrases:
        if phrase in query_lower:
            matches.append(phrase)
    return matches


def _check_word_matches(query_words: Set[str], word_set: Set[str]) -> List[str]:
    """Check which words from the set appear in the query."""
    matches = []
    for word in word_set:
        if word in query_words:
            matches.append(word)
    return matches


def classify_task(query: str) -> TaskClassification:
    """
    Classify a query into implementation/decision/continuation type.

    Rules (in order of priority):
    1. If ANY implementation keyword matches -> task_type = "implementation"
    2. If ANY decision word or phrase matches -> task_type = "decision"
    3. If ANY continuation word or phrase matches -> task_type = "continuation"
    4. Default -> task_type = "continuation"

    This is intentionally rule-based, lightweight, and observable.
    No embeddings, no semantic similarity, no query rewriting.

    Args:
        query: The user's query string

    Returns:
        TaskClassification with task_type, matched_keywords, and confidence
    """
    if not query or not isinstance(query, str):
        return TaskClassification(
            task_type="continuation",
            matched_keywords=[],
            confidence="low",
        )

    query_lower = query.lower().strip()
    # Strip punctuation from words for better matching
    query_words: Set[str] = set(w.strip('?.,!;:\'\"') for w in query_lower.split())

    # ------------------------------------------------------------------
    # Priority 1: Check for implementation keywords (substring match)
    # ------------------------------------------------------------------
    impl_matches = _check_substring_matches(query_lower, IMPL_KEYWORDS)
    if impl_matches:
        return TaskClassification(
            task_type="implementation",
            matched_keywords=impl_matches,
            confidence="high",
        )

    # ------------------------------------------------------------------
    # Priority 2: Check for decision keywords (word + phrase match)
    # ------------------------------------------------------------------
    decision_word_matches = _check_word_matches(query_words, DECISION_WORDS)
    decision_phrase_matches = _check_substring_matches(query_lower, DECISION_PHRASES)
    decision_matches = decision_word_matches + decision_phrase_matches

    if decision_matches:
        return TaskClassification(
            task_type="decision",
            matched_keywords=decision_matches,
            confidence="high" if decision_phrase_matches else "medium",
        )

    # ------------------------------------------------------------------
    # Priority 3: Check for continuation keywords (phrase + indicator match)
    # Generic question words (what/how/why/when/where/who) are NOT used
    # because they appear in all query types and don't discriminate.
    # ------------------------------------------------------------------
    continuation_phrase_matches = _check_substring_matches(query_lower, CONTINUATION_PHRASES)
    continuation_indicator_matches = _check_word_matches(query_words, CONTINUATION_INDICATORS)
    continuation_matches = continuation_phrase_matches + continuation_indicator_matches

    if continuation_matches:
        return TaskClassification(
            task_type="continuation",
            matched_keywords=continuation_matches,
            confidence="medium" if continuation_phrase_matches else "low",
        )

    # ------------------------------------------------------------------
    # Default: continuation (no keywords matched)
    # ------------------------------------------------------------------
    return TaskClassification(
        task_type="continuation",
        matched_keywords=[],
        confidence="low",
    )


# ------------------------------------------------------------------
# Convenience function for adapter layer
# ------------------------------------------------------------------

def should_bypass_context(query: str) -> tuple[bool, TaskClassification]:
    """
    Convenience function to determine if context injection should be bypassed.

    Returns:
        Tuple of (should_bypass, classification)
        - should_bypass: True if task_type == "implementation"
        - classification: Full TaskClassification for observability
    """
    classification = classify_task(query)
    should_bypass = classification.task_type == "implementation"
    return should_bypass, classification
