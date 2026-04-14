# 阶段 1.2: router.py 深度审查报告

**文件**: `4_core/logic/router.py`  
**审查时间**: 2026-04-12  
**审查级别**: 代码级深度审查

---

## 一、代码结构概览

| 函数 | 行数 | 职责 |
|-----|------|------|
| calculate_memory_score_detailed() | 130+ | 详细评分计算（主函数）|
| calculate_memory_score() | 10 | 兼容封装 |
| get_memory_level() | 15 | 评分 → 等级映射 |
| route_memory_type_and_level() | 30 | 路由决策 |

---

## 二、发现的问题（按严重性排序）

### 🔴 P0 问题（严重）

#### 问题 1.2.1: 关键词匹配存在重复调用 `detect_failure_content()`

**位置**: 第 89-90 行 和 第 175 行

**问题描述**:
`detect_failure_content()` 在两个地方被调用，导致重复计算。

**代码片段**:
```python
# calculate_memory_score_detailed() 中（第 89-90 行）
is_failure, failure_type = detect_failure_content(content)
if is_failure:
    relevance_score += score_rules.get("failure_experience", 0)

# route_memory_type_and_level() 中（第 175 行）
is_failure, failure_type = detect_failure_content(content)  # ← 重复调用！
```

**更严重的是**：在 `engine.py` 中也调用了一次（第 74 行）:
```python
# engine.py 第 74 行
is_failure, _ = detect_failure_content(content)
```

**影响**:
- 同一个内容可能被分析 3 次
- 不必要的性能开销
- 如果 `detect_failure_content()` 有副作用，可能导致不一致

**建议修复方案**:
```python
# 方案 A: 让 calculate_memory_score_detailed() 返回 is_failure
def calculate_memory_score_detailed(...) -> tuple[int, int, int, int, bool]:
    # ... 现有逻辑 ...
    is_failure, failure_type = detect_failure_content(content)
    if is_failure:
        relevance_score += score_rules.get("failure_experience", 0)
    # ...
    return relevance_score, type_weight, length_penalty, final_score, is_failure

# 方案 B: 或者在调用端缓存结果
#（但这需要修改接口契约）
```

---

#### 问题 1.2.2: 中英文关键词匹配逻辑重复，难以维护

**位置**: 第 23-87 行

**问题描述**:
4 类关键词（成功、策略、重要、知识）的匹配逻辑完全重复，只是关键词列表不同。

**代码片段**:
```python
# 成功/完成关键词（中文 3 倍权重）
success_keywords_cn = ["成功", "完成", "搞定", "胜利", "顺利"]
success_keywords_en = ["success", "done", "completed", "finished", "accomplished"]
for kw in success_keywords_cn:
    if kw in content:
        relevance_score += score_rules.get("success_keyword", 0) * 3
        break
else:
    content_lower = content.lower()
    for kw in success_keywords_en:
        if kw in content_lower:
            relevance_score += score_rules.get("success_keyword", 0)
            break

# 策略/规划关键词（中文 3 倍权重）
# ... 完全相同的结构，只是关键词列表不同 ...

# 重要/关键关键词（中文 3 倍权重）
# ... 完全相同的结构 ...

# 知识/规则关键词（中文 3 倍权重）
# ... 完全相同的结构 ...
```

**问题分析**:
- 4 次重复的代码块
- 如果要修改匹配逻辑，需要改 4 个地方
- 容易引入不一致

**建议重构**:
```python
@dataclass
class KeywordRule:
    name: str
    cn_keywords: List[str]
    en_keywords: List[str]
    weight_multiplier: int = 3

KEYWORD_RULES = [
    KeywordRule(
        name="success_keyword",
        cn_keywords=["成功", "完成", "搞定", "胜利", "顺利"],
        en_keywords=["success", "done", "completed", "finished", "accomplished"],
    ),
    KeywordRule(
        name="strategy_keyword",
        cn_keywords=["策略", "规划", "方案", "计划", "安排"],
        en_keywords=["policy", "strategy", "plan"],
    ),
    KeywordRule(
        name="important_keyword",
        cn_keywords=["重要", "关键", "核心", "必要", "主要", "至关重要"],
        en_keywords=["important", "critical", "essential", "key", "core", "vital"],
    ),
    KeywordRule(
        name="knowledge_keyword",
        cn_keywords=["知识", "规则", "原则", "方法", "理论", "准则", "规律"],
        en_keywords=["knowledge", "rule", "principle", "method", "theory"],
    ),
]

def _match_keywords(content: str, rule: KeywordRule, score_rules: Dict) -> int:
    """匹配单类关键词的辅助函数"""
    for kw in rule.cn_keywords:
        if kw in content:
            return score_rules.get(rule.name, 0) * rule.weight_multiplier
    # 中文没匹配到，试英文
    content_lower = content.lower()
    for kw in rule.en_keywords:
        if kw in content_lower:
            return score_rules.get(rule.name, 0)
    return 0

# 然后在主函数中使用:
for rule in KEYWORD_RULES:
    relevance_score += _match_keywords(content, rule, score_rules)
```

---

### 🟠 P1 问题（重要）

#### 问题 1.2.3: `content_lower` 变量赋值逻辑混乱

**位置**: 第 20 行、第 38 行、第 54 行、第 70 行

**问题描述**:
`content_lower` 在多个地方被赋值，逻辑不清晰。

**代码片段**:
```python
content_lower = content.lower()  # 第 20 行：赋值但之后立即被覆盖？

# ...

else:
    content_lower = content.lower()  # 第 38 行：重新赋值
    for kw in success_keywords_en:
        if kw in content_lower:
            ...

# ...

else:
    content_lower = content.lower()  # 第 54 行：又重新赋值
    ...
```

**问题分析**:
- 第 20 行的赋值基本是浪费的，因为在 `else` 块中会重新赋值
- 重复计算 `content.lower()`
- 代码可读性差

**建议修复**:
```python
# 方案 A: 只在需要时计算
#（删除第 20 行的赋值）

# 方案 B: 计算一次并复用
content_lower = content.lower()  # 计算一次

# 然后在匹配英文时直接使用，不再重新计算
for kw in success_keywords_en:
    if kw in content_lower:  # 直接使用
        ...
```

---

#### 问题 1.2.4: `route_memory_type_and_level()` 中也调整了失败经验评分，导致双重调整

**位置**: 第 178-180 行

**问题描述**:
在 `router.py` 中调整了一次评分，在 `engine.py` 中又调整了一次，可能导致过度调整。

**代码片段**:
```python
# router.py 第 178-180 行
if is_failure and score < 3:
    score = 3

# engine.py 第 74-77 行（也调整了一次！）
is_failure, _ = detect_failure_content(content)
if is_failure and final_score < 3:
    final_score = 3
    mem["_score"] = final_score
```

**问题分析**:
- 如果两个地方都调用，会发生什么？
- 需要理清职责：谁负责调整评分？

**影响**:
- 逻辑混乱
- 可能导致评分被不恰当地调整
- 代码重复

**建议修复**:
明确职责，只在一个地方调整：
```python
# 方案 A: 只在 engine.py 中调整（因为 engine 还需要更新 mem 的字段）
#（删除 router.py 中的调整逻辑）

# 方案 B: 只在 router.py 中调整，engine 信任返回的 score
#（需要修改接口，让 router 返回调整后的 score）
```

---

#### 问题 1.2.5: 缺少对空内容的处理

**位置**: 整个文件

**问题描述**:
没有验证 `content` 是否为空或只包含空白字符。

**潜在问题**:
```python
content = ""
# 或
content = "   \n\t  "
```

**当前行为**:
- `len(content)` 可能很小或为 0
- `length_penalty = 0`
- 关键词匹配不会命中
- `final_score = 1`（因为有保底逻辑）

**建议添加**:
```python
def calculate_memory_score_detailed(...):
    if not content or not content.strip():
        # 空内容处理
        return 0, 1, 0, 1  # 或其他合理的默认值
```

---

### 🟡 P2 问题（一般）

#### 问题 1.2.6: 魔法数字散落在代码中

**位置**: 多处

**问题描述**:
```python
type_weight = 3  # 第 105 行
type_weight = 2  # 第 107 行
length_penalty = content_len // 500  # 第 113 行
final_score = 1  # 第 119 行
score < 3  # 第 180 行
```

**建议**:
```python
# 定义常量
DEFAULT_TYPE_WEIGHT_STRATEGY = 3
DEFAULT_TYPE_WEIGHT_KNOWLEDGE = 2
LENGTH_PENALTY_THRESHOLD = 500
MINIMUM_SCORE = 1
FAILURE_MIN_SCORE = 3
```

---

#### 问题 1.2.7: `get_memory_level()` 的输入可以是任意整数，但输出只有 4 个等级

**位置**: 第 127-140 行

**问题描述**:
函数接受任意整数，但实际上评分范围很有限。

**建议**:
添加输入验证或文档说明合理的评分范围。

---

#### 问题 1.2.8: `route_memory_type_and_level()` 调用了 `calculate_memory_score()`，后者又调用 `detect_failure_content()`，然后前者又调用一次

**位置**: 第 170-180 行

**问题描述**:
这是问题 1.2.1 的延伸，调用链如下：

```
route_memory_type_and_level()
    ├─> calculate_memory_score()
    │   └─> calculate_memory_score_detailed()
    │       └─> detect_failure_content()  [第 1 次]
    │
    └─> detect_failure_content()  [第 2 次]
```

**建议**: 同问题 1.2.1 的修复方案

---

## 三、算法分析

### 评分公式

```
final_score = relevance_score × type_weight - length_penalty
```

### 分析

✅ **优点**:
- 公式简单易懂
- 多维度考虑（相关性、类型、长度）
- 有保底逻辑（至少 1 分）

⚠️ **潜在问题**:
1. **`length_penalty` 可能过大**：如果内容很长（例如 10000 字符），`length_penalty = 20`，可能完全抵消相关性评分
2. **没有上限**：`final_score` 理论上可以无限大
3. **保底逻辑可能隐藏问题**：如果计算出负分，直接设为 1，可能丢失 debug 信息

---

## 四、关键词匹配分析

### 当前匹配方式

| 语言 | 匹配方式 | 是否 lower() |
|-----|---------|-------------|
| 中文 | 精确子串匹配 | 否（直接用 `content`）|
| 英文 | 精确子串匹配 | 是（用 `content.lower()`）|

### 问题

⚠️ **英文匹配过于严格**：
- 只匹配完整单词的子串
- 例如 "successfully" 不会匹配 "success"（但实际上会匹配，因为是子串）
- 等等，实际上 "success" 是 "successfully" 的子串，所以会匹配

✅ **中文处理合理**：
- 中文没有大小写，所以不需要 `lower()`

---

## 五、修复优先级总结

| 优先级 | 问题编号 | 问题描述 | 预计修复时间 |
|-------|---------|---------|-------------|
| P0 | 1.2.1 | 重复调用 detect_failure_content() | 30 分钟 |
| P0 | 1.2.2 | 关键词匹配逻辑重复 | 1 小时 |
| P1 | 1.2.3 | content_lower 变量赋值混乱 | 15 分钟 |
| P1 | 1.2.4 | 双重调整失败经验评分 | 30 分钟 |
| P1 | 1.2.5 | 缺少空内容处理 | 15 分钟 |
| P2 | 1.2.6 | 魔法数字 | 10 分钟 |
| P2 | 1.2.7 | get_memory_level() 输入验证 | 10 分钟 |
| P2 | 1.2.8 | 调用链重复（同 1.2.1） | - |

---

## 六、阶段结论

`router.py` 的核心逻辑是合理的，但存在**2 个 P0 严重问题**，主要是代码重复和调用链不清晰。

**最严重的问题**:
1. 关键词匹配逻辑重复 4 次，难以维护
2. `detect_failure_content()` 可能被调用 3 次（router.py ×2 + engine.py ×1）

**建议**: 优先重构关键词匹配逻辑，然后理清调用链避免重复计算。

---

**审查完成时间**: 2026-04-12  
**下一步**: 继续审查其他逻辑模块（filter.py, rules.py, v2_compute.py）
