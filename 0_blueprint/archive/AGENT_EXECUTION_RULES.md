
# AGENT_EXECUTION_RULES.md

## Purpose

This file is the execution rulebook for Claude Code, Codex, and any other coding agent.

All implementation must comply with:

- `0_blueprint/`
- `3_governance/`

Violation = reject.

---

## A. Before doing anything, answer these 3 questions

1. Is this controlling memory, or storing memory?
2. Does this introduce dependency on a backend to make the system work?
3. Can this capability be replaced or disabled?

### Decision rule

- Any 1 "bad" answer → stop and review
- Any 2 "bad" answers → reject the direction
- All good → continue

---

## B. Hard stop conditions

If the task introduces any of the following, STOP:

- Cloud stores user primary memory
- Cloud provides `/memory/write` as core product capability
- A memory backend URL becomes required
- A centralized hosted memory service is introduced
- Storage is strongly bound to one DB / vector backend

---

## C. Must-pass architecture conditions

All of these must remain true:

- Control Plane and Memory Plane are clearly separated
- Product can exist without hosted memory backend
- Connector remains lightweight and replaceable
- Memory engine can be replaced
- Storage can be replaced
- Model can be replaced

---

## D. Feature value check

A feature must satisfy at least one:

- Improves token savings
- Improves recall quality
- Improves control capability (`policy`, `routing`, `metering`)
- Produces measurable usage / billing value

If none apply, do not build it.

---

## E. Commercial check

Before implementation, answer:

- How does this affect pricing?
- Can it be measured?
- Can it be gated by plan / quota?

If all answers are "no", lower priority or reject.

---

## F. Complexity check

Ask:

- Does this introduce a new system layer?
- Does this add cross-service dependency?
- Does this increase state complexity?

Rule:

- 2 yes → redesign first
- 3 yes → reject

---

## G. Observability check

Do not ship unless these exist:

- request_id
- tenant
- agent
- usage record

---

## H. UX check

Ask:

- Can the user get first success in 5 minutes?
- Does this require complex manual setup?
- Does this break existing workflow?

If setup becomes heavy, simplify before shipping.

---

## I. Final veto question

Will this make OmniMemora look like a memory storage system?

If the answer is even "a little bit yes", reject it.

---

## J. Execution instruction for coding agents

Before implementing, run this rule set.

If any violation appears:

- do not patch around it
- do not "just make it work"
- do not add hidden backend dependency

Stop, explain the boundary violation, and propose a compliant alternative.
