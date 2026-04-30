# OmniMemora MVP Proprietary Release Promo Kit (2026-04-30)

## Release Boundary

This kit is for a proprietary controlled-beta/product release, not an open-source launch.

- Do not describe the package as open source.
- Do not publish source-availability promises from this document.
- Keep OmniMemora separate from unrelated AI product experiments or local client setup projects.
- Before any external release, verify package version strings and release artifact metadata.

## Version Checkpoints

Current repo version sources observed on 2026-04-30:

| Component | Version Source | Current Value | Release Action |
|-----------|----------------|---------------|----------------|
| OpenClaw plugin | `5_connectors/omni-omnimemora-plugin/package.json` | `1.0.0` | confirm or bump before packaging |
| Dashboard | `6_console/demo-dashboard/package.json` | `0.0.0`, `private=true` | keep private or assign release version before distribution |
| Local runtime package | `4_core/local-runtime/scripts/release/RELEASE_NOTES.txt` | `{{PACKAGE_VERSION}}` placeholder | replace during packaging |
| Local runtime license | `4_core/local-runtime/scripts/release/LICENSE.txt` | proprietary beta template | keep aligned with package version |

## Positioning

OmniMemora is a user-controlled memory optimization layer for AI workflows:

- `5173`: user control and visibility
- `18011`: only product ingress after opt-in
- `8765`: internal memory plane

No silent takeover, no hidden multi-entry behavior.

## Core Value (MVP)

1. Save tokens on real user requests.
2. Save API cost on real user requests.
3. Keep response path stable and low-latency.

## Short Promo Copy

OmniMemora helps teams reduce LLM token spend without changing how they work.

You keep control in the UI, route through one product entry, and get memory-assisted responses only when you opt in.

Built for practical outcomes: lower cost, faster loops, no extra complexity.

## Social Post (CN)

我们把 OmniMemora 的 MVP 目标压到三件事：

- 真请求省 token
- 真请求省成本
- 低延迟稳定运行

架构上坚持三层边界：`5173 控制` / `18011 产品入口` / `8765 内部记忆层`。
不做静默接管，不做多入口绕行。

如果你在做 AI 产品降本，这条路线可以直接复用。

## Social Post (EN)

OmniMemora MVP is focused on 3 outcomes only:

- Real token savings on real requests
- Real API cost reduction
- Stable, low-latency operation

Boundary stays explicit:
`5173 control`, `18011 product ingress`, `8765 internal memory plane`.

No silent takeover. No multi-entry bypass.

## GitHub Release Note Draft

Use this as a private/proprietary release note draft. If the repository remains public-facing, do not imply that downloadable product artifacts are open source.

### What OmniMemora MVP proves

- Token-saving value on real requests
- Cost-saving value on real requests
- Stable operation without slowing users down

### Product boundary

- User control: `:5173`
- Product ingress (opt-in): `:18011`
- Internal memory plane: `:8765`

### Current verification status (2026-04-30)

- Local running reality: healthy
- Cloud running reality: follow-up verification required (DNS/timeout observed)

### License posture

- Proprietary controlled-beta package.
- Source repository docs may be visible for coordination, but product artifacts are not licensed as open source by this kit.
