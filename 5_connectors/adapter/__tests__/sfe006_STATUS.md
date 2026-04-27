# SFE-006 Status — 2026-04-27

## Conclusion (写死)

```
SFE-006 A/B gate harness implemented; real token-saving quality result not yet established
```

## What is done

- [x] Gate harness: `test_sfe006_real_token_saving_ab_gate.py`
- [x] Gate rule: `compile_success AND compiled_tokens < orig_tokens AND quality_pass`
- [x] Gate threshold: ≥ 9/10 eligible tasks pass
- [x] Token counting: tiktoken (OpenAI) / char/3.8 (Anthropic), conservative
- [x] Quality evaluation: per-task `must_contain` / `must_not_contain` / `min_length`
- [x] Task file: `sfe006_tasks.json` with 10 sample programming tasks

## What is NOT done

- [ ] Real Claude Code / OpenClaw task prompts (current tasks are generic samples)
- [ ] Actual A/B run against a live model
- [ ] Evidence that compiled payload == payload sent in real Claude Code proxy path

## Known gap: real-path parity

The harness calls `gateway_compile.run_gateway_compile()` directly.

This proves: **the compile strategy itself** produces shorter payloads.

It does NOT prove: **real Claude Code traffic** goes through the same compile path
and receives the same compiled payload in production.

A separate lightweight check is needed:
- Instrument the real proxy path (`/llm/anthropic`, `/llm/chat`)
- Log or record the actual payload forwarded upstream after compile
- Confirm it matches the `compiled_payload` returned by the harness path

Until that parity is confirmed, "test passes" ≠ "real traffic saves tokens".

## Next action (minimum)

1. Extract 10 real prompts from recent Claude Code / OpenClaw sessions
2. Write into `sfe006_tasks.json` with quality criteria
3. Run `python -m pytest __tests__/test_sfe006_real_token_saving_ab_gate.py -v`
4. Evaluate gate

**Do not touch: 5173 dashboard, RES计量, governance, meter UI.**

## Pass criteria

```
≥ 9/10 eligible tasks pass
→ OmniMemora can claim: compiled prompts are shorter AND quality is preserved
```

## Fail criteria

```
< 9/10 eligible tasks pass
→ Product cannot claim real token savings
→ Meter labels: observed_compression only, not saved
→ 5173: do not display real saving metrics
→ Action: revise compile strategy, not revise UI
```
