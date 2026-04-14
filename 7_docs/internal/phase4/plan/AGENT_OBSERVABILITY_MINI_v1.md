# OmniMemora Agent Observability 最小工程改造方案

**版本：** v1
**日期：** 2026-04-13
**范围：** `5_connectors/adapter/` 内部扩展

---

## 0. 目标

在**不新增系统层、不修改 engine、不修改 local-runtime 主体语义**的前提下，为现有 `5_connectors/adapter/` 增加：

1. agent 识别
2. session 识别
3. per-agent 指标统计
4. per-agent 控制模式
5. UI 所需聚合接口

最终产出一个**轻量 Agent Observability & Control 模块组**，全部挂在 adapter 内部。

---

## 1. 硬约束

### 不允许改

* `4_core/logic/engine.py`
* `4_core/local-runtime/`
* 8765 协议层
* Final Compile 现有主路径语义

### 允许改

* `5_connectors/adapter/main.py`
* `5_connectors/adapter/config.py`
* `5_connectors/adapter/meter_store.py`
* 在 `5_connectors/adapter/` 下新增薄模块

### 原则

* 不新增架构层
* 不引入新服务
* 不把 adapter 演化成 orchestration
* 所有新增能力都只服务于"识别、观测、轻控制"

---

## 2. 目录改造

在 `5_connectors/adapter/` 下新增以下文件：

```text
5_connectors/adapter/
├── agent_identity.py
├── control_mode.py
├── capability_registry.py
└── agent_metrics.py
```

说明：

* `agent_identity.py`：统一解析 agent/session/workspace 身份
* `control_mode.py`：per-agent 控制模式定义与读取
* `capability_registry.py`：按接入类型标记支持能力
* `agent_metrics.py`：agent 维度指标聚合与查询

---

## 3. 新增数据模型

## 3.1 AgentIdentity

```python
from pydantic import BaseModel
from typing import Literal, Optional

IntegrationType = Literal["tool_caller", "pre_llm_connector", "wrapper", "unknown"]

class AgentIdentity(BaseModel):
    agent_id: str = "unknown"
    agent_family: str = "unknown"
    session_id: str = "unknown"
    workspace_id: str = "unknown"
    user_id: str = "unknown"
    integration_type: IntegrationType = "unknown"
    source: str = "header"
```

---

## 3.2 ControlMode

```python
from pydantic import BaseModel
from typing import Literal

ControlModeValue = Literal["observe", "guided", "force_if_possible", "off"]

class ControlMode(BaseModel):
    mode: ControlModeValue = "observe"
```

解释：

* `observe`：只统计，不干预
* `guided`：维持当前引导语义
* `force_if_possible`：请求经过 adapter 时，若未优化则强制补做一次
* `off`：关闭该 agent 的 OmniMemora 优化

---

## 3.3 AgentMetricsSnapshot

```python
from pydantic import BaseModel
from typing import Optional

class AgentMetricsSnapshot(BaseModel):
    agent_id: str
    session_id: str
    workspace_id: str
    request_count: int = 0
    optimized_count: int = 0
    bypass_count: int = 0
    saved_tokens: int = 0
    raw_tokens: int = 0
    compressed_tokens: int = 0
    entry_rate: float = 0.0
    avg_compression_ratio: float = 0.0
    quality_delta_pct: float = 0.0
    last_seen_at: Optional[str] = None
```

---

## 4. agent 识别实现

## 4.1 解析来源优先级

优先级：

1. Header
   * `x-agent-id`, `x-agent-family`, `x-session-id`, `x-workspace-id`, `x-user-id`, `x-integration-type`
2. Query params
3. Body 中 metadata
4. fallback = `unknown`

---

## 5. capability registry

静态能力矩阵：

```python
CAPABILITY_REGISTRY = {
    "tool_caller": {
        "supports_guided": True,
        "supports_force_if_possible": False,
        "supports_usage_reporting": True,
    },
    "pre_llm_connector": {
        "supports_guided": True,
        "supports_force_if_possible": True,
        "supports_usage_reporting": True,
    },
    "wrapper": {
        "supports_guided": True,
        "supports_force_if_possible": True,
        "supports_usage_reporting": True,
    },
    "unknown": {
        "supports_guided": True,
        "supports_force_if_possible": False,
        "supports_usage_reporting": True,
    },
}
```

---

## 6. control mode 实现

## 6.1 配置方式

在 `config.py` 中新增：

```python
class AgentControlConfig(BaseModel):
    default_mode: str = os.getenv("OMNIMEMORA_AGENT_DEFAULT_MODE", "observe")
    per_agent_modes: dict[str, str] = {}
```

配置文件：`5_connectors/adapter/config/agent_modes.json`

---

## 6.2 load_control_mode 规则

1. 先查 per-agent 配置
2. 再用 default_mode
3. 如果 mode=`force_if_possible` 但 capability 不支持，则自动降级为 `guided`

---

## 7. main.py 主流程改造

## 7.1 新增导入

```python
from .agent_identity import resolve_agent_identity
from .control_mode import load_control_mode
from .capability_registry import get_capabilities
from .agent_metrics import record_agent_request, record_agent_result
```

## 7.2 请求进入时

```python
identity = resolve_agent_identity(request)
capabilities = get_capabilities(identity.integration_type)
control_mode = load_control_mode(identity.agent_id, identity.integration_type, config)
record_agent_request(identity=identity, mode=control_mode.mode)
```

## 7.3 优化路径判定

统一产出三个布尔值：

```python
optimization_attempted = False
optimization_applied = False
bypass_detected = False
```

### mode = off

* 不调用优化
* 标记 bypass
* passthrough

### mode = observe

* 保持当前行为
* 如果本次未走优化，标记 bypass

### mode = guided

* 保持当前行为
* 强化日志，不做强制补偿

### mode = force_if_possible

* 若本次已优化，正常走
* 若本次未优化且 capability 支持，则调用现有 `optimize_context()` 补做一次
* 若 capability 不支持，则降级 guided 并记录原因

### force_if_possible 边界

> **只用现有输入，重走一次 optimize_context。不允许额外 retrieval、不允许 hook LLM。**

---

## 8. quality_delta_pct 最小实现

代理指标公式：

```text
quality_delta_pct =
    0.5 * compression_gain_pct
  + 0.3 * dedup_gain_pct
  + 0.2 * selection_efficiency_pct
```

* compression_gain_pct = `(raw_tokens - compressed_tokens) / raw_tokens`
* dedup_gain_pct = 去重条目数 / 候选条目数
* selection_efficiency_pct = 选中条目数 / 候选条目数 的归一化评分

> 第一阶段只做代理指标，不做 LLM A/B。

---

## 9. agent_metrics.py 持久化与查询

## 9.1 需要实现的方法

```python
def record_agent_request(identity: AgentIdentity, mode: str) -> None
def record_agent_result(identity: AgentIdentity, mode: str, optimized: bool, bypassed: bool, meter, quality_delta_pct: float) -> None
def get_agent_metrics(agent_id: str | None = None, session_id: str | None = None) -> list[AgentMetricsSnapshot]
def get_live_agents(window_minutes: int = 30) -> list[dict]
```

## 9.2 聚合逻辑

* entry_rate = optimized_count / request_count
* bypass_count = request_count - optimized_count
* live agents = last_seen_at 在最近 N 分钟内

---

## 10. 新增 API

## 10.1 `GET /agents/live`

```json
[
  {
    "agent_id": "claude_code",
    "session_id": "sess_001",
    "workspace_id": "proj_alpha",
    "integration_type": "tool_caller",
    "mode": "guided",
    "request_count": 12,
    "optimized_count": 8,
    "entry_rate": 0.67,
    "saved_tokens": 1240,
    "quality_delta_pct": 13.2,
    "last_seen_at": "2026-04-14T10:00:00Z"
  }
]
```

## 10.2 `GET /agents/metrics`

支持 query：`agent_id`, `session_id`

---

## 11. UI 文案

| 字段 | UI 文案 |
|------|---------|
| entry_rate | 产品入口占比 |
| saved_tokens | 累计节省 Token |
| quality_delta_pct | 质量代理提升 |
| mode | 运行模式 |
| integration_type | 接入类型 |

---

## 12. 日志要求

```json
{
  "request_id": "...",
  "agent_id": "...",
  "session_id": "...",
  "workspace_id": "...",
  "integration_type": "...",
  "control_mode": "...",
  "optimization_applied": true,
  "bypass_detected": false
}
```

---

## 13. 测试要求

### unit tests

1. `resolve_agent_identity()` 头部解析正常
2. 缺失字段 fallback 为 unknown
3. `load_control_mode()` 能正确读取 per-agent mode
4. `force_if_possible` 在不支持 capability 时自动降级

### integration tests

5. observe 模式下未优化请求能被记录为 bypass
6. guided 模式下原有 optimize_context 路径不受影响
7. force_if_possible 模式下，当请求具备输入条件时能补做一次优化
8. `/agents/live` 与 `/agents/metrics` 返回结构正确

---

## 14. 验收标准（6 条）

1. engine 文件完全未改
2. 原有 query 主路径还能正常跑
3. 能识别 agent_id / session_id
4. UI 能拿到 per-agent 占比、节省、质量代理值
5. `force_if_possible` 只在 adapter 可控范围内生效
6. 所有新增能力都仍留在 `5_connectors/adapter/` 内部

---

## 15. 交付要求

1. 修改文件清单
2. 关键 diff 摘要
3. 新增 API 示例响应
4. 测试结果
5. 是否存在风险与回滚方案