# OpenViking Editions

This document explains the capability boundaries between the GitHub (open source) edition, Pro edition, and Enterprise edition of OpenViking.

## Core Principle

- **GitHub Edition**: Lets users "see it and run it"
- **Pro Edition**: Lets users "install it and use it stably"
- **Enterprise Edition**: Lets users "govern safely in production"

## Feature Capability Boundaries

| Capability | GitHub Edition | Pro Edition | Enterprise Edition | Notes |
|---|---|---|---|---|
| OpenClaw basic integration | Yes | Yes | Yes | memory-openviking entry point |
| Basic Memory Adapter | Yes | Yes | Yes | Write, search, read, delete pipeline |
| Core memory compilation/orchestration | Yes | Yes | Yes | Core cognitive asset of the project |
| P1 strategy configuration externalization | Yes | Yes | Yes | Core capability, not behind paywall |
| Basic tenant isolation | Yes | Yes | Yes | Demonstrates multi-tenant approach |
| Default P1 tenant_agent behavior | Yes | Yes | Yes | Consistent with currently verified behavior |
| tenant/tenant_agent switching | Yes | Yes | Yes | Core layering and strategy capability |
| doctor/verify capabilities | Limited | Yes | Yes | GitHub: minimal diagnosis and demo acceptance |
| Installer and standard installation | No | Yes | Yes | Reduces delivery friction |
| Standard upgrade/backup/rollback | No | Yes | Yes | Delivery certainty |
| Offline execution window | No | No | Yes | Enterprise delivery and change governance |
| Execute Engine / window packet | No | No | Yes | Higher governance capability |
| Audit reports and evidence | No | Yes | Yes | Pro: basic, Enterprise: complete |
| Production support policy | No | Yes | Yes | GitHub: community/self-help only |

## Delivery / Operations / Audit Boundaries

| Capability | GitHub Edition | Pro Edition | Enterprise Edition | Notes |
|---|---|---|---|---|
| Distribution format | Source/minimal example | Yes | Yes | GitHub: repository-based |
| One-click deployment | No | Yes | Yes | Turns "usable" into "easy to use" |
| Version verification & compatibility diagnosis | Basic | Yes | Yes | Free: basic visibility only |
| Automatic backup & recovery | No | Yes | Yes | Core paid value |
| Rollback protection | No | Yes | Yes | Pro: standard, Enterprise: enhanced |
| Offline change package | No | No | Yes | Enterprise requirement |
| Execution trace | Basic logs | Standard reports | Full audit chain | Emphasizes evidence completeness |
| Support boundary | Community/self-help | Standard support | Enterprise support | Value in support and delivery certainty |

## GitHub Edition

The GitHub edition's mission is to "demonstrate capability," not "bear delivery pressure." It should help users quickly understand:

- What problem OpenViking solves
- That it's not just a plugin, but an agent memory compilation and orchestration layer
- That its core capabilities are valid and can run locally

The GitHub edition is for:
- Quick experimentation
- Studying principles
- Prototyping
- Establishing trust in the approach

## Pro Edition

The Pro edition's value is "turning something that runs into something deliverable." It sells:

- Worry-free installation
- Clear acceptance criteria
- Boundaries for upgrades and rollbacks
- Troubleshooting when issues appear
- Complete delivery materials

This isn't the core algorithm itself, but delivery certainty around the core capability.

The Pro edition is for when you want:
- Standard installation
- Stable upgrades with rollback
- Basic audit reporting
- Standard support

## Enterprise Edition

The Enterprise edition's value is "turning something deliverable into something governable." Its focus isn't just piling on more features, but:

- Safe changes within offline windows
- Auditable evidence of execution
- Stricter recovery and governance
- Adaptation to formal production change requirements

The Enterprise edition is for when you need:
- Offline execution windows
- Complete audit evidence and chain
- Strict rollback and recovery closed-loop
- Production change governance

## Upgrade Path

1. **Start with GitHub**: Understand the architecture, run the pipeline, verify the approach.
2. **Upgrade to Pro**: When you need to install it for real, want standard acceptance, stable upgrades, and support.
3. **Upgrade to Enterprise**: When you need to run in production with offline change windows, full audit, and stronger governance.

This path matches the natural progression from experimentation to real deployment to production governance.
