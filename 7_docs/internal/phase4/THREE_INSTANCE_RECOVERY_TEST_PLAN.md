---
doc_id: PLAN-PHASE4-RECOVERY-TEST
title: Phase 4 Three Instance Recovery Test Plan
owner: doc-team
reviewers: [arch-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-12
depends_on: [ADR-0001-PRODUCT-BOUNDARY, PLAN-PHASE4-STATUS]
supersedes: []
last_verified_commit: ""
---

# 三实例恢复测试计划

**目标**: 确认框架修复后，OmniMemora 系统重新具备真实运行和真实测量资格
**日期**: 2026-04-12
**执行前提**: 框架修复完成，所有单元测试通过（31/31 task_classifier, 17/17 policy_v1_bypass, test_boundary, test_adapter_interface）

---

## 系统架构（当前状态）

```
                    ┌─────────────────────────────────────────────────────┐
                    │  OmniMemora System                                  │
                    │                                                     │
                    │  ┌──────────────┐      ┌────────────────────────┐  │
                    │  │ Claude Code  │      │ Codex                   │  │
                    │  │ OpenClaw     │──────│ (via memrun.py)         │  │
                    │  └──────────────┘      └────────────┬───────────┘  │
                    │                                     │               │
                    │                    ┌────────────────▼────────────┐  │
                    │                    │ Python Adapter (Unified)   │  │
                    │                    │ Port: 18011                 │  │
                    │                    │ Connects to: 8765           │  │
                    │                    └────────────┬───────────────┘  │
                    │                                 │                   │
                    │                    ┌────────────▼───────────────┐  │
                    │                    │ Go Runtime (Memory Plane)  │  │
                    │                    │ Port: 8765                 │  │
                    │                    │ Backend: omnimemora_runtime│  │
                    │                    └────────────────────────────┘  │
                    └─────────────────────────────────────────────────────┘
```

**关键端口**:
- `18011`: OmniMemora 统一产品入口（REST + MCP）
- `8765`: OmniMemora Go Runtime 内部后端（存储/检索）

---

## 测试矩阵

| 测试编号 | 测试类型 | 目标端口 | 验证内容 |
|---------|---------|---------|---------|
| T1 | 连通性 | 18011 | Unified Entry 健康检查 |
| T2 | 连通性 | 8765 | Go Runtime 内部后端健康检查 |
| T3 | 主链路 | 18011 → 8765 | `/memory/query` 完整路径 |
| T4 | 写入 | 18011 → 8765 | `/memory/write` 端点 |
| T5 | 搜索 | 18011 → 8765 | `/memory/search` 端点 |
| T6 | Token Savings | 18011 | Meter artifact 正常生成 |
| T7 | Usage Log | 18011 | Usage state 正常更新 |

---

## 第一阶段：连通性验证（T1-T2）

### T1: Unified Entry (18011) 健康检查

```bash
curl -s "http://127.0.0.1:18011/health?mode=local"
curl -s "http://127.0.0.1:18011/mcp"
```

**期望**: HTTP 200，返回健康状态
**失败则**: Adapter 未启动，需执行 `python tools\_run_adapter.py`

### T2: Go Runtime (8765) 内部后端健康检查（可选）

```bash
curl -s http://127.0.0.1:8765/health
```

**期望**: HTTP 200，返回健康状态
**失败则**: Go Runtime 未启动，需先执行 `tools\start_omnimemora.bat`

---

## 第二阶段：主链路验证（T3-T5）

### T3: Query Path（核心）

**请求**:
```bash
curl -s -X POST http://127.0.0.1:18011/memory/query \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test-tenant",
    "user": "test-user",
    "agent": "openclaw",
    "query": "what is the project architecture",
    "options": {
      "max_local_cards": 4,
      "enable_packing": true
    }
  }'
```

**期望**:
- HTTP 200
- 响应包含 `packed_context`, `meter_artifact`, `task_type`
- `meter_artifact.saved_tokens_estimate >= 0`
- 无 500/502/503 错误

**验证点**:
1. Adapter 能连接 Runtime (8765)
2. Query path 能执行 `optimize_context()`
3. Meter artifact 正常生成

### T4: Write Path

**请求**:
```bash
curl -s -X POST http://127.0.0.1:18011/memory/write \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test-tenant",
    "user": "test-user",
    "agent": "openclaw",
    "content": "这是一个测试记忆：OmniMemora 框架修复后验证",
    "category": "knowledge"
  }'
```

**期望**:
- HTTP 200 或 201
- 响应包含 `uri` 或 `id`

**注意**: Write 端点可能返回 501 (omnimemora_runtime 不支持写入)，这是已知限制

### T5: Search Path

**请求**:
```bash
curl -s -X POST http://127.0.0.1:18011/memory/search \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test-tenant",
    "user": "test-user",
    "query": "architecture"
  }'
```

**期望**:
- HTTP 200
- 响应包含 `results` 数组

---

## 第三阶段：Token Savings & Metering（T6-T7）

### T6: Token Savings 正常生成

从 T3 的响应中提取:

```python
meter = response["meter_artifact"]
assert meter["baseline_tokens_estimate"] > 0
assert meter["actual_tokens_estimate"] >= 0
assert meter["saved_tokens_estimate"] >= 0
assert 0 <= meter["savings_ratio"] <= 1.0
```

**验证 P0 修复未破坏**:
- `baseline_chars` 计算正确（avg_chars × candidate_limit）
- `_score` 和 `_final_score` 同步

### T7: Usage Log 一致性

检查 `data/usage_state.json`:

```bash
type "e:\AI2\Vault\13_OmniMemora\OmniMemora\4_core\data\usage_state.json"
```

**期望**:
- `request_count` >= 已执行的查询数
- `saved_tokens_total` >= 0
- `quota_status` 为 `untracked` / `within_quota` / `over_quota` 之一

---

## 第四阶段：Policy v1 Bypass 验证

### T8: Implementation Query Bypass

**请求**:
```bash
curl -s -X POST http://127.0.0.1:18011/memory/query \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test-tenant",
    "user": "test-user",
    "agent": "openclaw",
    "query": "write code for login function"
  }'
```

**期望**:
- `task_type == "implementation"`
- `context_bypass == true`
- `packed_context == ""` 或为空

### T9: Decision Query Non-Bypass

**请求**:
```bash
curl -s -X POST http://127.0.0.1:18011/memory/query \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test-tenant",
    "user": "test-user",
    "agent": "openclaw",
    "query": "which database should i choose for caching"
  }'
```

**期望**:
- `task_type == "decision"`
- `context_bypass == false`
- `packed_context != ""`

---

## 执行顺序

```
阶段一（T1-T2）  →  T3-T5  →  T6-T7  →  T8-T9
（先保连通）       （主链路）  （Token计量）  （Policy行为）
```

**全部通过则进入**：真实实例对话验证

---

## 真实实例对话验证（可选，如条件允许）

### Claude Code / Codex / OpenClaw 三实例

使用 `tools/memrun.py`:

```bash
# OpenClaw
python tools/memrun.py --agent openclaw --query "what is the project architecture"

# Codex
python tools/memrun.py --agent codex --query "summarize the codebase"

# Claude Code
python tools/memrun.py --agent claude_code --query "explain the auth flow"
```

**验证点**:
1. 每个实例能成功调用 adapter
2. 日志中能看到 task_type / context_bypass
3. usage_state.json 有对应记录

---

## 快速验证脚本

```bash
# 保存到: tools\quick_recovery_test.bat
@echo off
echo === OmniMemora Recovery Test ===
echo.

echo [T1] Checking Go Runtime (internal backend) on 8765...
curl -s --max-time 3 http://127.0.0.1:8765/health >nul 2>&1
if %errorlevel%==0 (echo  [PASS] Go Runtime is UP) else (echo  [FAIL] Go Runtime is DOWN)
echo.

echo [T2] Checking Python Adapter on 18011...
curl -s --max-time 3 "http://127.0.0.1:18011/health?mode=local" >nul 2>&1
if %errorlevel%==0 (echo  [PASS] Adapter is UP) else (echo  [FAIL] Adapter is DOWN)
echo.

echo [T3] Testing Query Path...
curl -s -X POST http://127.0.0.1:18011/memory/query ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"test query\",\"options\":{\"max_local_cards\":4}}" >nul 2>&1
if %errorlevel%==0 (echo  [PASS] Query path OK) else (echo  [FAIL] Query path FAILED)
echo.

echo [T8] Testing Implementation Bypass...
curl -s -X POST http://127.0.0.1:18011/memory/query ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"write code for login\"}" | findstr /C:"implementation" >nul 2>&1
if %errorlevel%==0 (echo  [PASS] Implementation bypass OK) else (echo  [FAIL] Implementation bypass FAILED)
echo.

echo === Quick Test Complete ===
pause
```

---

## 成功标准

| 测试阶段 | 通过条件 |
|---------|---------|
| T1-T2 连通性 | 两个端口都能响应 |
| T3 主链路 | Query 返回 200，含 meter_artifact |
| T6 Token Savings | saved_tokens_estimate >= 0 |
| T8-T9 Policy | implementation 走 bypass，decision 走正常 |
| **全部** | **T1-T2 + T3 + T6 + T8-T9 通过** |

---

## 失败处理

| 失败点 | 可能原因 | 处理方式 |
|--------|---------|---------|
| T1 Go Runtime down | `omnimemora.exe` 未启动 | 执行 `tools\start_omnimemora.bat` |
| T2 Adapter down | Python 服务未启动 | 执行 `python tools\_run_adapter.py` |
| T3 Query 500 | Engine 逻辑修复引入新 bug | 回滚 engine.py / router.py |
| T6 Savings = -1 | baseline 计算公式错误 | 检查 P0-1.1.1 修复 |
| T8 Implementation 未 bypass | task_classifier 逻辑损坏 | 检查 `_check_substring_matches` |

---

## 文档记录

测试完成后，填写 `7_docs/internal/phase4/p0-3_验收模板.md`：

```
- 日期：2026-04-12
- 执行人：Claude Code
- 环境：本地开发机
- Runtime 地址（内部后端）：http://127.0.0.1:8765
- 框架修复版本： AUDIT_REPORT_LOGIC_CORE_FIXES_2026-04-12.md
```

---

**下一步**: 执行本计划 → 通过后 → 进入真实实例对话验证 → 记录最终验收结果
