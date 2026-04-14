# MIGRATION_SOP_WIN_TO_MAC

目标：在 30 分钟内把 OmniMemora 从 Windows 环境迁移到 Mac 并完成最小验收。

## 1) clone 项目

```bash
git clone <repo-url>
cd OmniMemora
```

## 2) 安装依赖

```bash
brew install go python node
python -m pip install -r 4_core/adapter-raw/requirements.txt
```

## 3) 配置 `.env`

```bash
cp .env.example .env
```

必查项：

- `PORT=18011`
- `OMNIMEMORA_ADAPTER_URL=http://127.0.0.1:18011`
- `MEMORY_BACKEND_TYPE=omnimemora_runtime`
- `MEMORY_BACKEND_URL=http://127.0.0.1:8765`（内部后端）

## 4) 启动服务

优先方式（一条命令）：

```bash
make start
```

若 `make` 不可用：

```bash
bash ./start.sh
```

## 5) 验证步骤

```bash
curl -fsS http://127.0.0.1:18011/health
curl -fsS http://127.0.0.1:18011/mcp
curl -fsS http://127.0.0.1:8765/health   # 内部后端自检（可选）
```

写入与查询：

```bash
curl -X POST http://127.0.0.1:18011/memory/write \
  -H "Content-Type: application/json" \
  -d '{"agent":"migration-check","content":"migration sop verification"}'

curl -X POST http://127.0.0.1:18011/memory/query \
  -H "Content-Type: application/json" \
  -d '{"tenant":"migration-tenant","user":"migration-user","agent":"migration-check","query":"migration sop verification","limit":10}'
```

token savings 验证：

```bash
curl -X POST http://127.0.0.1:18011/memory/query \
  -H "Content-Type: application/json" \
  -d '{"tenant":"migration-tenant","user":"migration-user","agent":"codex","query":"which migration path should we choose"}'

curl -fsS "http://127.0.0.1:18011/usage/token-savings?tenant=migration-tenant&agent=codex"
```

## 验收标准

- Runtime 与 Adapter 健康检查通过
- 通过 18011 的 write/query 闭环成功
- token savings 有统计且 `request_count` 增长
- 全流程 30 分钟内完成
