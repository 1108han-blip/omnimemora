# SPEC-SKILL-SUGGESTION-CONSTRAINTS-002

## Scope

Constraint specification for Batch 1 Skill Suggestion behavior.

## Hard Constraints

- no file reads
- no env reads
- no network access
- no adapter/runtime/cloud imports
- no plugin/skill installation or execution
- no routing/path decision changes
- no transparent forwarding changes
- no direct UI behavior

## Product Boundary Alignment

- `18011` remains the product data path
- `8765` remains internal runtime/memory plane
- skill suggestion is logic-side advisory metadata only

## Output Constraints

- output field name: `skill_suggestions`
- sidecar metadata only
- MUST NOT be merged into `packed_context`
- default behavior must be safe when empty (empty list)

## Candidate Reality Checks

- logic tests confirm decision/continuation suggestions
- implementation/no-query produce empty suggestions
- adapter tests confirm metadata passthrough only
- no protocol behavior regression in OpenAI/Anthropic compile path
