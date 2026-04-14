"""
Unit tests for Policy v1 Task Classifier
========================================
Tests for: classify_task() and should_bypass_context()

Covers:
- implementation query classification (should bypass context)
- decision query classification (should NOT bypass)
- continuation query classification (should NOT bypass)
- keyword priority rules
- empty/null query handling
"""
import sys
import os

# Add adapter directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_classifier import (
    classify_task,
    should_bypass_context,
    TaskClassification,
    IMPL_KEYWORDS,
    DECISION_WORDS,
    CONTINUATION_INDICATORS,
)


class TestClassifyTask:
    """Tests for classify_task() function."""

    # ------------------------------------------------------------------
    # Implementation task tests (highest priority - should bypass)
    # ------------------------------------------------------------------

    def test_implementation_code_write(self):
        """Implementation: 'write code for login function' -> implementation"""
        result = classify_task("write code for login function")
        assert result.task_type == "implementation"
        assert "write code" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_create_function(self):
        """Implementation: 'create function to parse JSON' -> implementation"""
        result = classify_task("create function to parse JSON")
        assert result.task_type == "implementation"
        assert "create function" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_fix_bug(self):
        """Implementation: 'fix bug in user authentication' -> implementation"""
        result = classify_task("fix bug in user authentication")
        assert result.task_type == "implementation"
        assert "fix bug" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_refactor(self):
        """Implementation: 'refactor the database layer' -> implementation"""
        result = classify_task("refactor the database layer")
        assert result.task_type == "implementation"
        assert "refactor" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_add_class(self):
        """Implementation: 'add class for payment processing' -> implementation"""
        result = classify_task("add class for payment processing")
        assert result.task_type == "implementation"
        assert "add class" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_build_deploy(self):
        """Implementation: 'build and deploy the API' -> implementation"""
        result = classify_task("build and deploy the API")
        assert result.task_type == "implementation"
        assert "build" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_write_test(self):
        """Implementation: 'write test for the new feature' -> implementation"""
        result = classify_task("write test for the new feature")
        assert result.task_type == "implementation"
        assert "write test" in result.matched_keywords
        assert result.confidence == "high"

    def test_implementation_create_file(self):
        """Implementation: 'create file for configuration' -> implementation"""
        result = classify_task("create file for configuration")
        assert result.task_type == "implementation"
        assert "create file" in result.matched_keywords
        assert result.confidence == "high"

    # ------------------------------------------------------------------
    # Decision task tests (should NOT bypass)
    # ------------------------------------------------------------------

    def test_decision_choose(self):
        """Decision: 'choose between PostgreSQL and MySQL' -> decision"""
        result = classify_task("choose between PostgreSQL and MySQL")
        assert result.task_type == "decision"
        assert "choose" in result.matched_keywords
        # confidence="medium" because "choose" is a word match, not a phrase match
        assert result.confidence == "medium"

    def test_decision_which_is_better(self):
        """Decision: 'which is better for caching, Redis or Memcached?' -> decision"""
        result = classify_task("which is better for caching, Redis or Memcached?")
        assert result.task_type == "decision"
        assert "which is better" in result.matched_keywords
        assert result.confidence == "high"

    def test_decision_should_i(self):
        """Decision: 'should i use React or Vue for this project?' -> decision"""
        result = classify_task("should i use React or Vue for this project?")
        assert result.task_type == "decision"
        assert "should i" in result.matched_keywords
        assert result.confidence == "high"

    def test_decision_recommend(self):
        """Decision: 'recommend a cloud provider for startup' -> decision"""
        result = classify_task("recommend a cloud provider for startup")
        assert result.task_type == "decision"
        assert "recommend" in result.matched_keywords
        # confidence="medium" because "recommend" is a word match, not a phrase match
        assert result.confidence == "medium"

    def test_decision_pros_and_cons(self):
        """Decision: 'what are the pros and cons of microservices?' -> decision"""
        result = classify_task("what are the pros and cons of microservices?")
        assert result.task_type == "decision"
        assert "pros and cons" in result.matched_keywords
        assert result.confidence == "high"

    def test_decision_compare(self):
        """Decision: 'compare REST vs GraphQL for this API' -> decision"""
        result = classify_task("compare REST vs GraphQL for this API")
        assert result.task_type == "decision"
        assert "compare" in result.matched_keywords
        # confidence="medium" because "compare"/"vs" are word matches, not phrase matches
        assert result.confidence == "medium"

    # ------------------------------------------------------------------
    # Continuation task tests (default - should NOT bypass)
    # ------------------------------------------------------------------

    def test_continuation_what_is(self):
        """Continuation: 'what is the timezone setting?' -> continuation"""
        result = classify_task("what is the timezone setting?")
        assert result.task_type == "continuation"
        # phrase "what is the" matches, so check substring containment
        assert any("what is" in kw for kw in result.matched_keywords)
        assert result.confidence == "medium"

    def test_continuation_how_to(self):
        """Continuation: 'how to reset my password?' -> continuation"""
        result = classify_task("how to reset my password?")
        assert result.task_type == "continuation"
        # phrase "how to" matches
        assert any("how to" in kw for kw in result.matched_keywords)
        assert result.confidence == "medium"

    def test_continuation_explain(self):
        """Continuation: 'explain the authentication flow' -> continuation"""
        result = classify_task("explain the authentication flow")
        assert result.task_type == "continuation"
        # "explain" appears as both phrase ("explain the") and word
        assert any("explain" in kw for kw in result.matched_keywords)
        assert result.confidence == "medium"

    def test_continuation_tell_me(self):
        """Continuation: 'tell me about my project status' -> continuation"""
        result = classify_task("tell me about my project status")
        assert result.task_type == "continuation"
        # phrase "tell me about" matches, so "tell me" is a substring of a matched keyword
        assert any("tell me" in kw for kw in result.matched_keywords)
        assert result.confidence == "medium"

    def test_continuation_what_changed(self):
        """Continuation: 'what changed in the latest update?' -> continuation"""
        result = classify_task("what changed in the latest update?")
        assert result.task_type == "continuation"
        # phrase "what changed" matches
        assert any("what changed" in kw for kw in result.matched_keywords)
        assert result.confidence == "medium"

    def test_continuation_default(self):
        """Continuation: 'status of current sprint' -> continuation"""
        result = classify_task("status of current sprint")
        assert result.task_type == "continuation"
        assert "status" in result.matched_keywords
        # confidence="medium" because "status of" phrase matches (phrase > word -> medium)
        assert result.confidence == "medium"

    # ------------------------------------------------------------------
    # Priority rule tests
    # ------------------------------------------------------------------

    def test_implementation_priority_over_decision(self):
        """Implementation keywords take priority over decision keywords."""
        # Query contains both implementation and decision keywords
        result = classify_task("fix the bug - which approach is better?")
        # "fix" is implementation (matches "fix the" in IMPL_KEYWORDS)
        # "which is better" is decision phrase
        # Implementation should win due to priority
        assert result.task_type == "implementation"
        # "fix the" is the matched keyword (listed before "fix bug" in IMPL_KEYWORDS)
        assert any("fix" in kw for kw in result.matched_keywords)

    def test_decision_priority_over_continuation(self):
        """Decision keywords take priority over continuation keywords."""
        result = classify_task("which database should i choose - it's for user preferences")
        assert result.task_type == "decision"
        # "should", "choose", and "should i" are matched (word + phrase)
        # "which should" is NOT a contiguous substring of this query
        assert any(kw in result.matched_keywords for kw in ["should", "choose", "should i"])

    # ------------------------------------------------------------------
    # Edge case tests
    # ------------------------------------------------------------------

    def test_empty_query(self):
        """Empty query defaults to continuation."""
        result = classify_task("")
        assert result.task_type == "continuation"
        assert result.matched_keywords == []
        assert result.confidence == "low"

    def test_none_query(self):
        """None query defaults to continuation."""
        result = classify_task(None)
        assert result.task_type == "continuation"
        assert result.confidence == "low"

    def test_whitespace_query(self):
        """Whitespace-only query defaults to continuation."""
        result = classify_task("   ")
        assert result.task_type == "continuation"
        assert result.confidence == "low"

    def test_unknown_query(self):
        """Unknown query without keywords defaults to continuation."""
        result = classify_task("gibberish_random_text_here_12345")
        assert result.task_type == "continuation"
        assert result.matched_keywords == []
        assert result.confidence == "low"


class TestShouldBypassContext:
    """Tests for should_bypass_context() convenience function."""

    def test_bypass_true_for_implementation(self):
        """should_bypass_context returns True for implementation tasks."""
        should_bypass, classification = should_bypass_context("write code for login")
        assert should_bypass is True
        assert classification.task_type == "implementation"

    def test_bypass_false_for_decision(self):
        """should_bypass_context returns False for decision tasks."""
        should_bypass, classification = should_bypass_context("which database is better?")
        assert should_bypass is False
        assert classification.task_type == "decision"

    def test_bypass_false_for_continuation(self):
        """should_bypass_context returns False for continuation tasks."""
        should_bypass, classification = should_bypass_context("what is my project name?")
        assert should_bypass is False
        assert classification.task_type == "continuation"


class TestTaskClassificationToDict:
    """Tests for TaskClassification.to_dict() method."""

    def test_to_dict_contains_all_fields(self):
        """to_dict() should return all fields."""
        classification = TaskClassification(
            task_type="implementation",
            matched_keywords=["fix bug", "refactor"],
            confidence="high",
        )
        d = classification.to_dict()
        assert d["task_type"] == "implementation"
        assert d["matched_keywords"] == ["fix bug", "refactor"]
        assert d["confidence"] == "high"

    def test_to_dict_empty_keywords(self):
        """to_dict() should handle empty matched_keywords."""
        classification = TaskClassification(
            task_type="continuation",
            matched_keywords=[],
            confidence="low",
        )
        d = classification.to_dict()
        assert d["matched_keywords"] == []
