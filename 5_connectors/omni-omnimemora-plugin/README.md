# Memory OmniMemora Plugin

OpenClaw 插件，通过 OmniMemora Gateway 接入本地产品能力，实现长时记忆功能。

## 架构

```text
OpenClaw (Docker:18789)
    ↓
memory-openviking Plugin
    ↓
OmniMemora Gateway (Host:18011)
    ↓
OmniMemora Internal Runtime (internal plane)
```

## 功能特性

- ✅ **自动回忆 (Auto-Recall)**: 在构建提示前自动注入相关记忆
- ✅ **自动捕获 (Auto-Capture)**: 对话结束后自动提取重要信息
- ✅ **记忆工具**: `memory_recall`, `memory_store`, `memory_forget`
- ✅ **安全隔离**: 通过 OmniMemora Gateway 提供过滤、去重、限流、TTL 路由

## 安装

1. 确保插件位于 `extensions/memory-openviking/` 目录
2. 重启 OpenClaw 网关

## 配置

在 OpenClaw 中配置插件：

```bash
# 启用插件
openclaw config set plugins.enabled true --json

# 设置 memory slot 为 memory-openviking
openclaw config set plugins.slots.memory memory-openviking

# 配置插件参数
openclaw config set plugins.entries.memory-openviking.config.baseUrl "http://127.0.0.1:18011"
openclaw config set plugins.entries.memory-openviking.config.agentId "supervisor"
openclaw config set plugins.entries.memory-openviking.config.autoCapture true
openclaw config set plugins.entries.memory-openviking.config.autoRecall true

# 重启网关
docker restart openclaw-openclaw-gateway-1
```

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `baseUrl` | `http://127.0.0.1:18011` | OmniMemora Gateway 服务地址 |
| `agentId` | `supervisor` | 代理标识符 |
| `timeoutMs` | `30000` | 请求超时（毫秒） |
| `autoCapture` | `true` | 启用自动捕获 |
| `captureMaxLength` | `24000` | 捕获内容最大长度 |
| `autoRecall` | `true` | 启用自动回忆 |
| `recallLimit` | `6` | 最大召回记忆数 |
| `recallScoreThreshold` | `0.01` | 召回分数阈值 |

## Gateway API

插件只通过网关使用以下端点：

- `POST /memory/write` - 写入记忆
- `POST /memory/search` - 搜索记忆
- `POST /memory/read` - 读取记忆内容
- `POST /memory/delete` - 删除记忆
- `GET /health` - 健康检查

## 验证

检查插件状态：

```bash
# 查看 OpenClaw 日志
docker logs openclaw-openclaw-gateway-1 | grep memory-openviking

# 测试 OmniMemora Gateway
curl http://localhost:18011/health
```

## 与官方 OpenViking 插件对比

| 特性 | 官方插件 | 本插件 |
|------|----------|--------|
| 连接方式 | 直接连 OpenViking:1933 | 通过 OmniMemora Gateway:18011 |
| 内容过滤 | ❌ 无 | ✅ 标准化+过滤+去重+限流+路由+TTL |
| 失败经验 | ❌ 过滤掉 | ✅ 保留并路由到 L2 |
| 单向隔离 | ❌ 读写都通 | ✅ 只写不读（OpenClaw → Adapter） |
| 防膨胀 | ⚠️ 基础 | ✅ TTL + 层级路由 |

## 故障排查

### OmniMemora Gateway 未连接

```
memory-openviking: adapter health check failed
```

检查：
1. `docker ps` - 确认 gateway 进程或容器运行中
2. 查看 gateway 日志
3. `curl http://localhost:18011/health` - 测试健康端点

### 记忆未写入

检查：
1. Gateway 日志中的写入标记
2. OpenViking 服务是否正常运行
3. 数据目录权限：`E:\AI\docker-data\openviking-data`
