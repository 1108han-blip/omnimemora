# Policy Feedback Loop

通过 `usage_logs.jsonl` 数据持续优化 Policy v1 分类规则。

---

## 1. 看什么数据

运行分析：

```bash
python tools/analyze_usage_logs.py
python tools/analyze_usage_logs.py --tail 50   # 只看近期
```

重点关注：

| 指标 | 说明 | 参考值 |
| --- | --- | --- |
| `task_type` 分布 | implementation / decision / continuation 占比 | 正常应各有一定比例 |
| `bypass_ratio` | `bypass=true` 占比 | implementation 应高，decision/continuation 应低 |
| `matched_keywords` | 各 task_type 匹配到的关键词 | 数量少说明词表不足 |
| `context_stats.packed_context_length` | 注入字符数 | continuation 过大量需警惕 |
| `context_stats.saved_tokens_estimate` | 节省 token 数 | bypass=1 时应接近 baseline |

---

## 2. 怎么判断问题

| 现象 | 判断 | 状态 |
| --- | --- | --- |
| `task_type=implementation` 但 `bypass=false` | 关键词未命中，bypass 未触发 | ❌ 分类错误 |
| `task_type=decision` 但 `bypass=true` | 本应注入却被 bypass | ❌ 分类错误 |
| `task_type=continuation` 但注入 500+ 字符 | 无关 context 过多 | ⚠️ 上下文污染 |
| 所有请求都是 `implementation` | 关键词过于宽泛 | ❌ 分类噪声 |
| `matched_keywords=[]` 但 `task_type=xxx` | 落入默认分类，置信度低 | ⚠️ 规则不足 |

**快速定位问题行：**

```bash
# 查看特定 task_type 的原始日志
cat tools/usage_logs.jsonl | python -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    if d['task_type'] == 'implementation' and not d['context_bypass']:
        print(d['query'], '| matched:', d['_meta']['matched_keywords'])
"
```

---

## 3. 怎么改

### 调关键词

编辑 `5_connectors/adapter/task_classifier.py`：

```python
# IMPL_KEYWORDS — 提高优先级
IMPL_KEYWORDS = [
    ...
    "add feature",     # 新增漏掉的实现词
    "写测试",          # 中文补漏
]

# DECISION_KEYWORDS — 扩词
DECISION_WORDS = {
    ...
    "which_is_better",  # 补漏
}
```

### 调 classifier 规则

```python
# 调整优先级顺序（在 classify_task() 中）
# 例如：希望某些词优先判定为 decision 而非 implementation
DECISION_PHRASES = [
    ...
    "should i use",    # 优先触发 decision
]
```

### 调 context 上限

编辑 `4_core/logic/engine.py` 或 `v2_compute.py`：

```python
# 限制最大注入 context 长度
max_context_chars = 500   # 超过则截断，不影响 bypass 逻辑
```

### 验证修改

```bash
# 运行 Policy v1 验收测试
cd tools/../5_connectors/adapter/__tests__
python test_policy_v1_bypass.py

# 跑一轮 wrapper 验证
python tools/cxm.py --workspace-id ws-test "write code for login function"
python tools/analyze_usage_logs.py --tail 10
```

---

## 循环节奏

```
daily:   python analyze_usage_logs.py --tail 50
         → 发现异常分布

weekly:  审查 matched_keywords，看误分类案例
         → 更新词表或规则

stale:   implementation bypass_ratio < 50%
         → 关键词过于严格，需扩展
```
