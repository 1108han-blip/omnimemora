# 4_core/ - 核心逻辑

---

## 强制约束

**This layer implements logic ONLY.**

- Must not define product behavior, system role, or architecture
- Must not import external world concerns (HTTP, filesystem, config, databases)
- All definitions come from 0_blueprint/
- All rules/data injected from outside, never read from world

---

## 目录结构

```
4_core/
├── logic/                      # 纯逻辑层（无外部依赖）
│   ├── rules.py                # FilterRules / RoutingRules 数据对象
│   ├── dedup.py                # 写入去重（纯逻辑）
│   ├── normalizer.py            # 归一化（纯逻辑）
│   ├── filter.py               # 过滤判断（纯逻辑）
│   ├── router.py               # 路由评分（纯逻辑）
│   ├── v2_compute.py           # Token Savings 计算（纯逻辑，无文件 I/O）
│   └── engine.py               # 统一能力入口 ← 唯一产品能力出口
│
└── README.md
```

## 核心原则

```
4_core/logic/engine.py is the single product capability entrypoint.
All external dependencies (rules, candidate_memories, usage data) are injected.
The engine does not read config, does not touch filesystem, does not make HTTP calls.
```

---

## engine.py — 统一入口

**职责：** 串联纯逻辑模块，执行一次完整的 context 优化决策

**调用链：**
```
filter → route/score → select top-k → pack context → token savings compute → quota check → meter artifact
```

**输入：** `OptimizationInput`（query, candidate_memories, rules, usage, quota）
**输出：** `OptimizationResult`（selected_memories, packed_context, token_savings, quota_result, meter_artifact）

**边界：**
- ✅ 只接收规则和数据，不自己读配置
- ✅ 只做计算和决策，不碰文件系统
- ✅ 所有外部依赖通过 `OptimizationInput` 注入
- ✅ 可独立单元测试（无需 mock HTTP 或文件）

---

## 治理规则

| 规则 | 说明 |
|------|------|
| ❌ 不得 import httpx / fastapi / requests | 外部网络 |
| ❌ 不得 import os / glob / open() | 文件系统 |
| ❌ 不得 import config | 运行时配置 |
| ❌ 不得读写文件 | 世界交互 |
| ❌ 不得有 `__file__` 引用 | 路径依赖 |
| ✅ 所有数据通过参数注入 | 依赖反转 |
| ✅ 所有规则通过 FilterRules / RoutingRules 注入 | 数据对象 |
| ✅ 可独立运行（python -c "from 4_core.logic import engine"） | 可测试性 |

---

## 职责

- ✅ 记忆路由评分逻辑（router.py）
- ✅ Token Savings Meter 计算（v2_compute.py）
- ✅ 去重策略（dedup.py）
- ✅ 过滤策略（filter.py）
- ✅ 归一化逻辑（normalizer.py）
- ✅ 统一优化入口（engine.py ← 唯一能力出口）
