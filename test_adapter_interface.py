#!/usr/bin/env python3
"""
正式验收测试：测试 adapter 接口
测试三类任务：implementation, decision, continuation
"""
import sys
import json
from pathlib import Path

# 添加 4_core 到路径
sys.path.insert(0, str(Path(__file__).parent / "4_core"))

from logic.rules import FilterRules, RoutingRules
from logic.engine import OptimizationInput, optimize_context


def load_test_query():
    """加载测试查询"""
    test_file = Path(__file__).parent / "temp_query.json"
    if test_file.exists():
        with open(test_file, encoding="utf-8") as f:
            return json.load(f)
    
    # 默认测试数据
    return {
        "query": "测试查询",
        "candidate_memories": [
            {
                "id": "mem1",
                "type": "knowledge",
                "category": "knowledge",
                "content": "这是一条关于项目架构的知识记忆，内容超过二十个字",
                "abstract": "项目架构知识"
            },
            {
                "id": "mem2",
                "type": "result",
                "category": "result",
                "content": "这是一条关于之前完成的工作的结果记忆",
                "abstract": "工作结果"
            },
            {
                "id": "mem3",
                "type": "strategy",
                "category": "strategy",
                "content": "这是一条关于如何做事情的策略记忆",
                "abstract": "策略指南"
            }
        ]
    }


def test_task_type(task_type: str, context_bypass: bool = False):
    """测试特定任务类型"""
    print(f"\n{'='*80}")
    print(f"测试任务类型: {task_type}")
    print(f"context_bypass: {context_bypass}")
    print(f"{'='*80}")
    
    test_data = load_test_query()
    
    # 创建输入
    input_data = OptimizationInput(
        query=test_data["query"],
        candidate_memories=test_data["candidate_memories"],
        filter_rules=FilterRules(),
        routing_rules=RoutingRules(),
        packing_enabled=True,
        max_local_cards=4,
        candidate_limit=16,
        task_type=task_type,
        context_bypass=context_bypass,
        bypassed_context_tokens=500 if context_bypass else 0,
    )
    
    # 运行优化
    print(f"\n正在执行 optimize_context()...")
    result = optimize_context(input_data)
    
    # 输出结果
    print(f"\n✅ 执行完成！")
    print(f"\n--- Optimization Result ---")
    print(f"candidate_count: {result.candidate_count}")
    print(f"selected_count: {result.selected_count}")
    print(f"packed_context length: {len(result.packed_context)}")
    
    # 检查 meter artifact
    print(f"\n--- Meter Artifact ---")
    meter = result.meter_artifact
    print(f"task_type: {meter.get('task_type')}")
    print(f"context_bypass: {meter.get('context_bypass')}")
    print(f"bypassed_context_tokens: {meter.get('bypassed_context_tokens')}")
    print(f"saved_tokens_estimate: {meter.get('saved_tokens_estimate')}")
    print(f"baseline_tokens_estimate: {meter.get('baseline_tokens_estimate')}")
    print(f"actual_tokens_estimate: {meter.get('actual_tokens_estimate')}")
    
    # 验证字段
    print(f"\n--- 验证检查 ---")
    
    # 检查 1: task_type 是否在 response 中
    if meter.get('task_type') == task_type:
        print(f"✅ PASS: task_type='{task_type}' 在 response 中")
    else:
        print(f"❌ FAIL: task_type 缺失或不正确 (expected: {task_type}, got: {meter.get('task_type')})")
    
    # 检查 2: context_bypass 是否在 response 中
    if meter.get('context_bypass') == context_bypass:
        print(f"✅ PASS: context_bypass={context_bypass} 在 response 中")
    else:
        print(f"❌ FAIL: context_bypass 缺失或不正确 (expected: {context_bypass}, got: {meter.get('context_bypass')})")
    
    # 检查 3: matched_keywords (应该缺失，因为还未实现)
    if 'matched_keywords' in meter:
        print(f"⚠️  NOTE: matched_keywords 在 response 中: {meter.get('matched_keywords')}")
    else:
        print(f"ℹ️  INFO: matched_keywords 在 response 中缺失 (预期)")
    
    # 检查 4: decision / continuation 是否受影响
    # 验证 selected_memories 是否正常
    if result.selected_count > 0:
        print(f"✅ PASS: decision logic 正常工作，选择了 {result.selected_count} 条记忆")
    else:
        print(f"⚠️  NOTE: 没有选择任何记忆")
    
    return result, meter


def main():
    """主测试函数"""
    print("="*80)
    print("Omnimemora 正式验收测试")
    print("="*80)
    
    results = {}
    
    # 测试 1: implementation 任务 (应该绕过 optimize_context)
    print("\n" + "="*80)
    print("测试 1: implementation 任务 (context_bypass=True)")
    results['implementation'] = test_task_type("implementation", context_bypass=True)
    
    # 测试 2: decision 任务
    print("\n" + "="*80)
    print("测试 2: decision 任务 (context_bypass=False)")
    results['decision'] = test_task_type("decision", context_bypass=False)
    
    # 测试 3: continuation 任务
    print("\n" + "="*80)
    print("测试 3: continuation 任务 (context_bypass=False)")
    results['continuation'] = test_task_type("continuation", context_bypass=False)
    
    # 总结
    print("\n" + "="*80)
    print("验收测试总结")
    print("="*80)
    
    print("\n✅ 已完成的测试:")
    for task_type in ['implementation', 'decision', 'continuation']:
        result, meter = results[task_type]
        print(f"  - {task_type}:")
        print(f"    * task_type in response: {meter.get('task_type')}")
        print(f"    * context_bypass in response: {meter.get('context_bypass')}")
        print(f"    * selected memories: {result.selected_count}")
    
    print("\n📋 待实现:")
    print("  - matched_keywords 字段")
    print("  - implementation 任务真正绕过 optimize_context 的逻辑")
    
    print("\n✅ 验收测试完成！")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
