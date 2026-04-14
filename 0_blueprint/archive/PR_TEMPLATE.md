
# PR_TEMPLATE.md

## Summary

What is changed?

-
-

---

## Why

Why is this change needed?

-
-

---

## Scope

Which layer does this change belong to?

- [ ] 0_blueprint
- [ ] 1_architecture
- [ ] 2_product
- [ ] 3_governance
- [ ] 4_core
- [ ] 5_connectors
- [ ] 6_console
- [ ] 7_docs
- [ ] 8_migrations
- [ ] 9_adr

---

## Decision Checklist (must answer before merge)

### Core 3 questions

- [ ] This change is controlling memory, not storing primary memory
- [ ] This change does not introduce required backend dependency
- [ ] This capability remains replaceable / disableable

### Hard stop check

- [ ] Does NOT make cloud store user primary memory
- [ ] Does NOT introduce `/memory/write` as core cloud capability
- [ ] Does NOT require memory backend URL
- [ ] Does NOT create centralized hosted memory service
- [ ] Does NOT strongly bind system to one storage backend

### Architecture check

- [ ] Control Plane / Memory Plane separation remains clear
- [ ] Product still works without hosted memory backend
- [ ] Connector remains lightweight
- [ ] Engine / storage / model remain replaceable

### Value check

- [ ] Improves token savings, recall quality, control capability, or measurable usage
- [ ] If none of the above, this PR should not exist

### Commercial check

- [ ] Can explain pricing / metering / quota impact
- [ ] If not monetizable or measurable, priority has been justified

### Complexity check

- [ ] Does not introduce unnecessary new system layer
- [ ] Does not add unjustified cross-service dependency
- [ ] Does not create uncontrolled new state complexity

### Observability check

- [ ] request_id exists or is preserved
- [ ] tenant exists or is preserved
- [ ] agent exists or is preserved
- [ ] usage logging exists or is preserved

### UX check

- [ ] Does not make onboarding harder
- [ ] Does not break 5-minute first success goal
- [ ] Does not add unnecessary manual steps

---

## Files changed

-
-

---

## Acceptance criteria

-
-

---

## Governance result

- [ ] Pass
- [ ] Needs redesign
- [ ] Reject

### If redesign/reject, explain why:

-
