# MAC_MINI_COLD_START_ACCEPTANCE_CHECKLIST

## 1. 环境准备

- 安装 Go（1.21+）：`brew install go`
- 安装 Python（3.11+）：`brew install python`
- 安装 Node（18+）：`brew install node`
- clone 项目：`git clone <repo-url> && cd OmniMemora`

## 2. 配置

- 复制模板：`cp .env.example .env`（若仓库无 `.env.example`，按团队提供模板创建）
- 修改端口：
  - Runtime: `8765`
  - Adapter: `18011`
- 修改路径：
  - 数据目录使用 macOS 路径（禁止 `C:\...`）
  - 确认 `OMNIMEMORA_ADAPTER_URL=http://127.0.0.1:18011`
  - 确认 `MEMORY_BACKEND_URL=http://127.0.0.1:8765`（内部后端）

## 3. 启动

- 启动 8765（Runtime）：
  - `cd 4_core/local-runtime`
  - `go build -o omnimemora-runtime .`
  - `./omnimemora-runtime`
- 启动 18011（Adapter）：
  - 回到项目根目录
  - `PORT=18011 python tools/_run_adapter.py`

## 4. 验证（必须按顺序）

- `/health`
  - `curl http://127.0.0.1:18011/health`
  - `curl http://127.0.0.1:18011/mcp`
  - `curl http://127.0.0.1:8765/health`（内部后端自检，可选）
- write
  - `curl -X POST http://127.0.0.1:18011/memory/write -H "Content-Type: application/json" -d '{"agent":"mac-check","content":"mac cold start write check"}'`
- query
  - `curl -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d '{"tenant":"mac-check","user":"mac-check","agent":"mac-check","query":"mac cold start write check","limit":10}'`
- 三实例接入
  - `agent=openclaw` 调用一次 `POST /memory/query`
  - `agent=codex` 调用一次 `POST /memory/query`
  - `agent=claude_code` 调用一次 `POST /memory/query`

## 5. 验收

- token savings
  - `GET /usage/token-savings?tenant=<tenant>&agent=<agent>` 有非零 `saved_tokens_total`
- usage log
  - `request_count` 连续增长，`last_request_at` 持续更新
- scope 正确
  - 不同 agent/workspace 无越权读取
  - workspace shared 能共享，agent isolated 默认隔离
