---
doc_id: GOV-ARCH-NEXT-MAINLINE-2026-04-22
title: OmniMemora Architecture Governance Next Mainline
owner: doc-team
reviewers: [arch-lead]
status: closed
version: 1.0.0
effective_date: 2026-04-22
depends_on: [GOV-ARCH-BATCH2-CLOSEOUT-2026-04-22, ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: []
last_verified_commit: 89cde22
---

# OmniMemora Architecture Governance Next Mainline

**Status:** 已收口 ✓  
**Type:** roadmap 外架构治理增强线后续主线  
**Goal:** 在进入 Skill Suggestion 工程前，先把剩余架构调整完整做完  
**Phase Note:** 不新增 roadmap phase，不改 `ROADMAP.md` 正式 phase 编号

---

## 1. 主线目标

本主线的目标是把当前仍处于中间态的架构调整，推进到更完整的结构终态。

在 Batch 2 完成后，已经成立的是：

- `18011` 的 OpenAI-compatible / Anthropic-compatible 主路径已迁入 application 编排边界
- `control plane / read-model` 已从 action API 视图中剥离
- “用户端接入真相优先、只做最小必要兼容”已进入产品宪法

仍未完成的是：

- `18011` 的目录级三层结构尚未完全显式化
- `main.py` 仍是旧式总装配入口
- `diagnostics_surface.py` 仍未完全收敛为纯 read-model 面
- infrastructure 层在代码组织上仍未显式成层
- `8765` 仍只完成边界澄清，未进入新一轮结构治理

因此，下一阶段主线目标固定为：

> **先完成架构调整终态，再考虑 Skill Suggestion 工程。**

当前状态（2026-04-22）：

- Batch 3D 已完成：`18011` infrastructure 从目录概念收敛为真实依赖层
- Batch 3E 已完成：`8765` memory plane / carrier / operator surfaces 已完成结构治理收束
- 本文档从主线执行状态转入收口记录状态

---

## 2. 固定优先级

本主线优先级固定如下：

1. **完成 `18011` 的目录级三层重组**
2. **完成 `main.py` 装配收敛**
3. **完成 `diagnostics_surface.py` 的纯 read-model 化**
4. **完成 infrastructure 显式成层**
5. **启动 `8765` 的新一轮结构治理**
6. **以上全部完成后，才进入 Skill Suggestion 独立能力批**

Skill Suggestion、`5173` recommendation/advisory UI、cloud policy binding 都不再作为当前主线优先事项。

---

## 3. 18011 目标终态

### 3.1 目录结构终态

`5_connectors/adapter/` 应收敛出清晰的三层表达：

- `ingress/`
- `application/`
- `infrastructure/`

允许保留少量顶层兼容文件，但主职责必须能从目录组织上直接看出，不再依赖口头解释。

### 3.2 代码职责终态

- `llm_proxy.py` 只保留 ingress / egress / passthrough 角色
- compile orchestration、truth resolution、control orchestration、read-model 聚合留在 application
- runtime / backend / store / cloud 访问收敛到 infrastructure

### 3.3 装配终态

`main.py` 不再直接表现为“大一统 router 装配入口”，而应明确体现：

- product data path
- control plane
- read model
- supporting surfaces

---

## 4. diagnostics / read-model 终态

`diagnostics_surface.py` 的目标不是继续扩张，而是收敛为：

- diagnostics read model surface
- 只读聚合入口
- 不进入 compile 主链
- 不承担 control execution

必要时允许：

- 重命名
- 拆分聚合器与 surface
- 将真正的 read-model 逻辑迁入 `application/`

---

## 5. infrastructure 终态

当前 infrastructure 只在文档口径中成立，代码层尚未显式成层。

本主线要求把以下职责清楚归位：

- runtime bridge
- truth / backend resolution glue
- meter / trace / proxy stores
- cloud adapter / policy loader / usage reporter

目标不是为了移动文件而移动文件，而是要让：

- ingress 不再直接承担 infrastructure 访问判断
- application 不再散调基础能力
- infrastructure 成为明确可辨认的依赖层

---

## 6. 8765 结构治理目标

`8765` 的下一轮结构治理，目标不是重新定义它为产品入口，而是让以下边界在代码和文档两侧都更稳定：

- memory plane
- integration carrier
- operator/control carrier surfaces

至少需要完成：

- 把 `attach / detach / backup / restore / rescan` 的能力叙述，与 memory plane 本体继续剥离
- 避免 `8765` 的内部控制/接入动作被误表述成产品数据主路径
- 对 `api/`、`internal/attach/` 等现有现实结构给出稳定的治理口径

---

## 7. 不在本主线范围内

以下事项明确不进入当前主线：

- Skill Suggestion 模块实现
- `5173` recommendation/advisory UI
- cloud policy binding optional interface 落地
- 新的协议族扩展
- 新产品能力开发

---

## 8. 完成判定

本主线只有在以下条件同时满足时才算完成：

1. `18011` 的三层结构在代码组织和职责口径上都清晰成立
2. `main.py` 不再维持旧式总装配表达
3. diagnostics/read-model 面已从主数据链视觉上彻底脱开
4. infrastructure 已从概念层收敛到代码层
5. `8765` 的 memory plane / integration carrier 治理完成一轮正式收口

只有在这些条件满足后，才允许将 Skill Suggestion 提升为下一条工程主线。

---

## 9. 收口结论（2026-04-22）

本主线完成判定已全部满足：

1. `18011` 三层结构在代码组织和职责口径上成立（3A）
2. `main.py` 不再维持旧式总装配表达（3B）
3. diagnostics/read-model 已从主链视觉脱开（3C）
4. infrastructure 已从概念层收敛到代码依赖层（3D）
5. `8765` 的 memory plane / integration carrier 已完成一轮正式治理（3E）

正式后续结论：

> **Architecture Governance Next Mainline 已收口，可进入 Skill Suggestion 工程。**
