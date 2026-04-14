---
doc_id: SPEC-DOMAIN-NNN
title: <Interface/State Machine/Data Model Name>
owner: <team-name>
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 0.1.0
effective_date: YYYY-MM-DD
depends_on: []
supersedes: []
last_verified_commit: ""
---

# SPEC-DOMAIN-NNN: <Title>

**状态：** `{{STATUS}}`
**接口版本：** X.Y
**所属 ADR：** `<doc_id>`

---

## 0. Summary

> 一句话说明这个 spec 定义了什么。

---

## 1. 接口定义（Interface）

### 端点（Endpoints）

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/...` | ... | JSON | JSON |

### 请求/响应语义

#### Request
```json
{
  "field": "type — 说明"
}
```

#### Response (Success - 200)
```json
{
  "field": "type — 说明"
}
```

#### Response (Error - 4xx/5xx)
```json
{
  "error": "string — 错误码",
  "message": "string — 人类可读描述"
}
```

---

## 2. 状态机（State Machine）

```
  [State] --event--> [NextState]
```

| 当前状态 | 事件 | 下一状态 | 说明 |
|---------|------|---------|------|
| idle | start | running | ... |
| running | complete | success | ... |
| running | fail | error | ... |

---

## 3. 数据模型（Data Model）

### Entity: `<Name>`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string (UUID) | ✅ | 唯一标识 |
| `created_at` | int64 (unix ts) | ✅ | 创建时间 |
| `updated_at` | int64 (unix ts) | ✅ | 更新时间 |

---

## 4. 异常语义（Error Semantics）

| 错误码 | HTTP 状态 | 条件 | 处理建议 |
|--------|----------|------|---------|
| `ERR_NOT_FOUND` | 404 | 资源不存在 | 检查 id |
| `ERR_INVALID_INPUT` | 400 | 参数不合规 | 查看 message |

---

## 5. 可观测性（Observability）

- [ ] request_id：每个请求必须携带
- [ ] tenant：每个请求必须携带
- [ ] agent：每个请求必须携带
- [ ] usage record：写入操作必须记录

---

## 6. 与代码对照

| Spec 字段 | 代码位置 | 一致性 |
|-----------|---------|--------|
| 接口路径 | `pkg/api/handler.go` | ✅/❌ |
| 数据模型 | `pkg/models/` | ✅/❌ |

---

## 7. 变更历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | YYYY-MM-DD | 初始版本 |
