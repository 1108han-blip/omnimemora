# OpenViking

![OpenViking hero](docs/assets/openviking-hero-banner.png)

OpenViking is the memory compilation and orchestration layer for agents. It helps you transform fragmented memory writes, filtering, compilation, recall, and conflict handling into a verifiable middle layer pipeline -- not just stopping at "store and retrieve" plugin-level functionality.

This GitHub edition is for users who want to get the pipeline running, understand the architecture, and verify value first. It provides basic integration, core memory capabilities, and minimal working examples to help you quickly establish an intuitive understanding of the project's capabilities.

## Start Here

New to OpenViking? These documents will guide you:

- **[Quick Start](docs/quick-start.md)**: Your first stop -- understand what this repo contains and how to explore it
- **[Architecture Overview](docs/architecture.md)**: Learn the high-level architecture and how the layers fit together
- **[Editions Comparison](docs/editions.md)**: See detailed capability boundaries between editions
- **[Pricing & Upgrade Paths](docs/pricing-and-upgrade.md)**: Understand when to upgrade and what you get

## What Problems Does OpenViking Solve?

OpenViking doesn't solve "can we store a memory" -- it solves "how should an agent manage memory." In real-world usage, the hardest problems usually aren't the write interface itself, but questions like:

- What content should enter memory, what should be filtered?
- Which scope should memory be saved to?
- When to recall, how much to recall, how to avoid noise?
- When new and old memories conflict, how to keep results stable?
- How to maintain verifiable behavior across different environments and integration methods?

OpenViking brings these problems together from scattered scripts, ad-hoc conventions, and single-point logic into an independent middle layer. The benefit is that memory capability is no longer just "an accessory feature of some agent," but a product capability that can be reliably reused, gradually extended, and explicitly delivered.

## What's Included in the GitHub Edition?

The GitHub edition includes:

- OpenClaw side basic integration (memory-openviking entry point)
- Basic Memory Adapter (write, search, read, delete pipeline)
- Core memory compilation/orchestration logic
- P1 strategy configuration externalization
- Basic tenant isolation
- Default P1 tenant_agent behavior
- tenant/tenant_agent switching
- Limited doctor/verify capabilities (demo-level acceptance)

This is enough to see the pipeline in action, verify that "it can integrate, it can run, it can be understood." If your goal is just quick experimentation, studying principles, or prototyping, the open source edition already provides a minimal viable path.

## Why Upgrade?

When you start moving toward real deployment, the questions quickly change. You'll start caring about:

- Is installation straightforward?
- Can upgrades be rolled back if they fail?
- How to handle environment differences?
- Is there a standard for acceptance?
- How to diagnose issues when they appear?

At this point, what's valuable isn't just the core capability itself, but the delivery, operational certainty, and support boundaries built around the core capability.

## Editions Overview

OpenViking uses a three-tier distribution strategy to match different stages of real-world needs:

- **GitHub Edition**: Proves capability and builds trust. See it, run it, understand it.
- **Pro Edition**: Handles installation, acceptance, upgrades, rollbacks, and standard delivery. Get it installed, verified, and running stably.
- **Enterprise Edition**: Provides offline windows, audit evidence, and stronger governance. Operate safely in production with auditability and rollback.

This tiering isn't about splitting features for monetization -- it's about putting different stages of real requirements into the most appropriate product form.

For more details about edition boundaries, see [docs/editions.md](docs/editions.md).
