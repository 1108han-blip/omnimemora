# OmniMemora UXV-001 Personal Value Loop Repair Closeout

Date: 2026-04-27

## Fixed Conclusion

`dashboard value loop explains current usefulness; RES cleanup expansion paused`

## Scope

UXV-001 paused RES follow-up work and repaired the user-facing dashboard value semantics. The goal was not cleanup, launch, or another storage-governance step. The goal was to answer:

- Did OmniMemora participate in the current request?
- Which memory/value path was used?
- If the user cannot feel value, why not?

## Repository Reality

Implemented:

- Recent request diagnostics now include `qualification_reason`, `value_paths`, `user_visible_query`, `diagnostic_label`, and `display_savings_as_value`.
- System-reminder-only/context-envelope traffic is classified as internal/wrapper, not a normal task request.
- Non-value requests no longer display token reduction as product value.
- Core capabilities distinguish `Observed`, `Value Qualified`, `Non-Value`, and `Internal/Wrapper`.
- Dashboard Live Request Flow displays the user-visible query or a wrapper/context label instead of raw `<system-reminder>` envelopes.
- Dashboard includes a `Personal Value Loop` panel with `Working`, `Not helping yet`, or `Only observing`.

Primary files:

- `5_connectors/adapter/request_classifier.py`
- `5_connectors/adapter/metrics_service.py`
- `5_connectors/adapter/application/status_read_model.py`
- `5_connectors/adapter/data_lifecycle/summary_builder.py`
- `6_console/demo-dashboard/src/App.tsx`
- `6_console/demo-dashboard/src/components/LiveRequestFlow.tsx`
- `6_console/demo-dashboard/src/types.ts`

## Running Reality

Promotion:

- Command: `./tools/promotion/promotion.sh adapter+ui`
- Result: `running_reality_promoted`
- Running revision: `409d76e`
- Log: `tools/verification/logs/promotion_20260427_202807.log`

Live checks:

- `/health` returned `200`.
- `/metrics/core_capabilities?tenant=all` returned `observed_request_count=9`, `non_value_count=6`, `internal_or_wrapper_count=3`, and `real_requests.count=0`.
- `/metrics/recent_requests?tenant=all&limit=5&value_qualified_only=false` returned recent rows with `qualification_reason`, `value_paths`, `user_visible_query`, and `display_savings_as_value=false` for non-value rows.

Self-use validation:

- 10 product requests were generated through `POST /mcp/query` with tenant `uxv001`.
- `/metrics/core_capabilities?tenant=uxv001` returned `observed_request_count=10`, `non_value_count=10`, `internal_or_wrapper_count=0`, and `real_requests.count=0`.
- `/metrics/recent_requests?tenant=uxv001&limit=10&value_qualified_only=false` returned `10` task-non-value rows.
- The diagnostic reason was explicit: `no memory packed; no value path`.

This is the correct product truth: OmniMemora observed the requests, but did not contribute memory value to those self-use requests.

## Validation

- `python3 -m pytest -q 5_connectors/adapter/tests/test_metrics_service_summary_first.py 5_connectors/adapter/__tests__/test_status_read_model.py 5_connectors/adapter/tests/test_diagnostics_surface_smoke.py` -> `31 passed`
- `python3 -m pytest -q 5_connectors/adapter/tests/test_request_evidence_meter_route.py 5_connectors/adapter/tests/test_usage_surface_meter_route.py` -> `6 passed`
- `python3 -m py_compile 5_connectors/adapter/request_classifier.py 5_connectors/adapter/metrics_service.py 5_connectors/adapter/application/status_read_model.py 5_connectors/adapter/data_lifecycle/summary_builder.py` -> passed
- `npm run build` in `6_console/demo-dashboard` -> passed
- `git diff --check` -> passed

One broader legacy equivalence test in `test_data_lifecycle_plane.py` still reads live/global meter state through the status-read-model resolver while the summary-builder side uses isolated test meters. That is not a UXV regression and was not repaired in this batch.

## Boundary

- RES-028 follow-up remains paused.
- No cleanup execution was added.
- No delete/move/compress/truncate/batch cleanup path was added.
- No user-side memory governance was changed.
- No product value was rounded up: current self-use truth is `Not helping yet`, not `Working`.
