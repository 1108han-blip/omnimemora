# 阶段 1.1: engine.py 深度审查报告

**文件**: `4_core/logic/engine.py`  
**审查时间**: 2026-04-12  
**审查级别**: 代码级深度审查

---

## 一、代码结构概览

| 组件 | 行数 | 职责 |
|-----|------|------|
| OptimizationInput | 28 | 输入数据类 |
| OptimizationResult | 15 | 输出数据类 |
| reduce_redundancy() | 16 | 去重函数（未使用）|
| optimize_context() | 140+ | 主优化函数 |

---

## 二、发现的问题（按严重性排序）

### 🔴 P0 问题（严重）

#### 问题 1.1.1: Token savings 计算逻辑存在严重缺陷

**位置**: 第 103-110 行

**问题描述**:
`baseline_chars` 的计算方式不合理，可能导致 token savings 数据失真。

**代码片段**:
```python
# 第 103-110 行
actual_chars = len(packed_context) if input.packing_enabled else sum(len(m.get("content", "") or "") for m in selected)
baseline_chars = sum(len(m.get("content", "") or "") for m in selected) * input.candidate_limit  # ← 问题在这里
saved_chars = max(0, baseline_chars - actual_chars)
baseline_tokens = estimate_tokens(baseline_chars)
actual_tokens = estimate_tokens(actual_chars)
saved_tokens = max(0, baseline_tokens - actual_tokens)
savings_ratio = saved_tokens / baseline_tokens if baseline_tokens > 0 else 0.0
```

**问题分析**:
1. `baseline_chars` 被计算为 `sum(selected) * candidate_limit`
2. 这假设"如果不优化，我们会发送所有 candidate_limit 个记忆"
3. 但实际上，真实的 baseline 应该是：
   - **如果不优化**: 发送 `min(candidate_limit, total_available)` 个记忆
   - **或者**: 发送 `selected` 个记忆但不做 packing
4. 当前计算方式会夸大 savings_ratio，因为 `candidate_limit` 是一个乘数

**影响**:
- 计量数据不准确
- 可能导致错误的业务决策
- 用户看到的 savings 数据不可信

**建议修复方案**:
```python
# 方案 A: 比较 packing vs 不 packing（更真实）
actual_chars = len(packed_context) if input.packing_enabled else sum(len(m.get("content", "") or "") for m in selected)
baseline_chars = sum(len(m.get("content", "") or "") for m in selected)  # 不 packing 的情况

# 方案 B: 如果要比较"全部发送" vs "优化后"，需要明确注释
baseline_chars_all = sum(len(m.get("content", "") or "") for m in candidates)  # 所有候选
baseline_chars_selected = sum(len(m.get("content", "") or "") for m in selected)  # 选中的
```

---

#### 问题 1.1.2: 失败经验评分调整逻辑不一致

**位置**: 第 72-77 行

**问题描述**:
在调整失败经验的评分时，只更新了 `final_score` 和 `mem["_score"]`，但没有更新 `mem["_final_score"]`，导致数据不一致。

**代码片段**:
```python
# 第 64-69 行：设置所有字段
mem["_relevance_score"] = relevance_score
mem["_type_score"] = type_score
mem["_length_penalty"] = length_penalty
mem["_final_score"] = final_score  # ← 设置了这个
mem["_score"] = final_score  # 向后兼容

# 第 72-77 行：调整失败经验
is_failure, _ = detect_failure_content(content)
if is_failure and final_score < 3:
    final_score = 3
    mem["_score"] = final_score  # ← 只更新了这个，没更新 _final_score
```

**影响**:
- `mem["_final_score"]` 和 `mem["_score"]` 可能不一致
- 下游代码如果使用 `_final_score` 会得到错误的值
- 调试和日志分析时会产生困惑

**建议修复**:
```python
if is_failure and final_score < 3:
    final_score = 3
    mem["_score"] = final_score
    mem["_final_score"] = final_score  # ← 添加这行
```

---

### 🟠 P1 问题（重要）

#### 问题 1.1.3: 存在未使用的函数 `reduce_redundancy()`

**位置**: 第 40-53 行

**问题描述**:
`reduce_redundancy()` 函数定义了但从未被调用，造成代码冗余。

**代码片段**:
```python
def reduce_redundancy(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Query 侧去冗余：按内容归一化后去重
    最小实现：按 content.strip() 完全相同去重
    """
    seen = set()
    result = []
    for mem in candidates:
        content = mem.get("content", "").strip()
        if content not in seen:
            seen.add(content)
            result.append(mem)
    return result
```

**同时在第 79-85 行又重复实现了相同逻辑**:
```python
scored_without_dup = []
seen_contents = set()
for score, mem in scored:
    content = mem.get("content", "").strip()
    if content not in seen_contents:
        seen_contents.add(content)
        scored_without_dup.append((score, mem))
```

**建议修复**:
```python
# 方案 A: 删除未使用的函数，保留 inline 实现
#（删除第 40-53 行）

# 方案 B: 复用函数，删除 inline 实现
def reduce_redundancy_with_score(candidates: List[Tuple[int, Dict]]) -> List[Tuple[int, Dict]]:
    seen = set()
    result = []
    for score, mem in candidates:
        content = mem.get("content", "").strip()
        if content not in seen:
            seen.add(content)
            result.append((score, mem))
    return result

# 然后在 optimize_context() 中使用:
scored_without_dup = reduce_redundancy_with_score(scored)
```

---

#### 问题 1.1.4: 可变对象作为默认参数的风险（潜在）

**位置**: 第 14-15 行

**问题描述**:
虽然当前代码没有直接使用可变对象作为默认参数，但相关模块可能存在此问题。需要检查整个项目。

（这个问题在 engine.py 中不明显，但标记为需要在其他模块中检查）

---

#### 问题 1.1.5: Meter 字段 `dedup_applied` 始终为 False

**位置**: 第 132 行

**问题描述**:
虽然执行了去重逻辑，但 `dedup_applied` 字段被硬编码为 `False`，导致计量数据不准确。

**代码片段**:
```python
# 第 79-85 行：确实执行了去重
scored_without_dup = []
seen_contents = set()
for score, mem in scored:
    content = mem.get("content", "").strip()
    if content not in seen_contents:
        seen_contents.add(content)
        scored_without_dup.append((score, mem))

# 第 132 行：但这里写死了 False
dedup_applied=False,  # ← 问题
```

**影响**:
- 计量数据不真实
- 无法追踪去重功能的实际使用效果

**建议修复**:
```python
# 在去重后计算是否真的去重了
original_count = len(scored)
dedup_count = len(scored_without_dup)
dedup_applied = (original_count != dedup_count)

# 然后在 meter 中使用:
dedup_applied=dedup_applied,
```

---

#### 问题 1.1.6: 内容提取逻辑重复

**位置**: 第 59-60 行 和 第 66-67 行

**问题描述**:
相同的内容提取逻辑在两个地方重复出现。

**代码片段**:
```python
# 第 59-60 行（Filter 阶段）
content = mem.get("content", "") or mem.get("abstract", "") or ""
metadata = {"type": mem.get("category", "general")}

# 第 66-67 行（Route 阶段）
content = mem.get("content", "") or mem.get("abstract", "") or ""
metadata = {"type": mem.get("category", "general")}
```

**建议修复**:
```python
def extract_content_and_metadata(mem: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    content = mem.get("content", "") or mem.get("abstract", "") or ""
    metadata = {"type": mem.get("category", "general")}
    return content, metadata

# 然后使用:
content, metadata = extract_content_and_metadata(mem)
```

---

### 🟡 P2 问题（一般）

#### 问题 1.1.7: 注释编号错误

**位置**: 第 96 行

**问题描述**:
有两个"第 4 步"的注释。

**代码片段**:
```python
# 4. Select top-k
...

# 4. Build packed context  ← 应该是 5
```

**建议修复**: 更正编号

---

#### 问题 1.1.8: `timestamp` 字段为空字符串

**位置**: 第 117 行

**问题描述**:
`timestamp` 字段被硬编码为空字符串，可能影响日志和追踪。

**代码片段**:
```python
timestamp="",  # ← 空字符串
```

**建议修复**:
```python
from datetime import datetime
timestamp=datetime.utcnow().isoformat() + "Z",
```

---

#### 问题 1.1.9: 函数过长，可拆分

**位置**: `optimize_context()` 函数（140+ 行）

**问题描述**:
函数过长，包含多个阶段，可以拆分为更小的函数。

**建议拆分**:
```python
def optimize_context(input: OptimizationInput) -> OptimizationResult:
    candidates = input.candidate_memories[:input.candidate_limit]
    
    filtered = _apply_filter(candidates, input.filter_rules)
    scored = _apply_scoring(filtered, input.routing_rules)
    scored_without_dup = _apply_dedup(scored)
    selected = _select_top_k(scored_without_dup, input.max_local_cards)
    
    # ... 其余逻辑
```

---

#### 问题 1.1.10: 缺少输入验证

**位置**: 整个函数

**问题描述**:
没有对 `OptimizationInput` 的字段进行验证。

**建议添加**:
```python
def optimize_context(input: OptimizationInput) -> OptimizationResult:
    # 输入验证
    if input.candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    if input.max_local_cards <= 0:
        raise ValueError("max_local_cards must be positive")
    if input.max_local_cards > input.candidate_limit:
        raise ValueError("max_local_cards cannot exceed candidate_limit")
    
    # ... 其余逻辑
```

---

## 三、代码流程分析

### 数据流图

```
OptimizationInput
    ↓
[1] 截取候选 (candidate_limit)
    ↓
[2] Filter 阶段
    ├─ 提取 content/abstract
    ├─ 调用 filter_with_score()
    └─ 添加 _score, _filter_reason
    ↓
[3] Route/Score 阶段
    ├─ 提取 content/abstract (重复!)
    ├─ 调用 calculate_memory_score_detailed()
    ├─ 添加 _relevance_score, _type_score, _length_penalty, _final_score
    ├─ 检测失败内容
    └─ 调整失败经验评分 (不一致!)
    ↓
[4] 去重阶段
    ├─ 按 content.strip() 去重
    └─ 但 meter 中 dedup_applied=False (!)
    ↓
[5] Select top-k
    ↓
[6] Build packed context
    ↓
[7] Token savings 计算 (有缺陷!)
    ↓
[8] Build meter artifact
    ├─ 很多硬编码值
    └─ timestamp=""
    ↓
[9] Quota check
    ↓
OptimizationResult
```

---

## 四、边界条件分析

### 已正确处理的边界条件

✅ `candidate_memories` 为空 → 正常处理  
✅ `packing_enabled=False` → 正确计算 `actual_chars`  
✅ `baseline_tokens=0` → 正确处理除零  
✅ 失败经验评分 < 3 → 调整到 3  
✅ `selected` 为空 → `packed_context=""`  

### 未测试/未处理的边界条件

⚠️ `candidate_limit=0` → 可能导致问题  
⚠️ `max_local_cards > candidate_limit` → 逻辑上不合理  
⚠️ `monthly_quota=0` → 需要验证 `check_quota_enforcement`  
⚠️ 记忆同时有 `content` 和 `abstract` → 只使用 `content`（这是对的，但需要确认）  
⚠️ `content` 非常长（MB 级别）→ 内存使用是否合理？  

---

## 五、修复优先级总结

| 优先级 | 问题编号 | 问题描述 | 预计修复时间 |
|-------|---------|---------|-------------|
| P0 | 1.1.1 | Token savings 计算逻辑缺陷 | 30 分钟 |
| P0 | 1.1.2 | 失败经验评分调整不一致 | 5 分钟 |
| P1 | 1.1.3 | 未使用的函数 reduce_redundancy() | 15 分钟 |
| P1 | 1.1.5 | dedup_applied 始终为 False | 15 分钟 |
| P1 | 1.1.6 | 内容提取逻辑重复 | 10 分钟 |
| P2 | 1.1.7 | 注释编号错误 | 2 分钟 |
| P2 | 1.1.8 | timestamp 为空字符串 | 5 分钟 |
| P2 | 1.1.9 | 函数过长可拆分 | 1 小时 |
| P2 | 1.1.10 | 缺少输入验证 | 30 分钟 |

---

## 六、阶段结论

`engine.py` 整体结构清晰，职责分离良好，但存在**2 个 P0 严重问题**需要立即修复，主要集中在计量数据的准确性上。

**建议**: 优先修复 P0 问题，然后逐步处理 P1 和 P2 问题。

---

**审查完成时间**: 2026-04-12  
**下一步**: 继续审查 router.py
