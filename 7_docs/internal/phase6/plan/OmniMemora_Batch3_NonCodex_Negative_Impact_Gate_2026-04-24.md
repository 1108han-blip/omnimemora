# OmniMemora Batch 3 Non-Codex Negative-Impact Gate (2026-04-24)

## Batch Record

- batch: `3` (non-Codex sub-batch)
- date: `2026-04-24`
- validation target: `running reality + user-path reality`
- scope: `Claude Code default`, `Claude Code cc-haha`, `OpenClaw`
- result: `conditional pass`
- primary breakpoint: `control API latency under route toggling; no request-path failure evidence`

## Validation Method

- Baseline path:
  - route disabled via `POST /agents/control/disable`
  - requests still entered `18011`, produced `request_id`, and were queryable in `request_evidence`
  - expected request status: `bypassed`
- Product path:
  - route enabled via `POST /agents/control/enable`
  - requests entered the normal compile/product path
  - expected request status: `warning` with non-zero token savings evidence
- Evidence surfaces:
  - `GET /debug/request_evidence?request_id=...`
  - `GET /requests/{request_id}/meter`
  - `GET /proxy/events`
  - adapter running log (`adapter.launchd.err.log`)

## Claude Code Default

### Baseline
- short task:
  - request_id: `999bcb6a8a77`
  - request_status: `bypassed`
  - error_code: none
- medium task:
  - request_id: `e058107d174c`
  - request_status: `bypassed`
  - error_code: none

### Product Path
- short task:
  - request_id: `3d14c57c8c04`
  - request_status: `warning`
  - baseline_tokens_estimate: `123`
  - saved_tokens_estimate: `110`
- medium task:
  - request_id: `660ba20a13b7`
  - request_status: `warning`
  - baseline_tokens_estimate: `137`
  - saved_tokens_estimate: `124`

### Judgement
- No request-path failure or error-code increase was observed between baseline and product path.
- Product path remained callable and evidence-complete.
- Negative-impact judgement: `pass`

## Claude Code cc-haha

### Baseline
- short task:
  - request_id: `76f1f4dd692b`
  - request_status: `bypassed`
  - error_code: none
- medium task:
  - request_id: `de00ab913c49`
  - request_status: `bypassed`
  - error_code: none

### Product Path
- short task:
  - request_id: `3dfc97363b6b`
  - request_status: `warning`
  - baseline_tokens_estimate: `123`
  - saved_tokens_estimate: `110`
- medium task:
  - request_id: `47d5bc57efeb`
  - request_status: `warning`
  - baseline_tokens_estimate: `138`
  - saved_tokens_estimate: `125`

### Judgement
- Family-scope variant path remained usable in both baseline and product modes.
- No product-path-specific failure or error-code increase was observed.
- Negative-impact judgement: `pass`

## OpenClaw

### Baseline
- short task:
  - request_id: `ed9fadab6d8d`
  - request_status: `bypassed`
  - error_code: none
- medium task:
  - request_id: `447b9ebf0aa5`
  - request_status: `bypassed`
  - error_code: none

### Product Path
- short task:
  - request_id: `63d43fdfe524`
  - request_status: `warning`
  - baseline_tokens_estimate: `2362`
  - saved_tokens_estimate: `2349`
- medium task:
  - request_id: `5fd7b1f34b99`
  - request_status: `warning`
  - baseline_tokens_estimate: `2408`
  - saved_tokens_estimate: `2395`

### Judgement
- Baseline bypass behavior and product-path compile behavior both remained evidence-complete.
- No request-path failure or error-code increase was observed.
- Negative-impact judgement: `pass`

## Route State After Validation

- Final control state:
  - `claude_code.routing_enabled=true`
  - `openclaw.routing_enabled=true`
- Final truth snapshot:
  - `claude_code.route_truth=effective`
  - `openclaw.route_truth=effective`

## Overall Conclusion

- Non-Codex Batch 3 is `conditional pass`.
- Reason for not calling it full pass:
  - route toggling through `/agents/control` showed noticeable latency during the execution window
  - request-path evidence stayed healthy, but control-plane responsiveness itself should be treated as a follow-up operational observation
- Within the actual request path, no obvious negative impact was observed for:
  - Claude Code default
  - Claude Code `cc-haha`
  - OpenClaw

## Next Action

- Keep Codex deferred as a separate Batch 3 sub-batch.
- If needed later, open a small control-plane latency note for `/agents/control` route toggling under active validation load.
