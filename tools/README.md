# OmniMemora CLI Wrapper Tools

## 概述

本目录包含 OmniMemora 的 CLI wrapper 工具集，用于连接本地 OmniMemora adapter（Windows Python 进程）与各 agent CLI（Codex / Claude Code / OpenClaw）。

---

## 文件结构

```text
tools/
├── memrun.py               # 统一入口，按 --agent 分流
├── ccm.py                  # claude_code shortcut
├── ocm.py                  # openclaw shortcut
├── cxm.py                  # codex shortcut
├── agent_runners.py        # agent CLI 发现与调用
├── prompt_builder.py       # [Context] / [Task] prompt 拼接
├── usage_log.py            # Wrapper Real Usage Log（stdout + JSONL）
├── usage_insight.py        # usage_logs.jsonl 决策诊断分析器
├── analyze_usage_logs.py   # usage_logs.jsonl 统计分析
├── dashboard.py            # Streamlit 可视化 Dashboard（:8501）
├── omnimemora.exe          # Go Runtime 二进制（今日编译版，:8765）
├── start_omnimemora.bat    # Windows 一键启动双服务
└── usage_logs.jsonl        # 落地日志（自动创建）
```

---

## 快速开始

### 1. 双服务架构（启动前必读）

OmniMemora 本地运行依赖**两个同时在线的服务**：

| 服务 | 技术栈 | 端口 | 作用 |
|---|---|---|---|---|
| **Go Runtime** | Go | **8765** | Local Memory Plane（存储/检索后端） |
| **Python Adapter（Unified Entry）** | Python FastAPI + MCP HTTP/SSE | **18011** | Wrapper/CLI/MCP 统一入口、记忆读写、usage log |

> Claude Code / OpenClaw / Codex 统一通过 `18011` 接入（REST + MCP）。
> `8765` 为内部后端，不作为产品对外接入端口。
> 两个服务必须同时运行，缺一不可。

### 2. 一键启动（推荐）

```bash
# 双击 start_omnimemora.bat 即可同时启动两个服务
tools\start_omnimemora.bat
```

### 3. 验证服务运行

```bash
# Go Runtime（内部后端，可选自检）
curl http://127.0.0.1:8765/health
# 期望：{"status":"ok",...}

# Python Adapter（统一入口）
curl http://127.0.0.1:18011/health?mode=local
# 期望：{"status":"healthy","mode":"local",...}

# Python Adapter MCP（Claude/OpenClaw/Codex 兼容）
curl http://127.0.0.1:18011/mcp
# 期望：{"status":"ok","transport":"http-jsonrpc",...}

# Runtime 指纹（排查多实例/错实例）
curl http://127.0.0.1:18011/debug/runtime_fingerprint
# 期望：包含 pid/started_at/config/live_counts 等字段
```

### 4. 启动 Dashboard

```bash
# Streamlit Dashboard（自动弹浏览器）
streamlit run tools\dashboard.py --server.address=127.0.0.1 --server.port=8501 --server.headless=false
```

### 3. 运行 agent wrapper

```bash
# Codex
python tools/cxm.py --workspace-id ws-main "write code for login function"

# Claude Code（支持位置参数或 --query）
python tools/ccm.py --workspace-id ws-main "should we use JWT or session cookies"
python tools/ccm.py --workspace-id ws-main --query "should we use JWT or session cookies"

# OpenClaw
python tools/ocm.py --workspace-id ws-main "continue the current integration work"

# 或通过统一入口
python tools/memrun.py --agent codex --workspace-id ws-main --query "..."
```

---

## Wrapper 参数说明

| 参数 | 必须 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--agent` | memrun 必须 | - | `claude_code` / `openclaw` / `codex` |
| `--query`, `-q` | 是 | - | 用户查询 / 任务描述 |
| `--tenant` | 否 | `OMNIMEMORA_TENANT` 或 `default-tenant` | 租户名 |
| `--user` | 否 | `OMNIMEMORA_USER` 或 `default-user` | 用户名 |
| `--workspace-id` | 否 | `OMNIMEMORA_WORKSPACE_ID` 或 `default-workspace` | workspace ID |
| `--scope` | 否 | `workspace` | `workspace` / `server` / `global` |
| `--agent-id` | 否 | 同 `--agent` | agent 实例 ID |
| `--no-inject` | 否 | false | 跳过 OmniMemora，直接调 CLI |
| `--no-auto-start` | 否 | false | 不自动拉起服务 |

---

## 日志

### stdout（实时查看）

每次请求输出两条日志：

1. **Console 输出** — `[memrun] Calling OmniMemora...` 等调试信息
2. **Wrapper Real Usage Log** — JSON 单行，含完整 context_stats 和 identity

### 落地文件

```text
tools/usage_logs.jsonl    # JSON Lines，持续追加
```

### 分析日志

```bash
# 全量统计
python tools/analyze_usage_logs.py

# 只看最近 50 条
python tools/analyze_usage_logs.py --tail 50

# 指定路径
python tools/analyze_usage_logs.py --path /path/to/log.jsonl
```

输出示例：

```text
====================================================
 OMNIMEMORA WRAPPER REAL USAGE LOG — STATS SUMMARY
====================================================
  Log file : ...\tools\usage_logs.jsonl (last 50 of file)
  Total    : 50 entries

  [1] By agent_id
    codex                   20 calls
    claude_code            18 calls
    openclaw               12 calls

  [2] By task_type
    implementation         22 calls
    decision               18 calls
    continuation           10 calls

  [3] Context Bypass
    bypass=true  :   22 (44.0%)
    bypass=false :   28 (56.0%)
  ...
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OMNIMEMORA_ADAPTER_URL` | `http://127.0.0.1:18011` | adapter 服务地址 |
| `OMNIMEMORA_TENANT` | `default-tenant` | 租户 |
| `OMNIMEMORA_USER` | `default-user` | 用户 |
| `OMNIMEMORA_WORKSPACE_ID` | `default-workspace` | workspace ID |
| `PORT` | `18011` | adapter 监听端口（启动时设置） |

---

## 架构说明

```text
User / CI
    │
    ▼
cxm.py / ccm.py / ocm.py / memrun.py
    │  (Wrapper, Windows Python)
    │  ── GET /health?mode=local  ──► OmniMemora adapter
    │  ── POST /memory/query ──►
    │                              │
    │  ◄── Decision Log (stdout) ──┘
    │
    │  CLI 发现 + prompt 拼接
    ▼
Agent CLI (codex / claude / openclaw)
    │
    ▼
usage_log.py ──► usage_logs.jsonl (持久化)
```

---

**端口隔离：**
- 统一产品入口：`127.0.0.1:18011`（Windows Python 进程，REST + MCP）
- 内部后端：`127.0.0.1:8765`（Go Runtime，不对外作为兼容接入入口）
