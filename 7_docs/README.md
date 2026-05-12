
## 目录结构

```
7_docs/
  external/
    api/
    guides/
    examples/
    release-notes/

  internal/
    phase1/
    phase2/
    phase3/
    phase6/          # historical governance and promotion workstream
    structured_compile/  # current Phase 7 compile capability mainline
```

# 7_docs/ - 文档层

## Purpose

分为两类文档：

### external/
对外文档：

- API 文档（OpenAPI/Swagger）
- 集成指南
- 示例代码
- 用户手册
- 发布说明

### internal/
内部文档：

- Phase 阶段文档与当前能力主线
- 实施记录
- 审计报告
- 阶段总结

---

## 治理规则

### external/
- 面向用户/开发者
- 必须稳定、可使用

### internal/
- 面向开发与决策
- 描述“当前系统真实状态”
- 不允许包含未来设计（除当前 roadmap / active mainline 目标）
