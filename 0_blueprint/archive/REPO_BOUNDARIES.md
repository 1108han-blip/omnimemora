# REPO_BOUNDARIES.md

**Status:** FINAL  
**Source of Truth:** Global Product Blueprint  
**Role:** 商业能力分层

---

# 一、三层能力模型（来自 Blueprint）

## 1️⃣ Proof Layer（证明层）
→ GitHub

目标：证明能跑

---

## 2️⃣ Delivery Layer（交付层）
→ Pro

目标：可安装、可升级、可回滚

---

## 3️⃣ Governance Layer（治理层）
→ Enterprise

目标：可审计、可控制、可追溯

---

# 二、版本映射

---

## GitHub（Proof）

- 基础 memory orchestration
- 基础 tenant
- 基础 policy
- 基础 routing

不包含：

- installer
- audit
- rollback

---

## Pro（Delivery）

在 Proof 基础上增加：

- 安装器
- 升级/回滚
- 标准部署
- 生产支持

---

## Enterprise（Governance）

在 Pro 基础上增加：

- audit chain
- window execution
- offline package
- 合规能力

---

# 三、核心原则

任何功能必须归属于：

- Proof（能跑）
- Delivery（能交付）
- Governance（能治理）

---

# 四、禁止行为

- 不允许跨层偷放能力  
- 不允许为了销售随意移动能力  

---

# 五、版本治理

本文件只定义“能力归属”，不定义实现细节