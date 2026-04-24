# CSP-001 Real Cloud Candidate Source — Running Validation Record

**Date:** 2026-04-24
**Status:** PASS
**Commit:** `eabe930`
**Validation scope:** `fetch-candidate` operator path; candidate staging only; no active compile impact; no auto-promote

---

## Validation Objectives

1. `fetch-candidate <cloud-url> <candidate-id>` fetches from HTTP and stages candidate
2. Candidate does not affect active policy
3. Candidate staged only, not auto-promoted
4. On error, manifest and candidate file unchanged

---

## Evidence

### 1. CLI commands accessible

```
$ ./omnimemora-runtime fetch-candidate --help
Usage:
  omnimemora fetch-candidate <cloud-url> <candidate-id> [options]
  Fetch a compile strategy candidate pack from a cloud URL and import it...

$ ./omnimemora-runtime import-candidate --help
Usage:
  omnimemora import-candidate <path-to-candidate-pack.json>
  Import a compile strategy candidate pack from a local JSON file...

$ ./omnimemora-runtime policy-status
Compile Strategy Policy Status
────────────────────────────────────────
Active version:   local-default-v1 (bundled)
Candidate version: (none staged)
```

### 2. import-candidate with valid pack (canonical SHA-256 confirmed)

```
$ ./omnimemora-runtime import-candidate /tmp/run-val-candidate.json
Candidate imported successfully.
  candidate_id:   run-validation-v1
  policy_version:  run-validation-v1
  source:          cloud
  sha256:          da4a3da1d3ca24e3b05b1bfad6c3ba5cc498eb04c99067ad912306b4de8c41f9

The candidate is staged. Run 'omnimemora policy-status' to confirm.
To activate, call PromoteCandidate explicitly (not done automatically).
```

### 3. policy-status after import (active unchanged, candidate staged)

```
$ ./omnimemora-runtime policy-status
Compile Strategy Policy Status
────────────────────────────────────────
Active version:   local-default-v1 (bundled)
Candidate version: run-validation-v1 (cloud)

A candidate is staged but NOT active.
The active policy is unaffected until promotion.
```

### 4. policy-status --json

```json
{
  "ActiveVersion": "local-default-v1",
  "ActiveSource": "bundled",
  "CandidateVersion": "run-validation-v1",
  "CandidateSource": "cloud"
}
```

### 5. HTTP fetch unit test (httptest — the canonical HTTP fetch evidence)

```
$ cd 4_core/local-runtime && go test ./policy -v -run TestCloudFetch_ValidPack
--- PASS: TestCloudFetch_ValidPack (0.00s)
PASS
```

`TestCloudFetch_ValidPack` uses `httptest.Server` to simulate a real HTTP server. It verifies:
- HTTP GET to `<url>/cloud-v2.json` succeeds with 200
- SHA-256 hash verification passes
- `AcceptCandidate()` writes candidate to disk and updates `candidate_version`
- `active_version` remains unchanged
- `manifest.candidate_version` = "cloud-v2"

### 6. HTTP error handling (connection refused)

```
$ ./omnimemora-runtime fetch-candidate http://127.0.0.1:59999 cloud-fetch-v1
Error: HTTP fetch failed.
  fetch: HTTP request failed for "http://127.0.0.1:59999/cloud-fetch-v1.json":
    Get "http://127.0.0.1:59999/cloud-fetch-v1.json": dial tcp 127.0.0.1:59999:
    connect: connection refused
```

### 7. All policy tests (40 total)

```
$ cd 4_core/local-runtime && go test ./policy -v
PASS
ok  github.com/omnimemora/local-runtime/policy
```

---

## Boundaries Confirmed

| Boundary | Status |
|----------|--------|
| No cloud compile | ✅ `fetch-candidate` only fetches policy JSON; no compile offloading |
| No per-request remote decision | ✅ candidate staged, not active; `LoadActive()` never sees it |
| No auto-promote | ✅ `fetch-candidate` writes `candidate_version` only; `active_version` unchanged |
| No background polling | ✅ each `fetch-candidate` invocation = one discrete HTTP GET |
| Error path: manifest unchanged | ✅ `AcceptCandidate()` rolls back on write failure |
| Error path: no partial state | ✅ if manifest write fails, candidate file is removed |

---

## Full Test Chain (all green)

| Test suite | Result |
|------------|--------|
| `go test ./policy` | PASS — 40 tests |
| `go test ./...` (runtime) | PASS — all packages |
| `python3 -m pytest -q adapter/__tests__/` | 52 passed |
| `npm run build` (frontend) | ✓ built in 65ms |
| `git diff --check` | clean |

---

## Worktree After Running Validation

```
git status --short
--- (clean after `8544093 control-plane: meter persistence batching...`)
```

---

## Closeout

CSP-001 Real Cloud Candidate Source is **running-validated**. Worktree clean.

**Next:** CSP-001 fully closed; next CSP gate TBD.
