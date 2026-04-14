# P0-3 手工复测 SOP（OpenClaw）

## 目标

对自动化结果进行人工复核，确认不是单次偶发命中。

## 执行步骤

1. 启动并确认 Runtime 健康
   - `omnimemora status`
   - 打开 `http://127.0.0.1:18011/` 确认 Python Adapter 健康
   - 打开 `http://127.0.0.1:8765/dashboard` 确认 Go Runtime 健康（内部面板）
2. 确认 OpenClaw 已配置
   - `omnimemora attach openclaw`
   - `openclaw config validate`
3. 连续问答型（5-8轮）
   - 同一主题连续追问，观察是否持续使用 memory 工具
4. 编辑迭代型（3-5轮）
   - 同一文稿多次改写，观察 write/search/context 调用
5. 项目执行型（分步骤）
   - 同一项目拆步执行，观察后半段 savings 是否显著提升
6. 每类任务记录 5 值
   - MCP Handshakes
   - Tool Invocations
   - memory.write 次数
   - memory.search/context/recall 次数
   - token_savings.total_saved_tokens
7. 复跑 3 次
   - 记录每次是否满足固定阈值（1.3x、300、30%）

## 判定

- 三次都满足固定阈值：手工 PASS
- 任何一次失败：手工 FAIL

