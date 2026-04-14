---
doc_id: PLAN-PHASE4-OBSERVABILITY-JSONL
title: Agent Observability v1.1 — JSONL Persistence
owner: doc-team
reviewers: [arch-lead, sre-lead]
status: active
version: 1.1.0
effective_date: 2026-04-13
depends_on: [ADR-0001-PRODUCT-BOUNDARY, PLAN-PHASE4-STATUS]
supersedes: []
last_verified_commit: ""
---

# Agent Observability v1.1 — JSONL Persistence

**版本：** v1.1
**状态：** PENDING
**日期：** 2026-04-13
**前置：** Phase 4 / Agent Observability Mini v1 (ACCEPTED)

---

## 目标

将 `agent_metrics.py` 从纯内存存储改为 JSONL 持久化，解决"重启后指标清零"问题，同时保持 API 兼容。

---

## 范围

### 只做

1. **request/result 事件写盘** — 每个请求以 JSONL 行写入文件
2. **启动回放** — 进程启动时从 JSONL 文件重建内存状态
3. **API 保持兼容** — `/agents/live` 和 `/agents/metrics` 接口不变
4. **重启恢复测试** — 发送一批请求后重启进程，验证指标不丢失

### 不做

- 不改 `/mcp/query` 主路径
- 不改 engine.py
- 不新增 API
- 不做多文件聚合（单 JSONL 够用）

---

## 实现方案

### 1. JSONL 文件格式

文件路径：`~/.omnimemora/adapter/agent_events.jsonl`（config 可配置）

每行格式：

```jsonl
{"event":"request","agent_id":"openclaw-agent","session_id":"sess_001","mode":"observe","ts":"2026-04-13T16:00:00Z","integration_type":"unknown","workspace_id":"ws_001","user_id":"user_001"}
{"event":"result","agent_id":"openclaw-agent","session_id":"sess_001","optimized":true,"bypassed":false,"saved_tokens":83,"raw_tokens":132,"compressed_tokens":49,"quality_delta_pct":56.44,"ts":"2026-04-13T16:00:01Z"}
```

事件类型：`request` | `result`

### 2. 事件写入

每次 `record_request()` / `record_result()` 时，追加一行到文件。

写入策略：**异步批量写**（每 10 条或每 5 秒 flush 一次），避免 IO 成为瓶颈。

### 3. 启动回放

进程启动时，读取 JSONL 文件，按 `agent_id + session_id` 聚合，重建内存 store。

回放时忽略超过 30 天的旧事件（可配置）。

### 4. 文件滚动

当文件超过 50MB 时，自动 rename 为 `agent_events_YYYYMMDD.jsonl`，新建文件继续写。

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `5_connectors/adapter/agent_metrics.py` | 修改 | JSONL 持久化 + 启动回放 |
| `5_connectors/adapter/config.py` | 修改 | 新增 `agent_events_path` 配置项 |
| `5_connectors/adapter/tests/test_agent_metrics.py` | 新增 | JSONL 读写 + 回放 + 重启恢复测试 |

---

## 验收标准

1. **写盘验证** — 发送 10 条请求后，JSONL 文件存在且行数 >= 20（request + result 各一条）
2. **回放验证** — 重启进程后，`/agents/live` 返回的 request_count 与重启前一致
3. **API 兼容** — `/agents/live` 和 `/agents/metrics` 响应格式与 v1.0 完全一致
4. **重启恢复测试** — 发 5 条请求 → 重启 adapter → 再发 5 条 → 查询 metrics，确认 10 条全部计入

---

## 测试用例

```python
# test_jsonl_write
# test_jsonl_read_on_startup
# test_events_aggregated_correctly
# test_old_events_pruned_on_startup (>30 days)
# test_file_rotation_when_exceeds_50mb
# test_restart_recovery_request_count
```

---

## 风险与回滚

- **风险**：JSONL 写入失败（如磁盘满）导致指标丢失 → 降级为内存模式 + warning log
- **回滚**：将 `agent_metrics.py` 还原为纯内存版本（约 5 行改动），删除 JSONL 文件