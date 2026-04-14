
# 6_console/ - 用户控制台

**Purpose:** doloclaw.com / app.doloclaw.com 用户界面

## 职责

- 用户控制台 UI
- Token Savings Meter 展示
- API key 管理
- 用量统计
- 账单管理
- Trial/付费转化路径

## 目录结构

```
6_console/
  pages/          (Cloudflare Pages)
  functions/      (Pages Functions)
  ui-prototype/   (UI 原型)
```

## 治理规则

- 控制台只能通过标准 API 访问 backend
- 敏感操作必须有 audit log
- Token Savings Meter 是核心展示指标
