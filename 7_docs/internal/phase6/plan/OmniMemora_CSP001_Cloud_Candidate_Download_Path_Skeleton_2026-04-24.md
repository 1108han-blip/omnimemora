# CSP-001 Cloud Candidate Download Path — Plan (Skeleton Batch)

**Date:** 2026-04-24  
**Status:** In progress

---

## Context

CSP-001 local compile strategy policy execution chain is completed and
running-verified. The next logical step is to establish the local-side
infrastructure for receiving, validating, and staging a candidate policy
bundle downloaded from a cloud source — without actually integrating any
cloud fetch source in this batch.

This batch does **design + repo skeleton only**: schema, hash validation,
local candidate cache, and the `AcceptCandidate()` → `PromoteCandidate()`
boundary. No real network calls, no promotion to active, no Codex validation.

---

## Scope

### In Scope

- **`CandidatePack` type** in `policy/types.go`:
  - Fields: `candidate_id`, `policy_version`, `policy`, `sha256`,
    optional `signature`, `signature_status`, `source`, `fetched_at`
  - `Validate()` method: required fields, version match, sha256, nil policy
  - Unknown JSON fields silently ignored
  - Invalid pack never affects active policy

- **`CandidateSource` / `SignatureStatus` constants** in `policy/types.go`:
  - `CandidateSource`: `local`, `cloud`
  - `SignatureStatus`: `not_required`, `valid`, `invalid`, `absent`
  - `not_required` for local skeleton; future batches add real verification

- **`CandidateFetcher` interface** in `policy/manager.go`:
  - `Fetch(candidateID string, policyJSON []byte) (*CandidatePack, error)`
  - No concrete implementations in this batch
  - Defines contract for future Cloudflare/Railway/embedding sources
  - No dependency from runtime hot path to cloud packages

- **`Manager.AcceptCandidate(pack *CandidatePack)`** in `policy/manager.go`:
  - Validates pack (includes SHA256 re-hash verification)
  - Writes candidate policy file to policy dir
  - Updates `candidate_version` in manifest only
  - Does NOT update `active_version`
  - Atomic manifest write (temp + rename)
  - Failed write leaves manifest unchanged (candidate file removed)
  - Cannot overwrite an active version

- **`Manager.GetCandidateInfo()`** in `policy/manager.go`:
  - Returns candidate metadata without loading the policy
  - `CandidateInfo` struct with version, source, sha256, signature_status, fetched_at

- **Tests** in `policy/manager_test.go`:
  - `TestCandidatePack_Validate_*` (valid + 5 rejection cases)
  - `TestAcceptCandidate_ValidPackWritesCandidateFileAndUpdatesCandidateVersion`
  - `TestAcceptCandidate_InvalidHashRejected`
  - `TestAcceptCandidate_InvalidPolicyRejected`
  - `TestAcceptCandidate_CannotOverwriteActiveVersion`
  - `TestAcceptCandidate_CandidateDoesNotAffectLoadActive`
  - `TestPromoteCandidate_ActivatesCandidateOnlyAfterExplicitCall`
  - `TestGetCandidateInfo_ReturnsMetadata`
  - `TestGetCandidateInfo_NoCandidate_ReturnsNil`
  - `TestAcceptCandidate_NewManifestCreated`

### Out of Scope

- No cloud compile / no per-request remote strategy decision
- No automatic promotion
- No real Cloudflare/Railway integration
- No promotion/live validation
- No Codex validation
- Adapter cloud candidate source remains a separate family

---

## Design Decisions

1. **Canonical JSON SHA256**: The SHA256 stored in `CandidatePack.SHA256` is
   computed from `json.Marshal(policy)` canonical form. Callers (fetcher
   implementations) must pre-compute and embed this value so the manager
   can independently verify.

2. **Atomic manifest update**: `AcceptCandidate` uses `os.CreateTemp` + `os.Rename`
   to write manifest atomically. On failure, candidate file is removed and
   manifest is left in its prior state.

3. **No network in hot path**: `CandidateFetcher` is an interface only.
   No concrete implementation in this batch, so the runtime hot path has no
   dependency on cloud packages.

4. **`not_required` for signatures**: Signature verification is explicitly
   deferred. The `SignatureStatus` enum is in place; real verification
   (e.g., Ed25519 HMAC) is a future batch.

5. **Cannot overwrite active**: `AcceptCandidate` explicitly rejects a pack
   whose `policy_version` is already present as active in the manifest.

---

## Validation

```bash
cd 4_core/local-runtime && go test ./policy -v
cd 4_core/local-runtime && go test ./tests -run 'CSP001|CompileStrategy|Policy' -v
cd 4_core/local-runtime && go test ./...
git diff --check
git status --short
```

---

## Closeout

- **Commit message:** `runtime: add compile strategy cloud candidate skeleton`
- Worktree must be clean after commit.
- Next batch can add a real fetch source only after this local candidate
  cache/validation layer is protected by tests.
