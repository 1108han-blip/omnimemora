
# 5_connectors/ - 连接器

**Purpose:** 各终端的 connector/skill/plugin，必须隔离

## 职责

- omni-claude-code-skill（Claude Code 用户）
- omni-codex-connector（Codex 用户）
- omni-openclaw-plugin（OpenClaw 用户）
- omni-generic-connector（通用开发者）

## 目录结构

```
5_connectors/
  omni-claude-code-skill/
  omni-codex-connector/
  omni-openclaw-plugin/
  omni-generic-connector/
  shared/  (共享库，谨慎使用)
```

## 治理规则

- ✅ 各 connector 必须完全隔离
- ✅ 只能通过标准 API 与 core 交互
- ❌ 不得直接依赖另一 connector 的内部实现
- ❌ 共享逻辑必须放在 shared/ 并经过评审
