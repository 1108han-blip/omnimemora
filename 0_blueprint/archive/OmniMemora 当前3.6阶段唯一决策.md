
---

# 🚀 OmniMemora 当前3.6阶段唯一决策（定版）

## 一句话定死

> **OmniMemora = 记忆调度与上下文编译层（Memory Orchestrator & Context Compiler）**

不是替代，不是存储，而是：

> **决定“哪些记忆进入模型，以及以什么形式进入”**

---

# 🧠 核心认知对齐（最终版本）

## 1️⃣ 记忆不是单一系统

```txt
记忆 = LLM + 实例（ChatGPT/Codex/OpenClaw）+ 插件 + 用户行为 的协作结果
```

👉 无人能完全控制

---

## 2️⃣ 我们的定位

```txt
不是：取代 memory ❌
不是：唯一入口 ❌
而是：主调度层 + 编译层 ✅
```

---

## 3️⃣ 控制权的真实定义（非常关键）

> **控制权 = 对“最终进入模型的上下文”的决策权**

而不是：

- 控制所有 memory ❌
    
- 禁止用户行为 ❌
    

---

## 4️⃣ 三层现实模型（必须接受）

|层级|状态|
|---|---|
|主路径（MCP / Tool）|✅ 可控制|
|行为影响（策略）|⚠️ 可影响|
|平台内部机制|❌ 不可控|

---

## 5️⃣ 产品核心目标（重新定义）

```txt
跨窗口连续性
跨实例一致性
token 压缩与优化
多源记忆编译
```

---

# 🔥 关键设计原则（写死，不再摇摆）

## 原则 1

> 用户可以随意创建 memory（我们不干预）

---

## 原则 2

> 所有 memory 进入模型前，必须经过 OmniMemora 编译（主路径）

---

## 原则 3

> 原生 memory 保留，但使用权由策略调度

---

## 原则 4（最关键）

> **控制结果，而不是控制行为**

---

# 🧩 系统架构（唯一版本）

```txt
Agent（ChatGPT / Codex / OpenClaw）
            ↓
   OmniMemora（调度 + 编译）
            ↓
 ┌──────────────┬──────────────┬──────────────┐
 │ Native Memory │ Omni Memory  │ External Mem │
 └──────────────┴──────────────┴──────────────┘
            ↓
       Final Context
            ↓
           LLM
```

---

# ⚠️ 当前问题复盘（必须记录）

## 已解决（P0）

- MCP 接入 ✅
    
- Tool 调用 ✅
    
- savings 非 0 ✅
    
- 多轮链路打通 ✅
    

---

## 当前真实问题（P1）

### 1. Handshake 观测不一致

- `tool_invocations > 0`
    
- `handshakes = 0`  
    👉 **Telemetry 不完整**
    

---

### 2. MCP search 超时

👉 检索链路不稳定（但非架构问题）

---

### 3. Agent 自建 memory 干扰

👉 多路径 memory 使用不可控

---

# 🚀 改进方案（直接执行）

---

# 🔥 Phase 3.6+ 收口（必须完成）

## 1️⃣ Telemetry 修复（优先级 P1）

### 目标

```txt
任何真实调用 = 必须反映在状态上
```

### 动作

- `POST /mcp initialize` → 计入 handshake
    
- 若：
    
    - tool_invocations > 0  
        👉 自动推断 handshake
        

### UI 改动

```txt
MCP Connected（基于真实调用）
而不是依赖 handshake 计数
```

---

## 2️⃣ Memory Routing 明确化（核心）

### 目标

```txt
所有 memory 使用 → 必须经过 OmniMemora
```

### 动作

- 禁止 fallback：
    
    ```txt
    不允许：
    MCP 失败 → 直接用本地 memory
    ```
    
- 明确策略：
    

```json
{
  "routing": {
    "all_memory_calls_via_mcp": true,
    "allow_native_memory": true,
    "native_memory_usage": "controlled"
  }
}
```

---

## 3️⃣ Context Compiler（最核心能力）

### MVP 版本（必须上线）

```txt
输入：
- Omni memory
- native memory（可选）

处理：
- 去重
- 排序
- 截断
- 压缩

输出：
→ Final Context
```

---

## 4️⃣ 双 memory 可控接入（不是禁止）

### 目标

```txt
native memory = 数据源
不是 = 直接输入
```

### 动作

- 设计：
    

```txt
Native Memory Adapter（后续）
```

---

## 5️⃣ 禁止“无控制 memory 路径”（重要）

### 明确规则

```txt
允许 memory 存在
不允许 memory 绕过 OmniMemora 被使用
```

---

# 🔥 Phase 3.7（下一阶段）

---

## 1️⃣ Policy Layer（核心战略）

```txt
云端控制：
- recall 策略
- compression 策略
- dream 策略
```

---

## 2️⃣ 权重调度系统

```json
{
  "sources": {
    "native": { "weight": 0.6 },
    "omni": { "weight": 1.0 }
  }
}
```

---

## 3️⃣ 跨窗口恢复能力

👉 新窗口：

```txt
自动注入关键 context
```

---

## 4️⃣ 被选中率优化（最关键）

目标：

```txt
让 agent “更愿意用你”
```

---

# 🧠 产品表达（对外统一口径）

你可以直接用这段：

---

> OmniMemora 并不替代各类 AI 实例的原生记忆系统。
> 
> 我们提供的是一个**跨实例的记忆调度与上下文编译层**：
> 
> 在多源记忆之上，统一决定哪些信息被使用、如何组合、以及如何压缩进入模型。
> 
> 用户可以继续使用任何原生记忆机制，而 OmniMemora 负责在其之上提供连续性、一致性和效率优化。

---

# 🔚 最终收敛（这一轮的核心）

你们现在已经明确三件事：

---

## 1️⃣ 不能完全控制 memory（现实）

---

## 2️⃣ 但可以控制最终 context（关键）

---

## 3️⃣ 产品价值不在 memory，而在：

> **Context Compilation + Memory Orchestration**

---

# 🔥 最后一刀（写进你项目最顶层）

```txt
We do not own memory.
We own what becomes context.
```

---

这句话，就是你整个产品的战略锚点。