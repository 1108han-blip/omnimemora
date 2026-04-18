---
doc_id: SCAN-PHASE5_5-TRACKA-8765-2026-04-18
title: OmniMemora Phase 5.5 Track A 8765 Bounded Scan
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track A: 8765 对外接口收口 Bounded Scan

## 可复用

- [0_blueprint/PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md)
  - 已固定 `8765 = 内部 memory plane`
- [0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md)
  - 已固定 `18011/8765` 边界
- [4_core/local-runtime/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/README.md)
  - 已明确 runtime 是 internal only
- [5_connectors/adapter/agent_control_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/agent_control_api.py)
  - 已形成 `18011 -> runtime(/agents/control)` 的正式代理面

## 必须避开

- 把 runtime 公开给用户当成“第二产品入口”的旧叙事
- 把 `8765` 重新抬升成控制面或正式诊断面的对外主入口
- 直接依赖旧审计文档里的历史运行现实作为新阶段接口依据

## 需要清理

- [5_connectors/omni-omnimemora-plugin/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/omni-omnimemora-plugin/README.md)
  - 已在本轮改为只展示 `18011` 为用户可见入口
- [4_core/local-runtime/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/README.md)
  - 已补 internal-only 说明；后续仍需继续区分“内部可用 contract”与“正式产品叙事”
- [4_core/local-runtime/README.txt](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/README.txt)
  - 已去掉 `8765/dashboard` 的对外展示，改为 internal runtime health
- 旧 phase2 / legacy 文档中仍有 `8765` 作为显式接入面的历史描述

## 当前实现入口

- [4_core/local-runtime/api/server.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/api/server.go)
  - runtime 当前仍在 `8765` 暴露 `/health` 与 `/agents/control*`
- [4_core/local-runtime/api/agent_control.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/api/agent_control.go)
  - 低频 install/uninstall 真正落在 runtime 内部
- [5_connectors/adapter/config.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/config.py)
  - adapter 通过 `memory_backend.base_url` 指向 runtime
- [5_connectors/adapter/agent_control_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/agent_control_api.py)
  - `18011` 对外控制面已通过 runtime 代理取数和执行

## 扫描结论

Track A 不是“删除 8765”，而是“收掉把 8765 当对外产品面的叙事和误用面”。

按当前活跃文档面复扫，剩余 `8765` 提及主要属于以下几类：

- 产品边界基线文档中的明确边界声明
- Track A/Track B 兼容与验证记录
- runtime 默认端口、候选实例端口、测试夹具与内部 transport 说明

当前没有再发现把 runtime `/agents/control*` 或 runtime dashboard 写成用户直接控制面的活跃执行文档。

当前最安全的第一批动作应是：

1. 对外文档和插件说明的第一批收口已完成
2. runtime contract 的内部标注与退场清单整理已完成第一轮
3. 下一步只需在需要时继续审查实现注释与 internal contract，暂不触碰 `18011 -> runtime` 的内部调用链
