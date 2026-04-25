# OmniMemora RES-001 Batch 4/5 Running Validation Closeout (2026-04-25)

## Scope

Closeout for:

- Batch 4 running validation
- Batch 5 docs-only sync

Fixed conclusion:

`raw evidence segmentation introduced; legacy source retained; archive-at-scale execution still not started`

## Repo Reality

- RES-001 repo line was split into 3 commits:
  - `docs(res): introduce raw evidence segmentation baseline`
  - `feat(dlp): add raw evidence segment mirror writer`
  - `feat(dlp): expose raw evidence segment status`
- No destructive/source-mutating/read-path-switch feature was added.

## Running Reality

### Promotion

- Command: `./tools/promotion/promotion.sh adapter+ui`
- Result: `running_reality_promoted`
- Restart truth: `changed`
- Log: `tools/verification/logs/promotion_20260425_175529.log`

### Evidence Generation and Verification (non-Codex path via product API)

- Request: `POST http://127.0.0.1:18011/v1/chat/completions`
- Upstream result: `404 gateway_upstream_error` (non-blocking for RES-001 evidence-write validation)
- Legacy source growth observed:
  - `compile_events.jsonl`: bytes `35 -> 4209` (source retained and written)
  - `proxy_events.jsonl`: lines `4682 -> 4684`, bytes increased
  - `trace_events.jsonl`: lines `31964 -> 31975`, bytes increased
- Segment manifest API:
  - `GET /data-lifecycle/raw-evidence/segments`: schema `dlp-raw-evidence-segments-manifest-v1`
  - `POST /data-lifecycle/raw-evidence/segments/manifest/rebuild`: schema `dlp-raw-evidence-segments-rebuild-v1`, manifest schema `dlp-raw-evidence-segments-manifest-v1`
- Health projection:
  - `/data-lifecycle/status.raw_evidence_segments` present and consistent with segment manifest summary
- Request evidence path:
  - `GET /debug/request_evidence?request_id=<recent id>` returned `200` with stable payload keys

### Raw Mutation Check

- Source move: not observed
- Source delete: not observed
- Compression path: not observed
- Production read-path switch: not observed

## Docs Reality

- Phase6 index line updated from `running validation pending` to `observe-only running validation passed`.
- This closeout does not declare archive-at-scale execution or storage cleanup completion.

## Final Status

- `raw evidence segmentation observe-only running validation passed`
- `legacy source retained`
- `archive-at-scale execution still not started`
