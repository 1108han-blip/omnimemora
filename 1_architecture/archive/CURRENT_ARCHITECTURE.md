# CURRENT_ARCHITECTURE.md

**Status:** FINAL  
**Source of Truth:** Global Product Blueprint  
**Role:** Blueprint 的架构投影（结构层）

---

# 一、架构总原则（来自 Blueprint）

OmniMemora 是：

> Memory Control Plane

而不是：

- memory database  
- vector DB  
- storage system  

---

# 二、五层架构模型（唯一合法结构）
┌────────────────────────────┐
│ Client Layer │
│ (Agent / Claude / Codex) │
└────────────┬───────────────┘
▼
┌────────────────────────────┐
│ Connector Layer │
│ (Plugin / SDK / CLI) │
└────────────┬───────────────┘
▼
┌────────────────────────────┐
│ Control Plane │
│ (OmniMemora 核心) │
└────────────┬───────────────┘
▼
┌────────────────────────────┐
│ Memory Plane │
│ (外部执行层，不属于产品) │
└────────────┬───────────────┘
▼
┌────────────────────────────┐
│ Storage │
│ (完全抽象) │
└────────────────────────────┘

---

# 三、各层职责（严格边界）

## 1️⃣ Client Layer
- 发起请求
- 消费记忆

---

## 2️⃣ Connector Layer
- 注入 API key
- 转发请求
- 本地 fallback（可选）

👉 是产品入口，而不是核心

---

## 3️⃣ Control Plane（唯一核心）

负责：

- Identity（tenant / agent）
- Auth（API key）
- Policy（写/压缩/去重）
- Routing（去哪里）
- Metering（token savings）
- Billing（计费）
- Audit（日志）

---

## 4️⃣ Memory Plane（不属于 OmniMemora）

可以是：

- 本地文件
- SQLite
- 向量库
- 私有服务

👉 OmniMemora 不拥有它

---

## 5️⃣ Storage

完全不关心：

- 数据库类型
- 数据格式
- 存储位置

---

# 四、数据流（标准流程）

## Write

Client → Connector → Control Plane  
→ Policy → Dedup → Compile  
→ Routing → Memory Plane

---

## Query

Client → Connector → Control Plane  
→ Routing → Memory Plane  
→ Policy → 返回结果  
→ Metering

---

# 五、强约束（不可违反）

- Control Plane 不允许存储主记忆  
- Memory Plane 不允许进入产品核心  
- 所有能力必须可替换  

---

# 六、实现说明（非约束）

- api.doloclaw.com 属于实现，不属于架构定义  
- 本地 Docker 属于开发环境，不属于产品结构  

---

# 七、版本治理

本文件：

- 不定义产品  
- 不定义商业  
- 只映射 Blueprint 架构  