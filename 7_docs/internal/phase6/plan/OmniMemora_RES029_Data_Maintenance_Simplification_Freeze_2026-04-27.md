# OmniMemora RES-029 Data Maintenance Simplification Freeze (2026-04-27)

## Fixed Conclusion

`automatic cleanup expansion paused; manual maintenance surface preferred`

## Decision

RES-029 freezes the RES-020 through RES-028 automatic cleanup expansion track.

The existing cleanup governance work remains valuable as an internal safety and diagnosis layer, but it is no longer a reason to continue the approval -> second pilot -> scale-up automation path.

Next product direction:
- prefer a thin user-controlled manual maintenance surface.
- keep product behavior centered on detection, explanation, preview, backup verification, and rollback guidance.
- do not continue deep automation unless a separate future decision explicitly reopens it.

## Current State

Already completed:
- one single-file reversible quarantine pilot was executed in RES-023.
- parity, snapshot, preview, backup, rollback, stability, scale-up readiness, proposal, and approval-readiness artifacts exist as internal diagnostic capabilities.

Not started:
- second-file pilot execution not started
- automatic cleanup expansion paused
- batch cleanup not started
- delete/compress/truncate/batch cleanup not started
- automatic cleanup not opened

No rollback of existing engineering is required because it provides safety value:
- parity and snapshot explain meter consistency.
- cleanup preview and transaction preview explain possible candidates and risk.
- backup/export/readback artifacts explain recovery coverage.
- rollback/stability/readiness artifacts preserve guardrails.
- proposal and approval-readiness artifacts document why execution remains blocked.

## Repositioning

The following surfaces are retained as internal diagnosis and governance surfaces:
- parity
- snapshot
- preview
- backup
- rollback
- stability readiness
- scale-up readiness
- second-file proposal
- approval readiness

They are not approval pressure.
They are not an automatic execution queue.
They are not a reason to proceed to second-file execution.

## Preferred Next Product Surface

Future user-facing maintenance work should be a simple manual maintenance surface with:
- storage usage
- large files
- recommendation
- backup status
- risk label
- manual cleanup button
- restore button

Required behavior:
- show what is large or stale.
- explain risk in plain language.
- verify backup/readback before suggesting action.
- require explicit user action for cleanup.
- provide restore guidance and recovery state.

Out of scope for the next stage:
- auto approval injection
- automatic second-file execution
- scale-up automation
- hidden cleanup
- delete/compress/truncate/batch cleanup by default

## Repository Reality

This is a docs-only decision record.

No code changes are made in RES-029.
No promotion is run in RES-029.
No cleanup endpoint is called in RES-029.

Current pre-existing local environment drift:
- `.claude/settings.local.json`

Decision:
- excluded from RES-029
- not staged as part of this decision
- this record does not claim global worktree clean while that file remains modified

## Gate

Docs-only gate:
- README has a RES-029 row.
- this record contains `automatic cleanup expansion paused`.
- this record contains `manual maintenance surface preferred`.
- this record contains `delete/compress/truncate/batch cleanup not started`.

## Boundary Confirmation

- automatic cleanup expansion paused
- manual maintenance surface preferred
- second-file pilot execution not started
- cleanup scope expansion not started
- delete/compress/truncate/batch cleanup not started
