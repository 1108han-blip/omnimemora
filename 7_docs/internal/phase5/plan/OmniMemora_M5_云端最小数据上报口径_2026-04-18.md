---
doc_id: PLAN-PHASE5-M5-CLOUD-TELEMETRY-2026-04-18
title: OmniMemora M5 云端最小数据上报口径
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5-CONVERGENCE-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora M5 云端最小数据上报口径

## 一、文档定位

本文用于固定 phase5 `M5` 的“最小必要数据”边界。

它回答三个问题：

- 纯本地模式默认是否上报
- 开启云端策略更新后默认上报什么
- 哪些字段不得进入当前 usage telemetry

## 二、当前冻结结论

### 2.1 模式规则

- `纯本地模式`：默认关闭云端策略更新，默认不上报
- `云端增强模式`：开启云端策略更新后，最小必要 usage telemetry 自动启用

### 2.2 当前允许字段

当前 usage telemetry payload 允许包含以下字段：

- `request_id`
- `route`
- `version`
- `saved_tokens`
- `savings_ratio`
- `optimization_enabled`
- `latency_ms`
- `error_code`
- `timestamp`

说明：

- 这些字段都属于运行与质量改进所需的低敏元数据
- 当前实现中 `latency_ms`、`error_code` 可以为空；为空不影响 schema 合法性

### 2.3 当前禁止字段

当前 usage telemetry payload 明确禁止包含：

- `tenant`
- 原始 prompt
- memory 内容
- 上游 API key / Authorization
- 用户原始上游 endpoint secrets

## 三、当前代码对位结果

已确认以下文件共同实现了上述口径：

- [5_connectors/adapter/config.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/config.py)
- [5_connectors/adapter/cloud/models.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/cloud/models.py)
- [5_connectors/adapter/cloud/usage_reporter.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/cloud/usage_reporter.py)
- [5_connectors/adapter/main.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py)

当前实现结论：

- 纯本地模式默认不上报
- 开启云端策略更新后默认允许 usage telemetry
- usage telemetry schema 已移除 `tenant`
- 当前上报入口默认使用：
  - `route="/memory/query"`
  - `version="2.2.0"`
  - `saved_tokens`
  - `savings_ratio`
  - `optimization_enabled`
  - `error_code=None`

## 四、后续演进规则

- 若后续要新增字段，必须先判断是否仍属于“最小必要元数据”
- 若新增字段可能暴露身份、输入内容、记忆内容或密钥，默认禁止
- 若后续把 `latency_ms` 或其他运行指标正式接入，必须先更新本文，再进入实现
