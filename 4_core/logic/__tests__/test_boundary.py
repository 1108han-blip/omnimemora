"""
Boundary regression test for 4_core/logic layer.
Run from 4_core/ directory:  python -m logic.__tests__.test_boundary
"""
import ast
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = {
    "httpx", "requests", "fastapi", "starlette",
    "os", "glob", "pathlib", "tempfile", "shutil",
    "loguru", "structlog", "logging",
    "database", "sqlalchemy", "sqlite3",
    "app.config", "app.filter", "app.router", "app.dedup",
    "app.normalizer", "app.v2_query", "app.access",
}
FORBIDDEN_PATTERNS = ["open(", "__file__", "os.path", "glob.glob"]


def test_no_forbidden_imports():
    """No .py file in 4_core/logic may import world concerns."""
    errors = []
    DIR = Path(__file__).parent.parent
    for py_file in DIR.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        src = py_file.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS:
                        errors.append(f"{py_file.name}: forbids import '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module in FORBIDDEN_IMPORTS:
                    errors.append(f"{py_file.name}: forbids from '{node.module}'")
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS:
                        errors.append(f"{py_file.name}: forbids '{alias.name}'")

    assert not errors, "\n".join(errors)


def test_no_worldly_patterns():
    """No file may read environment, open files, or use __file__."""
    errors = []
    DIR = Path(__file__).parent.parent
    for py_file in DIR.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        src = py_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in src:
                errors.append(f"{py_file.name}: contains '{pattern}'")

    assert not errors, "\n".join(errors)


def test_rules_and_engine_functional():
    """FilterRules, RoutingRules, and engine.optimize_context must run with zero external deps."""
    # Import as package from parent of 4_core
    # Add 4_core's parent (project root) so 'logic' package is importable
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from logic.rules import FilterRules, RoutingRules
    from logic.engine import OptimizationInput, optimize_context

    fr = FilterRules()
    rr = RoutingRules()
    assert fr.min_content_length == 20
    assert rr.long_term_threshold == 2

    input_data = OptimizationInput(
        query="测试查询",
        candidate_memories=[
            {"content": "这是一个重要的成功经验内容超过二十字", "category": "result", "score": 0.9},
            {"content": "短", "category": "general", "score": 0.5},
            {"content": "这是一个错误失败经验内容要进入L2", "category": "strategy", "score": 0.8},
        ],
        filter_rules=FilterRules(),
        routing_rules=RoutingRules(),
        packing_enabled=True,
        max_local_cards=2,
        candidate_limit=16,
    )
    result = optimize_context(input_data)
    assert isinstance(result.selected_memories, list)
    assert result.candidate_count == 3
    assert result.selected_count <= 2
    assert result.token_savings.saved_tokens_estimate >= 0
    assert result.quota_result.quota_status in ("untracked", "within_quota", "over_quota")


if __name__ == "__main__":
    print("Running boundary tests from:", Path(__file__).parent)
    try:
        test_no_forbidden_imports()
        print("  test_no_forbidden_imports PASSED")
    except AssertionError as e:
        print(f"  test_no_forbidden_imports FAILED:\n    {e}")
        sys.exit(1)

    try:
        test_no_worldly_patterns()
        print("  test_no_worldly_patterns PASSED")
    except AssertionError as e:
        print(f"  test_no_worldly_patterns FAILED:\n    {e}")
        sys.exit(1)

    try:
        test_rules_and_engine_functional()
        print("  test_rules_and_engine_functional PASSED")
    except Exception as e:
        print(f"  test_rules_and_engine_functional FAILED:\n    {e}")
        sys.exit(1)

    print("\nAll boundary tests passed.")
