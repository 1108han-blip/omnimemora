# CSP-001 Candidate Pack Local Import — Closeout Record

**Date**: 2026-04-24
**Status**: Closed
**Batch**: CSP-001 Candidate Pack Local Import — Phase 6 First Batch
**Decision**: `docs/adr/DECISION-CSP-001.md`

---

## Objective

Deliver a local-only candidate pack import entry for the compile strategy policy layer. The entry reads a JSON candidate pack from the local filesystem, validates it, and writes it to the candidate cache. It does not trigger cloud download, does not auto-promote, and does not enter the compile hot path.

---

## Repository Reality (Code & Schema)

### Local Import Entry

- `policy/import.go` — `ImportCandidate(path, policyDir)` reads a candidate pack JSON, validates it, calls `Manager.AcceptCandidate()`. Exit codes: 0 success, 1 failure (hash mismatch / active-overwrite / manifest write). No partial state on failure.
- `policy/types.go` — `CandidatePack` struct with `Validate()` method; `CandidateSource` constants (local/cloud).
- `policy/manager.go` — `AcceptCandidate()` re-marshals policy to compute canonical SHA-256, compares to stored hash, writes `{version}.json`, updates `manifest.json` candidate_version. Guards against overwriting active version.
- `GetPolicyStatus(policyDir)` — returns `PolicyStatus` with active/candidate version and source without loading full policy into memory.

### CLI Wiring

- `internal/cli/commands.go` — `ImportCandidate(args)` and `PolicyStatus(args)` commands. `main.go` routes `import-candidate` and `policy-status` subcommands.
- Usage docs embedded in each command (`printImportCandidateUsage`, `printPolicyStatusUsage`).
- Exit codes propagated via `os.Exit()` — process terminates with non-zero on validation/hash/overwrite errors.

### Boundaries Held

| Boundary | Status |
|----------|--------|
| No cloud download | ✅ `import.go` reads only local files |
| No auto-promote | ✅ Candidate staged only; `PromoteCandidate()` requires explicit call |
| No compile hot-path entry | ✅ Candidate does not affect `LoadActive()` |
| Active policy unaffected | ✅ `LoadActive()` reads active_version from manifest, not candidate_version |

---

## Running Reality (Verified)

### Unit Tests — policy package

```
cd 4_core/local-runtime && go test ./policy -v
PASS — 28 tests covering:
  - Local default policy load
  - Missing/invalid policy falls back to built-in
  - Candidate does not affect active before promotion
  - Manual promotion switches active
  - auto resolves per policy rules
  - Mode defaults from policy
  - No network calls
  - CandidatePack.Validate() — all invalid cases rejected
  - AcceptCandidate — valid pack writes file and manifest
  - AcceptCandidate — invalid hash rejected, manifest unchanged
  - AcceptCandidate — cannot overwrite active version
  - ImportCandidate — valid pack file
  - ImportCandidate — hash mismatch fails manifest unchanged
  - ImportCandidate — invalid policy fails manifest unchanged
  - ImportCandidate — active-overwrite attempt fails
  - GetPolicyStatus — active only, with candidate
```

### Full Runtime Test Suite

```
cd 4_core/local-runtime && go test ./...
ok   github.com/omnimemora/local-runtime
ok   github.com/omnimemora/local-runtime/api
ok   github.com/omnimemora/local-runtime/internal/attach
ok   github.com/omnimemora/local-runtime/internal/cli
ok   github.com/omnimemora/local-runtime/policy
ok   github.com/omnimemora/local-runtime/tests
ok   github.com/omnimemora/local-runtime/tests/legacy/phase2b
```

### gofmt Hygiene

All 4 modified/new files pass `gofmt`:
- `policy/import.go` — new file, formatted ✅
- `internal/cli/commands.go` — reformatted ✅
- `main.go` — reformatted ✅
- `policy/manager_test.go` — reformatted ✅

---

## Excluded Artifacts (Not Part of This Batch)

The following remain in working tree and are not in scope for this closeout:
- Cloud candidate download path (CSP-001 Real Cloud Candidate Source — next batch)
- `promote-candidate` CLI command (explicit promotion call; handled by `policy-status` guidance for now)
- Recommendation policy (`recommendation_policy` family)

---

## Constraints Maintained

- **Local-only import**: `import-candidate` reads only from local filesystem; no HTTP, no cloud fetch.
- **No automatic promotion**: Candidate is staged; `PromoteCandidate()` must be called explicitly.
- **Active policy untouched**: `LoadActive()` reads `active_version`, not `candidate_version`. Candidate never enters compile hot path before promotion.
- **No cloud compile**: Strategy decisions remain local.
- **No Codex validation**: Out of scope for this batch.
- **No UI changes**: CLI only.

---

## Acceptance Criteria

- [x] `import-candidate <path>` reads local JSON, validates, writes candidate cache
- [x] SHA-256 hash mismatch → exit 1, manifest unchanged, no candidate file written
- [x] Missing/invalid candidate_id, policy_version, or nil Policy → exit 1, manifest unchanged
- [x] Active-overwrite attempt (pack version == active version) → exit 1, manifest unchanged
- [x] Valid pack → candidate `{version}.json` written, `manifest.json` candidate_version updated, active_version unchanged
- [x] `policy-status [--json]` reports active version, candidate version, source
- [x] Candidate does not affect `LoadActive()` — active strategy unchanged after import
- [x] All policy package tests pass
- [x] All runtime tests pass
- [x] gofmt clean on all 4 files

---

## Next Batch

After this closeout, the next batch is **CSP-001 Real Cloud Candidate Source**:

- Cloud-side candidate pack fetch → write to local cache via `AcceptCandidate()`
- Reuses existing `policy/manager.go` `AcceptCandidate()` path — no second candidate-write logic
- No cloud compilation, no automatic promotion, no Codex validation
- First real cloud source calls the same local `import/accept` entry as this batch's local path

---

## Files in This Batch

**Modified**:
- `4_core/local-runtime/internal/cli/commands.go` (+146 lines: `import-candidate`, `policy-status` commands)
- `4_core/local-runtime/main.go` (+6 lines: `import-candidate` routing)
- `4_core/local-runtime/policy/manager_test.go` (+521 lines: import/scenario tests)

**New**:
- `4_core/local-runtime/policy/import.go` — local candidate pack import entry

**Docs-only** (separate commit after code):
- `docs/adr/DECISION-CSP-001.md` — updated status to reflect batch 1 complete
- `docs/spec/SPEC-COMPILE-STRATEGY-POLICY-001.md` — local import already in scope, no change needed
- `3_governance/OPERATIONAL_DRIFT_REGISTER.md` — this closeout record appended
