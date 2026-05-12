# Promotion Workflow Usage Governance

> **状态**: ✅ 已收口（2026-04-20 通过 adapter-only 真实场景验证）
>
> **2026-05-10 supersession**: 当前用户控制/展示面是 OmniMemora Desktop app。`5173` 仅为 legacy/dev dashboard；仅在显式 legacy 验证任务中检查，不再作为当前产品默认验收依赖。

## 概述

本文档将 `tools/promotion/` 从"可用工具"升级为**团队默认工作方式**，明确使用边界、强制检查项、失败停住规则和宣告职责。

**目标**：把"何时必须用 `tools/promotion/`"从经验判断变成明确规则。

---

## 1. 使用边界分类

### 1.1 必须走 Promotion

以下场景**必须**使用 `tools/promotion/promotion.sh`：

| 场景 | 说明 |
|------|------|
| 把 `repo reality` 提升到 `running reality` 的 runtime 变更 | 任何 `4_core/local-runtime` 的改动 |
| 把 `repo reality` 提升到 `running reality` 的 adapter 变更 | 任何 `5_connectors/adapter` 的改动 |
| 把 `repo reality` 提升到 `running reality` 的桌面 GUI 变更 | 任何 `6_console/desktop-shell` 的改动需要重新构建/安装桌面 App |
| 把 `repo reality` 提升到 `running reality` 的 legacy UI 变更 | `6_console/demo-dashboard` 仅作为 legacy/dev surface；不得作为当前桌面 GUI 依赖启动 |
| 影响 `8765` 端口当前在线行为的改动 | Runtime health/API 行为变更 |
| 影响 `18011` 端口当前在线行为的改动 | Adapter API 行为变更 |
| 影响 `5173` 端口当前在线行为的改动 | legacy dashboard 行为变更；不代表当前桌面 GUI running reality |
| launchd 服务配置的变更 | `com.omnimemora.*.plist` 相关改动 |

**判断原则**：如果改动会改变**当前运行中服务**的行为，就必须走 promotion。

### 1.2 禁止绕过 Promotion

以下行为**严禁**执行：

| 行为 | 原因 |
|------|------|
| 手工复制文件到 `~/.omnimemora/service/current` | 绕过受控发布流程，无法审计 |
| 手工 `kill` 后直接 shell 拉起进程 | 绕过 launchd 管理，失去进程守护 |
| 不经记录回填就宣告 `running_reality_promoted` | 违反 evidence routing 要求 |
| 绕过 `promotion.sh` 直接修改 service 目录 | 破坏 repo reality 与 running reality 同步 |
| 未经验证就在 phase 记录中写入 promotion 结论 | 违反 adoption verification 要求 |

**例外**：本地开发调试时可以使用非 promotion 路径，但**不得**将调试产物合并到主分支。

### 1.3 不需要走 Promotion

以下场景**不需要**走 promotion：

| 场景 | 说明 |
|------|------|
| 纯文档改动 | `.md` 文件、docs 目录下的修改 |
| 纯治理补丁 | governance、policy 类文档修改 |
| repo 内部实现，未准备提升到 running reality | 功能未完成，不影响运行 |
| 客户端本地环境问题排查 | 不涉及服务端 runtime/adapter/UI |
| ADR 决策记录 | `docs/adr/` 下的文件 |
| 纯代码重构（不影响运行时行为） | 如果重构后行为不变，可不走 promotion |

---

## 2. Promotion 执行前检查项

每次执行 promotion 前，**必须**确认以下所有项目：

### 2.1 变更范围确认

- [ ] 当前变更真的要提升到 `running reality`
- [ ] 变更范围已确认（runtime / adapter / ui / 组合）
- [ ] 已知晓变更将影响哪些运行面（8765 / 18011 / Desktop GUI / legacy 5173）

### 2.2 环境状态确认

- [ ] 当前 worktree 在可控范围（干净或已知状态）
- [ ] promotion 目标组件源码目录存在
- [ ] 必要的构建工具可用（Go / Node.js / npm）
- [ ] launchd 服务配置文件存在

### 2.3 上下文确认

- [ ] 当前 active docs / phase 入口已清楚
- [ ] 已知晓本次变更对应的 phase/工作项
- [ ] 相关 stakeholder 已知悉本次 promotion 计划

### 2.4 风险确认

- [ ] 不存在已知阻塞 warning / finding
- [ ] 若有 warning，已确认是否需要先升级为 finding
- [ ] 已评估回滚方案

**执行前若有任何一项未确认，停止并先解决该问题。**

---

## 3. Promotion 执行后检查项

每次执行 promotion 后，**必须**确认以下所有项目：

### 3.1 结构化日志确认

- [ ] `tools/verification/logs/promotion_*.log` 已生成
- [ ] 日志包含目标组件、repo revision、每步结果

### 3.2 健康验证确认

**Runtime（8765）**：
- [ ] `curl http://127.0.0.1:8765/health` 返回成功

**Adapter（18011）**：
- [ ] `curl http://127.0.0.1:18011/health` 返回成功
- [ ] launchd plist reality 可查
- [ ] 进程 reality 存在

**Desktop GUI（packaged app）**：
- [ ] 桌面 App 已重新构建并安装到 `/Applications/OmniMemora Desktop.app`
- [ ] 桌面 GUI 可打开并能从 `18011` 刷新当前状态

**Legacy UI（5173，仅在显式验证 legacy dashboard 时适用，默认可跳过）**：
- [ ] `curl http://127.0.0.1:5173/` 返回成功
- [ ] `curl http://127.0.0.1:5173/agents?tenant=all` 返回成功

### 3.3 记录回填确认

- [ ] adoption verification record 已写入
- [ ] 对应 health/API/UI 验证结论已记录
- [ ] 若失败，primary breakpoint 已记录

### 3.4 宣告条件确认

- [ ] 满足 `running_reality_promoted` 的正式宣告条件
- [ ] 不存在口径冲突（脚本 / 文档 / running reality）

**执行后若有任何一项未通过，停止并记录为 finding，不继续组合验证。**

---

## 4. 失败处理规则

### 4.1 失败分类

| 分类 | 说明 | 处理方式 |
|------|------|----------|
| `build` | 构建失败 | 停止，不继续 |
| `file_sync` | 文件同步失败 | 停止，不继续 |
| `reload` | 重载失败 | 停止，不继续 |
| `health_check` | 运行存活但接口不达标 | 停止，不继续 |
| `ui_bringup` | UI bring-up 失败 | 停止，不继续 |
| `ui_alignment` | UI 对位失败 | 停止，不继续 |

### 4.2 强制停住规则

- **单组件失败**：停止，不继续组合验证
- **组合失败**：停止，不并行修多个面
- **warning 未契约化**：先升级为 finding，再继续判断
- **口径冲突**（脚本 / 文档 / running reality）：先收敛口径，再继续

### 4.3 唯一主断点

每次 promotion 失败后，**必须**记录唯一主断点（primary breakpoint）：

```
## Primary Breakpoint

**component**: <runtime|adapter|ui>
**failure_type**: <build|file_sync|reload|health_check|ui_bringup|ui_alignment>
**failure_detail**: <具体描述>
**repo_revision**: <当前 commit hash>
**log_file**: <promotion log 路径>
```

---

## 5. 宣告职责规则

### 5.1 运行成功 ≠ 阶段完成

promotion 脚本输出 `running_reality_promoted` **不等于**阶段完成。

正式宣告需要基于：
1. **promotion success definition**（成功定义）
2. **evidence routing**（证据路由）
3. **adoption verification record**（验证记录）

### 5.2 分层宣告规则

| Layer | 说明 | 谁可以写 |
|-------|------|----------|
| Layer 1 | Promotion 执行结果（脚本输出） | 自动化脚本 |
| Layer 2 | Adoption verification record（验证记录） | 执行者 |
| Layer 3 | Phase 层结论（running reality 已提升） | Phase owner |

### 5.3 宣告权限

- **谁可以在记录中写 `promotion success`**：执行者，基于 Layer 1 结果填写 Layer 2
- **谁可以把结论提升到 phase 层**：Phase owner，基于 Layer 1+2 填写 Layer 3
- **何时只允许写 Layer 1/2**：证据不完整、存在口径冲突、warning 未解决

### 5.4 禁止行为

- **禁止**仅凭终端输出一句 `success` 就当作正式结论
- **禁止**在口径冲突未解决时写入 Layer 3 结论
- **禁止**在 warning 未契约化时跳过该 warning 的验证

---

## 6. 真实场景验证要求

### 6.1 验证目标

本 governance 文档必须通过至少一次**真实日常变更场景**验证。

### 6.2 验证标准

- [ ] 选择一个小而真实的 runtime-only 或 adapter-only 变更
- [ ] 按本 governance 文档完整流程执行
- [ ] 确认"是否真的不再靠个人经验"
- [ ] 记录验证结果到 adoption verification records

### 6.3 验证记录格式

```
## Governance Validation Record

**date**: <YYYY-MM-DD>
**scenario**: <变更描述>
**promotion_target**: <runtime|adapter|ui|组合>
**governance_compliance**: <完全合规|部分合规|不合规>
**deviation**: <若有偏差，描述之>
**lessons_learned**: <如有>
```

---

## 7. 工具位置

```
Promotion 入口: tools/promotion/promotion.sh
Promotion 日志: tools/verification/logs/promotion_YYYYMMDD_HHMMSS.log
Running Reality 状态: tools/verification/logs/running_reality_before.txt
```

### 快速参考

```bash
# 必须走 promotion 的场景
./tools/promotion/promotion.sh runtime      # Runtime 变更
./tools/promotion/promotion.sh adapter      # Adapter 变更
./tools/promotion/promotion.sh ui           # UI 变更
./tools/promotion/promotion.sh runtime+adapter  # 组合

# 查看 promotion 状态
tail -f tools/verification/logs/promotion_*.log
```

---

## 8. 违规处理

| 违规行为 | 处理方式 |
|----------|----------|
| 绕过 promotion 直接修改 service | 回滚并重新走 promotion |
| 未记录宣告依据写入 Layer 3 | 撤销宣告，补齐依据 |
| 失败后不记录 primary breakpoint | 补记后视为未完成 |
| 单组件失败后继续组合验证 | 停止，当前 promotion 标记为失败 |

---

## 9. 文档维护

- 本文档跟随 `tools/promotion/` 更新
- 重大变更需经过 governance review
- 验证记录保存在 `docs/phase6/adoption_verification/`
