# 6_console/ - 用户控制台

Purpose: `:5173` 用户控制入口（本地），对接 `:18011` 产品数据入口。

## 职责

- 用户控制台 UI
- Agent 接入/路由双开关控制
- Token Savings 与运行证据展示
- 控制面状态投影（不承载产品数据主路径）

## 当前目录

```text
6_console/
  demo-dashboard/   (active local dashboard at :5173)
```

## 云端边界说明

- `doloclaw.com` 是外部正式域名入口与轻控制面承载。
- 本目录不再包含 cloud UI 原型工程。
- Cloudflare/Railway 的职责定义见 `9_adr/ADR-0002-cloud-refactor.md`。

## 治理规则

- 控制台只能通过标准 API 访问 `:18011`
- 控制动作必须可审计
- 不得把 UI 当作产品数据入口
