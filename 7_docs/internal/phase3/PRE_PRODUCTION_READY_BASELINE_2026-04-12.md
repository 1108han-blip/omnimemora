# OmniMemora Pre-Production Ready Baseline

**日期**: 2026-04-12
**版本**: 1.0
**状态**: ✅ PRE-PRODUCTION READY

---

## 版本声明

> **OmniMemora 已完成核心四链闭环验证，具备 pre-production ready 条件，可进入稳定性验证与迁移验收阶段。**

---

## 基线版本信息

| 属性 | 值 |
|------|-----|
| 审计报告 | `7_docs/internal/phase3/audit/AUDIT_REPORT_LOGIC_CORE_FIXES_2026-04-12.md` |
| 稳定化计划 | `7_docs/internal/phase3/LOCAL_STABILIZATION_AND_MIGRATION_PLAN.md` |
| 恢复测试计划 | `7_docs/internal/phase4/THREE_INSTANCE_RECOVERY_TEST_PLAN.md` |
| 测试基线时间 | 2026-04-12 22:47 UTC |
| 框架修复完成时间 | 2026-04-12 |

---

## 四链闭环状态

| 链路 | 状态 | 验证结果 |
|------|------|---------|
| 数据链（write/query） | ✅ | 写入成功，URI返回，可查询命中 |
| 策略链（Policy bypass） | ✅ | implementation bypass=True, decision bypass=False |
| 压缩链（Token savings） | ✅ | baseline=108, saved=44, ratio=0.407 |
| 观测链（Usage log + instance区分） | ✅ | request_count正常，按agent分组正确 |

---

## 核心验证数据

### Query Path
```
Request ID: req-06dca738
tenant=test, agent=claude_code
baseline_tokens=108, actual_tokens=64, saved_tokens=44
savings_ratio=0.407
```

### Usage Aggregation
```
tenant=test
request_count=1
saved_tokens_total=44
by_agent=[{'agent': 'claude_code', 'saved_tokens': 44, 'savings_ratio': 0.407}]
```

### Three Instance Differentiation
```
tenant=prod
openclaw:  saved=44, ratio=0.407
claude_code: saved=44, ratio=0.407
codex:     saved=44, ratio=0.407
total request_count=3
```

---

## 单元测试基线

| 测试文件 | 结果 |
|---------|------|
| `test_boundary.py` | ✅ PASS |
| `test_policy_v1_bypass.py` | ✅ 17/17 PASS |
| `test_adapter_interface.py` | ✅ PASS |
| `test_task_classifier.py` | ✅ 31/31 PASS（校准后）|

---

## 框架修复清单（来源：AUDIT_REPORT_LOGIC_CORE_FIXES_2026-04-12）

### engine.py
- P0-1.1.1: `baseline_chars` 计算公式修复（avg_chars × candidate_limit）
- P0-1.1.2: `_score` / `_final_score` 同步更新
- P1-1.1.3: 删除死函数 `reduce_redundancy()`，新增 `_extract_content_metadata()`
- P1-1.1.5: `dedup_applied` 改为动态计算
- P2-1.1.8: `timestamp` 硬编码修复
- P2-1.1.10: 输入验证（candidate_limit, max_local_cards）

### router.py
- P0-1.2.1: `calculate_memory_score_detailed()` 返回 5-tuple（含 `is_failure`）
- P0-1.2.2: 提取 `_match_keywords()` helper，消除 4x 关键词匹配重复

### filter.py
- P1-1.3.3: `success_keywords` 中 `"完成"` 去重

### v2_compute.py
- P1-1.3.8: `build_packed_context()` score 显示修复（score= 而非 %）
- P1-1.3.9: `classify_query_shape()` 短句模式增加字数保护

---

## 恢复测试补充修复

### X-1: `meter_store.py` — dict 类型直接存储
**问题**: `store_meter(dict)` 将 dict 直接存入 `_meter_store`，导致 `get_meter()` 返回 dict，调用 `.to_dict()` 时报错
**修复**: dict 先转换为 `TokenSavingsMeter` 再存储

### X-2: `main.py:2164` — tenant 硬编码为 "engine"
**问题**: `result.meter_artifact["tenant"]` 未设置，engine 返回的 meter 中 tenant="engine"，导致按真实租户的 usage 聚合始终为空
**修复**: `result.meter_artifact["tenant"] = access.tenant_id`

---

## 系统架构

```
Port 8765  →  OmniMemora Go Runtime (MCP SSE) v1.0.0
Port 18011 →  Python REST Adapter
                  ├── Query Path: optimize_context()
                  ├── Policy v1: task_classifier bypass
                  ├── Metering: meter_store (persistence)
                  └── Usage: per-tenant per-agent aggregation
```

---

## 关联文档

| 文档 | 路径 |
|------|------|
| 框架修复审计报告 | `7_docs/internal/phase3/audit/AUDIT_REPORT_LOGIC_CORE_FIXES_2026-04-12.md` |
| 稳定化与迁移计划 | `7_docs/internal/phase3/LOCAL_STABILIZATION_AND_MIGRATION_PLAN.md` |
| 三实例恢复测试计划 | `7_docs/internal/phase4/THREE_INSTANCE_RECOVERY_TEST_PLAN.md` |
| P0-3 验收模板 | `7_docs/internal/phase4/p0-3_验收模板.md` |
| P0-3 手工 SOP | `7_docs/internal/phase4/p0-3_手工SOP_openclaw.md` |

---

**签署**: Claude Code
**日期**: 2026-04-12
