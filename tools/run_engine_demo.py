#!/usr/bin/env python3
"""
Engine Demo Tool - 黑盒验证 engine.optimize_context()
"""
import argparse
import json
import sys
from pathlib import Path

# Add 4_core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "4_core"))

from logic.engine import (
    OptimizationInput,
    OptimizationResult,
    optimize_context,
)
from logic.rules import FilterRules, RoutingRules
from logic.filter import filter_with_score, detect_failure_content
from logic.router import calculate_memory_score_detailed
from logic.v2_compute import (
    TokenSavingsMeter,
    build_packed_context,
    check_quota_enforcement,
    estimate_tokens,
)


def load_input_file(file_path: str) -> dict:
    """Load input JSON file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_default_rules() -> tuple[FilterRules, RoutingRules]:
    """Create default filter and routing rules"""
    # Use default rules from logic.rules
    return FilterRules(), RoutingRules()


def print_text_result(result: OptimizationResult, input_data: dict, sort_by: str = "score", all_scored: list = None, output_file: str = None) -> None:
    """Print text format result, optionally to file"""
    import io
    buffer = io.StringIO()
    
    buffer.write("=" * 60 + "\n")
    buffer.write("Engine Optimization Result\n")
    buffer.write("=" * 60 + "\n")
    buffer.write("\n")
    buffer.write(f"Query: {input_data.get('query', '')[:100]}\n")
    buffer.write(f"Sort By: {sort_by}\n")
    buffer.write("\n")
    buffer.write(f"Candidate Memories: {result.candidate_count}\n")
    buffer.write(f"Selected Memories: {result.selected_count}\n")
    buffer.write("\n")
    buffer.write(f"Packed Context Tokens: {result.token_savings.actual_tokens_estimate}\n")
    buffer.write(f"Saved Tokens: {result.token_savings.saved_tokens_estimate}\n")
    buffer.write(f"Savings Percent: {result.token_savings.savings_ratio * 100:.1f}%\n")
    buffer.write("\n")
    buffer.write("Quota:\n")
    buffer.write(f"  - current_usage: {input_data.get('current_usage', 0)}\n")
    buffer.write(f"  - monthly_quota: {input_data.get('monthly_quota')}\n")
    buffer.write(f"  - quota_exceeded: {result.quota_result.quota_exceeded}\n")
    buffer.write(f"  - quota_status: {result.quota_result.quota_status}\n")
    buffer.write("\n")
    
    if all_scored:
        buffer.write("All Scored Memories (with score breakdown):\n")
        for i, mem in enumerate(all_scored, 1):
            final_score = mem.get("_final_score") or mem.get("_score", 0) or mem.get("score", 0)
            tokens = mem.get("tokens", len(mem.get("content", "")) // 4)  # 估算 tokens
            value_density = final_score / max(tokens, 1)
            relevance_score = mem.get("_relevance_score", "-")
            type_score = mem.get("_type_score", "-")
            length_penalty = mem.get("_length_penalty", "-")
            
            if relevance_score != "-":
                buffer.write(f"  {i}. {mem.get('id', 'unknown')}\n")
                buffer.write(f"     ├─ relevance: {relevance_score}\n")
                buffer.write(f"     ├─ type_weight: {type_score}\n")
                buffer.write(f"     ├─ length_penalty: {length_penalty}\n")
                buffer.write(f"     ├─ final_score: {final_score}\n")
                buffer.write(f"     ├─ tokens: {tokens}\n")
                buffer.write(f"     └─ value_density: {value_density:.4f}\n")
            else:
                buffer.write(f"  {i}. {mem.get('id', 'unknown')} (score: {final_score}, tokens: {tokens}, value_density: {value_density:.4f})\n")
        buffer.write("\n")
    
    buffer.write("Selected Memories:\n")
    for i, mem in enumerate(result.selected_memories, 1):
        final_score = mem.get("_final_score") or mem.get("_score", 0) or mem.get("score", 0)
        tokens = mem.get("tokens", len(mem.get("content", "")) // 4)
        value_density = final_score / max(tokens, 1)
        buffer.write(f"  {i}. {mem.get('id', 'unknown')} (score: {final_score}, tokens: {tokens}, value_density: {value_density:.4f})\n")
    buffer.write("\n")
    
    buffer.write("Packed Context:\n")
    buffer.write("-" * 60 + "\n")
    buffer.write(result.packed_context[:500])
    if len(result.packed_context) > 500:
        buffer.write("... (truncated)\n")
    buffer.write("-" * 60 + "\n")
    
    output = buffer.getvalue()
    print(output, end="")
    
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)


def print_json_result(result: OptimizationResult, input_data: dict, output_file: str = None) -> None:
    """Print JSON format result, optionally to file"""
    output = {
        "query": input_data.get('query', ''),
        "candidate_count": result.candidate_count,
        "selected_count": result.selected_count,
        "packed_context_tokens": result.token_savings.actual_tokens_estimate,
        "saved_tokens": result.token_savings.saved_tokens_estimate,
        "savings_percent": round(result.token_savings.savings_ratio * 100, 1),
        "quota": {
            "current_usage": input_data.get('current_usage', 0),
            "monthly_quota": input_data.get('monthly_quota'),
            "quota_exceeded": result.quota_result.quota_exceeded,
            "quota_status": result.quota_result.quota_status,
        },
        "selected_memories": [
            {
                "id": mem.get('id'),
                "category": mem.get('category', 'general'),
                "score": mem.get("_score", 0) or mem.get("score", 0)
            }
            for mem in result.selected_memories
        ],
        "packed_context": result.packed_context,
        "meter_artifact": result.meter_artifact,
    }
    json_output = json.dumps(output, ensure_ascii=False, indent=2)
    print(json_output)
    
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json_output)


def run_optimization_with_sort(input_data: dict, sort_by: str = "score") -> tuple[OptimizationResult, list]:
    """Run optimization with custom sorting"""
    # Create default rules
    filter_rules, routing_rules = create_default_rules()

    # Build OptimizationInput
    opt_input = OptimizationInput(
        query=input_data.get("query", ""),
        candidate_memories=input_data.get("candidate_memories", []),
        filter_rules=filter_rules,
        routing_rules=routing_rules,
        agent=input_data.get("agent", "supervisor"),
        client=input_data.get("client", "openclaw"),
        current_usage=input_data.get("current_usage", 0),
        monthly_quota=input_data.get("monthly_quota"),
        packing_enabled=input_data.get("packing_enabled", True),
        max_local_cards=input_data.get("max_local_cards", 4),
        candidate_limit=input_data.get("candidate_limit", 16),
    )

    candidates = opt_input.candidate_memories[:opt_input.candidate_limit]
    candidate_count = len(candidates)

    # 1. Filter 阶段
    filtered = []
    for mem in candidates:
        content = mem.get("content", "") or mem.get("abstract", "") or ""
        metadata = {"type": mem.get("category", "general")}
        ok, reason, score = filter_with_score(content, metadata, opt_input.filter_rules)
        if ok:
            mem["_score"] = score
            mem["_filter_reason"] = reason
            filtered.append(mem)

    # 2. Route / Score 阶段
    scored = []
    for mem in filtered:
        content = mem.get("content", "") or mem.get("abstract", "") or ""
        metadata = {"type": mem.get("category", "general")}
        relevance_score, type_score, length_penalty, final_score = calculate_memory_score_detailed(content, metadata, opt_input.routing_rules)
        
        # 记录 3 个维度 + final_score
        mem["_relevance_score"] = relevance_score
        mem["_type_score"] = type_score
        mem["_length_penalty"] = length_penalty
        mem["_final_score"] = final_score
        mem["_score"] = final_score  # 向后兼容
        
        is_failure, _ = detect_failure_content(content)
        if is_failure and final_score < 3:
            final_score = 3
            mem["_score"] = final_score  # 更新向后兼容的 score
        scored.append(mem)

    # 3. Reduce redundancy（query 侧去冗余）
    scored_without_dup = []
    seen_contents = set()
    for mem in scored:
        content = mem.get("content", "").strip()
        if content not in seen_contents:
            seen_contents.add(content)
            scored_without_dup.append(mem)

    # 4. Select top-k with custom sorting
    if sort_by == "score_per_token":
        scored_without_dup.sort(key=lambda x: (x.get("_final_score", 0) / max(x.get("tokens", len(x.get("content", "")) // 4), 1)), reverse=True)
    else:
        scored_without_dup.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
    
    selected = scored_without_dup[:opt_input.max_local_cards]
    selected_count = len(selected)

    # 5. Build packed context
    packed_context = build_packed_context(selected) if opt_input.packing_enabled else ""

    # 6. Token savings compute
    actual_chars = len(packed_context) if opt_input.packing_enabled else sum(len(m.get("content", "") or "") for m in selected)
    baseline_chars = sum(len(m.get("content", "") or "") for m in selected) * opt_input.candidate_limit
    saved_chars = max(0, baseline_chars - actual_chars)
    baseline_tokens = estimate_tokens(baseline_chars)
    actual_tokens = estimate_tokens(actual_chars)
    saved_tokens = max(0, baseline_tokens - actual_tokens)
    savings_ratio = saved_tokens / baseline_tokens if baseline_tokens > 0 else 0.0

    # 7. Meter artifact
    meter = TokenSavingsMeter(
        request_id="engine-local",
        tenant="engine",
        user="engine",
        agent=opt_input.agent,
        client=opt_input.client,
        timestamp="",
        query_shape="mixed",
        query_chars=len(opt_input.query),
        query=opt_input.query[:100],
        baseline_chars=baseline_chars,
        actual_chars=actual_chars,
        saved_chars=saved_chars,
        baseline_tokens_estimate=baseline_tokens,
        actual_tokens_estimate=actual_tokens,
        saved_tokens_estimate=saved_tokens,
        savings_ratio=round(savings_ratio, 3),
        packed_memory_count=len(selected),
        local_cards_used=len(selected),
        remote_candidates_considered=opt_input.candidate_limit,
        remote_candidates_skipped=opt_input.candidate_limit - len(selected),
        remote_used_count=0,
        skipped_remote_reason="local-first coverage satisfied",
        coverage_satisfied=True,
        packing_enabled=opt_input.packing_enabled,
        abstract_preferred=False,
        dedup_applied=False,
    )

    # 8. Quota check
    quota_result = check_quota_enforcement(opt_input.current_usage, opt_input.monthly_quota)

    result = OptimizationResult(
        selected_memories=selected,
        packed_context=packed_context,
        token_savings=meter,
        quota_result=quota_result,
        meter_artifact=meter.to_dict(),
        candidate_count=candidate_count,
        selected_count=selected_count,
    )
    
    return result, scored_without_dup


def main():
    parser = argparse.ArgumentParser(description="Engine Demo Tool")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Output format (default: text)")
    parser.add_argument("--sort-by", default="score", choices=["score", "score_per_token"], help="Sorting method (default: score)")
    parser.add_argument("--compare", action="store_true", help="Compare both sorting methods")
    parser.add_argument("--output", help="Output file path to save the result (optional)")
    args = parser.parse_args()

    # Load input
    input_data = load_input_file(args.input)

    if args.compare:
        # Run both sorting methods and compare
        print("=" * 60)
        print("COMPARISON: score vs score_per_token")
        print("=" * 60)
        print()
        
        # Method 1: sort by score
        print("\n" + "=" * 60)
        print("METHOD 1: Sorted by final_score")
        print("=" * 60)
        result_score, all_scored_score = run_optimization_with_sort(input_data, "score")
        print_text_result(result_score, input_data, "score", all_scored_score, args.output if args.format == "text" and not args.compare else None)
        
        # Method 2: sort by score_per_token
        print("\n" + "=" * 60)
        print("METHOD 2: Sorted by value_density (final_score / tokens)")
        print("=" * 60)
        result_density, all_scored_density = run_optimization_with_sort(input_data, "score_per_token")
        print_text_result(result_density, input_data, "score_per_token", all_scored_density)
        
        # Comparison summary
        print("\n" + "=" * 60)
        print("COMPARISON SUMMARY")
        print("=" * 60)
        print()
        print("Selected IDs by final_score:")
        print(f"  {[mem.get('id') for mem in result_score.selected_memories]}")
        print()
        print("Selected IDs by value_density:")
        print(f"  {[mem.get('id') for mem in result_density.selected_memories]}")
        print()
        
        # Check if selections are different
        set_score = set([mem.get('id') for mem in result_score.selected_memories])
        set_density = set([mem.get('id') for mem in result_density.selected_memories])
        
        if set_score != set_density:
            print("✓ Selections DIFFER between the two methods!")
            only_score = set_score - set_density
            only_density = set_density - set_score
            if only_score:
                print(f"  Only in final_score: {only_score}")
            if only_density:
                print(f"  Only in value_density: {only_density}")
        else:
            print("✗ Selections are IDENTICAL between the two methods.")
        
    else:
        # Run single sorting method
        result, all_scored = run_optimization_with_sort(input_data, args.sort_by)
        
        # Print result
        if args.format == "json":
            print_json_result(result, input_data, args.output)
        else:
            print_text_result(result, input_data, args.sort_by, all_scored, args.output)


if __name__ == "__main__":
    main()
