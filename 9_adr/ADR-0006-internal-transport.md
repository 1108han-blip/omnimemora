---
doc_id: ADR-0006-INTERNAL-TRANSPORT
title: OmniMemora Internal Transport Specification
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

# ADR-0006: OmniMemora 内部直连传递规范

**版本：** v1.0
**状态：** Accepted
**日期：** 2026-04-14
**所有者：** OmniMemora Architecture Team

---

## 1. 核心原则

### Principle 1：内外流量分治

所有网络请求分成两类：

| 类型 | 定义 | 行为 |
|------|------|------|
| **Internal Traffic** | 本机内部调用（adapter ↔ runtime、MCP 内部、UI → 本地 API、healthcheck、metrics） | 直连，绕过代理 |
| **External Traffic** | 离开本机的调用（LLM provider、cloud policy、billing、第三方公网 API） | 尊重环境代理 |

### Principle 2：内部请求目标是"直连"，不是"指定地址"

内部请求必须绕过环境代理，但不规范单一地址。

❌ 不允许写死 `127.0.0.1`
❌ 不允许写死 `localhost`
❌ 不允许写死 `::1`

原因：不同用户环境下：
- 有的只通 IPv4
- 有的 localhost 解析优先走 IPv6
- 有的服务监听双栈，有的只监听某一边

**直连是硬规则，地址是运行时决策。**

### Principle 3：地址选择由"可用性解析器"决定

内部调用时，系统先判断当前机器哪种本地地址可达，再缓存使用。

---

## 2. 工程设计

### 2.1 新增模块

```
5_connectors/adapter/internal_transport.py
```

职责：
1. 判断某个目标是不是内部目标
2. 选择本机最优直连地址
3. 创建统一 internal HTTP client

### 2.2 内部目标识别

```python
def is_internal_target(host: str, port: int | None = None) -> bool:
```

判断标准：
- 主机是 `localhost`
- 主机是 `127.0.0.0/8`
- 主机是 `::1`
- 主机命中已配置的本地服务 host 列表
- 端口命中本地产品端口列表（如 18011 / 8765 / 5173）**且** host 明确为本机

> 注意：必须 host + port 一起判断，避免误伤。

### 2.3 内部 HTTP Client 工厂

```python
def create_internal_http_client() -> httpx.AsyncClient:
```

要求：
- `trust_env=False`（不继承系统代理）
- 合理 timeout
- 不继承系统代理
- 默认关闭代理自动发现
- 可加统一 headers / request_id

**以后代码里禁止直接裸写 `httpx.AsyncClient()`。**

外部 client：

```python
def create_external_http_client() -> httpx.AsyncClient:
```

要求：
- `trust_env=True`（尊重用户代理环境）

---

## 3. 地址解析策略

### 3.1 配置保留"逻辑地址"

配置里不强迫写死某一个地址：

```json
{
  "runtime_endpoint": "auto://runtime",
  "adapter_endpoint": "auto://adapter"
}
```

或内部统一过一层 resolver。

### 3.2 运行时解析顺序

```python
def resolve_internal_base_url(service_name: str, configured_url: str | None) -> str:
```

解析策略：
1. 如果用户明确配置了 host，先尝试该地址（用 internal client 直连，不走代理）
2. 如果配置是 localhost，做可达性探测（按顺序：配置值本身 → 127.0.0.1 → localhost → [::1]）
3. 选第一个真正可达的地址，缓存结果

### 3.3 缓存结果

```python
_internal_endpoint_cache = {
    "runtime": "http://127.0.0.1:8765"
}
```

避免每次请求都探测。允许 TTL 刷新或失败后重新探测。

---

## 4. 配置结构

```python
class InternalTransportConfig(BaseModel):
    enabled: bool = True
    probe_on_startup: bool = True
    cache_ttl_seconds: int = 300
    connect_timeout_seconds: float = 1.5
    read_timeout_seconds: float = 5.0
    loopback_candidates: list[str] = [
        "127.0.0.1",
        "localhost",
        "::1",
    ]
```

> 关键点：`loopback_candidates` 是候选集，不是强制集。

---

## 5. 启动时预探测

应用启动时，做一次轻量探测：

```python
probe_internal_endpoint("runtime")
probe_internal_endpoint("adapter")
```

结果写日志：

```json
{
  "service": "runtime",
  "configured": "http://localhost:8765",
  "resolved": "http://127.0.0.1:8765",
  "reason": "localhost_ipv6_unreachable"
}
```

---

## 6. 失败回退机制

内部请求失败时，自动回退重试：

```
当前缓存: http://[::1]:8765  →  连接失败
↓
回退: 127.0.0.1
↓
回退: localhost
↓
回退: ::1
```

选下一个可达地址并刷新缓存。

---

## 7. 日志规范

每次内部请求带以下字段：

```json
{
  "transport_type": "internal",
  "proxy_bypassed": true,
  "resolved_host": "127.0.0.1",
  "original_host": "localhost",
  "fallback_used": false
}
```

---

## 8. 测试规范

### 单元测试覆盖

- `is_internal_target()` 各种 host/port 组合
- `resolve_internal_base_url()` 候选优先级
- 失败后 fallback 逻辑
- 缓存 TTL 过期

### 集成测试场景

| 场景 | 预期 |
|------|------|
| localhost 可通 | 解析到 localhost |
| localhost 不通但 127.0.0.1 可通 | 回退到 127.0.0.1 |
| 127.0.0.1 不通但 ::1 可通 | 回退到 ::1 |
| 环境代理开启时 internal path | 仍正常直连 |
| external path | 仍能正常继承代理 |

---

## 9. 用户保障

> OmniMemora 不依赖用户手动配置 NO_PROXY、绕过规则或 Clash 本地排除规则来保证内部链路可用。

用户配了，产品兼容。用户没配，产品也尽量自保。
