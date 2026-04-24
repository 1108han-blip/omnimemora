# OmniMemora DLP Batch 4.1 Closeout - Family Alias Contract Repair (2026-04-25)

## 1. Summary

Batch 4.1 applies a minimal repo-only contract repair to prevent DLP hot summary from becoming a family-semantic drift source.

Scope:

- repair `data_lifecycle.summary_builder.normalize_agent_to_family()`
- align alias contract with product family semantics, especially `cc-haha -> claude_code`
- keep `/agents/control` response schema unchanged
- no UI change, no promotion, no destructive maintenance

---

## 2. Repo Changes

Updated:

- `5_connectors/adapter/data_lifecycle/summary_builder.py`
- `5_connectors/adapter/tests/test_data_lifecycle_plane.py`

Key implementation points:

- normalization now first reuses canonical resolution via `agent_identity.resolve_canonical_agent_id(...)` (when available), then applies DLP alias mapping
- added Claude Code profile aliases in DLP contract, including:
  - `cc-haha`
  - `cc_haha`
  - `claude-code-haha`
  - `claude_code_haha`
- summary contract no longer emits `cc-haha` as an independent family key

---

## 3. Validation

Added/strengthened tests:

- meter agent `cc-haha` -> summary family `claude_code`
- compile event agent `cc-haha` -> compile summary contributes to `claude_code`
- summary `families` does not include standalone `cc-haha`

Regression commands:

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_plane.py
python3 -m pytest -q 5_connectors/adapter/__tests__/test_status_read_model.py
python3 -m pytest -q 5_connectors/adapter/tests/test_agent_control_api.py
```

Results:

- `test_data_lifecycle_plane.py`: `15 passed`
- `test_status_read_model.py`: `21 passed`
- `test_agent_control_api.py`: `7 passed`

---

## 4. Acceptance Check

- DLP summary family scope and control-card family scope are aligned: **PASS**
- `cc-haha` is not an independent family in summary: **PASS**
- worktree can be returned clean after commit: **PASS**

Next line: proceed to DLP Batch 5 running validation.
