# OmniMemora 零维护安装与 MCP 自动适配方案（v1）

更新时间：2026-04-10  
适用范围：`E:\AI2\Vault\13_OmniMemora\OmniMemora` 全产品系统

## 1. 产品目标（唯一标准）

用户只做两件事：
1. 双击运行 `omnimemora`
2. 在可选页勾选要连接的主体

其余全部自动完成，不要求用户修配置、不要求用户学习主体差异。

## 2. 核心原则

1. 零维护：不给用户任何“手工修复配置”的任务。
2. 协议优先：接入优先走 MCP 能力发现与协商，不写死私有键。
3. 自动适配：主体升级后由适配层吸收变化，不把维护成本转嫁给用户。
4. 幂等安全：重复连接/断开不产生脏配置，失败可回滚。

## 3. 多主体自动适配模型

| 主体 | 接入策略 | 配置载体 |
|---|---|---|
| Codex | 主体特定适配器 | `~/.codex/config.toml` |
| Claude Code | 主体特定适配器 | `~/.claude/settings.json` 或 `~/.claude.json` |
| Cursor | 主体特定适配器 | 平台对应 `settings.json` |
| OpenClaw | MCP 服务器注册 | `~/.openclaw/openclaw.json` 的 `mcp.servers` |

说明：各主体由独立 `Attach/Detach/Verify` 适配器处理，禁止共享“通用写死结构”。

## 4. OpenClaw 已落地修正（P0）

问题：旧实现写入根键 `omnimemora`，会被 OpenClaw schema 判定为未识别键。  
修正：改为 schema 合法结构 `mcp.servers.omnimemora`，并自动清理 legacy 根键。

当前目标结构示例：

```json
{
  "mcp": {
    "servers": {
      "omnimemora": {
        "url": "http://127.0.0.1:18011"
      }
    }
  }
}
```

> **注意**：OpenClaw MCP 配置必须指向 Python Adapter（:18011），这是 OmniMemora 唯一产品入口。
> Go Runtime（:8765）仅作为 Local Memory Plane，不承载产品入口功能。

## 5. 验收标准（Attach 成功判定）

Attach 不再以“写入函数返回成功”作为最终成功，必须同时满足：

1. 写入成功：目标配置文件实际更新。
2. 读回成功：读回内容包含目标接入项。
3. 主体验证通过：主体自身 validate/自检通过（例如 OpenClaw `config validate` 通过）。

任一失败都应显示“未连接”，并自动回滚本次变更。

## 6. 迭代优先级

### P0（当前必须完成）

1. OpenClaw 由非法根键切换为 `mcp.servers`。
2. Attach 成功标准升级为“写入 + 读回 + 主体验证”。
3. 兼容清理旧配置脏键，避免用户手工处理。
4. Dashboard 无数据态改为“连接态感知”：
   - 已连接但未产生节省：显示 `agent connected, waiting for first memory activity`
   - 未连接：显示连接指引（`omnimemora attach ...`）

### P1（下一阶段）

1. 增加适配规则包（本地缓存 + 可热更新），降低主体升级带来的失配。
2. 自动降级策略：协商失败时落到最小可用 MCP 通道，优先“可用”。
3. 可选页产品化（非工程态）：推荐选择、风险提示、一步完成。

## 7. 文档与代码对齐机制

从本版本开始，任何接入层改动必须同步更新：

1. 本文档（策略与验收）
2. 安装引导文档（用户视角）
3. 变更记录文档（本次改动、验证结果、回滚点）

未完成文档对齐，不允许标记为“安装体验已完成”。
