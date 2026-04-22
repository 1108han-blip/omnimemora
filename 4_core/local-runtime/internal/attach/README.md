# internal/attach

`internal/attach` is the runtime-local **integration carrier implementation**.

It exists for low-frequency integration actions:

- detect supported local agents
- attach/install OmniMemora integration config
- detach/uninstall and restore backups
- attach strategy and terminal quick-select UI helpers

Boundary:

- This package is **not** the memory plane.
- This package is **not** a product data entry surface.
- This package does not define product routing policy.

Port semantics:

- Product-facing data entry stays at `:18011` (gateway).
- Runtime `:8765` remains internal; attach actions are runtime-local carrier operations only.
