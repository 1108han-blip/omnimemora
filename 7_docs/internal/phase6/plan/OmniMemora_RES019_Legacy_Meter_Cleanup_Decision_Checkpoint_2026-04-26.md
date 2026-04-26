# OmniMemora RES-019 Legacy Meter Cleanup Decision Checkpoint (2026-04-26)

## Fixed Conclusion

`legacy meter cleanup decision checkpoint recorded; cleanup execution not started; delete/move/compress/truncate execution not started`

## Scope

RES-019 is a decision checkpoint only.

- switched on: cleanup readiness decision record after RES-017 copy pilot, RES-018 restore/readback validation, and RES-018A hash-contract hardening
- not switched on: cleanup execution
- not switched on: legacy source deletion
- not switched on: source move/compress/truncate
- not switched on: production read-path changes

## Evidence Chain

Completed prerequisites:

- RES-001 to RES-007: storage governance baseline closed; sqlite-first read paths passed; legacy cleanup not started
- RES-008: cleanup readiness design completed
- RES-009: cleanup preview generated; cleanup execution not started
- RES-010 to RES-016A: backup export readiness, gates, proposal, running alignment, and parity preflight completed
- RES-017: single backup export copy pilot completed; source retained; cleanup execution not started
- RES-018: restore/readback validation passed; source retained; cleanup execution not started
- RES-018A: restore/readback recorded hash contract hardened; running validation remains passed

Current running evidence:

- promotion revision: `caa01f3`
- promotion log: `tools/verification/logs/promotion_20260426_111139.log`
- parity: `critical_mismatch_count=0`
- restore/readback: `status=passed`
- source retained: `true`
- production restore started: `false`
- cleanup started: `false`

## Decision Output

- `ready_to_execute_cleanup=false`
- `reason`:
  - this checkpoint records evidence readiness only
  - cleanup remains destructive or potentially irreversible from the product user's perspective
  - RES-018 and RES-018A validate backup readability, but do not authorize deleting, moving, compressing, or truncating legacy meter source files
- `required_next_scope`:
  - explicit operator cleanup approval design or execution gate
  - source-file inventory with exact file names, byte counts, hashes, and backup package references
  - rollback/readback instructions that do not depend on memory of this conversation
  - final running parity check immediately before any future execution attempt
- `forbidden_next_scope_without_new_explicit_approval`:
  - deleting legacy meter JSON
  - moving legacy meter JSON
  - compressing legacy meter JSON
  - truncating legacy meter JSON
  - switching production read path as part of cleanup
  - touching user/client memory
  - Codex live validation

## Boundary Confirmation

- cleanup execution not started
- delete/move/compress/truncate execution not started
- backup export copy remains copy-only evidence
- restore/readback remains validation-only evidence
- production read path remains unchanged
- legacy source remains retained
