---
doc_id: ADR-PROJECT-CONVENTIONS
title: OmniMemora Engineering Conventions
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: []
supersedes: []
last_verified_commit: ""
---

# ADR-PROJECT-CONVENTIONS.md - OmniMemora Engineering Conventions

## 1. Legacy File Marking

### Rule
Any file, directory, or module that is **no longer the current design** MUST be marked as legacy to prevent accidental usage and confusion.

### Marking Requirements

**For directories:**
- Rename directory to include `/archive/` or `/legacy/` suffix
- Add `README_LEGACY.md` inside explaining:
  1. What this was
  2. Why it's archived
  3. What superseded it

**For files:**
- Add `ARCHIVED - ` prefix to filename
- OR move to nearest `/archive/` directory

**For code blocks within files:**
```python
# ARCHIVED: This code is no longer used
# Superseded by: pkg/constants.go
```

### Examples

**GOOD:**
```
4_core/adapter-raw/archive/
├── README_LEGACY.md      # Explains this was Docker-based adapter (port 8000)
├── Dockerfile            # Archived
└── docker-compose.yml    # Archived
```

**BAD:**
```
4_core/adapter-raw/       # Unmarked - appears to be active code!
├── Dockerfile
└── docker-compose.yml
```

### How to Archive

1. Create `/archive/` subdirectory
2. Move old files into `/archive/`
3. Add `README_LEGACY.md` with:
   - What it was
   - Why it was archived
   - What replaced it (with path)

### Why This Matters

Without marking:
- Code audits see `docker-compose.yml` → assume it's official deployment
- New developers use old patterns
- Old bugs resurface as "new" implementations

With marking:
-一眼就知道是遗留的
- Code reviewers know to ignore in active code paths
- Port audits (port_audit.py) skip automatically

---

## 2. Port Constants

### Rule
**All port numbers MUST be defined in `pkg/constants.go`** and referenced by constant name, never hardcoded.

### Canonical Ports

| Constant | Value | Purpose |
|----------|-------|---------|
| `PortRuntime` | 8765 | OmniMemora Runtime HTTP server |
| `PortAdapter` | 18011 | Memory Adapter (product entry) |
| `PortOpenViking` | 1933 | OpenViking Backend (legacy) |
| `PortDashboard` | 5173 | Demo dashboard UI |
| `PortFallback1` | 8766 | Runtime fallback port 1 |
| `PortFallback2` | 8767 | Runtime fallback port 2 |
| `PortFallback3` | 8775 | Runtime fallback port 3 |

### Why 8000 Was Wrong

- `8000` was the old Python Adapter Docker port
- `8765` is the Go Runtime port (per design docs)
- Mixing these caused connectors to connect to wrong service

### Code Pattern

**BAD:**
```go
server := api.NewServer(cfg, s, rtCtx, 8000)
```

**GOOD:**
```go
server := api.NewServer(cfg, s, rtCtx, pkg.PortRuntime)
```

---

## 3. Port Audit Tool

### Tool: `tools/verification/port_audit.py`

Run before any release:
```bash
python tools/verification/port_audit.py
```

Checks:
1. `pkg/constants.go` has correct canonical values
2. No code uses deprecated ports (8000, old values)
3. All port literals match constants

Exit code 0 = PASS
Exit code 1 = FAIL (action required)

---

## 4. Architecture Decision Log

| ADR | Decision | Date |
|-----|----------|------|
| ADR-0001 | Product boundary: local Docker = dev only, not commercial | 2026-04-14 |
| ADR-0006 | Internal transport: loopback + internal port detection | 2026-04-14 |

---

## 5. Code Review Checklist

- [ ] New port hardcoded? → Must use `pkg/constants.go`
- [ ] Old file/directory unmarked as legacy? → Archive it
- [ ] Docker Compose in active code? → Confirm it's current deployment method
- [ ] Port 8000 in code? → Must be 8765 or 18011 (or flagged as legacy)
