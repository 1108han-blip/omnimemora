工程级专业审计机构草案
# 🧭 OmniMemora Phase 3 + 上线MVP 审计方案

---

# 一、审计目标（必须统一认知）

```text
本次审计不评估“技术先进性”
只评估：

1. 是否符合产品宪法（不越界）
2. 是否达到可发布状态
3. 是否具备用户级可用性
```

---

# 二、审计范围（明确边界）

---

## ✅ 包含

```text
- Phase 3 所有新增能力
- /metrics API
- /memory/search response增强
- dashboard
- CLI lifecycle（start/status/stop）
- first-run bootstrap
- demo data / demo query
- packaging & release
- deterministic tests
- E2E 用户级流程
```

---

## ❌ 不包含

```text
- Stripe / billing
- 云端 control plane
- 未来 roadmap
- 性能极限优化
```

---

# 三、审计维度（核心结构）

审计分 5 大模块：

```text
A. 架构合规性（Architecture Compliance）
B. 功能正确性（Functional Correctness）
C. 产品体验（User Experience）
D. 稳定性与确定性（Stability）
E. 发布就绪度（Release Readiness）
```

---

# 四、详细审计清单（可打分）

---

# A. 架构合规性（最高优先级）

---

## A1. 是否遵守 Memory Augmentation 定位

检查点：

```text
[ ] 未接管 Agent memory ownership
[ ] 未引入 orchestration / routing
[ ] 未扩展为 Agent runtime
```

---

## A2. Context Strategy 合规

```text
[ ] 无 query understanding
[ ] 无 intent classification
[ ] 无 multi-stage pipeline
[ ] 仅做 selection + compression
```

---

## A3. Local First

```text
[ ] 默认本地运行
[ ] 无 API key 依赖
[ ] 离线可运行
```

---

## A4. Scope 模型未破坏

```text
[ ] 无跨 scope 泄漏
[ ] 无默认共享
[ ] SQL WHERE 过滤存在
```

---

## A5. Cache 状态

```text
[ ] cache 未启用
[ ] 代码中明确标注 disabled 原因
```

---

## A评分标准

```text
全部通过 = PASS
任一违反 = BLOCK（禁止上线）
```

---

# B. 功能正确性

---

## B1. /metrics API

检查：

```text
[ ] total / today / week / month 正确
[ ] by_workspace 聚合正确
[ ] by_agent 聚合正确
[ ] avg_compression_ratio 正确
[ ] avg_saved_per_query 正确
```

验证方式：

- 构造测试数据
    
- 手动计算 vs API 返回比对
    

---

## B2. Search Response

```text
[ ] compression_ratio 正确
[ ] strategy_resolved 正确（不出现 auto）
[ ] mode 正确
[ ] items_selected 正确
[ ] token_budget_used 合理
```

---

## B3. Token Savings 真实性（关键）

```text
[ ] saved_tokens = raw - compressed
[ ] assemble_context=false → saved=0
[ ] 无伪造 savings
```

---

## B4. Demo 流程

```text
[ ] 首次运行写入 demo 数据
[ ] 自动触发 demo query
[ ] dashboard 有初始数据
[ ] 不重复写入
```

---

## B评分

```text
≥95% PASS
否则 FAIL
```

---

# C. 产品体验（上线关键）

---

## C1. 安装体验

```text
[ ] 下载后可直接运行
[ ] 无依赖安装要求
[ ] 无配置步骤
```

---

## C2. 启动体验

```text
[ ] omnimemora start 可运行
[ ] 自动打开浏览器
[ ] 自动进入 dashboard
```

---

## C3. 首次价值感知（最关键）

```text
[ ] 60秒内看到 token savings
[ ] 无需任何操作
```

---

## C4. Dashboard 可读性

```text
[ ] 首屏显示 savings
[ ] 无技术术语干扰
[ ] 信息层级清晰
```

---

## C5. 空状态处理

```text
[ ] 无数据时有提示
[ ] 不出现错误堆栈
```

---

## C评分标准

```text
用户测试通过率 ≥ 80% 才能 PASS
```

---

# D. 稳定性与确定性

---

## D1. Deterministic 测试

```text
[ ] 相同输入 → 完全相同输出
[ ] auto strategy deterministic
[ ] mode deterministic
```

---

## D2. 多次启动

```text
[ ] start → stop → start 正常
[ ] 不重复 seed
```

---

## D3. 端口冲突

```text
[ ] 自动切换端口
[ ] dashboard 正确
```

---

## D4. 错误处理

```text
[ ] 无 panic 暴露
[ ] 错误为用户可理解信息
```

---

## D评分

```text
全部通过才 PASS
```

---

# E. 发布就绪度（上线门槛）

---

## E1. Packaging

```text
[ ] macOS amd64/arm64
[ ] Windows amd64
[ ] 压缩包结构正确
```

---

## E2. 一键运行验证（必须实测）

```text
新机器测试：

下载 → 解压 → 双击/命令运行 → 成功
```

---

## E3. CLI 命令完整性

```text
[ ] start
[ ] status
[ ] stop
[ ] dashboard
```

---

## E4. Connect 能力（最低）

```text
[ ] connect codex
[ ] connect claude
[ ] 至少输出接入说明
```

---

## E5. README

```text
[ ] 3步启动说明
[ ] 无技术门槛
```

---

## E评分

```text
全部通过才允许发布
```

---

# 五、审计执行流程（你给团队）

---

## Step 1：代码审计

```text
负责人：架构审计
范围：A + B
```

---

## Step 2：功能验证

```text
负责人：QA
范围：B + D
```

---

## Step 3：用户测试

```text
负责人：非开发人员
要求：不解释使用
验证：C
```

---

## Step 4：发布测试

```text
负责人：DevOps / QA
范围：E
```

---

# 六、最终审计结论标准

---

## ✅ 允许上线（Green）

```text
A: PASS
B: ≥95%
C: ≥80%
D: PASS
E: PASS
```

---

## ⚠️ 可灰度（Yellow）

```text
无架构问题
但 UX 有问题
```

---

## ❌ 禁止上线（Red）

```text
任一：

- 架构违规
- token savings 不真实
- 无法完成首次运行
- deterministic 不成立
```

---

# 七、我帮你加一个“致命检查”（很多人会漏）

---

## 👉 Audit Kill Switch

审计团队必须做这个测试：

---

### 测试：

```text
关闭 OmniMemora
再运行同样任务
```

---

### 如果结果：

```text
“差不多”
```

👉 说明产品价值不成立

---

### 如果结果：

```text
token ↑ / 输出变差
```

👉 产品成立

整体上，你可以做出

👉「审计评分表（Excel版 / Notion版）+ 自动打分模板」