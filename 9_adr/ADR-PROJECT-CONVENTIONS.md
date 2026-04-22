---
doc_id: ADR-PROJECT-CONVENTIONS
title: OmniMemora Engineering Conventions
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.1.0
effective_date: 2026-04-22
depends_on: []
supersedes: []
last_verified_commit: ""
---

# ADR-PROJECT-CONVENTIONS

## 1. Legacy Marking

Rule: any file/module no longer in current design must be archived or marked historical.

Minimum requirements:

- move retired assets under `/archive/` or `/legacy/`
- provide a short README for why it was retired and what supersedes it
- do not keep retired assets in active-entry directories

## 2. Port Conventions

Active canonical ports:

| Port | Role |
|------|------|
| `5173` | User control UI |
| `18011` | Product data ingress |
| `8765` | Internal memory plane |

Rules:

- do not treat legacy ports as current product truth
- do not represent internal ports as user-facing product entry

## 3. Worktree Governance Thresholds

- `<= 8`: normal progress
- `9-12`: tighten scope
- `13-15`: warning zone
- `> 15`: no default scope expansion
- `> 20`: pause implementation; do batching/governance/alignment only

## 4. Reality Separation Rule

Every validation claim must explicitly name one reality:

- repository reality
- candidate reality
- running reality

Do not mix these in one conclusion sentence.

## 5. Cloud Boundary Rule

- Cloudflare: external domain + control-plane API/auth/tenant/billing/policy access
- Railway: recommendation candidate state/snapshots and lightweight async jobs
- Local: execution truth and active promotion

Cloud-side candidate data must not directly override local active policy.
